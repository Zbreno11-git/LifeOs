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

from lifeos import registro
from lifeos.calendar import tools as calendario
from lifeos.calendar.service import Evento, Pedido
from lifeos.reminders import service as reminders_service
from lifeos.reminders import store
from lifeos.reminders.models import Reminder

mcp = FastMCP(
    name="viking",
    instructions=(
        "Calendário e lembretes pessoais do Viking (Life OS). Apagar e reagendar evento só "
        "registram um PEDIDO: nada muda até o dono aprovar no terminal dele (`viking aprovar`). "
        "O código de aprovação nunca passa por aqui; não o peça ao usuário."
    ),
)


def _pelo_mcp() -> None:
    """Toda tool marca a origem no registro de ações. Por chamada: o FastMCP roda cada tool num
    contexto copiado, então um valor posto só no `main()` não chegaria (nem nos testes)."""
    registro.ORIGEM.set("mcp")


def _evento_para_dict(evento: Evento) -> dict[str, Any]:
    return {
        "id": evento.id,
        "title": evento.titulo,
        "start": evento.inicio,
        "end": evento.fim,
        "all_day": evento.dia_inteiro,
        "link": evento.link,
    }


def _resultado(resposta: calendario.Resposta) -> ToolResult:
    """Mesmo texto que o Gemini recebe + dados estruturados. Recusa de trava (título divergente,
    ID vazio...) e falha da API viram erro de verdade (`is_error`), como nos lembretes. Um pedido
    registrado não é erro: é `aguardando_aprovacao`."""
    if resposta.erro is not None:
        return ToolResult(
            content=resposta.texto,
            structured_content={"erro": resposta.erro.codigo, **resposta.erro.dados},
            is_error=True,
        )
    if isinstance(resposta.dados, Pedido):
        dados = {
            "estado": "aguardando_aprovacao",
            "acao": resposta.dados.acao,
            "evento": _evento_para_dict(resposta.dados.evento),
            "expira_em": resposta.dados.expira.isoformat(),
            "aprovar_com": "viking aprovar",
        }
    elif isinstance(resposta.dados, list):
        # `completa`: se a lista parou no teto (Sessão 8b); sem o atributo, falha aqui, não mente.
        dados = {
            "eventos": [_evento_para_dict(e) for e in resposta.dados],
            "completa": resposta.dados.completa,
        }
    else:
        dados = _evento_para_dict(resposta.dados)
    return ToolResult(content=resposta.texto, structured_content=dados)


@mcp.tool()
def viking_listar_proximos_eventos(max_results: int = 10) -> ToolResult:
    """Lista os próximos eventos do Google Calendar."""
    return _resultado(calendario.responder_proximos(max_results))


@mcp.tool()
def viking_listar_eventos_por_data(data_inicio: str, data_fim: str | None = None) -> ToolResult:
    """Lista eventos do Google Calendar num dia ou intervalo (YYYY-MM-DD)."""
    return _resultado(calendario.responder_por_data(data_inicio, data_fim))


@mcp.tool()
def viking_criar_evento(
    summary: str, start_time: str, end_time: str, description: str = ""
) -> ToolResult:
    """Cria um evento com horário marcado no Google Calendar."""
    _pelo_mcp()
    return _resultado(calendario.responder_criar(summary, start_time, end_time, description))


@mcp.tool()
def viking_criar_evento_dia_inteiro(summary: str, data: str, description: str = "") -> ToolResult:
    """Cria um evento de dia inteiro no Google Calendar."""
    _pelo_mcp()
    return _resultado(calendario.responder_criar_dia_inteiro(summary, data, description))


@mcp.tool()
def viking_buscar_eventos(termo_busca: str) -> ToolResult:
    """Busca eventos futuros por termo e devolve os candidatos com seus IDs."""
    return _resultado(calendario.responder_buscar(termo_busca))


@mcp.tool()
def viking_apagar_evento(event_id: str, titulo_esperado: str) -> ToolResult:
    """PEDE para apagar UM evento pelo ID — não apaga. O pedido espera o dono aprovar no terminal
    dele (`viking aprovar`), por até 1 hora. Busque o evento antes: o título tem de bater."""
    _pelo_mcp()
    return _resultado(calendario.responder_pedir_apagar(event_id, titulo_esperado))


@mcp.tool()
def viking_reagendar_evento(
    event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str
) -> ToolResult:
    """PEDE para reagendar UM evento pelo ID — não reagenda. O pedido espera o dono aprovar no
    terminal dele (`viking aprovar`), por até 1 hora. Busque o evento antes."""
    _pelo_mcp()
    return _resultado(
        calendario.responder_pedir_reagendar(event_id, titulo_esperado, novo_inicio, novo_fim)
    )


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
    _pelo_mcp()
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
    _pelo_mcp()
    reminder = reminders_service.concluir(reminder_id)
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
