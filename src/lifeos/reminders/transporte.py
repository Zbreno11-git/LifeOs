"""Um lembrete pela rede (Sessão 11, D61): o formato que o Mac manda ao motor na migração e a
impressão que confere a cópia.

Só regras: nada de rede nem de banco (o Mac usa sem o extra `nuvem`, o motor usa do outro lado).
Todo campo vai, inclusive o estado do envio: um lembrete que já saiu por e-mail no Mac não sai de
novo pela nuvem. A impressão (`impressao`) é o sha256 de uma forma canônica dos campos; os dois
lados a calculam do mesmo jeito, e a migração só termina quando cada id do Mac tem, na nuvem, a
mesma impressão.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from lifeos.reminders import interface
from lifeos.reminders.models import Reminder

CAMPOS = (
    "id",
    "type",
    "title",
    "body",
    "tags",
    "due_at",
    "completed_at",
    "source",
    "external_id",
    "metadata",
    "created_at",
    "updated_at",
    "enviado_em",
    "envio_estado",
)
_INSTANTES = ("due_at", "completed_at", "created_at", "updated_at", "enviado_em")
MAX_LOTE = 100


class LembreteInvalido(ValueError):
    """O formato não é o combinado: nada é gravado."""


def _texto(momento: datetime | None) -> str | None:
    if momento is None:
        return None
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise LembreteInvalido("horário sem fuso: só instantes vão pela rede")
    return momento.astimezone(UTC).isoformat(timespec="microseconds")


def para_dict(lembrete: Reminder) -> dict[str, Any]:
    dados = {c: getattr(lembrete, c) for c in CAMPOS}
    for campo in _INSTANTES:
        dados[campo] = _texto(dados[campo])
    dados["tags"] = list(dados["tags"])
    dados["metadata"] = dict(dados["metadata"])
    return dados


def de_dict(dados: Any) -> Reminder:
    """O lembrete, conferido campo a campo; `LembreteInvalido` sem ecoar o conteúdo."""
    if not isinstance(dados, dict) or set(dados) != set(CAMPOS):
        raise LembreteInvalido(f"o lembrete tem de ter exatamente os campos {list(CAMPOS)}")
    if not interface.id_valido(dados["id"]):
        raise LembreteInvalido("o id do lembrete tem de ser um UUID")
    for campo in ("type", "title", "body", "source"):
        if not isinstance(dados[campo], str):
            raise LembreteInvalido(f"{campo} tem de ser texto")
    if not isinstance(dados["tags"], list) or not all(isinstance(t, str) for t in dados["tags"]):
        raise LembreteInvalido("tags tem de ser uma lista de textos")
    if not isinstance(dados["metadata"], dict):
        raise LembreteInvalido("metadata tem de ser um objeto")
    for campo in ("external_id", "envio_estado"):
        if dados[campo] is not None and not isinstance(dados[campo], str):
            raise LembreteInvalido(f"{campo} tem de ser texto ou nulo")
    if dados["envio_estado"] not in (None, interface.ENVIADO, interface.INCERTO):
        raise LembreteInvalido("envio_estado desconhecido")
    instantes: dict[str, datetime | None] = {}
    for campo in _INSTANTES:
        valor = dados[campo]
        if valor is None:
            instantes[campo] = None
            continue
        try:
            momento = datetime.fromisoformat(valor) if isinstance(valor, str) else None
        except ValueError:
            momento = None
        if momento is None or momento.tzinfo is None:
            raise LembreteInvalido(f"{campo} tem de ser um instante ISO 8601 com fuso")
        instantes[campo] = momento.astimezone(UTC)
    if instantes["created_at"] is None or instantes["updated_at"] is None:
        raise LembreteInvalido("created_at e updated_at são obrigatórios")
    return Reminder(
        id=dados["id"],
        type=dados["type"],
        title=dados["title"],
        body=dados["body"],
        tags=list(dados["tags"]),
        source=dados["source"],
        external_id=dados["external_id"],
        metadata=dict(dados["metadata"]),
        envio_estado=dados["envio_estado"],
        **instantes,
    )


def impressao(lembrete: Reminder) -> str:
    """O sha256 da forma canônica: igual nos dois lados se e só se todo campo é igual."""
    canonico = json.dumps(para_dict(lembrete), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
