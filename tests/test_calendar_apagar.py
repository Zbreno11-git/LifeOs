"""A exclusão de evento é a ação mais destrutiva do Viking — a trava é testada, não confiada."""

import pytest

from lifeos.calendar import tools


class _Exec:
    def __init__(self, valor):
        self._valor = valor

    def execute(self):
        return self._valor


class _Events:
    def __init__(self, evento, apagados):
        self._evento = evento
        self.apagados = apagados

    def get(self, calendarId, eventId):
        if self._evento is None:
            raise RuntimeError("Not Found")
        return _Exec(self._evento)

    def delete(self, calendarId, eventId):
        self.apagados.append(eventId)
        return _Exec({})


class _Service:
    def __init__(self, evento, apagados):
        self._events = _Events(evento, apagados)

    def events(self):
        return self._events


@pytest.fixture()
def calendario(monkeypatch):
    estado = {"apagados": [], "evento": {"summary": "Dentista", "start": {"date": "2026-10-01"}}}

    def fake_service():
        return _Service(estado["evento"], estado["apagados"])

    monkeypatch.setattr(tools, "get_calendar_service", fake_service)
    return estado


def test_apaga_quando_o_titulo_confere(calendario):
    resposta = tools.apagar_evento_por_id("abc123", "Dentista")
    assert calendario["apagados"] == ["abc123"]
    assert "apagado" in resposta
    assert "2026-10-01" in resposta


def test_aceita_titulo_parcial(calendario):
    tools.apagar_evento_por_id("abc123", "dentista")
    assert calendario["apagados"] == ["abc123"]


def test_recusa_quando_o_titulo_nao_bate(calendario):
    """Trava principal: ID certo mas título errado significa que o modelo se confundiu."""
    resposta = tools.apagar_evento_por_id("abc123", "Deepwater horizon")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta
    assert "Dentista" in resposta


def test_id_inexistente_nao_apaga_nada(calendario):
    calendario["evento"] = None
    resposta = tools.apagar_evento_por_id("sumiu", "Dentista")
    assert calendario["apagados"] == []
    assert "Não encontrei" in resposta
