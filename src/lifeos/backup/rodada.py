"""A rodada do backup pela nuvem (Sessão 11c, D63): o Cloud Scheduler chama `POST /tarefas/backup`
uma vez por dia (só o `viking-agendador@`), com o Mac desligado.

Lê as três coleções que entram no backup (os lembretes, o registro dos 30 dias, os gastos do
teto), monta o arquivo (`formato.montar`, que o lê de volta antes de devolver), sobe ao Drive
(`drive.subir`, dentro de `registro.acao`) e **só então** grava `estado/backup`: uma rodada que
falha não mexe no estado, e a falha aparece como "backup velho" na abertura do `viking chat
--nuvem` e na prova do deploy, nunca como sucesso.

A resposta e o log levam só contagens e o nome do arquivo (a data), nunca um título.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config, firestore_comum

COLECAO, DOCUMENTO = "estado", "backup"
# Sem backup há mais que isto, a abertura do chat da nuvem avisa (resposta do dono, 2026-10-06).
VELHO_DEPOIS_DE = timedelta(hours=48)


def _ref() -> Any:
    return firestore_comum.cliente().collection(COLECAO).document(DOCUMENTO)


def rodar(agora: datetime | None = None, *, commit: str = "") -> dict[str, Any]:
    from lifeos import custos, registro
    from lifeos.backup import drive, formato
    from lifeos.reminders import store_firestore

    agora = (agora or datetime.now(UTC)).astimezone(UTC)
    dados = formato.montar(
        store_firestore.todos(),
        registro.exportar(agora),
        custos.exportar_gastos(),
        agora=agora,
        commit=commit,
    )
    arquivo = drive.subir(
        formato.nome_do_arquivo(agora), formato.para_bytes(dados), dados["contagens"]
    )
    _ref().set({"ultimo": agora, "arquivo": arquivo.nome, "contagens": dados["contagens"]})
    return {"arquivo": arquivo.nome, **dados["contagens"]}


def ultimo() -> datetime | None:
    """O instante do último backup que o Drive confirmou; fora da nuvem, `None`."""
    if config.STORE != "firestore":
        return None
    snap = _ref().get()
    return firestore_comum.lido(snap.get("ultimo")) if snap.exists else None
