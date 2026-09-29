"""Armazenamento SQLite dos lembretes/notas do Viking: a implementação de hoje de
`reminders/interface.py` (as regras estão lá; o contrato, em `tests/test_reminders_contrato.py`).

A tabela nasce e muda só pelas migrations de `lifeos/banco.py`. Instantes gravados em UTC com
largura fixa (`timespec="microseconds"`): a janela dos vencidos compara texto, e texto só compara
certo num formato só (a migração 5 normalizou os antigos).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from lifeos import banco
from lifeos.reminders.models import Reminder

_COLUNAS = (
    "id, type, title, body, tags, due_at, completed_at, source, external_id, metadata, "
    "created_at, updated_at, enviado_em, envio_estado"
)
# Aberto e sem envio marcado: o que ainda pode sair por e-mail.
_A_ENVIAR = "completed_at IS NULL AND enviado_em IS NULL"


@contextmanager
def _session() -> Iterator[sqlite3.Connection]:
    with banco.conectar() as conn:
        yield conn


def _gravavel(momento: datetime) -> str:
    """O texto de um instante: UTC, largura fixa. Sem fuso é recusado: o fuso de quem digitou é
    decidido na borda (`service.py`), nunca aqui."""
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("horário sem fuso: o store só grava instantes (converta na borda)")
    return momento.astimezone(UTC).isoformat(timespec="microseconds")


def _lido(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto).astimezone(UTC) if texto else None


def _agora() -> str:
    return _gravavel(datetime.now(UTC))


def _lembrete(linha: sqlite3.Row) -> Reminder:
    return Reminder(
        id=linha["id"],
        type=linha["type"],
        title=linha["title"],
        body=linha["body"],
        tags=json.loads(linha["tags"]),
        due_at=_lido(linha["due_at"]),
        completed_at=_lido(linha["completed_at"]),
        source=linha["source"],
        external_id=linha["external_id"],
        metadata=json.loads(linha["metadata"]),
        created_at=_lido(linha["created_at"]),
        updated_at=_lido(linha["updated_at"]),
        enviado_em=_lido(linha["enviado_em"]),
        envio_estado=linha["envio_estado"],
    )


def _um(conn: sqlite3.Connection, reminder_id: str) -> Reminder | None:
    linha = conn.execute(
        f"SELECT {_COLUNAS} FROM reminders WHERE id = ?", (reminder_id,)
    ).fetchone()
    return _lembrete(linha) if linha else None


def add(
    title: str,
    body: str = "",
    type: str = "reminder",
    tags: list[str] | None = None,
    due_at: datetime | None = None,
    source: str = "manual",
    external_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    id: str | None = None,
) -> Reminder:
    prazo = _gravavel(due_at) if due_at is not None else None  # recusa antes de abrir o banco
    reminder_id = id or str(uuid.uuid4())
    agora = _agora()
    with _session() as conn:
        conn.execute(
            "INSERT INTO reminders (id, type, title, body, tags, due_at, source, external_id, "
            "metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (id) DO NOTHING",
            (
                reminder_id,
                type,
                title,
                body,
                json.dumps(tags or []),
                prazo,
                source,
                external_id,
                json.dumps(metadata or {}),
                agora,
                agora,
            ),
        )
        lembrete = _um(conn, reminder_id)
    if lembrete is None:  # gravado sem erro e não volta: erra alto, nunca "criado" sem prova
        raise sqlite3.DatabaseError("o lembrete gravado não voltou do banco")
    return lembrete


def get(reminder_id: str) -> Reminder | None:
    with _session() as conn:
        return _um(conn, reminder_id)


def list_open(type: str | None = None) -> list[Reminder]:
    query = f"SELECT {_COLUNAS} FROM reminders WHERE completed_at IS NULL"
    params: tuple[Any, ...] = ()
    if type:
        query += " AND type = ?"
        params = (type,)
    query += " ORDER BY due_at IS NULL, due_at, created_at"
    with _session() as conn:
        return [_lembrete(linha) for linha in conn.execute(query, params)]


def complete(reminder_id: str) -> Reminder | None:
    """`None` se o id não existe. Concluir de novo não muda a hora da primeira vez."""
    agora = _agora()
    with _session() as conn:
        conn.execute(
            "UPDATE reminders SET completed_at = ?, updated_at = ? "
            "WHERE id = ? AND completed_at IS NULL",
            (agora, agora, reminder_id),
        )
        return _um(conn, reminder_id)


def vencidos(desde: datetime, ate: datetime) -> list[Reminder]:
    with _session() as conn:
        linhas = conn.execute(
            f"SELECT {_COLUNAS} FROM reminders WHERE {_A_ENVIAR} "
            "AND due_at >= ? AND due_at <= ? ORDER BY due_at, created_at",
            (_gravavel(desde), _gravavel(ate)),
        )
        return [_lembrete(linha) for linha in linhas]


def atrasados(antes_de: datetime) -> list[Reminder]:
    with _session() as conn:
        linhas = conn.execute(
            f"SELECT {_COLUNAS} FROM reminders WHERE {_A_ENVIAR} "
            "AND due_at < ? ORDER BY due_at, created_at",
            (_gravavel(antes_de),),
        )
        return [_lembrete(linha) for linha in linhas]


def reservar_envio(reminder_id: str, *, por: str, ate: datetime, agora: datetime) -> bool:
    # Um `UPDATE ... WHERE` só: dois processos com o mesmo lembrete, só um muda a linha.
    with _session() as conn:
        cursor = conn.execute(
            "UPDATE reminders SET envio_reservado_por = ?, envio_reservado_ate = ? "
            f"WHERE id = ? AND {_A_ENVIAR} "
            "AND (envio_reservado_ate IS NULL OR envio_reservado_ate <= ?)",
            (por, _gravavel(ate), reminder_id, _gravavel(agora)),
        )
        return cursor.rowcount == 1


def marcar_envio(reminder_id: str, *, por: str, estado: str, agora: datetime) -> bool:
    with _session() as conn:
        cursor = conn.execute(
            "UPDATE reminders SET enviado_em = ?, envio_estado = ?, updated_at = ?, "
            "envio_reservado_por = NULL, envio_reservado_ate = NULL "
            "WHERE id = ? AND envio_reservado_por = ? AND enviado_em IS NULL",
            (_gravavel(agora), estado, _gravavel(agora), reminder_id, por),
        )
        return cursor.rowcount == 1


def soltar_envio(reminder_id: str, *, por: str) -> None:
    with _session() as conn:
        conn.execute(
            "UPDATE reminders SET envio_reservado_por = NULL, envio_reservado_ate = NULL "
            "WHERE id = ? AND envio_reservado_por = ?",
            (reminder_id, por),
        )
