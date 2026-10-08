"""O resumo da semana por e-mail (Sessão 13, D48 e D66): na segunda às 9h, no fuso do dono, só se
o Viking anotou algo (o dono, 2026-10-08). É a revisão que chega sozinha: o dono corrige de uma
vez o que entrou errado (o resto de risco da D48, um e-mail colado que virou fato).

Roda na rodada do envio de lembretes (a cada minuto, `POST /tarefas/lembretes`), sem recurso novo:
- **uma vez por semana:** o documento `estado/resumo-AAAA-Www` (a semana ISO no fuso do dono) é
  criado por `create()` antes do envio; a rodada seguinte o acha e não manda de novo (o Scheduler
  entrega "at least once");
- **a janela** é a semana que terminou nesta segunda às 9h: um fato anotado às 9h05 entra no
  resumo seguinte, e nenhum fica de fora;
- **o envio** é o livre da D46 (`gmail_envio.novo("eu", …)`, no registro de ações); o que fazer
  com cada falha é o do envio de lembretes: recusa ou limite soltam a reserva (a próxima rodada da
  mesma segunda tenta), "pode ter saído" (5xx) fica e não reenvia;
- **uma segunda inteira sem rodada** (o motor fora o dia todo) pula aquela semana: não há como
  saber se o dono ainda quer o resumo velho, e o `viking memoria --semana` mostra o mesmo.

O e-mail, lido de volta pelo Viking, é conteúdo de terceiro (D53): a marca dele vira só a etiqueta.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config, firestore_comum
from lifeos.memoria import store

COLECAO = "estado"
DIA, HORA = 0, 9  # segunda (weekday 0) às 9h no fuso do dono


def _chave(local: datetime) -> str:
    ano, semana, _dia = local.isocalendar()
    return f"resumo-{ano}-W{semana:02d}"


def janela(agora: datetime) -> tuple[datetime, datetime] | None:
    """(início, fim) da semana a resumir, se agora é segunda depois das 9h no fuso do dono."""
    local = agora.astimezone(config.TIMEZONE)
    if local.weekday() != DIA or local.hour < HORA:
        return None
    fim = local.replace(hour=HORA, minute=0, second=0, microsecond=0)
    return (fim - timedelta(days=7)).astimezone(UTC), fim.astimezone(UTC)


def _dia(momento: datetime) -> str:
    return f"{momento.astimezone(config.TIMEZONE):%d/%m}"


def corpo(fatos: list[store.Fato], inicio: datetime, fim: datetime) -> str:
    """O texto do e-mail: cada anotação da semana com o id curto e o estado de hoje."""
    linhas = [f"O que o Viking anotou de {_dia(inicio)} a {_dia(fim)}:", ""]
    for fato in fatos:
        if fato.esquecido_em is not None:
            estado = " (esquecido)"
        elif fato.invalida_em is not None:
            estado = " (já trocado por outro)"
        else:
            estado = ""
        linhas.append(f"- [{fato.curto}] {fato.texto}{estado}")
    linhas += [
        "",
        (
            'Algo errado? No Mac: viking memoria --corrigir ID --texto "o certo", ou '
            "viking memoria --esquecer ID. Todos: viking memoria --todos."
        ),
    ]
    return "\n".join(linhas)


def rodar(agora: datetime | None = None) -> str:
    """Uma rodada: o que aconteceu, numa palavra (vai à resposta da rota, nunca um fato)."""
    from google.api_core.exceptions import AlreadyExists

    from lifeos.gmail import envio as gmail_envio
    from lifeos.gmail import service as gmail_service

    agora = (agora or datetime.now(UTC)).astimezone(UTC)
    semana = janela(agora)
    if semana is None:
        return "fora da hora"
    if not config.gmail_no_motor():
        return "sem o Gmail"
    inicio, fim = semana
    ref = (
        firestore_comum.cliente()
        .collection(COLECAO)
        .document(_chave(agora.astimezone(config.TIMEZONE)))
    )
    try:
        ref.create({"estado": "reservado", "em": agora})
    except AlreadyExists:
        return "já feito"
    try:
        fatos = store.criados_entre(inicio, fim)
        if not fatos:
            ref.update({"estado": "vazio"})
            return "nada anotado"
        assunto = f"Viking: o que anotei esta semana ({len(fatos)})"
        pedido = gmail_envio.novo("eu", assunto, corpo(fatos, inicio, fim))
    except gmail_service.ErroGmail as exc:
        if exc.incerta:
            ref.update({"estado": "incerto"})
            return "incerto"
        ref.delete()
        return "recusado"
    except BaseException:
        ref.delete()
        raise
    if pedido.enviado is None:  # "eu" é a conta: só o caminho livre existe aqui
        ref.delete()
        return "recusado"
    ref.update({"estado": "enviado"})
    return "enviado"


def estado(agora: datetime) -> dict[str, Any] | None:
    """O documento da semana de `agora` (para os testes e a conferência), ou `None`."""
    ref = (
        firestore_comum.cliente()
        .collection(COLECAO)
        .document(_chave(agora.astimezone(config.TIMEZONE)))
    )
    snap = ref.get()
    return snap.to_dict() if snap.exists else None
