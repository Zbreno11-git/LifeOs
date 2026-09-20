"""Serviço de aplicação para lembretes — usado por CLI/Gemini (assistant/agent.py) e MCP
(mcp_server/server.py) pra não duplicar a interpretação de `quando` (achado §12.5 da auditoria:
CLI aceitava prazo, MCP não, porque a mesma lógica foi escrita duas vezes e só uma cópia recebeu
a opção). Camada fina: não decide nada de UI/formatação, só monta o `Reminder`.
"""

from __future__ import annotations

from datetime import datetime

from lifeos.reminders import store
from lifeos.reminders.models import Reminder


class QuandoInvalido(ValueError):
    """`quando` não é uma data/hora ISO 8601 válida."""


def _interpretar_quando(quando: str) -> datetime | None:
    quando = quando.strip()
    if not quando:
        return None
    try:
        return datetime.fromisoformat(quando)
    except ValueError as exc:
        raise QuandoInvalido(quando) from exc


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
    return store.add(
        title=titulo,
        body=corpo,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        due_at=due_at,
        source=source,
    )
