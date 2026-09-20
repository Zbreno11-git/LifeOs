"""Ferramentas de Google Calendar, expostas como funções (function-calling do Gemini e tools MCP).

Portado de `calendar-bot/calendar_tools.py` sem mudanças de lógica — só o import de
`get_calendar_service` passou a ser absoluto (`lifeos.calendar.oauth`).
"""

# NÃO adicionar `from __future__ import annotations` aqui: o google-genai valida os argumentos
# das tools com isinstance(valor, anotação), e o future import transforma as anotações em strings,
# quebrando toda chamada que passe argumento (`isinstance() arg 2 must be a type...`).
import unicodedata
from datetime import UTC, date, datetime, timedelta

from lifeos.calendar.oauth import get_calendar_service
from lifeos.config import TIMEZONE


def listar_proximos_eventos(max_results: int = 10) -> str:
    """Lista os próximos eventos do calendário a partir de agora.
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


def _janela(data_inicio: str, data_fim: str | None) -> tuple[str, str]:
    """timeMin/timeMax em RFC3339, no fuso civil configurado (`TIMEZONE`).

    `data_fim` é INCLUSIVA (o último dia que você quer ver); convertemos para o início do dia
    seguinte porque o `timeMax` do Google é exclusivo. Sem `data_fim`, a janela é só o dia de
    `data_inicio`.
    """
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim) if data_fim else inicio
    if fim < inicio:
        raise ValueError(f"data_fim ({data_fim}) é anterior a data_inicio ({data_inicio}).")
    t_min = datetime(inicio.year, inicio.month, inicio.day, tzinfo=TIMEZONE)
    seguinte = fim + timedelta(days=1)
    t_max = datetime(seguinte.year, seguinte.month, seguinte.day, tzinfo=TIMEZONE)
    return t_min.isoformat(), t_max.isoformat()


def listar_eventos_por_data(data_inicio: str, data_fim: str | None = None) -> str:
    """Lista eventos de um dia ou intervalo, no fuso civil configurado. Datas em YYYY-MM-DD.
    Sem `data_fim`, busca só o dia de `data_inicio`. Com `data_fim`, o intervalo é INCLUSIVO
    (o último dia também entra).
    """
    try:
        time_min, time_max = _janela(data_inicio, data_fim)
    except ValueError as exc:
        return f"Não entendi as datas: {exc}"

    service = get_calendar_service()
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
    fim_exibido = data_fim or data_inicio
    if not events:
        return f"Nenhum evento encontrado entre {data_inicio} e {fim_exibido}."

    resultado = [f"Eventos encontrados de {data_inicio} até {fim_exibido}:"]
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        resumo = event.get("summary", "Sem título")
        resultado.append(f"- [{start}]: {resumo} (ID: {event.get('id')})")

    return "\n".join(resultado)


def _instante(valor: str) -> datetime:
    """Parseia ISO 8601 e anexa o fuso configurado quando vier sem offset.

    Anexar em vez de recusar: o modelo às vezes esquece o offset, e falhar aí só gera uma volta
    extra de conversa. O que NÃO pode passar é intervalo invertido — isso é validado por quem chama.
    """
    dt = datetime.fromisoformat(valor.strip())
    return dt if dt.tzinfo else dt.replace(tzinfo=TIMEZONE)


def criar_evento(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """Cria um evento com horário marcado. `start_time` e `end_time` em ISO 8601, com ou sem fuso
    (ex.: '2026-09-23T10:00:00-03:00'); sem fuso, assume o fuso configurado do Viking.
    """
    try:
        inicio = _instante(start_time)
        fim = _instante(end_time)
    except ValueError:
        return f"Não entendi os horários '{start_time}' / '{end_time}'. Use ISO 8601."
    if fim <= inicio:
        return f"O horário de fim ({end_time}) precisa ser depois do início ({start_time})."

    service = get_calendar_service()
    evento = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": inicio.isoformat()},
        "end": {"dateTime": fim.isoformat()},
    }
    created = service.events().insert(calendarId="primary", body=evento).execute()
    return f"✅ Evento '{summary}' criado com sucesso para {inicio.isoformat()}! Link: {created.get('htmlLink')}"


def criar_evento_dia_inteiro(summary: str, data: str, description: str = "") -> str:
    """Cria um evento de dia inteiro, sem horário. `data` em YYYY-MM-DD.
    """
    try:
        dia = date.fromisoformat(data.strip())
    except ValueError:
        return f"Não entendi a data '{data}'. Use YYYY-MM-DD."

    service = get_calendar_service()
    evento = {
        "summary": summary,
        "description": description,
        "start": {"date": dia.isoformat()},
        # end.date do Google é EXCLUSIVO: um evento de um dia termina no dia seguinte.
        "end": {"date": (dia + timedelta(days=1)).isoformat()},
    }
    service.events().insert(calendarId="primary", body=evento).execute()
    return f"✅ Evento de dia inteiro '{summary}' criado para a data {dia.isoformat()}!"


def _quando(evento: dict) -> str:
    inicio = evento.get("start", {})
    return inicio.get("dateTime") or inicio.get("date") or "sem data"


def buscar_eventos_por_termo(termo_busca: str) -> str:
    """Busca eventos futuros por termo e devolve os candidatos com seus IDs. Use antes de apagar
    qualquer coisa: é daqui que sai o ID, e é isto que você mostra ao usuário para ele confirmar.
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


def _titulo_igual(a: str, b: str) -> bool:
    """Compara títulos ignorando caixa, forma Unicode e espaçamento — nada além disso.

    Era uma checagem de substring, e substring vazia casa com qualquer string:
    `titulo_esperado=""` apagava qualquer evento. Agora exige igualdade normalizada.
    """

    def chave(texto: str) -> str:
        return " ".join(unicodedata.normalize("NFC", texto).casefold().split())

    return chave(a) == chave(b)


def apagar_evento_por_id(event_id: str, titulo_esperado: str) -> str:
    """Apaga UM evento do calendário. Irreversível: só chame após buscar o evento e o usuário
    confirmar qual. `titulo_esperado` precisa bater EXATAMENTE com o título real (ignorando caixa
    e acentuação/forma Unicode) — a exclusão é recusada se divergir ou se vier vazio.
    `event_id` vem de uma busca ou listagem, nunca de chute.
    """
    if not event_id.strip():
        return "NÃO apaguei nada: o ID do evento veio vazio. Busque o evento antes de apagar."
    if not titulo_esperado.strip():
        return (
            "NÃO apaguei nada: preciso do título exato do evento para conferir antes de apagar. "
            "Busque o evento e use o título que a busca devolveu."
        )

    service = get_calendar_service()
    try:
        evento = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:  # noqa: BLE001 - erro da API vira resposta legível para o modelo
        return f"Não encontrei o evento de ID '{event_id}': {exc}"

    titulo_real = evento.get("summary", "Sem título")
    if not _titulo_igual(titulo_esperado, titulo_real):
        return (
            f"NÃO apaguei nada. O evento {event_id} se chama '{titulo_real}', "
            f"não '{titulo_esperado}'. Confirme com o usuário qual é o evento certo."
        )

    quando = _quando(evento)
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:  # noqa: BLE001 - erro da API vira resposta legível para o modelo
        return f"NÃO consegui apagar o evento '{titulo_real}': {exc}"
    return f"🗑️ Evento '{titulo_real}' ([{quando}]) foi apagado."


def reagendar_evento_por_id(
    event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str
) -> str:
    """Muda o horário de UM evento já identificado. `titulo_esperado` precisa bater EXATAMENTE com
    o título real (ignorando caixa e acentuação/forma Unicode) — o reagendamento é recusado se
    divergir ou vier vazio. `event_id` vem de uma busca ou listagem, nunca de chute. Novos horários
    em ISO 8601, com ou sem fuso.
    """
    if not event_id.strip():
        return "NÃO reagendei nada: o ID do evento veio vazio. Busque o evento antes."
    if not titulo_esperado.strip():
        return (
            "NÃO reagendei nada: preciso do título exato do evento para conferir antes. "
            "Busque o evento e use o título que a busca devolveu."
        )

    service = get_calendar_service()
    try:
        evento = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:  # noqa: BLE001 - erro da API vira resposta legível para o modelo
        return f"Não encontrei o evento de ID '{event_id}': {exc}"

    titulo_real = evento.get("summary", "Sem título")
    if not _titulo_igual(titulo_esperado, titulo_real):
        return (
            f"NÃO reagendei nada. O evento {event_id} se chama '{titulo_real}', "
            f"não '{titulo_esperado}'. Confirme com o usuário qual é o evento certo."
        )

    try:
        inicio = _instante(novo_inicio)
        fim = _instante(novo_fim)
    except ValueError:
        return f"Não entendi os horários '{novo_inicio}' / '{novo_fim}'. Use ISO 8601."
    if fim <= inicio:
        return f"O novo horário de fim ({novo_fim}) precisa ser depois do início ({novo_inicio})."

    service.events().patch(
        calendarId="primary",
        eventId=event_id,
        body={
            "start": {"dateTime": inicio.isoformat()},
            "end": {"dateTime": fim.isoformat()},
        },
    ).execute()

    return f"✅ O evento '{titulo_real}' foi reagendado com sucesso para {inicio.isoformat()}!"
