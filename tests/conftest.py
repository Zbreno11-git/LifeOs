"""Trava de segurança da suíte inteira: nenhum teste fala com o Google de verdade.

No Mac do dono os tokens OAuth existem — um teste que escapasse do fake criaria ou apagaria evento
na agenda real, ou leria a caixa de e-mail dele. Os testes trocam `get_calendar_service` /
`get_gmail_service` por fakes depois desta trava (fixtures `autouse` são montadas antes das que o
teste pede). A trava cobre também o fundo do poço (`google_auth.build` e o fluxo de login), para
um caminho novo que esqueça os dois nomes acima.
"""

import base64

import httplib2
import pytest
from googleapiclient.errors import HttpError


def _proibido(*_args, **_kwargs):
    raise AssertionError("um teste tentou abrir o Google de verdade — use o fake")


@pytest.fixture(autouse=True)
def _sem_google_de_verdade(monkeypatch):
    monkeypatch.setattr("lifeos.calendar.oauth.get_calendar_service", _proibido)
    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service", _proibido)
    monkeypatch.setattr("lifeos.gmail.oauth.get_gmail_service", _proibido)
    monkeypatch.setattr("lifeos.gmail.service.get_gmail_service", _proibido)
    monkeypatch.setattr("lifeos.google_auth.build", _proibido)
    monkeypatch.setattr(
        "lifeos.google_auth.InstalledAppFlow.from_client_secrets_file", staticmethod(_proibido)
    )


# --- Google Calendar falso, compartilhado pelos testes de calendário e do MCP -------------


class _Exec:
    def __init__(self, valor):
        self._valor = valor

    def execute(self):
        return self._valor


class _Events:
    def __init__(self, evento, estado):
        self._evento = evento
        self._estado = estado

    def get(self, calendarId, eventId):
        if self._evento is None:
            raise RuntimeError("Not Found")
        return _Exec(self._evento)

    def delete(self, calendarId, eventId):
        if self._estado.get("falhar_delete"):
            raise RuntimeError("API fora do ar")
        self._estado["apagados"].append(eventId)
        return _Exec({})

    def patch(self, calendarId, eventId, body):
        if self._estado.get("falhar_patch"):
            raise RuntimeError("API fora do ar")
        self._estado["patches"].append((eventId, body))
        return _Exec({"summary": self._evento.get("summary") if self._evento else None})

    def insert(self, calendarId, body):
        if self._estado.get("falhar_insert"):
            raise RuntimeError("API fora do ar")
        self._estado["enviados"].append(body)
        return _Exec({"id": "novo123", "htmlLink": "http://exemplo"})

    def list(self, calendarId, **kwargs):
        if self._estado.get("falhar_list"):
            raise RuntimeError("API fora do ar")
        self._estado["consultas"].append(kwargs)
        return _Exec({"items": self._estado["itens"]})


class _Service:
    def __init__(self, evento, estado):
        self._events = _Events(evento, estado)

    def events(self):
        return self._events


@pytest.fixture()
def calendario(monkeypatch):
    """Fake do Google no lugar do `get_calendar_service` que o serviço usa. `estado` registra o
    que foi enviado e permite configurar o evento do `get`, os itens do `list` e falhas."""
    estado = {
        "apagados": [],
        "patches": [],
        "enviados": [],
        "consultas": [],
        "itens": [],
        "falhar_delete": False,
        "evento": {"summary": "Dentista", "start": {"date": "2026-10-01"}},
    }

    def fake_service():
        return _Service(estado["evento"], estado)

    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service", fake_service)
    return estado


# --- Gmail falso, no formato da API real (users.messages list/get + lotes) ------------------


def corpo_b64(texto: str, charset: str = "utf-8") -> str:
    """Como o Gmail entrega `body.data`: base64url, SEM o padding `=` no fim."""
    return base64.urlsafe_b64encode(texto.encode(charset)).decode().rstrip("=")


def _erro_http(status: int) -> HttpError:
    return HttpError(httplib2.Response({"status": str(status)}), b"erro falso")


class _GmailPedido:
    def __init__(self, acao):
        self._acao = acao

    def execute(self):
        return self._acao()


class _GmailLote:
    def __init__(self, estado, callback):
        self._estado, self._callback, self._itens = estado, callback, []

    def add(self, pedido, request_id):
        self._itens.append((request_id, pedido))

    def execute(self):
        self._estado["lotes"].append(len(self._itens))
        if self._estado["falhar_lote"]:
            raise RuntimeError("lote fora do ar")
        for request_id, pedido in self._itens:
            try:
                self._callback(request_id, pedido.execute(), None)
            except Exception as exc:  # noqa: BLE001 - o lote real entrega a exceção por item
                self._callback(request_id, None, exc)


class _GmailMensagens:
    def __init__(self, estado):
        self._estado = estado

    def list(self, userId, q, maxResults, pageToken=None):
        estado = self._estado

        def acao():
            estado["consultas"].append(q)
            if estado["falhar_list"]:
                raise RuntimeError("API fora do ar")
            ids = list(estado["mensagens"])
            inicio = int(pageToken or 0)
            fim = inicio + min(maxResults, estado["por_pagina"])
            resposta = {"messages": [{"id": i, "threadId": i} for i in ids[inicio:fim]]}
            if fim < len(ids):
                resposta["nextPageToken"] = str(fim)
            return resposta

        return _GmailPedido(acao)

    def get(self, userId, id, format, metadataHeaders=None):
        estado = self._estado

        def acao():
            estado["gets"].append((id, format))
            if id in estado["falhar_sempre"]:
                raise _erro_http(500)
            if id in estado["falhar_uma_vez"]:
                estado["falhar_uma_vez"].discard(id)
                raise _erro_http(429)
            if id not in estado["mensagens"]:
                raise _erro_http(404)
            return estado["mensagens"][id]

        return _GmailPedido(acao)


class _GmailServico:
    def __init__(self, estado):
        self._estado = estado
        self._mensagens = _GmailMensagens(estado)

    def users(self):
        return self

    def getProfile(self, userId):
        return _GmailPedido(lambda: {"emailAddress": "dono@example.com", "messagesTotal": 1234})

    def messages(self):
        return self._mensagens

    def new_batch_http_request(self, callback):
        return _GmailLote(self._estado, callback)


def mensagem_gmail(
    email_id: str,
    *,
    de: str = "Loja <ofertas@loja.example>",
    assunto: str = "Oferta",
    trecho: str = "trecho",
    rotulos: tuple = ("INBOX", "UNREAD"),
    lista: bool = False,
    partes: list | None = None,
    quando_ms: int = 1_790_000_000_000,
) -> dict:
    cabecalhos = [{"name": "From", "value": de}, {"name": "Subject", "value": assunto}]
    if lista:
        cabecalhos.append({"name": "List-Unsubscribe", "value": "<mailto:sair@loja.example>"})
    payload = {"mimeType": "multipart/alternative", "headers": cabecalhos, "parts": partes or []}
    return {
        "id": email_id,
        "threadId": email_id,
        "labelIds": list(rotulos),
        "snippet": trecho,
        "internalDate": str(quando_ms),
        "payload": payload,
    }


@pytest.fixture()
def gmail(monkeypatch):
    """Gmail falso no lugar do `get_gmail_service` que o serviço usa. `estado["mensagens"]` é a
    caixa (id → mensagem no formato da API); o resto registra o que foi pedido e liga falhas."""
    estado = {
        "mensagens": {},
        "consultas": [],
        "gets": [],
        "lotes": [],
        "por_pagina": 100,
        "falhar_list": False,
        "falhar_lote": False,
        "falhar_sempre": set(),
        "falhar_uma_vez": set(),
    }

    def nova(email_id, **campos):
        estado["mensagens"][email_id] = mensagem_gmail(email_id, **campos)
        return estado["mensagens"][email_id]

    def parte(tipo, texto, charset="utf-8", nome=""):
        return {
            "mimeType": tipo,
            "filename": nome,
            "headers": [{"name": "Content-Type", "value": f'{tipo}; charset="{charset}"'}],
            "body": {"data": corpo_b64(texto, charset)},
        }

    estado["nova"], estado["parte"] = nova, parte
    monkeypatch.setattr("lifeos.gmail.service.get_gmail_service", lambda: _GmailServico(estado))
    monkeypatch.setattr("lifeos.gmail.service.PAUSA_S", 0)
    return estado
