"""Servidor MCP do Viking — expõe calendário e lembretes como tools para outras ferramentas
(Claude Desktop, Gemini CLI, etc.). Ver docs/arquitetura/viking-visao-e-arquitetura.md, seção 4.4.
"""

# Nota corrigida (achado da auditoria de 2026-09-20): ao contrário de `assistant/agent.py` e
# `calendar/tools.py`, este módulo é consumido pelo FastMCP, não pelo google-genai — e testamos que
# o FastMCP resolve `from __future__ import annotations` sem problema (schema e chamada de tool
# funcionam com tipos reais, não strings). A regra "não adicionar" só valeria aqui se uma função
# deste arquivo também fosse registrada como tool do Gemini, o que hoje não acontece.
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from lifeos.calendar import (
    apagar_evento_por_id,
    buscar_eventos_por_termo,
    criar_evento,
    criar_evento_dia_inteiro,
    listar_eventos_por_data,
    listar_proximos_eventos,
    reagendar_evento_por_id,
)
from lifeos.reminders import service as reminders_service
from lifeos.reminders import store
from lifeos.reminders.models import Reminder

mcp = FastMCP(name="viking", instructions="Calendário e lembretes pessoais do Viking (Life OS).")


@mcp.tool()
def viking_listar_proximos_eventos(max_results: int = 10) -> str:
    """Lista os próximos eventos do Google Calendar."""
    return listar_proximos_eventos(max_results)


@mcp.tool()
def viking_listar_eventos_por_data(data_inicio: str, data_fim: str | None = None) -> str:
    """Lista eventos do Google Calendar num dia ou intervalo (YYYY-MM-DD)."""
    return listar_eventos_por_data(data_inicio, data_fim)


@mcp.tool()
def viking_criar_evento(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """Cria um evento com horário marcado no Google Calendar."""
    return criar_evento(summary, start_time, end_time, description)


@mcp.tool()
def viking_criar_evento_dia_inteiro(summary: str, data: str, description: str = "") -> str:
    """Cria um evento de dia inteiro no Google Calendar."""
    return criar_evento_dia_inteiro(summary, data, description)


@mcp.tool()
def viking_buscar_eventos(termo_busca: str) -> str:
    """Busca eventos futuros por termo e devolve os candidatos com seus IDs."""
    return buscar_eventos_por_termo(termo_busca)


@mcp.tool()
def viking_apagar_evento(event_id: str, titulo_esperado: str) -> str:
    """Apaga UM evento pelo ID. Irreversível: busque e confirme com o usuário antes."""
    return apagar_evento_por_id(event_id, titulo_esperado)


@mcp.tool()
def viking_reagendar_evento(
    event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str
) -> str:
    """Reagenda UM evento pelo ID. Irreversível: busque e confirme com o usuário antes."""
    return reagendar_evento_por_id(event_id, titulo_esperado, novo_inicio, novo_fim)


def _lembrete_para_dict(reminder: Reminder) -> dict[str, Any]:
    return {
        "id": reminder.id,
        "type": reminder.type,
        "title": reminder.title,
        "body": reminder.body,
        "tags": reminder.tags,
        "due_at": reminder.due_at.isoformat() if reminder.due_at else None,
        "completed_at": reminder.completed_at.isoformat() if reminder.completed_at else None,
        "source": reminder.source,
        "external_id": reminder.external_id,
        "metadata": reminder.metadata,
        "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
        "updated_at": reminder.updated_at.isoformat() if reminder.updated_at else None,
    }


@mcp.tool()
def viking_criar_lembrete(
    titulo: str, corpo: str = "", tags: str = "", quando: str = ""
) -> ToolResult:
    """Cria um lembrete/nota geral do Viking. `quando` é o prazo opcional em ISO 8601
    ('2026-09-25' ou '2026-09-25T14:00') — mesma regra do assistente de chat.
    """
    try:
        reminder = reminders_service.criar_lembrete(titulo, corpo, tags, quando, source="mcp")
    except reminders_service.QuandoInvalido:
        return ToolResult(
            content=(
                f"Não entendi a data '{quando}'. Use ISO 8601, ex.: 2026-09-25 ou 2026-09-25T14:00."
            ),
            structured_content={"erro": "quando_invalido", "quando": quando},
            is_error=True,
        )
    return ToolResult(
        content=f"Lembrete #{reminder.id} criado.",
        structured_content=_lembrete_para_dict(reminder),
    )


@mcp.tool()
def viking_listar_lembretes() -> ToolResult:
    """Lista lembretes/notas pendentes do Viking."""
    reminders = store.list_open()
    if reminders:
        texto = "\n".join(f"#{r.id} {r.title}" for r in reminders)
    else:
        texto = "Nenhum lembrete pendente."
    return ToolResult(
        content=texto,
        structured_content={"lembretes": [_lembrete_para_dict(r) for r in reminders]},
    )


@mcp.tool()
def viking_concluir_lembrete(reminder_id: int) -> ToolResult:
    """Marca um lembrete do Viking como concluído."""
    reminder = store.complete(reminder_id)
    if not reminder:
        return ToolResult(
            content=f"Lembrete #{reminder_id} não encontrado.",
            structured_content={"erro": "nao_encontrado", "reminder_id": reminder_id},
            is_error=True,
        )
    return ToolResult(
        content=f"Lembrete #{reminder_id} concluído.",
        structured_content=_lembrete_para_dict(reminder),
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
