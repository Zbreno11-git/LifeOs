"""Ferramentas de Google Calendar, expostas como funções (function-calling do Gemini e tools MCP).

Portado de `calendar-bot/calendar_tools.py` sem mudanças de lógica — só o import de
`get_calendar_service` passou a ser absoluto (`lifeos.calendar.oauth`).
"""

# NÃO adicionar `from __future__ import annotations` aqui: o google-genai valida os argumentos
# das tools com isinstance(valor, anotação), e o future import transforma as anotações em strings,
# quebrando toda chamada que passe argumento (`isinstance() arg 2 must be a type...`).
from datetime import UTC, date, datetime, timedelta

from lifeos.calendar.oauth import get_calendar_service


def listar_proximos_eventos(max_results: int = 10) -> str:
    """
    Lista os próximos eventos agendados no Google Calendar a partir do momento atual.

    Args:
        max_results: Quantidade máxima de eventos a retornar (padrão 10).
    """
    service = get_calendar_service()
    agora = datetime.now(UTC).isoformat()

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=agora,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    if not events:
        return "Nenhum próximo evento encontrado."

    resultado = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        resumo = event.get("summary", "Sem título")
        resultado.append(f"- [{start}]: {resumo} (ID: {event.get('id')})")

    return "\n".join(resultado)


def listar_eventos_por_data(data_inicio: str, data_fim: str | None = None) -> str:
    """
    Lista eventos de um dia específico ou dentro de um intervalo de datas.

    Args:
        data_inicio: Data de início no formato YYYY-MM-DD (ex: '2026-09-23').
        data_fim: Data de término opcional no formato YYYY-MM-DD. Se omitido, busca apenas no dia_inicio.
    """
    service = get_calendar_service()

    time_min = f"{data_inicio}T00:00:00Z"

    if not data_fim:
        data_fim = (date.fromisoformat(data_inicio) + timedelta(days=1)).isoformat()

    time_max = f"{data_fim}T23:59:59Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    if not events:
        return f"Nenhum evento encontrado entre {data_inicio} e {data_fim}."

    resultado = [f"Eventos encontrados de {data_inicio} até {data_fim}:"]
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        resumo = event.get("summary", "Sem título")
        resultado.append(f"- [{start}]: {resumo} (ID: {event.get('id')})")

    return "\n".join(resultado)


def criar_evento(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """
    Cria um evento com horário marcado no Google Calendar.

    Args:
        summary: Título do evento.
        start_time: Data/hora de início no formato ISO 8601 (ex: '2026-09-23T10:00:00-03:00').
        end_time: Data/hora de término no formato ISO 8601 (ex: '2026-09-23T11:00:00-03:00').
        description: Descrição opcional.
    """
    service = get_calendar_service()
    evento = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }
    created = service.events().insert(calendarId="primary", body=evento).execute()
    return f"✅ Evento '{summary}' criado com sucesso para {start_time}! Link: {created.get('htmlLink')}"


def criar_evento_dia_inteiro(summary: str, data: str, description: str = "") -> str:
    """
    Cria um evento de dia inteiro no Google Calendar (sem horário específico).

    Args:
        summary: Título do evento.
        data: Data do evento no formato YYYY-MM-DD (ex: '2026-09-23').
        description: Descrição opcional.
    """
    service = get_calendar_service()
    evento = {
        "summary": summary,
        "description": description,
        "start": {"date": data},
        "end": {"date": data},
    }
    service.events().insert(calendarId="primary", body=evento).execute()
    return f"✅ Evento de dia inteiro '{summary}' criado para a data {data}!"


def deletar_evento_por_termo(termo_busca: str) -> str:
    """
    Busca um evento pelo nome/termo e o exclui do calendário.

    Args:
        termo_busca: Palavra-chave ou título do evento que deseja apagar.
    """
    service = get_calendar_service()
    agora = datetime.now(UTC).isoformat()

    events_result = (
        service.events()
        .list(calendarId="primary", q=termo_busca, timeMin=agora, singleEvents=True)
        .execute()
    )

    events = events_result.get("items", [])
    if not events:
        return f"Não encontrei nenhum evento futuro com o termo '{termo_busca}' para apagar."

    evento_alvo = events[0]
    event_id = evento_alvo["id"]
    summary = evento_alvo.get("summary", "Sem título")

    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"🗑️ O evento '{summary}' foi excluído com sucesso do seu calendário."


def reagendar_evento(termo_busca: str, novo_inicio: str, novo_fim: str) -> str:
    """
    Muda o horário de um evento existente.

    Args:
        termo_busca: Nome do evento para encontrar.
        novo_inicio: Nova data/hora inicial (ISO 8601).
        novo_fim: Nova data/hora final (ISO 8601).
    """
    service = get_calendar_service()
    agora = datetime.now(UTC).isoformat()

    events_result = (
        service.events()
        .list(calendarId="primary", q=termo_busca, timeMin=agora, singleEvents=True)
        .execute()
    )

    events = events_result.get("items", [])
    if not events:
        return f"Não encontrei nenhum evento com o termo '{termo_busca}' para reagendar."

    evento_alvo = events[0]
    evento_alvo["start"] = {"dateTime": novo_inicio}
    evento_alvo["end"] = {"dateTime": novo_fim}

    service.events().update(
        calendarId="primary", eventId=evento_alvo["id"], body=evento_alvo
    ).execute()

    return f"✅ O evento '{evento_alvo['summary']}' foi reagendado com sucesso para {novo_inicio}!"
