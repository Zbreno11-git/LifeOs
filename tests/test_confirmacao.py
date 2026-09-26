"""Confirmação mecânica: o código aprova uma proposta exata, uma vez, por pouco tempo.

É a trava que separa "o Gemini propôs" de "o dono aprovou" (D26). Cada teste é um jeito de um
código errado, velho ou reaproveitado aprovar algo que o dono não viu.
"""

from datetime import UTC, datetime, timedelta

import pytest

from lifeos import confirmacao

T0 = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
ACAO = "gmail.arquivar"


def test_codigo_aprova_os_dados_exatos_uma_vez():
    proposta = confirmacao.propor(ACAO, {"ids": ["a", "b"]}, agora=T0)
    assert len(proposta.codigo) == confirmacao.DIGITOS and proposta.codigo.isdigit()
    registro = confirmacao.consumir(ACAO, proposta.codigo, agora=T0)
    assert registro.dados == {"ids": ["a", "b"]}
    with pytest.raises(confirmacao.JaUsado):
        confirmacao.consumir(ACAO, proposta.codigo, agora=T0)


def test_codigo_vencido_nao_aprova():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    depois = T0 + confirmacao.VALIDADE + timedelta(seconds=1)
    with pytest.raises(confirmacao.Expirado):
        confirmacao.consumir(ACAO, proposta.codigo, agora=depois)


def test_codigo_no_ultimo_segundo_ainda_vale():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    confirmacao.consumir(ACAO, proposta.codigo, agora=T0 + confirmacao.VALIDADE)


def test_proposta_nova_invalida_o_codigo_velho():
    """O Gemini (induzido por um e-mail) propõe de novo no mesmo turno: o código que o dono leu
    na primeira lista não pode aprovar a segunda."""
    velha = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    nova = confirmacao.propor(ACAO, {"ids": ["a", "banco"]}, agora=T0)
    assert velha.codigo != nova.codigo
    with pytest.raises(confirmacao.CodigoInvalido):
        confirmacao.consumir(ACAO, velha.codigo, agora=T0)
    assert confirmacao.consumir(ACAO, nova.codigo, agora=T0).dados == {"ids": ["a", "banco"]}


def test_codigo_de_uma_acao_nao_aprova_outra():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    with pytest.raises(confirmacao.CodigoInvalido):
        confirmacao.consumir("calendario.apagar", proposta.codigo, agora=T0)


def test_codigo_inventado_nao_aprova():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    outro = f"{(int(proposta.codigo) + 1) % 10**confirmacao.DIGITOS:0{confirmacao.DIGITOS}d}"
    with pytest.raises(confirmacao.CodigoInvalido):
        confirmacao.consumir(ACAO, outro, agora=T0)


@pytest.mark.parametrize("digitado", ["", "12", "12345", "abcd", "1 2 3", "１２３４"])
def test_formato_errado_e_recusado(digitado):
    """Inclui dígitos de largura total, que `\\d` do Python aceitaria (erro pego por este teste)."""
    with pytest.raises(confirmacao.CodigoInvalido):
        confirmacao.normalizar(digitado)


def test_espacos_em_volta_sao_tolerados():
    assert confirmacao.normalizar(" 0042 ") == "0042"


def test_codigo_nao_se_repete_na_janela_do_desfazer(monkeypatch):
    """Com o sorteio preso num valor, a segunda proposta tem de pular o código já usado."""
    sorteios = iter([42, 42, 7])
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(sorteios))
    primeira = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    confirmacao.consumir(ACAO, primeira.codigo, agora=T0)
    segunda = confirmacao.propor(ACAO, {"ids": ["b"]}, agora=T0 + timedelta(days=1))
    assert (primeira.codigo, segunda.codigo) == ("0042", "0007")


def test_desfazer_acha_a_acao_feita_dentro_da_janela():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    registro = confirmacao.consumir(ACAO, proposta.codigo, agora=T0)
    confirmacao.registrar(registro.id, {"arquivados": ["a"]})
    janela = timedelta(days=7)
    achado = confirmacao.consumida(ACAO, proposta.codigo, janela=janela, agora=T0 + janela)
    assert achado.resultado == {"arquivados": ["a"]}
    with pytest.raises(confirmacao.Expirado):
        confirmacao.consumida(
            ACAO, proposta.codigo, janela=janela, agora=T0 + janela + timedelta(seconds=1)
        )


def test_desfazer_nao_aceita_proposta_que_nao_foi_aprovada():
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    with pytest.raises(confirmacao.CodigoInvalido):
        confirmacao.consumida(ACAO, proposta.codigo, janela=timedelta(days=7), agora=T0)


def test_banco_de_teste_isolado_do_real():
    """A trava do `conftest` está de pé: o banco não é o `viking.db` do dono."""
    from lifeos.config import REMINDERS_DB_PATH

    assert confirmacao.DB_PATH != REMINDERS_DB_PATH
