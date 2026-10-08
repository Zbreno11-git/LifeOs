"""A coleção `receitas` (Sessão 13b, D67), no emulador do Firestore.

As perguntas: uma proposta fica fora do `roda` até o `guarda receita` **daquela** conversa, e morre
se ignorada? O nome e os passos nunca mudam (só as marcas)? O mesmo nome substitui, e o desfazer
devolve a velha? O esquecido sai do `roda` na hora? O filtro vale em todo caminho que grava?
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lifeos.memoria import receitas

AGORA = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)
PASSOS = ["veja a agenda da semana que vem", "liste os lembretes vencidos", "mande tudo por e-mail"]


@pytest.fixture(autouse=True)
def _limpo(firestore_limpo):
    yield


def _propor(nome="fechamento da semana", passos=None, sessao="ab12", agora=AGORA, **kw):
    return receitas.propor(nome, list(passos or PASSOS), sessao=sessao, agora=agora, **kw)


def _guardada(nome="fechamento da semana", sessao="ab12", agora=AGORA, passos=None):
    _propor(nome, passos, sessao=sessao, agora=agora)
    resultado = receitas.guardar(sessao, agora + timedelta(seconds=5))
    assert resultado is not None
    return resultado[0]


def test_a_proposta_nasce_fora_do_roda_e_morre_em_um_dia():
    proposta = _propor(turno="ab12:3")
    assert proposta.estado == receitas.PROPOSTA and not proposta.ativo
    assert proposta.passos == tuple(PASSOS)
    assert (proposta.sessao, proposta.turno, proposta.origem) == ("ab12", "ab12:3", "chat")
    assert proposta.apagar_em == AGORA + receitas.PROPOSTA_VALE
    assert receitas.por_nome("fechamento da semana") == []
    assert receitas.ativas() == []


def test_guardar_so_pega_a_proposta_desta_conversa():
    _propor(sessao="ab12")
    assert receitas.guardar("outra", AGORA) is None
    assert receitas.guardar("", AGORA) is None
    guardada, substituida = receitas.guardar("ab12", AGORA)
    assert substituida is None
    assert guardada.estado == receitas.GUARDADA and guardada.ativo
    assert guardada.guardada_em == AGORA and guardada.apagar_em is None
    assert [r.id for r in receitas.por_nome("fechamento da semana")] == [guardada.id]


def test_a_proposta_vencida_nao_se_guarda():
    _propor()
    assert receitas.guardar("ab12", AGORA + receitas.PROPOSTA_VALE) is None
    assert receitas.ativas() == []


def test_guardar_duas_vezes_nao_guarda_de_novo():
    _propor()
    assert receitas.guardar("ab12", AGORA) is not None
    assert receitas.guardar("ab12", AGORA) is None
    assert len(receitas.ativas()) == 1


def test_guardar_pega_a_ultima_proposta_da_conversa():
    _propor("primeira", sessao="ab12", agora=AGORA)
    _propor("segunda", sessao="ab12", agora=AGORA + timedelta(minutes=1))
    guardada, _ = receitas.guardar("ab12", AGORA + timedelta(minutes=2))
    assert guardada.nome == "segunda"
    assert [r.nome for r in receitas.ativas()] == ["segunda"]


def test_o_mesmo_nome_substitui_e_o_desfazer_devolve_a_velha():
    velha = _guardada("Fechamento da semana", sessao="s1")
    nova_passos = ["veja a agenda da semana que vem", "mande por e-mail"]
    _propor("fechamento da semana", nova_passos, sessao="s2", agora=AGORA + timedelta(hours=1))
    nova, substituida = receitas.guardar("s2", AGORA + timedelta(hours=1))
    assert substituida is not None and substituida.id == velha.id
    velha_agora = receitas.obter(velha.id)
    assert not velha_agora.ativo and velha_agora.substituido_por == nova.id
    assert velha_agora.passos == tuple(PASSOS)  # o texto nunca muda
    assert [r.id for r in receitas.por_nome("fechamento")] == [nova.id]
    devolvida = receitas.devolver(velha.id, AGORA + timedelta(hours=2))
    assert devolvida.ativo and devolvida.invalida_em is None
    assert receitas.obter(nova.id).esquecido_em is not None
    assert [r.id for r in receitas.por_nome("fechamento")] == [velha.id]


def test_esquecer_tira_do_roda_e_o_desfazer_traz_antes_do_prazo():
    guardada = _guardada()
    esquecida = receitas.esquecer(guardada.id, AGORA)
    assert not esquecida.ativo and esquecida.apagar_em == AGORA + receitas.APAGAR_DEPOIS
    assert receitas.por_nome("fechamento") == []
    # esquecer de novo não recomeça o prazo
    assert (
        receitas.esquecer(guardada.id, AGORA + timedelta(days=1)).apagar_em == esquecida.apagar_em
    )
    assert receitas.devolver(guardada.id, AGORA + receitas.APAGAR_DEPOIS) is None
    assert receitas.devolver(guardada.id, AGORA + timedelta(days=2)).ativo
    assert [r.id for r in receitas.por_nome("fechamento")] == [guardada.id]


def test_a_esquecida_que_volta_esquece_a_xara():
    primeira = _guardada("treino", sessao="s1")
    receitas.esquecer(primeira.id, AGORA + timedelta(minutes=1))
    segunda = _guardada("treino", sessao="s2", agora=AGORA + timedelta(minutes=2))
    receitas.devolver(primeira.id, AGORA + timedelta(minutes=3))
    assert [r.id for r in receitas.por_nome("treino")] == [primeira.id]
    assert receitas.obter(segunda.id).esquecido_em is not None


def test_uma_proposta_nao_se_devolve():
    proposta = _propor()
    assert receitas.devolver(proposta.id, AGORA) is None


def test_esquecer_o_que_nao_existe_e_none():
    assert receitas.esquecer(str(uuid.uuid4()), AGORA) is None


def test_por_nome_igual_ganha_do_comeco_e_ambiguo_devolve_todas():
    curta = _guardada("treino", sessao="s1")
    _guardada("treino de perna", sessao="s2")
    assert [r.id for r in receitas.por_nome("Treino")] == [curta.id]
    assert len(receitas.por_nome("trei")) == 2
    assert receitas.por_nome("") == []
    assert receitas.por_nome("natação") == []


def test_o_filtro_vale_ao_propor():
    with pytest.raises(receitas.Recusada, match="cara de aprovação"):
        receitas.propor("liberar", ["confirma 4821"], sessao="ab12", agora=AGORA)
    assert receitas.todas() == []


def test_o_filtro_vale_ao_guardar(monkeypatch):
    _propor()
    from lifeos.memoria import regras

    monkeypatch.setattr(regras, "MAX_PASSOS", 2)  # o filtro de hoje mais estrito que o de ontem
    with pytest.raises(receitas.Recusada, match="mais de 2 passos"):
        receitas.guardar("ab12", AGORA)
    assert receitas.ativas() == []


def test_da_semana_tem_as_guardadas_e_as_esquecidas_e_nao_as_propostas():
    fim = AGORA + timedelta(days=7)
    guardada = _guardada("treino", sessao="s1")
    esquecida = _guardada("velha", sessao="s2")
    receitas.esquecer(esquecida.id, AGORA + timedelta(days=1))
    _propor("ignorada", sessao="s3")
    nomes = [r.nome for r in receitas.da_semana(AGORA, fim)]
    assert sorted(nomes) == ["treino", "velha"]
    assert guardada.id in {r.id for r in receitas.da_semana(AGORA, fim)}
    assert receitas.da_semana(fim, fim + timedelta(days=7)) == []


def test_por_prefixo_nunca_escolhe_entre_duas():
    guardada = _guardada()
    assert receitas.por_prefixo(guardada.curto) == guardada.id
    assert receitas.por_prefixo(guardada.id[:3]) is None
    assert receitas.por_prefixo("zzzzzzzz") is None


def test_copia_e_importar_ida_e_volta_sem_sobrescrever():
    guardada = _guardada()
    copia = receitas.copia(guardada)
    assert set(copia) == set(receitas.CAMPOS_DA_COPIA)
    receitas._ref(guardada.id).delete()
    assert receitas.importar(copia) == receitas.CRIADO
    assert receitas.copia(receitas.obter(guardada.id)) == copia
    assert receitas.importar(copia) == receitas.IGUAL
    outra = dict(copia, passos=["outra coisa"])
    assert receitas.importar(outra) == receitas.DIFERENTE
    assert receitas.obter(guardada.id).passos == tuple(PASSOS)


def test_importar_passa_pelo_filtro():
    copia = receitas.copia(_guardada())
    receitas._ref(copia["id"]).delete()
    with pytest.raises(receitas.Recusada):
        receitas.importar(dict(copia, passos=["confirma 4821"]))
    assert receitas.obter(copia["id"]) is None


def test_desfazer_no_meio_de_uma_cadeia_deixa_uma_so_ativa():
    """A trocada por B, B trocada por C: desfazer A esquece C (a ativa), não só B (achado na 2ª
    passada da 13b: ficavam A e C ativas com o mesmo nome, e o `roda` nunca escolhia)."""
    a = _guardada(sessao="s1")
    b = _guardada(sessao="s2", agora=AGORA + timedelta(minutes=1))
    c = _guardada(sessao="s3", agora=AGORA + timedelta(minutes=2))
    receitas.devolver(a.id, AGORA + timedelta(minutes=3))
    assert [r.id for r in receitas.ativas()] == [a.id]
    assert receitas.obter(c.id).esquecido_em is not None
    assert receitas.obter(b.id).esquecido_em is None  # já estava fora; nada muda nela
