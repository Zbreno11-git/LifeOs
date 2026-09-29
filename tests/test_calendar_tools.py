"""Calendário: exclusão e reagendamento são as ações mais destrutivas do Viking — a trava é
testada, não confiada. Este arquivo também cobre a janela de datas e o fim exclusivo do dia
inteiro, os outros dois achados P0 da auditoria do Codex (docs/historico/auditoria_codex_1.md)."""

from zoneinfo import ZoneInfo

import pytest

from lifeos.calendar import service, tools

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


def test_titulo_vazio_nao_apaga_evento_de_titulo_em_branco(calendario):
    """Achado pela mutação da Sessão 4b: um evento cujo título é só espaço normaliza igual a um
    `titulo_esperado` vazio. Aí só a primeira trava (título vazio) segura — a comparação de
    títulos, sozinha, deixaria apagar."""
    calendario["evento"] = {"summary": "   ", "start": {"date": "2026-10-01"}}
    resposta = tools.apagar_evento_por_id("abc123", "")
    assert calendario["apagados"] == []
    assert "preciso do título exato" in resposta
    resposta = tools.reagendar_evento_por_id(
        "abc123", "", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert calendario["patches"] == []


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
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
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
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
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
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    t_min, t_max = service._janela("2026-09-20", None)
    assert t_min == "2026-09-20T00:00:00-03:00"
    assert t_max == "2026-09-21T00:00:00-03:00"


def test_janela_intervalo_e_inclusiva(monkeypatch):
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    t_min, t_max = service._janela("2026-09-20", "2026-09-22")
    assert t_min == "2026-09-20T00:00:00-03:00"
    assert t_max == "2026-09-23T00:00:00-03:00"


def test_janela_data_fim_anterior_a_inicio_levanta(monkeypatch):
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    with pytest.raises(ValueError):
        service._janela("2026-09-20", "2026-09-19")


def test_janela_respeita_fuso_utc(monkeypatch):
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("UTC"))
    t_min, t_max = service._janela("2026-09-20", None)
    assert t_min == "2026-09-20T00:00:00+00:00"
    assert t_max == "2026-09-21T00:00:00+00:00"


def test_listar_eventos_por_data_usa_a_janela(calendario, monkeypatch):
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))
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
    assert service._titulo_igual(nfc, nfd)


def test_titulo_igual_string_vazia_nao_casa_com_tudo():
    assert not service._titulo_igual("", "Qualquer coisa")


# --- fuso inventado pelo modelo (Mac, 2026-09-27) -----------------------------------------
# O dono pediu "amanhã às 10h" e o Gemini mandou `10:00:00-08:00`: o evento caiu às 15h de
# Brasília. Nas tools do Gemini, fuso diferente do do dono é recusado com a instrução de mandar
# sem fuso; o mesmo fuso, ou nenhum, segue.


def test_criar_evento_recusa_fuso_diferente_do_dono(calendario):
    resposta = tools.criar_evento(
        "Teste Viking", "2026-09-28T10:00:00-08:00", "2026-09-28T11:00:00-08:00"
    )
    assert calendario["enviados"] == []
    assert resposta.startswith("NÃO criei o evento: o horário veio com fuso -08:00")
    assert "sem fuso" in resposta


def test_criar_evento_com_o_fuso_do_dono_segue(calendario):
    tools.criar_evento("Teste Viking", "2026-09-28T10:00:00-03:00", "2026-09-28T11:00:00-03:00")
    assert calendario["enviados"][0]["start"]["dateTime"] == "2026-09-28T10:00:00-03:00"


def test_fuso_so_no_fim_tambem_e_recusado(calendario):
    # 14:00Z = 11:00 em Brasília, depois do início: só a régua do fuso pode recusar.
    tools.criar_evento("Teste Viking", "2026-09-28T10:00:00", "2026-09-28T14:00:00Z")
    assert calendario["enviados"] == []


def test_reagendar_recusa_fuso_diferente_do_dono(calendario):
    resposta = tools.reagendar_evento_por_id(
        "abc123", "Dentista", "2026-10-02T10:00:00+00:00", "2026-10-02T11:00:00+00:00"
    )
    assert calendario["patches"] == []
    assert resposta.startswith("NÃO reagendei: o horário veio com fuso +00:00")


def test_fuso_do_dono_segue_o_horario_de_verao(calendario, monkeypatch):
    """O fuso do dono é o da data do evento, não o de hoje: em Nova York, julho é -04:00 e janeiro
    é -05:00. As duas datas juntas separam isso de "o fuso de agora", seja qual for o dia."""
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/New_York"))
    tools.criar_evento("Verão", "2026-07-01T10:00:00-04:00", "2026-07-01T11:00:00-04:00")
    tools.criar_evento("Inverno", "2026-01-15T10:00:00-05:00", "2026-01-15T11:00:00-05:00")
    assert [e["summary"] for e in calendario["enviados"]] == ["Verão", "Inverno"]
    tools.criar_evento("Trocado", "2026-07-01T10:00:00-05:00", "2026-07-01T11:00:00-05:00")
    assert len(calendario["enviados"]) == 2


def test_mcp_nao_passa_pela_regua_do_fuso(calendario):
    """Pelo MCP quem manda o fuso é o app que chama; a régua é da tool do Gemini."""
    tools.responder_criar("Outro app", "2026-09-28T10:00:00-08:00", "2026-09-28T11:00:00-08:00")
    assert len(calendario["enviados"]) == 1


@pytest.mark.parametrize("valor", ["2026-09-28T10:00:00", "2026-09-28", "não é data", ""])
def test_sem_fuso_ou_invalido_nao_e_fuso_diferente(calendario, valor):
    """Formato inválido é problema do serviço (mensagem própria), não da régua do fuso."""
    assert service.fuso_diferente(valor) is None


# --- lista incompleta (Sessão 8b) ------------------------------------------------------------


def _serie(n: int) -> list[dict]:
    return [
        {"id": f"s{i}", "summary": "Aula", "start": {"date": f"2027-01-{i % 28 + 1:02d}"}}
        for i in range(n)
    ]


def test_busca_incompleta_diz_que_ha_mais(calendario):
    calendario["itens"] = _serie(600)
    texto = tools.buscar_eventos_por_termo("Aula")
    assert texto.count("\n- [") == 500
    assert "há mais" in texto
    assert "500" in texto.splitlines()[0]


def test_por_data_incompleta_diz_que_ha_mais(calendario):
    calendario["itens"] = _serie(600)
    texto = tools.listar_eventos_por_data("2027-01-01", "2027-12-31")
    assert "há mais" in texto


def test_lista_completa_nao_avisa(calendario):
    calendario["itens"] = _serie(300)
    texto = tools.buscar_eventos_por_termo("Aula")
    assert texto.count("\n- [") == 300
    assert "há mais" not in texto
