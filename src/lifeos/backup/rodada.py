"""A rodada do backup pela nuvem (Sessão 11c, D63): o Cloud Scheduler chama `POST /tarefas/backup`
uma vez por dia (só o `viking-agendador@`), com o Mac desligado.

Lê as três coleções que entram no backup (os lembretes, o registro dos 30 dias, os gastos do
teto) e monta o arquivo (`formato.montar`, que o lê de volta antes de devolver). Então **baixa o
arquivo mais novo do Drive e o lê de volta**: se o conteúdo é o mesmo
(`formato.impressao_do_conteudo`), não sobe outro (resposta do dono, 2026-10-07: um arquivo novo
só quando algo mudou). Sem arquivo, com um que não se lê, ou com conteúdo diferente, sobe
(`drive.subir`, dentro de `registro.acao`). Decidir pelo Drive, e não por um estado gravado aqui,
faz um arquivo apagado à mão ou estragado virar um novo no dia seguinte, e confere todo dia que o
último se lê.

**Só depois** grava `estado/backup` (`ultimo` = o instante em que o Drive confirmou guardar o
conteúdo de agora): uma rodada que falha não mexe no estado, e a falha aparece como "backup
velho" na abertura do `viking chat --nuvem` e na prova do deploy, nunca como sucesso.

A resposta e o log levam só contagens e o nome do arquivo (a data), nunca um título.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from lifeos import config, firestore_comum

if TYPE_CHECKING:
    from lifeos.backup import formato as _formato

log = logging.getLogger(__name__)

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
    no_drive = _o_mais_novo_do_drive()
    if no_drive is not None and no_drive[1] == formato.impressao_do_conteudo(formato.ler(dados)):
        nome, contagens, novo = no_drive[0], no_drive[2].contagens(), False
    else:
        arquivo = drive.subir(
            formato.nome_do_arquivo(agora), formato.para_bytes(dados), dados["contagens"]
        )
        nome, contagens, novo = arquivo.nome, dados["contagens"], True
    _ref().set({"ultimo": agora, "arquivo": nome, "contagens": contagens, "novo": novo})
    return {"arquivo": nome, "novo": novo, **contagens}


def _o_mais_novo_do_drive() -> tuple[str, str, _formato.Backup] | None:
    """O nome, a impressão do conteúdo e o backup do arquivo mais novo da pasta, lido de volta;
    `None` sem arquivo ou com um que não se lê (aí sobe outro). Uma falha do Drive sobe como erro:
    a rodada não marca nada."""
    from lifeos.backup import drive, formato

    ultimo = drive.ultimo()
    if ultimo is None:
        return None
    try:
        backup = formato.de_bytes(drive.baixar(ultimo.id))
    except formato.BackupInvalido:
        log.warning("o último backup do Drive não se lê: sobe outro")
        return None
    return ultimo.nome, formato.impressao_do_conteudo(backup), backup


def ultimo() -> datetime | None:
    """O instante em que o Drive confirmou por último guardar o conteúdo da nuvem (subindo um
    arquivo ou conferindo que o mais novo é igual); fora da nuvem, `None`."""
    if config.STORE != "firestore":
        return None
    snap = _ref().get()
    return firestore_comum.lido(snap.get("ultimo")) if snap.exists else None
