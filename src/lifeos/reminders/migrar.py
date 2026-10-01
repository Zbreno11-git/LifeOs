"""A migração dos lembretes do Mac para a nuvem (Sessão 11, D61): `viking lembretes --migrar`.

Sem `--executar` é um **ensaio**: conta o que há no `viking.db`, pergunta ao motor o que já está
lá e se o envio por e-mail da nuvem está ligado, e não copia nada. Com `--executar`:

1. recusa se o envio da nuvem não está ligado (resposta do dono, 2026-10-01: a cópia de verdade
   só com o e-mail da nuvem funcionando, para não haver dia sem e-mail de lembrete);
2. marca "migrando" (`reminders/onde.py`): as gravações daqui param;
3. copia tudo (lembretes e notas, abertos e concluídos, com o estado do envio) em lotes, pelo
   motor; a nuvem grava com o mesmo id e nunca sobrescreve (idempotente: rodar de novo depois
   de uma queda não duplica);
4. confere relendo: cada id daqui tem, na nuvem, a mesma impressão (`transporte.impressao`);
5. só então marca "migrado": daí em diante o Mac lê e grava na nuvem, e a tabela `reminders` fica
   como cópia congelada (o backup da migração 7 também guarda o banco de antes).

Se algo diverge, a marca fica em "migrando" e nada se perde: o texto diz o que conferir.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lifeos.nuvem import cliente
from lifeos.reminders import onde, store, transporte


class NaoMigrou(RuntimeError):
    """A cópia não terminou; a mensagem diz por quê e o que fazer."""


@dataclass
class Relatorio:
    locais: int = 0
    abertos: int = 0
    concluidos: int = 0
    enviados: int = 0
    ja_iguais: int = 0  # já na nuvem, iguais aos daqui
    divergentes: list[str] = field(default_factory=list)  # já na nuvem, diferentes (ids)
    copiados: int = 0
    envio_ligado: bool = False
    estado: str | None = None  # a marca do `viking.db` no fim


def _medir() -> tuple[Relatorio, list, object, dict[str, str]]:
    locais = store.todos()
    sessao = cliente.sessao_de_chat()
    capacidades = cliente.capacidades(sessao)
    remotas = cliente.impressoes_dos_lembretes(sessao)
    relatorio = Relatorio(
        locais=len(locais),
        abertos=sum(1 for r in locais if r.completed_at is None),
        concluidos=sum(1 for r in locais if r.completed_at is not None),
        enviados=sum(1 for r in locais if r.enviado_em is not None),
        envio_ligado=capacidades.get("envio_de_lembretes") is True,
        estado=onde.estado(),
    )
    for lembrete in locais:
        if lembrete.id in remotas:
            if remotas[lembrete.id] == transporte.impressao(lembrete):
                relatorio.ja_iguais += 1
            else:
                relatorio.divergentes.append(str(lembrete.id))
    return relatorio, locais, sessao, remotas


def ensaio() -> Relatorio:
    """O que a cópia faria, sem copiar nada."""
    return _medir()[0]


def executar() -> Relatorio:
    relatorio, locais, sessao, _remotas = _medir()
    if relatorio.estado == onde.MIGRADO:
        return relatorio
    if not relatorio.envio_ligado:
        raise NaoMigrou(
            "o envio por e-mail da nuvem ainda não está ligado (o agendador não rodou nos últimos "
            "10 minutos): nada foi copiado, e os lembretes continuam aqui"
        )
    if relatorio.divergentes:
        raise NaoMigrou(
            f"{len(relatorio.divergentes)} lembrete(s) já estão na nuvem com outro conteúdo: nada "
            "foi copiado nem marcado; confira com o VPS antes de seguir"
        )
    onde.marcar(onde.MIGRANDO)
    for inicio in range(0, len(locais), transporte.MAX_LOTE):
        lote = locais[inicio : inicio + transporte.MAX_LOTE]
        resposta = cliente.importar_lembretes(sessao, [transporte.para_dict(r) for r in lote])
        relatorio.copiados += len(resposta["criados"])
        if resposta["diferentes"]:
            relatorio.divergentes += resposta["diferentes"]
    remotas = cliente.impressoes_dos_lembretes(sessao)
    faltam = [r.id for r in locais if remotas.get(str(r.id)) != transporte.impressao(r)]
    if relatorio.divergentes or faltam:
        relatorio.estado = onde.MIGRANDO
        raise NaoMigrou(
            f"a conferência achou {len(faltam)} lembrete(s) que não estão iguais na nuvem: a marca "
            "ficou em 'migrando' (nada se grava aqui); rode de novo, e se repetir, confira com o "
            "VPS"
        )
    onde.marcar(onde.MIGRADO)
    relatorio.estado = onde.MIGRADO
    return relatorio


def texto(relatorio: Relatorio, *, executou: bool) -> str:
    """O que a CLI mostra: contagens, nunca um título (a saída é colada em conversa)."""
    linhas = [
        (
            f"📦 Neste Mac: {relatorio.locais} lembrete(s) ({relatorio.abertos} aberto(s), "
            f"{relatorio.concluidos} concluído(s), {relatorio.enviados} já enviado(s) por e-mail)."
        ),
        f"☁️  Na nuvem já iguais: {relatorio.ja_iguais}.",
        "✉️  Envio por e-mail da nuvem: "
        + ("ligado." if relatorio.envio_ligado else "ainda não ligado."),
    ]
    if relatorio.estado == onde.MIGRADO and executou:
        linhas.append(
            f"✅ Migrado: {relatorio.copiados} copiado(s), todos conferidos. Daqui em diante os "
            "lembretes deste Mac moram na nuvem (o `viking.db` guarda a cópia de antes)."
        )
    elif relatorio.estado == onde.MIGRADO:
        linhas.append("✅ Este Mac já migrou: os lembretes moram na nuvem.")
    elif not executou:
        linhas.append(
            "Ensaio: nada foi copiado. Para copiar de verdade (com o envio da nuvem ligado): "
            "`viking lembretes --migrar --executar`."
        )
    return "\n".join(linhas)
