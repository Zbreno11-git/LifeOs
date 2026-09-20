"""Servidor MCP do Viking — expõe calendário e lembretes como tools para outras ferramentas
(Claude Desktop, Gemini CLI, etc.). Ver docs/arquitetura/viking-visao-e-arquitetura.md, seção 4.4.
"""

# Nota corrigida (achado da auditoria de 2026-09-20): ao contrário de `assistant/agent.py` e
# `calendar/tools.py`, este módulo é consumido pelo FastMCP, não pelo google-genai — e testamos que
# o FastMCP resolve `from __future__ import annotations` sem problema (schema e chamada de tool
# funcionam com tipos reais, não strings). A regra "não adicionar" só valeria aqui se uma função
# deste arquivo também fosse registrada como tool do Gemini, o que hoje não acontece.
from fastmcp import FastMCP

from lifeos.calendar import (
    apagar_evento_por_id,
    buscar_eventos_por_termo,
    criar_evento,
    criar_evento_dia_inteiro,
    listar_eventos_por_data,
    listar_proximos_eventos,
    reagendar_evento_por_id,
)
from lifeos.reminders import store

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


@mcp.tool()
def viking_criar_lembrete(titulo: str, corpo: str = "", tags: str = "") -> str:
    """Cria um lembrete/nota geral do Viking."""
    reminder = store.add(
        title=titulo,
        body=corpo,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        source="mcp",
    )
    return f"Lembrete #{reminder.id} criado."


@mcp.tool()
def viking_listar_lembretes() -> str:
    """Lista lembretes/notas pendentes do Viking."""
    reminders = store.list_open()
    if not reminders:
        return "Nenhum lembrete pendente."
    return "\n".join(f"#{r.id} {r.title}" for r in reminders)


@mcp.tool()
def viking_concluir_lembrete(reminder_id: int) -> str:
    """Marca um lembrete do Viking como concluído."""
    reminder = store.complete(reminder_id)
    return (
        f"Lembrete #{reminder_id} concluído." if reminder else f"Lembrete #{reminder_id} não encontrado."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
