"""Vários tipos de aprovação no mesmo laço do chat (Sessão 5).

A pergunta de cada teste: um código de um tipo aprova (ou vaza) outro? Um código de pedido que
veio pelo MCP — que só se aprova no terminal, com `viking aprovar` — nunca vai ao Gemini e nunca
é aprovado pelo chat.
"""

from datetime import timedelta

import pytest

from lifeos import aprovacoes, confirmacao
from lifeos.assistant import agent
from lifeos.gmail import limpeza


@pytest.fixture()
def pedido_do_mcp(monkeypatch):
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: 4821)
    return confirmacao.propor(
        aprovacoes.CALENDARIO_APAGAR,
        {"event_id": "e1", "titulo": "Dentista"},
        validade=aprovacoes.VALIDADE_MCP,
        substituir=False,
    )


@pytest.mark.parametrize(
    "linha", ["confirma 4821", "4821", "o código é 4821, confirma", "desfaz 4821", "4821!"]
)
def test_codigo_do_mcp_no_chat_aponta_o_terminal_e_nao_age(pedido_do_mcp, monkeypatch, linha):
    chamados = []
    monkeypatch.setattr(limpeza, "confirmar", lambda c: chamados.append(c))
    monkeypatch.setattr(limpeza, "desfazer", lambda c: chamados.append(c))
    texto, nota = agent.aprovacao_local(linha)
    assert "viking aprovar" in texto and nota == ""
    assert chamados == []
    assert confirmacao.aberta(aprovacoes.CALENDARIO_APAGAR)  # continua esperando o terminal


def test_numero_qualquer_com_so_pedido_do_mcp_aberto_segue_para_o_gemini(pedido_do_mcp):
    assert agent.aprovacao_local("1530") is None
    assert agent.aprovacao_local("a reunião é às 1530") is None


def test_os_tipos_tem_acoes_distintas_e_o_gmail_e_do_chat():
    acoes = [t.acao for t in aprovacoes.TIPOS]
    assert len(acoes) == len(set(acoes))
    assert limpeza.ACAO in {t.acao for t in aprovacoes.do_chat()}
    assert limpeza.DESFAZER_POR == timedelta(days=7)


def test_notas_ao_gemini_se_somam():
    assert agent._juntar("", "b") == "b"
    assert agent._juntar("a", "") == "a"
    assert agent._juntar("a", "b") == "a\nb"
