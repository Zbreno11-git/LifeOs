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
from lifeos import aprovacoes, confirmacao, registro
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


class NaoDesfazivel(ErroCalendario):
    codigo = "nao_desfazivel"


class LimiteDePedidos(ErroCalendario):
    codigo = "limite_de_pedidos"


class MudouDesdeOPedido(ErroCalendario):
    codigo = "mudou_desde_o_pedido"


class FalhaDaApi(ErroCalendario):
    codigo = "falha_api"

    def __init__(self, mensagem: str, *, incerta: bool = False, **dados: object) -> None:
        super().__init__(mensagem, **dados)
        # O pedido pode ter sido aplicado (tempo esgotado, 5xx, conexão caída): o registro de
        # ações grava "incerta" e o chat diz "pode ter sido feito" em vez de "falhou".
        self.incerta = incerta


def _status_http(exc: Exception) -> int | None:
    status = getattr(getattr(exc, "resp", None), "status", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def _executar(montar):
    """Toda chamada ao Google passa por aqui: falha vira `FalhaDaApi`. Antes, uma falha em criar,
    reagendar ou listar subia crua pelo laço do Gemini. Recebe a MONTAGEM da requisição (um
    callable), não a requisição pronta: a falha pode vir já ao montar, não só no `.execute()`.

    Falha ao montar, ou um 4xx do Google, é certeza de que nada mudou; qualquer outra falha depois
    de enviar é `incerta`."""
    try:
        requisicao = montar()
    except Exception as exc:
        raise FalhaDaApi(str(exc)) from exc
    try:
        return requisicao.execute()
    except Exception as exc:  # qualquer falha da API vira erro de domínio
        status = _status_http(exc)
        raise FalhaDaApi(str(exc), incerta=not (status and 400 <= status < 500)) from exc


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


def _offset(dt: datetime) -> str:
    total = int(dt.utcoffset().total_seconds()) // 60
    sinal = "-" if total < 0 else "+"
    return f"{sinal}{abs(total) // 60:02d}:{abs(total) % 60:02d}"


def fuso_diferente(valor: str) -> tuple[str, str] | None:
    """(fuso que veio, fuso do dono naquela data) se `valor` traz um fuso diferente do do dono.
    `None` sem fuso, com o mesmo fuso ou se não for ISO (o formato é validado por quem cria).

    Existe porque o Gemini inventou `-08:00` para "amanhã às 10h" e o evento caiu às 15h de
    Brasília (Mac, 2026-09-27). O fuso do dono é o da data do horário, não o de hoje (horário de
    verão)."""
    try:
        dt = datetime.fromisoformat(str(valor or "").strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    do_dono = dt.replace(tzinfo=TIMEZONE)
    if dt.utcoffset() == do_dono.utcoffset():
        return None
    return _offset(dt), _offset(do_dono)


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


def _conferido(service, event_id: str, titulo_esperado: str) -> tuple[Evento, dict]:
    """Busca o evento e confere o título. Só devolve o evento (e o item bruto do Google, que é a
    cópia para desfazer) se o título bater."""
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
    return evento, item


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
    return _inserir(corpo)


def _inserir(corpo: dict) -> Evento:
    service = get_calendar_service()
    parametros = {"titulo": corpo["summary"], "inicio": corpo["start"], "fim": corpo["end"]}
    with registro.acao("calendario.criar", parametros) as marca:
        criado = _executar(lambda: service.events().insert(calendarId="primary", body=corpo))
        marca.feito({"event_id": criado.get("id"), "titulo": corpo["summary"]})
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
    return _inserir(corpo)


def apagar(event_id: str, titulo_esperado: str) -> Evento:
    """Apaga UM evento, só depois de todas as travas. Devolve o evento apagado."""
    _validar_alvo(event_id, titulo_esperado)
    service = get_calendar_service()
    evento, item = _conferido(service, event_id, titulo_esperado)
    parametros = {"event_id": event_id, "titulo": evento.titulo, "inicio": evento.inicio}
    try:
        with registro.acao("calendario.apagar", parametros) as marca:
            _executar(lambda: service.events().delete(calendarId="primary", eventId=event_id))
            marca.feito(
                {"titulo": evento.titulo, "inicio": evento.inicio},
                desfazer={"evento": {**item, "id": item.get("id") or event_id}},
            )
    except FalhaDaApi as exc:
        exc.dados["titulo_real"] = evento.titulo
        raise
    return evento


def reagendar(event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str) -> Evento:
    """Muda o horário de UM evento já conferido. Devolve o evento com o horário novo."""
    _validar_alvo(event_id, titulo_esperado)
    service = get_calendar_service()
    evento, item = _conferido(service, event_id, titulo_esperado)
    inicio, fim = _intervalo(novo_inicio, novo_fim)
    novo = {"start": {"dateTime": inicio.isoformat()}, "end": {"dateTime": fim.isoformat()}}
    parametros = {"event_id": event_id, "titulo": evento.titulo, "de": evento.inicio, **novo}
    antigo = {
        "event_id": event_id,
        "start": item.get("start"),
        "end": item.get("end"),
        "novo_start": novo["start"],
        "novo_end": novo["end"],
    }
    try:
        with registro.acao("calendario.reagendar", parametros) as marca:
            _executar(
                lambda: service.events().patch(calendarId="primary", eventId=event_id, body=novo)
            )
            marca.feito({"titulo": evento.titulo, "para": inicio.isoformat()}, desfazer=antigo)
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


# --- desfazer (Sessão 5) ---------------------------------------------------------------------

OPERACOES_DESFAZIVEIS = ("calendario.apagar", "calendario.reagendar")
# O que a cópia leva: sem `attendees` (reconvidar mandaria e-mail em nome do dono), sem `id`
# (um insert com o ID antigo dá conflito) e sem campos de controle do Google.
_CAMPOS_DA_COPIA = (
    "summary",
    "description",
    "location",
    "start",
    "end",
    "colorId",
    "reminders",
    "transparency",
    "visibility",
)


@dataclass(frozen=True)
class Restaurado:
    titulo: str
    # "restaurado" (mesmo ID) · "recriado" (ID novo, sem convidados) · "horario" (voltou o
    # horário antigo) · "ja_estava" (nada a fazer)
    como: str
    event_id: str | None


def restaurar(acao_id: int) -> Restaurado:
    """Desfaz UMA ação de calendário do registro, uma vez só (a reivindicação é atômica). Se o
    desfazer falha, a ação volta a ser desfazível."""
    acao = registro.obter(acao_id)
    if acao is None or acao.operacao not in OPERACOES_DESFAZIVEIS:
        raise NaoDesfazivel("essa ação não é do calendário, ou não existe", acao_id=acao_id)
    copia = registro.reivindicar_desfazer(acao_id)
    if copia is None:
        raise NaoDesfazivel("essa ação já foi desfeita, ou não chegou a acontecer", acao_id=acao_id)
    try:
        if acao.operacao == "calendario.apagar":
            return _devolver_evento(copia["evento"])
        return _voltar_horario(copia)
    except Exception as exc:
        # Falha ambígua (o Google pode ter recriado): a ação continua desfeita — senão um segundo
        # `desfaz` recriaria outra cópia. Falha certa: volta a ser desfazível.
        if not getattr(exc, "incerta", False):
            registro.devolver_desfazer(acao_id)
        raise


def _titulo(item: dict) -> str:
    return limpar_controles(str(item.get("summary") or "(sem título)"))


def _devolver_evento(item: dict) -> Restaurado:
    titulo, event_id = _titulo(item), item.get("id")
    if item.get("recurringEventId") or item.get("recurrence"):
        raise NaoDesfazivel("é um evento de série: recrie pelo Google Calendar", titulo=titulo)
    organizador = item.get("organizer") or {}
    if organizador and not organizador.get("self", False):
        raise NaoDesfazivel("o evento é de outra pessoa (você era convidado)", titulo=titulo)
    service = get_calendar_service()
    with registro.acao("calendario.restaurar", {"titulo": titulo, "event_id": event_id}) as marca:
        atual = None
        if event_id:
            try:
                atual = service.events().get(calendarId="primary", eventId=event_id).execute()
            except Exception:  # noqa: BLE001 - sumiu de vez (404 ou outro): sobra recriar
                atual = None
        if atual and atual.get("status") != "cancelled":
            marca.feito({"titulo": titulo, "como": "ja_estava"})
            return Restaurado(titulo, "ja_estava", event_id)
        if atual:
            # Cancelado no calendário do organizador: a documentação do Google diz que os
            # detalhes ficam "so that they can be restored". Não medido: validar no Mac.
            try:
                _executar(
                    lambda: service.events().patch(
                        calendarId="primary",
                        eventId=event_id,
                        body={"status": "confirmed"},
                        sendUpdates="none",
                    )
                )
                marca.feito({"titulo": titulo, "como": "restaurado"})
                return Restaurado(titulo, "restaurado", event_id)
            except FalhaDaApi as exc:
                if exc.incerta:
                    raise
        corpo = {campo: item[campo] for campo in _CAMPOS_DA_COPIA if campo in item}
        criado = _executar(
            lambda: service.events().insert(calendarId="primary", body=corpo, sendUpdates="none")
        )
        marca.feito({"titulo": titulo, "como": "recriado", "event_id": criado.get("id")})
        return Restaurado(titulo, "recriado", criado.get("id"))


def _mesmo_horario(a: dict | None, b: dict | None) -> bool:
    a, b = a or {}, b or {}
    if a.get("dateTime") and b.get("dateTime"):
        try:
            return datetime.fromisoformat(a["dateTime"]) == datetime.fromisoformat(b["dateTime"])
        except ValueError:
            return False
    return bool(a.get("date")) and a.get("date") == b.get("date")


def _para_patch(horario: dict) -> dict:
    """O horário antigo inteiro, com o campo que não vale anulado: um `patch` em `start` mescla,
    e um `dateTime` que sobrasse faria o evento de dia inteiro voltar com hora."""
    if horario.get("date"):
        return {"date": horario["date"], "dateTime": None}
    corpo = {"dateTime": horario.get("dateTime"), "date": None}
    if horario.get("timeZone"):
        corpo["timeZone"] = horario["timeZone"]
    return corpo


def _voltar_horario(copia: dict) -> Restaurado:
    service = get_calendar_service()
    event_id = copia["event_id"]
    try:
        atual = service.events().get(calendarId="primary", eventId=event_id).execute()
    except Exception as exc:
        raise EventoNaoEncontrado(str(exc), event_id=event_id) from exc
    titulo = _titulo(atual)
    if atual.get("status") == "cancelled":
        raise NaoDesfazivel("o evento foi apagado depois do reagendamento", titulo=titulo)
    if not (
        _mesmo_horario(atual.get("start"), copia["novo_start"])
        and _mesmo_horario(atual.get("end"), copia["novo_end"])
    ):
        raise NaoDesfazivel("o horário mudou depois do reagendamento; não mexi", titulo=titulo)
    if not isinstance(copia.get("start"), dict) or not isinstance(copia.get("end"), dict):
        raise NaoDesfazivel("não guardei o horário antigo inteiro; não mexi", titulo=titulo)
    corpo = {"start": _para_patch(copia["start"]), "end": _para_patch(copia["end"])}
    with registro.acao("calendario.restaurar", {"titulo": titulo, "event_id": event_id}) as marca:
        _executar(
            lambda: service.events().patch(calendarId="primary", eventId=event_id, body=corpo)
        )
        marca.feito({"titulo": titulo, "como": "horario"})
    return Restaurado(titulo, "horario", event_id)


# --- pedidos de fora (MCP) e a aprovação no terminal (Sessão 5, D36) ------------------------

APAGAR = aprovacoes.CALENDARIO_APAGAR
REAGENDAR = aprovacoes.CALENDARIO_REAGENDAR
MAX_PEDIDOS_ABERTOS = 5
MAX_PEDIDOS_POR_HORA = 20


@dataclass(frozen=True)
class Pedido:
    acao: str
    evento: Evento
    descricao: str  # "apagar o evento 'Dentista' (2026-10-01)"
    expira: datetime


def pedir_mudanca(
    acao: str,
    event_id: str,
    titulo_esperado: str,
    novo_inicio: str = "",
    novo_fim: str = "",
    *,
    agora: datetime | None = None,
) -> Pedido:
    """Registra o pedido de outro app (pelo MCP) sem mudar nada: as mesmas travas de apagar e
    reagendar, e a proposta espera o dono em `viking aprovar`. O código não sai daqui — nem no
    texto nem nos dados que o MCP devolve."""
    if acao not in (APAGAR, REAGENDAR):
        raise EntradaInvalida("pedido de uma ação que o MCP não pede", campo="acao")
    _validar_alvo(event_id, titulo_esperado)
    novo: dict = {}
    if acao == REAGENDAR:
        inicio, fim = _intervalo(novo_inicio, novo_fim)
        novo = {"novo_inicio": inicio.isoformat(), "novo_fim": fim.isoformat()}
    momento = (agora or datetime.now(UTC)).astimezone(UTC)
    abertos = len(confirmacao.abertas(APAGAR, agora=momento)) + len(
        confirmacao.abertas(REAGENDAR, agora=momento)
    )
    na_hora = confirmacao.criadas_desde(APAGAR, momento - timedelta(hours=1))
    na_hora += confirmacao.criadas_desde(REAGENDAR, momento - timedelta(hours=1))
    if abertos >= MAX_PEDIDOS_ABERTOS or na_hora >= MAX_PEDIDOS_POR_HORA:
        raise LimiteDePedidos(
            f"há pedidos demais esperando o dono ({abertos} abertos, {na_hora} na última hora)"
        )
    service = get_calendar_service()
    evento, item = _conferido(service, event_id, titulo_esperado)
    if acao == APAGAR:
        descricao = f"apagar o evento '{evento.titulo}' ({evento.inicio})"
    else:
        descricao = (
            f"mudar o evento '{evento.titulo}' de {evento.inicio} para {novo['novo_inicio']}"
        )
    dados = {
        "event_id": event_id,
        "titulo": evento.titulo,
        "inicio": evento.inicio,
        "etag": item.get("etag"),
        "updated": item.get("updated"),
        "descricao": descricao,
        **novo,
    }
    proposta = confirmacao.propor(
        acao, dados, validade=aprovacoes.VALIDADE_MCP, substituir=False, agora=momento
    )
    return Pedido(acao, evento, descricao, proposta.expira)


def executar_aprovado(acao: str, codigo: str) -> Evento:
    """O que `viking aprovar` roda depois que o dono digitou o código: gasta o código, relê o
    evento e só age se ele é o mesmo do pedido (versão, título, início). Nunca chamado pelo MCP."""
    aprovado = confirmacao.consumir(acao, codigo)
    dados = aprovado.dados
    service = get_calendar_service()
    try:
        atual = service.events().get(calendarId="primary", eventId=dados["event_id"]).execute()
    except Exception as exc:
        raise EventoNaoEncontrado(str(exc), event_id=dados["event_id"]) from exc
    mudou = (
        atual.get("status") == "cancelled"
        or (dados.get("etag") and atual.get("etag") != dados["etag"])
        or (dados.get("updated") and atual.get("updated") != dados["updated"])
        or not _titulo_igual(dados["titulo"], _evento_de(atual).titulo)
        or _evento_de(atual).inicio != dados["inicio"]
    )
    if mudou:
        confirmacao.registrar(aprovado.id, {"feito": False, "motivo": "mudou"})
        raise MudouDesdeOPedido(
            f"o evento '{dados['titulo']}' mudou (ou foi apagado) desde o pedido; não mexi",
            event_id=dados["event_id"],
        )
    anterior = registro.ORIGEM.set("mcp")  # o pedido veio de outro app; o dono só aprovou
    try:
        if acao == APAGAR:
            evento = apagar(dados["event_id"], dados["titulo"])
        else:
            evento = reagendar(
                dados["event_id"], dados["titulo"], dados["novo_inicio"], dados["novo_fim"]
            )
    finally:
        registro.ORIGEM.reset(anterior)
    confirmacao.registrar(aprovado.id, {"feito": True})
    return evento
