"""Serviço de aplicação do Google Calendar: a lógica e as travas, sem formatação de texto.

Consumido por `calendar/tools.py`, que monta o texto que o Gemini lê e que o MCP também devolve
(`mcp_server/server.py` junta o texto com os dados estruturados daqui). Mesmo desenho de
`reminders/service.py`.

Pode ter `from __future__ import annotations`: nenhuma função daqui é registrada como tool do
Gemini — só chamada por dentro delas.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

# `_redacao` é stdlib pura e a única cópia da regra de caracteres de controle — títulos de
# convites vêm de terceiros (§6.3). Mover para um módulo neutro quando surgir um terceiro uso.
from lifeos.browser._redacao import limpar_controles
from lifeos.calendar.oauth import get_calendar_service
from lifeos.config import TIMEZONE


@dataclass(frozen=True)
class Evento:
    id: str | None
    titulo: str
    inicio: str
    fim: str | None = None
    dia_inteiro: bool = False
    link: str | None = None


class ErroCalendario(Exception):
    """Base dos erros de domínio. `codigo` vira `structured_content["erro"]` no MCP; `dados` são
    os campos extras dessa resposta."""

    codigo = "falha_api"

    def __init__(self, mensagem: str, **dados: object) -> None:
        super().__init__(mensagem)
        self.dados = dados


class EntradaInvalida(ErroCalendario):
    """`dados["campo"]` diz qual entrada: event_id, titulo_esperado, data, horario ou intervalo."""

    codigo = "entrada_invalida"


class EventoNaoEncontrado(ErroCalendario):
    codigo = "nao_encontrado"


class TituloDivergente(ErroCalendario):
    codigo = "titulo_divergente"


class FalhaDaApi(ErroCalendario):
    codigo = "falha_api"


def _executar(montar):
    """Toda chamada ao Google passa por aqui: falha vira `FalhaDaApi`. Antes, uma falha em criar,
    reagendar ou listar subia crua pelo laço do Gemini. Recebe a MONTAGEM da requisição (um
    callable), não a requisição pronta: a falha pode vir já ao montar, não só no `.execute()`."""
    try:
        return montar().execute()
    except Exception as exc:  # qualquer falha da API vira erro de domínio
        raise FalhaDaApi(str(exc)) from exc


def _evento_de(item: dict) -> Evento:
    inicio = item.get("start", {})
    fim = item.get("end", {})
    return Evento(
        id=item.get("id"),
        titulo=limpar_controles(item.get("summary", "Sem título")),
        inicio=inicio.get("dateTime") or inicio.get("date") or "sem data",
        fim=fim.get("dateTime") or fim.get("date"),
        dia_inteiro="date" in inicio and "dateTime" not in inicio,
        link=item.get("htmlLink"),
    )


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


def _instante(valor: str) -> datetime:
    """Parseia ISO 8601 e anexa o fuso configurado quando vier sem offset.

    Anexar em vez de recusar: o modelo às vezes esquece o offset, e falhar aí só gera uma volta
    extra de conversa. O que NÃO pode passar é intervalo invertido — isso é validado por quem chama.
    """
    dt = datetime.fromisoformat(valor.strip())
    return dt if dt.tzinfo else dt.replace(tzinfo=TIMEZONE)


def _intervalo(inicio_txt: str, fim_txt: str) -> tuple[datetime, datetime]:
    try:
        inicio = _instante(inicio_txt)
        fim = _instante(fim_txt)
    except ValueError as exc:
        raise EntradaInvalida(str(exc), campo="horario") from exc
    if fim <= inicio:
        raise EntradaInvalida("o fim precisa ser depois do início", campo="intervalo")
    return inicio, fim


def _titulo_igual(a: str, b: str) -> bool:
    """Compara títulos ignorando caixa, forma Unicode e espaçamento — nada além disso.

    Era uma checagem de substring, e substring vazia casa com qualquer string:
    `titulo_esperado=""` apagava qualquer evento. Agora exige igualdade normalizada.
    """

    def chave(texto: str) -> str:
        return " ".join(unicodedata.normalize("NFC", texto).casefold().split())

    return chave(a) == chave(b)


def _validar_alvo(event_id: str, titulo_esperado: str) -> None:
    """Primeiras travas de toda mutação por ID — antes de abrir o serviço, como sempre foi."""
    if not event_id.strip():
        raise EntradaInvalida("o ID do evento veio vazio", campo="event_id")
    if not titulo_esperado.strip():
        raise EntradaInvalida("o título esperado veio vazio", campo="titulo_esperado")


def _conferido(service, event_id: str, titulo_esperado: str) -> Evento:
    """Busca o evento e confere o título. Só devolve o evento se o título bater."""
    try:
        item = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:  # qualquer falha ao buscar = não dá pra conferir
        raise EventoNaoEncontrado(str(exc), event_id=event_id) from exc
    evento = _evento_de(item)
    if not _titulo_igual(titulo_esperado, evento.titulo):
        raise TituloDivergente(
            f"o evento se chama '{evento.titulo}'",
            event_id=event_id,
            titulo_real=evento.titulo,
            titulo_esperado=titulo_esperado,
        )
    return evento


def proximos(max_results: int = 10) -> list[Evento]:
    service = get_calendar_service()
    resposta = _executar(
        lambda: service.events().list(
            calendarId="primary",
            timeMin=datetime.now(UTC).isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
    )
    return [_evento_de(item) for item in resposta.get("items", [])]


def por_data(data_inicio: str, data_fim: str | None = None) -> list[Evento]:
    # A janela é validada antes de abrir o serviço: data inválida não chega a chamar a API.
    try:
        time_min, time_max = _janela(data_inicio, data_fim)
    except ValueError as exc:
        raise EntradaInvalida(str(exc), campo="data") from exc
    service = get_calendar_service()
    resposta = _executar(
        lambda: service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
    )
    return [_evento_de(item) for item in resposta.get("items", [])]


def buscar(termo_busca: str) -> list[Evento]:
    service = get_calendar_service()
    resposta = _executar(
        lambda: service.events().list(
            calendarId="primary",
            q=termo_busca,
            timeMin=datetime.now(UTC).isoformat(),
            singleEvents=True,
        )
    )
    return [_evento_de(item) for item in resposta.get("items", [])]


def criar(summary: str, start_time: str, end_time: str, description: str = "") -> Evento:
    inicio, fim = _intervalo(start_time, end_time)
    corpo = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": inicio.isoformat()},
        "end": {"dateTime": fim.isoformat()},
    }
    service = get_calendar_service()
    criado = _executar(lambda: service.events().insert(calendarId="primary", body=corpo))
    # O que enviamos prevalece sobre o eco da API: é o que o usuário pediu, e mantém o texto de
    # resposta idêntico ao de antes. Da resposta vêm id e link.
    return _evento_de({**criado, **corpo})


def criar_dia_inteiro(summary: str, data: str, description: str = "") -> Evento:
    try:
        dia = date.fromisoformat(data.strip())
    except ValueError as exc:
        raise EntradaInvalida(str(exc), campo="data") from exc
    corpo = {
        "summary": summary,
        "description": description,
        "start": {"date": dia.isoformat()},
        # end.date do Google é EXCLUSIVO: um evento de um dia termina no dia seguinte.
        "end": {"date": (dia + timedelta(days=1)).isoformat()},
    }
    service = get_calendar_service()
    criado = _executar(lambda: service.events().insert(calendarId="primary", body=corpo))
    return _evento_de({**criado, **corpo})


def apagar(event_id: str, titulo_esperado: str) -> Evento:
    """Apaga UM evento, só depois de todas as travas. Devolve o evento apagado."""
    _validar_alvo(event_id, titulo_esperado)
    service = get_calendar_service()
    evento = _conferido(service, event_id, titulo_esperado)
    try:
        _executar(lambda: service.events().delete(calendarId="primary", eventId=event_id))
    except FalhaDaApi as exc:
        exc.dados["titulo_real"] = evento.titulo
        raise
    return evento


def reagendar(event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str) -> Evento:
    """Muda o horário de UM evento já conferido. Devolve o evento com o horário novo."""
    _validar_alvo(event_id, titulo_esperado)
    service = get_calendar_service()
    evento = _conferido(service, event_id, titulo_esperado)
    inicio, fim = _intervalo(novo_inicio, novo_fim)
    try:
        _executar(
            lambda: service.events().patch(
                calendarId="primary",
                eventId=event_id,
                body={
                    "start": {"dateTime": inicio.isoformat()},
                    "end": {"dateTime": fim.isoformat()},
                },
            )
        )
    except FalhaDaApi as exc:
        exc.dados["titulo_real"] = evento.titulo
        raise
    return Evento(
        id=evento.id,
        titulo=evento.titulo,
        inicio=inicio.isoformat(),
        fim=fim.isoformat(),
        link=evento.link,
    )
