"""Lembretes por e-mail (Sessão 9): `viking lembretes --enviar` manda um e-mail por lembrete
vencido nas últimas 24 h, para a própria conta do dono, e **um só** por lembrete.

Decisões do dono (2026-09-29): um e-mail por lembrete, assunto = título (na nuvem, S11, cada um
dispara na hora dele: o formato já fica igual); vencidos há mais de 24 h não saem, são listados
(evita uma rajada de e-mails velhos na primeira vez). O envio é o livre da D46
(`gmail/envio.novo("eu", ...)`): só para a conta, no limite de 20 em 24 h, no registro de ações.

Um envio só, por reserva no banco (`interface.Lembretes.reservar_envio`): duas execuções juntas
(o dono rodando duas vezes; o Scheduler da nuvem, que entrega "at least once") disputam o mesmo
`UPDATE`, e só uma ganha. Depois do Google:
- saiu → `marcar_envio(ENVIADO)`;
- **pode ter saído** (5xx, tempo esgotado) → `marcar_envio(INCERTO)` e o texto diz "Não sei se":
  reenviar a cada rodada mandaria duplicado, e o registro já tem a linha `incerta`;
- recusa definitiva, texto recusado, limite do dia → `soltar_envio`: a próxima rodada tenta;
- sem login ou sem cota do Gmail → solta e para a rodada, dizendo o que já saiu antes;
- qualquer outra exceção → solta e sobe: nada fica preso.

Sobra um caso, declarado: se o processo morre **entre** o Google aceitar e o `marcar_envio`, a
reserva vence em `PRAZO_DA_RESERVA` e a próxima rodada manda de novo (duplicado para o próprio
dono, nunca para outra pessoa).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from lifeos import config
from lifeos.gmail import envio as gmail_envio
from lifeos.gmail import service as gmail_service
from lifeos.reminders import interface
from lifeos.reminders.models import Reminder
from lifeos.reminders.service import store

JANELA = timedelta(hours=24)  # decisão do dono; janela móvel, sem fuso de ninguém
PRAZO_DA_RESERVA = timedelta(minutes=5)  # um envio leva segundos; morto no meio, outro pega
MAX_ATRASADOS_LISTADOS = 10


@dataclass
class Resultado:
    enviados: list[str] = field(default_factory=list)
    incertos: list[str] = field(default_factory=list)
    recusados: list[tuple[str, str]] = field(default_factory=list)  # (título, motivo)
    limite: str = ""  # o motivo, se o limite de 24 h parou a rodada
    ficaram: int = 0  # vencidos que o limite deixou para a próxima rodada
    pulados: int = 0  # reservados por outra execução em curso
    atrasados: list[str] = field(default_factory=list)  # vencidos antes da janela: não saem
    avisos: list[str] = field(default_factory=list)
    parou: str = ""  # sem login, cota do Gmail: vale para todos os seguintes, a rodada para

    @property
    def parcial(self) -> bool:
        """Algo que venceu não saiu com certeza (a CLI sai com 2)."""
        return bool(self.incertos or self.recusados or self.limite or self.avisos or self.parou)


def _prazo_do_dono(lembrete: Reminder) -> str:
    assert lembrete.due_at is not None  # `vencidos` só devolve com prazo
    return f"{lembrete.due_at.astimezone(config.TIMEZONE):%d/%m/%Y %H:%M}"


def _corpo(lembrete: Reminder) -> str:
    """O texto do e-mail: o corpo do lembrete e o prazo no fuso do dono (a borda)."""
    linhas = [lembrete.body.strip()] if lembrete.body.strip() else []
    linhas.append(f"Lembrete para {_prazo_do_dono(lembrete)}.")
    return "\n\n".join(linhas)


def _enviar_um(lembrete: Reminder, execucao: str, agora: datetime, resultado: Resultado) -> bool:
    """Um lembrete já reservado por `execucao`. Devolve `False` se a rodada tem de parar."""
    assert lembrete.id is not None
    try:
        pedido = gmail_envio.novo("eu", lembrete.title, _corpo(lembrete))
    except gmail_envio.LimiteDiario as exc:
        store.soltar_envio(lembrete.id, por=execucao)
        resultado.limite = str(exc)
        return False
    except gmail_service.ErroGmail as exc:
        if exc.incerta:
            store.marcar_envio(lembrete.id, por=execucao, estado=interface.INCERTO, agora=agora)
            resultado.incertos.append(lembrete.title)
            return True
        store.soltar_envio(lembrete.id, por=execucao)
        if isinstance(exc, gmail_service.SemLogin | gmail_service.LimiteDoGmail):
            resultado.parou = str(exc)  # vale para todos os seguintes: parar e dizer
            return False
        resultado.recusados.append((lembrete.title, str(exc)))
        return True
    except BaseException:
        store.soltar_envio(lembrete.id, por=execucao)
        raise
    if pedido.enviado is None:  # "eu" é a conta: só o caminho livre existe aqui
        store.soltar_envio(lembrete.id, por=execucao)
        resultado.recusados.append((lembrete.title, "não saiu como e-mail para a sua conta"))
        return True
    if not store.marcar_envio(lembrete.id, por=execucao, estado=interface.ENVIADO, agora=agora):
        resultado.avisos.append(
            f"'{lembrete.title}' saiu, mas a reserva já tinha vencido: pode chegar duplicado"
        )
    resultado.enviados.append(lembrete.title)
    return True


def enviar_vencidos(agora: datetime | None = None) -> Resultado:
    agora = (agora or datetime.now(UTC)).astimezone(UTC)
    execucao = uuid.uuid4().hex
    resultado = Resultado()
    vencidos = store.vencidos(agora - JANELA, agora)
    for posicao, lembrete in enumerate(vencidos):
        assert lembrete.id is not None
        if not store.reservar_envio(
            lembrete.id, por=execucao, ate=agora + PRAZO_DA_RESERVA, agora=agora
        ):
            resultado.pulados += 1
            continue
        if not _enviar_um(lembrete, execucao, agora, resultado):
            resultado.ficaram = len(vencidos) - posicao
            break
    resultado.atrasados = [r.title for r in store.atrasados(agora - JANELA)]
    return resultado


def texto(resultado: Resultado) -> str:
    """O que a CLI mostra. Nunca o endereço: a saída é colada em conversa."""
    linhas = []
    if resultado.enviados:
        linhas.append(f"📧 {len(resultado.enviados)} lembrete(s) enviado(s) para o seu e-mail:")
        linhas += [f"  ✅ {t}" for t in resultado.enviados]
    for titulo in resultado.incertos:
        linhas.append(
            f"  ❓ Não sei se '{titulo}' saiu (o Google não confirmou): não vou reenviar; confira "
            "na sua caixa."
        )
    for titulo, motivo in resultado.recusados:
        linhas.append(f"  ⛔ '{titulo}' não saiu: {motivo}. Tento de novo na próxima rodada.")
    if resultado.limite:
        linhas.append(
            f"  ⏸️ Parei: {resultado.limite}. {resultado.ficaram} ficam para a próxima rodada."
        )
    if resultado.parou:
        linhas.append(
            f"  ⛔ Parei: {resultado.parou}. {resultado.ficaram} ficam para a próxima rodada "
            "(nada ficou reservado)."
        )
    linhas += [f"  ⚠️ {aviso}" for aviso in resultado.avisos]
    if resultado.pulados:
        linhas.append(f"  (… {resultado.pulados} já estava(m) saindo por outra execução)")
    if resultado.atrasados:
        mostrados = ", ".join(resultado.atrasados[:MAX_ATRASADOS_LISTADOS])
        resto = len(resultado.atrasados) - MAX_ATRASADOS_LISTADOS
        mais = f" e mais {resto}" if resto > 0 else ""
        linhas.append(
            f"⏳ {len(resultado.atrasados)} vencido(s) há mais de 24 h não saem por e-mail "
            f"(continuam pendentes no Viking): {mostrados}{mais}."
        )
    if not linhas:
        linhas.append("Nenhum lembrete vencido nas últimas 24 h.")
    return "\n".join(linhas)
