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


def _quando(evento: dict) -> str:
    inicio = evento.get("start", {})
    return inicio.get("dateTime") or inicio.get("date") or "sem data"


def buscar_eventos_por_termo(termo_busca: str) -> str:
    """
    Busca eventos futuros que casem com um termo e devolve os candidatos com seus IDs.

    Use isto ANTES de apagar qualquer coisa: é daqui que sai o ID exigido por
    `apagar_evento_por_id`, e é isto que você mostra ao usuário para ele confirmar qual evento é.

    Args:
        termo_busca: Palavra-chave ou título a procurar.
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
        return f"Nenhum evento futuro encontrado com o termo '{termo_busca}'."

    linhas = [f"{len(events)} evento(s) com o termo '{termo_busca}':"]
    for event in events:
        titulo = event.get("summary", "Sem título")
        linhas.append(f"- [{_quando(event)}] {titulo} (ID: {event.get('id')})")
    return "\n".join(linhas)


def apagar_evento_por_id(event_id: str, titulo_esperado: str) -> str:
    """
    Apaga UM evento específico do Google Calendar, identificado pelo ID.

    Ação irreversível. Só chame depois de ter buscado o evento e o usuário ter confirmado
    explicitamente qual apagar. O `titulo_esperado` é conferido contra o título real do evento e a
    exclusão é recusada se não baterem — é uma trava contra apagar o evento errado.

    Args:
        event_id: ID exato do evento, vindo de uma busca ou listagem.
        titulo_esperado: Título que você e o usuário acreditam que esse evento tem.
    """
    service = get_calendar_service()
    try:
        evento = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:  # noqa: BLE001 - erro da API vira resposta legível para o modelo
        return f"Não encontrei o evento de ID '{event_id}': {exc}"

    titulo_real = evento.get("summary", "Sem título")
    if titulo_esperado.strip().lower() not in titulo_real.lower():
        return (
            f"NÃO apaguei nada. O evento {event_id} se chama '{titulo_real}', "
            f"não '{titulo_esperado}'. Confirme com o usuário qual é o evento certo."
        )

    quando = _quando(evento)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"🗑️ Evento '{titulo_real}' ([{quando}]) foi apagado."


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
