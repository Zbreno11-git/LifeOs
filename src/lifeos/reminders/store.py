"""Armazenamento SQLite dos lembretes/notas do Viking. Ver `models.py` para o schema."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from lifeos.config import REMINDERS_DB_PATH
from lifeos.reminders.models import Reminder

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    due_at TEXT,
    completed_at TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    external_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def _session():
    REMINDERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REMINDERS_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=row["id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        tags=json.loads(row["tags"]),
        due_at=datetime.fromisoformat(row["due_at"]) if row["due_at"] else None,
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
                due_at.isoformat() if due_at else None,
                source,
                external_id,
                json.dumps(metadata or {}),
                now,
                now,
            ),
        )
        reminder_id = cursor.lastrowid
    return get(reminder_id)


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
