"""Registro de ações (Sessão 5, auditoria §7): o que foi feito fica escrito, e o que pode ter sido
feito também.

As perguntas: um efeito que aconteceu some do registro? Uma falha ambígua vira "falhou" (e o dono
repete)? Um dado sensível ou um caractere de controle entra cru? Desfazer duas vezes funciona?
"""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from lifeos import banco, registro

T0 = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
RLO = chr(0x202E)


@pytest.fixture(autouse=True)
def _origem_chat():
    token = registro.ORIGEM.set("chat")
    turno = registro.TURNO.set("sessao-a:1")
    yield
    registro.TURNO.reset(turno)
    registro.ORIGEM.reset(token)


class _Ambigua(Exception):
    incerta = True


def test_efeito_feito_fica_registrado_com_origem_e_turno():
    with registro.acao("calendario.criar", {"titulo": "Dentista"}) as marca:
        marca.feito({"event_id": "e1"})
    (a,) = registro.do_turno("sessao-a:1")
    assert (a.operacao, a.estado, a.origem, a.resultado) == (
        "calendario.criar",
        "feita",
        "chat",
        {"event_id": "e1"},
    )
    assert not a.pode_ter_acontecido


def test_falha_certa_e_falhou_e_a_excecao_sobe():
    with pytest.raises(ValueError), registro.acao("calendario.criar", {"titulo": "x"}):
        raise ValueError("400 recusado")
    (a,) = registro.do_turno("sessao-a:1")
    assert a.estado == "falhou" and "400 recusado" in a.erro


def test_falha_ambigua_e_incerta():
    with pytest.raises(_Ambigua), registro.acao("calendario.apagar", {"event_id": "e1"}):
        raise _Ambigua("timed out")
    (a,) = registro.do_turno("sessao-a:1")
    assert a.estado == "incerta" and a.pode_ter_acontecido


def test_processo_que_morre_no_meio_deixa_iniciada():
    contexto = registro.acao("navegador.executar", {"objetivo": "x"})
    contexto.__enter__()  # e nunca sai: o processo "morreu"
    (a,) = registro.do_turno("sessao-a:1")
    assert a.estado == "iniciada" and a.pode_ter_acontecido


def test_dado_sensivel_e_controle_saem_redigidos():
    titulo = f"Consulta CPF 529.982.247-25 {RLO}chave sk-abc123def456ghi789jkl012mno345"
    with registro.acao("calendario.criar", {"titulo": titulo, "lista": [titulo]}) as marca:
        marca.feito({"titulo": titulo})
    (a,) = registro.do_turno("sessao-a:1")
    guardado = str(a.parametros) + str(a.resultado)
    assert "529.982.247-25" not in guardado and "sk-abc123" not in guardado
    assert RLO not in guardado and "[CPF]" in guardado


def test_desfazer_guarda_a_copia_bruta():
    evento = {"summary": "CPF 529.982.247-25", "start": {"date": "2026-10-01"}}
    with registro.acao("calendario.apagar", {"event_id": "e1"}) as marca:
        marca.feito({"titulo": "x"}, desfazer={"evento": evento})
    (a,) = registro.do_turno("sessao-a:1")
    assert a.desfazivel
    assert registro.reivindicar_desfazer(a.id) == {"evento": evento}  # bruto, para recriar


def test_desfazer_duas_vezes_so_a_primeira_leva():
    with registro.acao("calendario.apagar", {"event_id": "e1"}) as marca:
        marca.feito(desfazer={"evento": {}})
    (a,) = registro.do_turno("sessao-a:1")
    assert registro.reivindicar_desfazer(a.id) == {"evento": {}}
    assert registro.reivindicar_desfazer(a.id) is None
    registro.devolver_desfazer(a.id)  # o desfazer falhou: volta a poder
    assert registro.reivindicar_desfazer(a.id) == {"evento": {}}


def test_falhou_nao_se_desfaz():
    with pytest.raises(ValueError), registro.acao("calendario.apagar", {}) as marca:
        marca.feito(desfazer={"evento": {}})
        raise ValueError("não aplicou")
    (a,) = registro.do_turno("sessao-a:1")
    assert registro.reivindicar_desfazer(a.id) is None


def test_ultima_desfazivel_so_desta_sessao_e_dentro_da_janela():
    with registro.acao("calendario.apagar", {}, agora=T0) as marca:
        marca.feito(desfazer={"n": 1})
    with registro.acao("calendario.apagar", {}, agora=T0 + timedelta(minutes=1)) as marca:
        marca.feito(desfazer={"n": 2})
    registro.TURNO.set("sessao-b:1")
    with registro.acao("calendario.apagar", {}, agora=T0 + timedelta(minutes=2)) as marca:
        marca.feito(desfazer={"n": 3})
    achada = registro.ultima_desfazivel(
        ("calendario.apagar",),
        prefixo_turno="sessao-a:",
        janela=timedelta(days=7),
        agora=T0 + timedelta(minutes=3),
    )
    assert registro.reivindicar_desfazer(achada.id) == {"n": 2}
    velha = registro.ultima_desfazivel(
        ("calendario.apagar",),
        prefixo_turno="sessao-a:",
        janela=timedelta(days=7),
        agora=T0 + timedelta(days=8),
    )
    assert velha is None


def test_prefixo_com_curinga_nao_pega_outra_sessao():
    with registro.acao("calendario.apagar", {}) as marca:
        marca.feito(desfazer={})
    assert (
        registro.ultima_desfazivel(
            ("calendario.apagar",), prefixo_turno="%", janela=timedelta(days=7)
        )
        is None
    )


def test_purga_depois_de_30_dias():
    with registro.acao("calendario.criar", {}, agora=T0) as marca:
        marca.feito()
    assert len(registro.recentes(dias=40, agora=T0 + timedelta(days=29))) == 1
    assert registro.recentes(dias=40, agora=T0 + timedelta(days=31)) == []


def test_recentes_mais_novas_primeiro():
    for n in range(3):
        with registro.acao(f"op{n}", {}, agora=T0 + timedelta(minutes=n)) as marca:
            marca.feito()
    assert [a.operacao for a in registro.recentes(agora=T0 + timedelta(hours=1))] == [
        "op2",
        "op1",
        "op0",
    ]


def test_texto_com_sql_e_gravado_literal():
    with registro.acao("calendario.criar", {"titulo": "x'); DROP TABLE acoes; --"}) as marca:
        marca.feito()
    (a,) = registro.do_turno("sessao-a:1")
    assert a.parametros["titulo"] == "x'); DROP TABLE acoes; --"


def test_as_duas_tabelas_no_mesmo_arquivo():
    from lifeos import confirmacao

    confirmacao.propor("gmail.arquivar", {"ids": []})
    with registro.acao("calendario.criar", {}) as marca:
        marca.feito()
    with sqlite3.connect(banco.CAMINHO) as conn:
        tabelas = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"acoes", "confirmacoes"} <= tabelas
