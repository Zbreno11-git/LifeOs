"""Schema de lembretes/notas do Viking.

Estruturado o bastante para ser "RAG-ready" no futuro (ids, timestamps, tipos consistentes — ver
docs/arquitetura/viking-visao-e-arquitetura.md, seção 7) e para acomodar dados externos como
transações do Pluggy sem migração de schema (`type`/`source`/`external_id`/`metadata` são o gancho
deliberado — ver docs/fontes/pluggy-open-finance.md). Nenhum desses usos futuros está implementado
ainda; hoje isto é só um lembrete/nota estruturado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Reminder:
    id: int | None
    type: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    due_at: datetime | None = None
    completed_at: datetime | None = None
    source: str = "manual"
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
