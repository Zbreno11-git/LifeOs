"""Registro de ações (Sessão 5, auditoria §7): o que foi feito fica escrito, e o que pode ter sido
feito também.

As perguntas: um efeito que aconteceu some do registro? Uma falha ambígua vira "falhou" (e o dono
repete)? Um dado sensível ou um caractere de controle entra cru? Desfazer duas vezes funciona?

Desde a Sessão 10b é o **contrato** do store do registro (`registro_interface.Registro`): todo
teste roda no SQLite do Mac e no Firestore da nuvem (no emulador, limpo a cada teste). A regra
fica em `registro.py`; o que muda entre os dois é só onde se guarda.
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta

import pytest

from lifeos import banco, registro, registro_firestore, registro_interface, registro_sqlite

STORES = {"sqlite": registro_sqlite, "firestore": registro_firestore}
JUNTAS = 16

T0 = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
RLO = chr(0x202E)


@pytest.fixture(autouse=True, params=sorted(STORES))
def store_do_registro(request, monkeypatch):
    if request.param == "firestore":  # o emulador, limpo a cada teste (`conftest`)
        request.getfixturevalue("firestore_limpo")
    monkeypatch.setattr(registro, "_STORE", STORES[request.param])
    return request.param


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


@pytest.mark.parametrize("store_do_registro", ["sqlite"], indirect=True)
def test_as_duas_tabelas_no_mesmo_arquivo():
    from lifeos import confirmacao

    confirmacao.propor("gmail.arquivar", {"ids": []})
    with registro.acao("calendario.criar", {}) as marca:
        marca.feito()
    with sqlite3.connect(banco.CAMINHO) as conn:
        tabelas = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"acoes", "confirmacoes"} <= tabelas


def test_desfazer_disputado_so_um_leva():
    """Duas execuções (o chat e a CLI, ou duas instâncias do motor) pedem o mesmo desfazer: a cópia
    vai a uma só. Exceção numa thread não reprova o teste sozinha: são recolhidas."""
    with registro.acao("calendario.apagar", {"event_id": "e1"}) as marca:
        marca.feito(desfazer={"evento": {"id": "e1"}})
    (a,) = registro.do_turno("sessao-a:1")
    largada = threading.Barrier(JUNTAS)
    levaram: list[dict] = []
    erros: list[BaseException] = []

    def tentar():
        try:
            largada.wait()
            copia = registro.reivindicar_desfazer(a.id)
            if copia is not None:
                levaram.append(copia)
        except BaseException as exc:  # noqa: BLE001 - recolhida e conferida abaixo
            erros.append(exc)

    threads = [threading.Thread(target=tentar) for _ in range(JUNTAS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert erros == []
    assert levaram == [{"evento": {"id": "e1"}}]


def test_contaveis_so_da_operacao_e_sem_as_que_falharam():
    with registro.acao("gmail.enviar_para_si", {}, agora=T0) as marca:
        marca.feito()
    with pytest.raises(ValueError), registro.acao("gmail.enviar_para_si", {}, agora=T0):
        raise ValueError("400")
    with pytest.raises(_Ambigua), registro.acao("gmail.enviar_para_si", {}, agora=T0):
        raise _Ambigua("timed out")
    with registro.acao("calendario.criar", {}, agora=T0) as marca:
        marca.feito()
    contadas = registro.contaveis("gmail.enviar_para_si", desde=T0 - timedelta(hours=1))
    assert [a.estado for a in contadas] == ["feita", "incerta"]
    assert registro.contaveis("gmail.enviar_para_si", desde=T0 + timedelta(hours=1)) == []


def test_obter_acha_pelo_id_e_nao_acha_o_que_nao_existe():
    with registro.acao("calendario.criar", {"titulo": "x"}) as marca:
        marca.feito()
    assert registro.obter(marca.id).parametros == {"titulo": "x"}
    assert registro.obter(marca.id + 10**12) is None


def test_ids_crescem_na_ordem_em_que_as_acoes_nascem():
    ids = []
    for n in range(5):
        with registro.acao(f"op{n}", {}) as marca:
            marca.feito()
        ids.append(marca.id)
    assert ids == sorted(ids) and len(set(ids)) == 5
    assert [a.operacao for a in registro.do_turno("sessao-a:1")] == [f"op{n}" for n in range(5)]


def test_recentes_respeita_o_limite():
    for n in range(4):
        with registro.acao(f"op{n}", {}, agora=T0 + timedelta(minutes=n)) as marca:
            marca.feito()
    feitas = registro.recentes(limite=2, agora=T0 + timedelta(hours=1))
    assert [a.operacao for a in feitas] == ["op3", "op2"]


def test_o_que_passou_dos_30_dias_nao_volta_por_nenhum_caminho():
    """A TTL do Firestore apaga com atraso: a leitura por turno e por id também corta nos 30 dias,
    não só a listagem por data (que já filtra na consulta)."""
    velha = datetime.now(UTC) - registro.RETENCAO - timedelta(days=1)
    with registro.acao("calendario.apagar", {}, agora=velha) as marca:
        marca.feito(desfazer={"evento": {}})
    assert registro.do_turno("sessao-a:1") == []
    assert registro.obter(marca.id) is None


# --- a cópia do backup (Sessão 11c, D63) --------------------------------------------------------


def test_exportar_traz_a_linha_inteira_com_a_copia_para_desfazer():
    with registro.acao("calendario.apagar", {"event_id": "e1"}) as marca:
        marca.feito({"titulo": "x"}, desfazer={"evento": {"summary": "Dentista"}})
    (copia,) = registro.exportar()
    assert set(copia) == set(registro_interface.CAMPOS_DA_COPIA)
    assert copia["id"] == marca.id and copia["estado"] == "feita"
    assert json.loads(copia["desfazer"]) == {"evento": {"summary": "Dentista"}}
    assert copia["terminada_em"] is not None and copia["desfeita_em"] is None
    for campo in registro_interface.INSTANTES_DA_COPIA:
        valor = copia[campo]
        assert valor is None or valor.endswith("+00:00") and len(valor) == 32


def test_exportar_corta_pelos_30_dias():
    velha = datetime.now(UTC) - registro.RETENCAO - timedelta(days=1)
    with registro.acao("calendario.criar", {}, agora=velha) as marca:
        marca.feito()
    with registro.acao("calendario.criar", {}) as nova:
        nova.feito()
    assert [c["id"] for c in registro.exportar()] == [nova.id]


def test_importar_num_registro_vazio_devolve_a_mesma_linha():
    with registro.acao("gmail.arquivar", {"remetentes": ["a@b.c"]}) as marca:
        marca.feito({"n": 3}, desfazer={"ids": ["m1", "m2"]})
    (copia,) = registro.exportar()
    _esvaziar()
    assert registro.exportar() == []
    assert registro.importar(copia) == registro_interface.CRIADA
    assert registro.exportar() == [copia]
    assert registro.reivindicar_desfazer(copia["id"]) == {"ids": ["m1", "m2"]}


def test_importar_de_novo_e_igual_e_diferente_nao_sobrescreve():
    with registro.acao("calendario.criar", {"titulo": "x"}) as marca:
        marca.feito()
    (copia,) = registro.exportar()
    assert registro.importar(copia) == registro_interface.IGUAL
    assert registro.importar({**copia, "estado": "falhou"}) == registro_interface.DIFERENTE
    assert registro.exportar() == [copia]


def _esvaziar() -> None:
    """Apaga o registro do store em uso (o banco do teste), para restaurar num vazio."""
    if registro._STORE is registro_sqlite:
        with banco.conectar() as conn:
            conn.execute("DELETE FROM acoes")
        return
    for snap in registro_firestore._colecao().stream():
        snap.reference.delete()
