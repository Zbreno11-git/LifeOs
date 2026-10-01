"""Serviço de aplicação para lembretes — usado por CLI/Gemini (assistant/agent.py) e MCP
(mcp_server/server.py) pra não duplicar a interpretação de `quando` (achado §12.5 da auditoria:
CLI aceitava prazo, MCP não, porque a mesma lógica foi escrita duas vezes e só uma cópia recebeu
a opção). Camada fina: não decide nada de UI/formatação, só monta o `Reminder`.

Desde a Sessão 11 (D61), quando a marca do `viking.db` diz que os lembretes deste Mac migraram
(`reminders/onde.py`), criar, listar e concluir vão ao motor da nuvem (`nuvem/cliente.py`): uma
fonte só, para o chat do Mac, o MCP e `viking lembretes`. Quem registra a ação é o motor, onde
ela acontece (D57); o Mac não registra de novo. O fuso do `quando` continua decidido aqui, na
borda, e vai como instante.
"""

from __future__ import annotations

from datetime import datetime

from lifeos import config, registro
from lifeos.reminders import interface, onde
from lifeos.reminders import store as _sqlite
from lifeos.reminders.models import Reminder

# Onde moram os lembretes (`VIKING_STORE`): o `viking.db` no Mac, o Firestore no motor da nuvem
# (Sessão 10). As duas atribuições passam pelo tipo da interface, e o `mypy` confere cada módulo
# contra ela. Chat, MCP, CLI e o envio passam por este `store`, nunca pelo módulo direto.
store: interface.Lembretes = _sqlite
if config.STORE == "firestore":
    from lifeos.reminders import store_firestore

    store = store_firestore


class QuandoInvalido(ValueError):
    """`quando` não é uma data/hora ISO 8601 válida."""


def _interpretar_quando(quando: str) -> datetime | None:
    """A borda: um horário sem fuso é o do dono (`VIKING_TIMEZONE`), decidido aqui e não no store,
    que só grava instantes."""
    quando = quando.strip()
    if not quando:
        return None
    try:
        prazo = datetime.fromisoformat(quando)
    except ValueError as exc:
        raise QuandoInvalido(quando) from exc
    return prazo if prazo.tzinfo is not None else prazo.replace(tzinfo=config.TIMEZONE)


def criar_lembrete(
    titulo: str,
    corpo: str = "",
    tags: str = "",
    quando: str = "",
    source: str = "manual",
) -> Reminder:
    """Levanta `QuandoInvalido` se `quando` não for vazio nem ISO 8601 válido. Cada adaptador
    (CLI/Gemini, MCP) decide como comunicar esse erro no seu próprio formato."""
    due_at = _interpretar_quando(quando)
    if onde.na_nuvem():  # `MigracaoEmCurso` no meio da cópia: nada se grava aqui
        from lifeos.nuvem import cliente

        instante = due_at.isoformat() if due_at else ""
        return cliente.criar_lembrete(titulo, corpo, tags, instante, source)
    parametros = {"titulo": titulo, "quando": quando}
    with registro.acao("lembrete.criar", parametros) as marca:
        lembrete = store.add(
            title=titulo,
            body=corpo,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            due_at=due_at,
            source=source,
        )
        marca.feito({"id": lembrete.id, "titulo": titulo})
    return lembrete


def pendentes(type: str | None = None) -> list[Reminder]:
    """Os abertos, pelo prazo (os sem prazo no fim)."""
    if onde.estado() == onde.MIGRADO:
        from lifeos.nuvem import cliente

        abertos = cliente.lembretes_pendentes()
        return [r for r in abertos if not type or r.type == type]
    return store.list_open(type)


def concluir(reminder_id: str) -> Reminder | None:
    """Marca como concluído; `None` se o ID não existe. Um caminho só para chat e MCP, para o
    registro de ações ver os dois."""
    if onde.na_nuvem():
        from lifeos.nuvem import cliente

        return cliente.concluir_lembrete(reminder_id)
    with registro.acao("lembrete.concluir", {"id": reminder_id}) as marca:
        lembrete = store.complete(reminder_id)
        marca.feito({"id": reminder_id, "achado": lembrete is not None})
    return lembrete
