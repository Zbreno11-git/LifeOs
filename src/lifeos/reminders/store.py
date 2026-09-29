"""Armazenamento SQLite dos lembretes/notas do Viking. Ver `models.py` para o schema; a tabela
nasce e muda só pelas migrations de `lifeos/banco.py`."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from lifeos import banco
from lifeos.config import TIMEZONE
from lifeos.reminders.models import Reminder


def _para_utc_isoformato(dt: datetime) -> str:
    """Normaliza um datetime pra UTC antes de gravar. Sem isso, `due_at` ordenava como TEXTO puro:
    "08:00+00:00" (=08:00Z) vinha antes de "09:00+02:00" (=07:00Z, que é o horário real mais cedo).
    Datetime sem fuso (naive) é tratado como estando no fuso configurado do Viking (o mesmo que o
    calendário usa) — é a mesma suposição que `criar_lembrete` já faz implicitamente hoje.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    return dt.astimezone(UTC).isoformat()


@contextmanager
def _session():
    with banco.conectar() as conn:
        yield conn


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    due_at = datetime.fromisoformat(row["due_at"]).astimezone(TIMEZONE) if row["due_at"] else None
    return Reminder(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        tags=json.loads(row["tags"]),
        due_at=due_at,
        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        source=row["source"],
        external_id=row["external_id"],
        metadata=json.loads(row["metadata"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def add(
    title: str,
    body: str = "",
    type: str = "reminder",
    tags: list[str] | None = None,
    due_at: datetime | None = None,
    source: str = "manual",
    external_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Reminder:
    now = datetime.now(UTC).isoformat()
    with _session() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders
                (type, title, body, tags, due_at, source, external_id, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                type,
                title,
                body,
                json.dumps(tags or []),
                _para_utc_isoformato(due_at) if due_at else None,
                source,
                external_id,
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        reminder_id = cursor.lastrowid
    lembrete = get(reminder_id) if reminder_id is not None else None
    if lembrete is None:  # gravado sem erro e não volta: erra alto, nunca "criado" sem prova
        raise sqlite3.DatabaseError("o lembrete gravado não voltou do banco")
    return lembrete


def get(reminder_id: int) -> Reminder | None:
    with _session() as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row_to_reminder(row) if row else None


def list_open(type: str | None = None) -> list[Reminder]:
    query = "SELECT * FROM reminders WHERE completed_at IS NULL"
    params: tuple[Any, ...] = ()
    if type:
        query += " AND type = ?"
        params = (type,)
    query += " ORDER BY due_at IS NULL, due_at, created_at"
    with _session() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_reminder(row) for row in rows]


def complete(reminder_id: int) -> Reminder | None:
    now = datetime.now(UTC).isoformat()
    with _session() as conn:
        conn.execute(
            "UPDATE reminders SET completed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, reminder_id),
        )
    return get(reminder_id)
