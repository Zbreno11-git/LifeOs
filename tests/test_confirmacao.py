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
    from lifeos import banco
    from lifeos.config import REMINDERS_DB_PATH

    assert banco.CAMINHO != REMINDERS_DB_PATH


def test_vivo_so_enquanto_serve_para_algo():
    janela = timedelta(days=7)
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    assert confirmacao.vivo(ACAO, proposta.codigo, janela=janela, agora=T0)
    vencida = T0 + confirmacao.VALIDADE + timedelta(seconds=1)
    assert not confirmacao.vivo(ACAO, proposta.codigo, janela=janela, agora=vencida)
    confirmacao.consumir(ACAO, proposta.codigo, agora=T0)
    assert confirmacao.vivo(ACAO, proposta.codigo, janela=janela, agora=T0 + janela)
    depois = T0 + janela + timedelta(seconds=1)
    assert not confirmacao.vivo(ACAO, proposta.codigo, janela=janela, agora=depois)
    assert not confirmacao.vivo(ACAO, "abcd", janela=janela, agora=T0)


# --- Sessão 5: vários tipos de ação ----------------------------------------------------------

OUTRA = "calendario.apagar"


def _sorteio(monkeypatch, *numeros):
    """Sorteios presos e FINITOS: uma reserva quebrada levanta StopIteration em vez de travar."""
    fila = iter(numeros)
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(fila))


def test_codigo_nao_se_repete_entre_acoes(monkeypatch):
    _sorteio(monkeypatch, 1234, 1234, 5678)
    gmail = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    calendario = confirmacao.propor(OUTRA, {"event_id": "e"}, agora=T0)
    assert (gmail.codigo, calendario.codigo) == ("1234", "5678")


def test_codigo_substituido_nao_volta_enquanto_nao_vence(monkeypatch):
    _sorteio(monkeypatch, 1234, 1234, 5678)
    confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    nova = confirmacao.propor(ACAO, {"ids": ["a", "banco"]}, agora=T0)
    assert nova.codigo == "5678"


def test_codigo_vencido_e_nao_usado_deixa_de_reservar(monkeypatch):
    _sorteio(monkeypatch, 1234, 1234)
    confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    depois = T0 + confirmacao.VALIDADE + timedelta(seconds=1)
    assert confirmacao.propor(OUTRA, {"event_id": "e"}, agora=depois).codigo == "1234"


def test_codigo_usado_reserva_pela_janela_do_desfazer(monkeypatch):
    _sorteio(monkeypatch, 1234, 1234, 5678)
    usada = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    confirmacao.consumir(ACAO, usada.codigo, agora=T0)
    seis_dias = T0 + timedelta(days=6)
    assert confirmacao.propor(OUTRA, {"event_id": "e"}, agora=seis_dias).codigo == "5678"


def test_validade_da_proposta_pode_ser_maior():
    uma_hora = timedelta(hours=1)
    proposta = confirmacao.propor(OUTRA, {"event_id": "e"}, validade=uma_hora, agora=T0)
    assert confirmacao.aberta(OUTRA, agora=T0 + timedelta(minutes=59))
    assert not confirmacao.aberta(OUTRA, agora=T0 + timedelta(minutes=61))
    with pytest.raises(confirmacao.Expirado):
        confirmacao.consumir(OUTRA, proposta.codigo, agora=T0 + timedelta(minutes=61))


def test_sem_substituir_as_propostas_convivem():
    a = confirmacao.propor(OUTRA, {"event_id": "a"}, substituir=False, agora=T0)
    b = confirmacao.propor(OUTRA, {"event_id": "b"}, substituir=False, agora=T0)
    assert [p.dados for p in confirmacao.abertas(OUTRA, agora=T0)] == [
        {"event_id": "a"},
        {"event_id": "b"},
    ]
    assert confirmacao.consumir(OUTRA, a.codigo, agora=T0).dados == {"event_id": "a"}
    assert confirmacao.consumir(OUTRA, b.codigo, agora=T0).dados == {"event_id": "b"}


def test_criadas_desde_conta_so_a_acao():
    confirmacao.propor(OUTRA, {"event_id": "a"}, substituir=False, agora=T0)
    confirmacao.propor(OUTRA, {"event_id": "b"}, substituir=False, agora=T0 + timedelta(hours=2))
    confirmacao.propor(ACAO, {"ids": ["x"]}, agora=T0 + timedelta(hours=2))
    assert confirmacao.criadas_desde(OUTRA, T0 + timedelta(hours=1)) == 1


def test_acao_do_codigo():
    proposta = confirmacao.propor(OUTRA, {"event_id": "e"}, agora=T0)
    assert confirmacao.acao_do_codigo(f" {proposta.codigo} ") == OUTRA
    assert confirmacao.acao_do_codigo("99999") is None
    assert confirmacao.acao_do_codigo("abcd") is None
