"""O que só as confirmações no Firestore têm (Sessão 10c, D60); o comportamento comum está no
contrato (`tests/test_confirmacao.py`, que roda nos dois stores). Contra o emulador.

- todo documento nasce inteiro, com a data em que a TTL pode apagá-lo;
- a TTL é maior que as janelas que ainda leem a proposta (unicidade e desfazer);
- um documento parcial (escrito por fora) erra alto na leitura;
- o código gasto fica reservado pela janela de uso no documento `codigos/NNNN`.
"""

from datetime import UTC, datetime, timedelta

import pytest

from lifeos import aprovacoes, confirmacao, confirmacao_firestore, firestore_comum

T0 = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)
ACAO = "gmail.arquivar"


@pytest.fixture
def cf(firestore_limpo, monkeypatch):
    monkeypatch.setattr(confirmacao, "_STORE", confirmacao_firestore)
    return confirmacao_firestore


def _cru(colecao: str, doc_id) -> dict:
    return firestore_comum.cliente().collection(colecao).document(str(doc_id)).get().to_dict()


def test_a_ttl_passa_das_janelas_que_ainda_leem_a_proposta():
    janelas = [confirmacao.JANELA_UNICA, *(t.janela for t in aprovacoes.TIPOS)]
    assert confirmacao_firestore.VIDA > max(janelas)


def test_todo_documento_nasce_inteiro_com_a_validade(cf):
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    cru = _cru(cf.COLECAO, proposta.id)
    assert set(cru) == set(cf._CAMPOS)
    assert cru["erros"] == 0 and cru["consumida_em"] is None and cru["resultado"] is None
    assert firestore_comum.lido(cru["apagar_em"]) == T0 + cf.VIDA


def test_documento_parcial_erra_alto(cf):
    from google.cloud.firestore import DELETE_FIELD

    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    firestore_comum.cliente().collection(cf.COLECAO).document(str(proposta.id)).update(
        {"erros": DELETE_FIELD}
    )
    with pytest.raises(ValueError, match="sem os campos"):
        confirmacao.consumir(ACAO, proposta.codigo, agora=T0)


def test_codigo_gasto_fica_reservado_pela_janela_de_uso(cf):
    proposta = confirmacao.propor(ACAO, {"ids": ["a"]}, agora=T0)
    reserva = _cru(cf.CODIGOS, proposta.codigo)
    assert firestore_comum.lido(reserva["reservado_ate"]) == T0 + confirmacao.VALIDADE
    gasto = T0 + timedelta(minutes=1)
    confirmacao.consumir(ACAO, proposta.codigo, agora=gasto)
    reserva = _cru(cf.CODIGOS, proposta.codigo)
    assert firestore_comum.lido(reserva["reservado_ate"]) == gasto + confirmacao.JANELA_UNICA
