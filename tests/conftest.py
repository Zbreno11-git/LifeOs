"""Trava de segurança da suíte inteira: nenhum teste fala com o Google Calendar de verdade.

No Mac do dono o token OAuth existe — um teste que escapasse do fake criaria ou apagaria evento
na agenda real. Os testes de calendário trocam `service.get_calendar_service` por um fake depois
desta trava (fixtures `autouse` são montadas antes das que o teste pede).
"""

import pytest


def _proibido(*_args, **_kwargs):
    raise AssertionError("um teste tentou abrir o Google Calendar de verdade — use o fake")


@pytest.fixture(autouse=True)
def _sem_google_de_verdade(monkeypatch):
    monkeypatch.setattr("lifeos.calendar.oauth.get_calendar_service", _proibido)
    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service", _proibido)


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
