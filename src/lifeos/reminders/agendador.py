"""O envio dos lembretes pela nuvem (Sessão 11, D61): a rodada que o Cloud Scheduler dispara a cada
minuto (`POST /tarefas/lembretes`, só do `viking-agendador@`), com o Mac desligado.

A rodada é a mesma do `viking lembretes --enviar` (`reminders/envio.py`: um e-mail por lembrete
vencido nas últimas 24 h, para a conta do dono, um só por lembrete, pela reserva no Firestore),
sem reler os atrasados (custo). Ela tem prazo próprio (`PRAZO_DA_RODADA_S`), como o turno do
chat: as esperas da cota do Gmail não passam do `--timeout` do Cloud Run.

**"Envio ligado"** quer dizer que uma rodada terminou sem parar (com o Gmail na nuvem, com cota)
nos últimos `LIGADO_POR`: o documento `estado/envio_de_lembretes` guarda o instante. O chat da
nuvem deixa de avisar "o e-mail deste lembrete ainda não existe", e a migração do Mac só copia
de verdade com ele ligado (resposta do dono, 2026-10-01: nenhum dia sem e-mail de lembrete).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config, firestore_comum, prazo

COLECAO, DOCUMENTO = "estado", "envio_de_lembretes"
LIGADO_POR = timedelta(minutes=10)
PRAZO_DA_RODADA_S = 200  # abaixo dos 300 s do Cloud Run, como o turno do chat


def _ref() -> Any:
    return firestore_comum.cliente().collection(COLECAO).document(DOCUMENTO)


def rodar(agora: datetime | None = None) -> dict[str, Any]:
    """Uma rodada do envio. Só contagens na resposta: nunca o título de um lembrete."""
    from lifeos.reminders import envio

    agora = (agora or datetime.now(UTC)).astimezone(UTC)
    with prazo.ate(PRAZO_DA_RODADA_S):
        resultado = envio.enviar_vencidos(agora, listar_atrasados=False)
    if not resultado.parou:
        _ref().set({"ultima": agora})
    return {
        "enviados": len(resultado.enviados),
        "incertos": len(resultado.incertos),
        "recusados": len(resultado.recusados),
        "pulados": resultado.pulados,
        "ficaram": resultado.ficaram,
        "parou": bool(resultado.parou),
        "limite": bool(resultado.limite),
    }


def ligado(agora: datetime | None = None) -> bool:
    """Uma rodada terminou sem parar há menos de `LIGADO_POR`? Fora da nuvem, nunca; e sem o token
    do Gmail no motor, nunca: uma rodada sem nada vencido termina sem parar, e o primeiro vencido
    pararia (a migração do Mac confia nesta resposta)."""
    if config.STORE != "firestore" or not config.gmail_no_motor():
        return False
    snap = _ref().get()
    ultima = firestore_comum.lido(snap.get("ultima")) if snap.exists else None
    return ultima is not None and ultima >= (agora or datetime.now(UTC)) - LIGADO_POR
