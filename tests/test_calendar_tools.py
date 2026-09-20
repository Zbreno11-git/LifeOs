"""Calendário: exclusão e reagendamento são as ações mais destrutivas do Viking — a trava é
testada, não confiada. Este arquivo também cobre a janela de datas e o fim exclusivo do dia
inteiro, os outros dois achados P0 da auditoria do Codex (auditoria_codex_1.md)."""

from zoneinfo import ZoneInfo

import pytest

from lifeos.calendar import tools


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
        self._estado["patches"].append((eventId, body))
        return _Exec({"summary": self._evento.get("summary") if self._evento else None})

    def insert(self, calendarId, body):
        self._estado["enviados"].append(body)
        return _Exec({"htmlLink": "http://exemplo"})

    def list(self, calendarId, **kwargs):
        self._estado["consultas"].append(kwargs)
        return _Exec({"items": []})


class _Service:
    def __init__(self, evento, estado):
        self._events = _Events(evento, estado)

    def events(self):
        return self._events


@pytest.fixture()
def calendario(monkeypatch):
    estado = {
        "apagados": [],
        "patches": [],
        "enviados": [],
        "consultas": [],
        "falhar_delete": False,
        "evento": {"summary": "Dentista", "start": {"date": "2026-10-01"}},
    }

    def fake_service():
        return _Service(estado["evento"], estado)

    monkeypatch.setattr(tools, "get_calendar_service", fake_service)
    return estado


# --- apagar_evento_por_id -----------------------------------------------------------------


def test_apaga_quando_o_titulo_confere(calendario):
    resposta = tools.apagar_evento_por_id("abc123", "Dentista")
    assert calendario["apagados"] == ["abc123"]
    assert "apagado" in resposta
    assert "2026-10-01" in resposta


def test_aceita_diferenca_de_caixa(calendario):
    tools.apagar_evento_por_id("abc123", "dentista")
    assert calendario["apagados"] == ["abc123"]


def test_aceita_espacamento_diferente(calendario):
    calendario["evento"] = {"summary": "Reunião com o time", "start": {"date": "2026-10-01"}}
    tools.apagar_evento_por_id("abc123", "Reunião  com   o time")
    assert calendario["apagados"] == ["abc123"]


def test_recusa_quando_o_titulo_nao_bate(calendario):
    """Trava principal: ID certo mas título errado significa que o modelo se confundiu."""
    resposta = tools.apagar_evento_por_id("abc123", "Deepwater horizon")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta
    assert "Dentista" in resposta


def test_recusa_substring_curta(calendario):
    """O achado da auditoria: era checagem de substring, e 'com' casava com 'Reunião com o time'."""
    calendario["evento"] = {"summary": "Reunião com o time", "start": {"date": "2026-10-01"}}
    resposta = tools.apagar_evento_por_id("abc123", "com")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta


def test_recusa_titulo_vazio(calendario):
    resposta = tools.apagar_evento_por_id("abc123", "")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta


def test_recusa_titulo_so_espacos(calendario):
    """Substring vazia (após strip) casava com QUALQUER título — o buraco mais grave do achado."""
    resposta = tools.apagar_evento_por_id("abc123", "   ")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta


def test_recusa_id_vazio(calendario):
    resposta = tools.apagar_evento_por_id("", "Dentista")
    assert calendario["apagados"] == []
    assert "NÃO apaguei" in resposta


def test_id_inexistente_nao_apaga_nada(calendario):
    calendario["evento"] = None
    resposta = tools.apagar_evento_por_id("sumiu", "Dentista")
    assert calendario["apagados"] == []
    assert "Não encontrei" in resposta


def test_falha_da_api_ao_deletar_nao_reporta_sucesso(calendario):
    calendario["falhar_delete"] = True
    resposta = tools.apagar_evento_por_id("abc123", "Dentista")
    assert calendario["apagados"] == []
    assert "NÃO consegui apagar" in resposta


# --- reagendar_evento_por_id ---------------------------------------------------------------


def test_reagenda_quando_o_titulo_confere(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "Dentista", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert len(calendario["patches"]) == 1
    event_id, body = calendario["patches"][0]
    assert event_id == "abc123"
    assert body["start"]["dateTime"] == "2026-10-02T10:00:00-03:00"
    assert body["end"]["dateTime"] == "2026-10-02T11:00:00-03:00"
    assert "reagendado" in resposta


def test_reagendar_recusa_titulo_divergente(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "Corte de cabelo", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "NÃO reagendei" in resposta


def test_reagendar_recusa_titulo_vazio(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "NÃO reagendei" in resposta


def test_reagendar_recusa_id_vazio(calendario):
    resposta = tools.reagendar_evento_por_id(
        "", "Dentista", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "NÃO reagendei" in resposta


def test_reagendar_recusa_fim_antes_do_inicio(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "Dentista", "2026-10-02T11:00:00-03:00", "2026-10-02T10:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "depois do início" in resposta


def test_reagendar_recusa_fim_igual_ao_inicio(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "Dentista", "2026-10-02T10:00:00-03:00", "2026-10-02T10:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "depois do início" in resposta


def test_reagendar_id_inexistente(calendario):
    calendario["evento"] = None
    resposta = tools.reagendar_evento_por_id(
        "sumiu", "Dentista", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert calendario["patches"] == []
    assert "Não encontrei" in resposta


def test_reagendar_horario_invalido(calendario):
    resposta = tools.reagendar_evento_por_id("abc123", "Dentista", "not-a-date", "also-not-a-date")
    assert calendario["patches"] == []
    assert "Não entendi" in resposta


def test_reagendar_aceita_horario_sem_fuso(calendario, monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    tools.reagendar_evento_por_id(
        "abc123", "Dentista", "2026-10-02T10:00:00", "2026-10-02T11:00:00"
    )
    _, body = calendario["patches"][0]
    assert body["start"]["dateTime"] == "2026-10-02T10:00:00-03:00"


# --- criar_evento ------------------------------------------------------------------------


def test_criar_evento_recusa_fim_antes_do_inicio(calendario):
    resposta = tools.criar_evento(
        "Reunião", "2026-10-02T11:00:00-03:00", "2026-10-02T10:00:00-03:00"
    )
    assert calendario["enviados"] == []
    assert "depois do início" in resposta


def test_criar_evento_recusa_horario_invalido(calendario):
    resposta = tools.criar_evento("Reunião", "not-a-date", "also-not")
    assert calendario["enviados"] == []
    assert "Não entendi" in resposta


def test_criar_evento_envia_horario_normalizado(calendario, monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    tools.criar_evento("Reunião", "2026-10-02T10:00:00", "2026-10-02T11:00:00")
    assert calendario["enviados"][0]["start"]["dateTime"] == "2026-10-02T10:00:00-03:00"


# --- criar_evento_dia_inteiro (fim exclusivo) --------------------------------------------


def test_dia_inteiro_termina_no_dia_seguinte(calendario):
    tools.criar_evento_dia_inteiro("Feriado", "2026-09-20")
    corpo = calendario["enviados"][0]
    assert corpo["start"]["date"] == "2026-09-20"
    assert corpo["end"]["date"] == "2026-09-21"


def test_dia_inteiro_vira_de_mes(calendario):
    tools.criar_evento_dia_inteiro("Fim de mês", "2026-09-30")
    corpo = calendario["enviados"][0]
    assert corpo["end"]["date"] == "2026-10-01"


def test_dia_inteiro_vira_de_ano(calendario):
    tools.criar_evento_dia_inteiro("Ano novo", "2026-12-31")
    corpo = calendario["enviados"][0]
    assert corpo["end"]["date"] == "2027-01-01"


def test_dia_inteiro_ano_bissexto(calendario):
    tools.criar_evento_dia_inteiro("Bissexto", "2028-02-29")
    corpo = calendario["enviados"][0]
    assert corpo["end"]["date"] == "2028-03-01"


def test_dia_inteiro_recusa_data_invalida(calendario):
    resposta = tools.criar_evento_dia_inteiro("Feriado", "20-09-2026")
    assert calendario["enviados"] == []
    assert "Não entendi" in resposta


# --- _janela / listar_eventos_por_data (fuso + fim exclusivo) ----------------------------


def test_janela_um_dia_nao_inclui_o_dia_seguinte(monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    t_min, t_max = tools._janela("2026-09-20", None)
    assert t_min == "2026-09-20T00:00:00-03:00"
    assert t_max == "2026-09-21T00:00:00-03:00"


def test_janela_intervalo_e_inclusiva(monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    t_min, t_max = tools._janela("2026-09-20", "2026-09-22")
    assert t_min == "2026-09-20T00:00:00-03:00"
    assert t_max == "2026-09-23T00:00:00-03:00"


def test_janela_data_fim_anterior_a_inicio_levanta(monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    with pytest.raises(ValueError):
        tools._janela("2026-09-20", "2026-09-19")


def test_janela_respeita_fuso_utc(monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("UTC"))
    t_min, t_max = tools._janela("2026-09-20", None)
    assert t_min == "2026-09-20T00:00:00+00:00"
    assert t_max == "2026-09-21T00:00:00+00:00"


def test_listar_eventos_por_data_usa_a_janela(calendario, monkeypatch):
    monkeypatch.setattr(tools, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    tools.listar_eventos_por_data("2026-09-20")
    consulta = calendario["consultas"][0]
    assert consulta["timeMin"] == "2026-09-20T00:00:00-03:00"
    assert consulta["timeMax"] == "2026-09-21T00:00:00-03:00"


def test_listar_eventos_por_data_invalida_nao_chama_a_api(calendario):
    resposta = tools.listar_eventos_por_data("2026-09-20", "2026-09-10")
    assert calendario["consultas"] == []
    assert "Não entendi" in resposta


# --- _titulo_igual -------------------------------------------------------------------------


def test_titulo_igual_ignora_forma_unicode():
    # "á" como um único codepoint (NFC) vs "a" + acento combinante (NFD) devem casar.
    nfc = "Reunião"
    nfd = "Reunião"
    assert tools._titulo_igual(nfc, nfd)


def test_titulo_igual_string_vazia_nao_casa_com_tudo():
    assert not tools._titulo_igual("", "Qualquer coisa")
