"""O que só o registro no Firestore tem (Sessão 10b, D59); o comportamento comum está no contrato
(`tests/test_registro.py`, que roda nos dois stores). Contra o emulador.

- a TTL (`expira_em`) é a retenção de `registro.py`: se as duas divergissem, a nuvem guardaria o
  registro por mais (ou menos) tempo do que o dono decidiu;
- um documento parcial (escrito por fora) erra alto na leitura;
- dois ids no mesmo nanossegundo não se sobrescrevem;
- o índice composto de `contaveis` está na lista que `scripts/nuvem.py` cria.
"""

from datetime import UTC, datetime, timedelta

import pytest

from lifeos import firestore_comum, registro, registro_firestore

T0 = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)


@pytest.fixture
def rf(firestore_limpo, monkeypatch):
    monkeypatch.setattr(registro, "_STORE", registro_firestore)
    origem, turno = registro.ORIGEM.set("nuvem"), registro.TURNO.set("s:1")
    yield registro_firestore
    registro.TURNO.reset(turno)
    registro.ORIGEM.reset(origem)


def _cru(acao_id):
    colecao = firestore_comum.cliente().collection(registro_firestore.COLECAO)
    return colecao.document(str(acao_id)).get().to_dict()


def test_a_ttl_e_a_retencao_do_dono():
    assert registro_firestore.VIDA == registro.RETENCAO


def test_todo_documento_nasce_inteiro_com_a_validade(rf):
    with registro.acao("calendario.criar", {"titulo": "x"}, agora=T0) as marca:
        marca.feito()
    cru = _cru(marca.id)
    assert set(cru) == set(registro_firestore._CAMPOS)
    assert cru["expira_em"] == T0 + registro.RETENCAO
    assert cru["id"] == marca.id


def test_documento_parcial_erra_alto_na_leitura(rf):
    from google.cloud import firestore

    with registro.acao("calendario.criar", {}) as marca:
        marca.feito()
    colecao = firestore_comum.cliente().collection(registro_firestore.COLECAO)
    colecao.document(str(marca.id)).update({"estado": firestore.DELETE_FIELD})
    with pytest.raises(ValueError, match="estado"):
        registro.obter(marca.id)


def test_dois_no_mesmo_nanossegundo_nao_se_sobrescrevem(rf, monkeypatch):
    monkeypatch.setattr(registro_firestore.time, "time_ns", lambda: 1_000)
    with registro.acao("op-a", {}) as a:
        a.feito()
    with registro.acao("op-b", {}) as b:
        b.feito()
    assert a.id == 1_000 and b.id == 1_001
    assert [x.operacao for x in registro.do_turno("s:1")] == ["op-a", "op-b"]


def test_o_indice_de_contaveis_esta_na_lista_da_infraestrutura():
    assert (
        registro_firestore.COLECAO,
        (("operacao", "ASCENDING"), ("criada_em", "ASCENDING")),
    ) in registro_firestore.INDICES


def test_prefixo_do_turno_e_texto_e_nao_alcanca_o_vizinho(rf):
    """`ab:` não pode pegar `ab:1` de outra sessão chamada `ab` + algo: o intervalo termina no
    menor texto maior que o prefixo."""
    for turno in ("ab:1", "ab;1", "abc:1"):
        registro.TURNO.set(turno)
        with registro.acao("calendario.apagar", {}) as marca:
            marca.feito(desfazer={"t": turno})
    achada = registro.ultima_desfazivel(
        ("calendario.apagar",), prefixo_turno="ab:", janela=timedelta(days=1)
    )
    assert achada is not None and achada.turno == "ab:1"
