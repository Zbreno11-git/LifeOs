"""A coleção `memoria` (Sessão 13, D66), no emulador do Firestore.

As perguntas: só se acrescenta (o texto nunca muda; substituir e esquecer mudam marcas)? O filtro
vale em todo caminho que grava? O esquecido sai da busca na hora e volta pelo desfazer só antes do
prazo? A busca por significado acha o fato certo no conjunto de ouro (vetores do
`gemini-embedding-2` medidos em 2026-10-08, `tests/dados/memoria_ouro.json`), e o `find_nearest` dá
o mesmo top-k que a conta à mão (o índice reconstruído não muda a resposta)?
"""

import json
import math
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lifeos.memoria import regras, store, vetores

OURO = json.loads((Path(__file__).parent / "dados" / "memoria_ouro.json").read_text())
AGORA = datetime(2026, 10, 8, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _limpo(firestore_limpo):
    yield


def _vetor(n: int = 0) -> list[float]:
    """Um vetor unitário qualquer de 768 dimensões (o n-ésimo eixo)."""
    v = [0.0] * vetores.DIMENSAO
    v[n] = 1.0
    return v


def _gravar(texto="O usuário treina às 7h.", **kw):
    kw.setdefault("origem", "chat")
    kw.setdefault("vetor", _vetor())
    kw.setdefault("agora", AGORA)
    return store.gravar(texto, **kw)


def test_o_ouro_tem_a_forma_medida():
    assert OURO["modelo"] == vetores.MODELO and OURO["dimensao"] == vetores.DIMENSAO
    assert len(OURO["fatos"]) == len(OURO["perguntas"]) == 24
    assert all(len(f["vetor"]) == vetores.DIMENSAO for f in OURO["fatos"] + OURO["perguntas"])
    assert OURO["prefixo_fato"] == vetores.PREFIXO_FATO
    assert OURO["prefixo_pergunta"] == vetores.PREFIXO_PERGUNTA


def test_gravar_guarda_o_texto_limpo_e_as_marcas():
    fato = _gravar("O usuário  treina\x1b às 7h.", sessao="ab12", turno="ab12:3")
    assert fato.texto == "O usuário treina às 7h."
    assert fato.ativo and fato.invalida_em is None and fato.esquecido_em is None
    assert (fato.origem, fato.sessao, fato.turno) == ("chat", "ab12", "ab12:3")
    assert (fato.vetor_modelo, fato.vetor_dim) == (vetores.MODELO, vetores.DIMENSAO)
    assert fato.criado_em == AGORA
    assert store.id_valido(fato.id)


def test_o_filtro_vale_no_store_e_nada_e_gravado():
    with pytest.raises(store.Recusado) as erro:
        _gravar("O usuário ganha R$ 8.000 por mês.")
    assert str(erro.value) == "valor em dinheiro"
    assert store.todos() == []


def test_origem_desconhecida_e_vetor_de_outra_dimensao_sao_recusados():
    with pytest.raises(ValueError, match="origem"):
        _gravar(origem="email")
    with pytest.raises(ValueError, match="dimensões"):
        _gravar(vetor=[1.0, 0.0])
    assert store.todos() == []


def test_substituir_marca_o_antigo_e_nao_muda_o_texto_dele():
    antigo = _gravar("O usuário treina às 7h.")
    novo = _gravar("O usuário treina às 6h.", substitui=antigo.id, agora=AGORA + timedelta(days=1))
    relido = store.obter(antigo.id)
    assert relido is not None
    assert relido.texto == "O usuário treina às 7h."
    assert not relido.ativo
    assert relido.invalida_em == AGORA + timedelta(days=1)
    assert relido.substituido_por == novo.id
    assert [f.id for f in store.ativos()] == [novo.id]


def test_substituir_um_esquecido_nao_mexe_nele():
    antigo = _gravar()
    store.esquecer(antigo.id, AGORA)
    _gravar("O usuário treina às 6h.", substitui=antigo.id)
    relido = store.obter(antigo.id)
    assert relido is not None
    assert relido.substituido_por is None and relido.invalida_em is None


def test_esquecer_tira_da_busca_e_marca_30_dias():
    fato = _gravar()
    esquecido = store.esquecer(fato.id, AGORA)
    assert esquecido is not None
    assert not esquecido.ativo
    assert esquecido.apagar_em == AGORA + store.APAGAR_DEPOIS
    assert esquecido.texto == fato.texto  # ainda guardado até a TTL
    assert store.parecidos(_vetor()) == []
    de_novo = store.esquecer(fato.id, AGORA + timedelta(days=5))
    assert de_novo is not None and de_novo.apagar_em == AGORA + store.APAGAR_DEPOIS


def test_esquecer_um_id_que_nao_existe():
    assert store.esquecer(str(uuid.uuid4()), AGORA) is None


def test_desfazer_o_esquecido_antes_do_prazo():
    fato = _gravar()
    store.esquecer(fato.id, AGORA)
    voltou = store.desfazer(fato.id, AGORA + timedelta(days=29))
    assert voltou is not None and voltou.ativo
    assert voltou.esquecido_em is None and voltou.apagar_em is None
    assert [f.id for f in store.parecidos(_vetor())] == [fato.id]


def test_desfazer_depois_do_prazo_nao_devolve():
    fato = _gravar()
    store.esquecer(fato.id, AGORA)
    assert store.desfazer(fato.id, AGORA + store.APAGAR_DEPOIS) is None
    relido = store.obter(fato.id)
    assert relido is not None and not relido.ativo


def test_desfazer_um_esquecido_que_tinha_sido_substituido_nao_o_reativa():
    antigo = _gravar()
    _gravar("O usuário treina às 6h.", substitui=antigo.id)
    store.esquecer(antigo.id, AGORA)
    voltou = store.desfazer(antigo.id, AGORA)
    assert voltou is not None and not voltou.ativo and voltou.esquecido_em is None


def test_desfazer_a_substituicao_devolve_o_antigo_e_esquece_o_novo():
    antigo = _gravar("O usuário treina às 7h.")
    novo = _gravar("O usuário treina às 6h.", substitui=antigo.id, vetor=_vetor(1))
    voltou = store.desfazer(antigo.id, AGORA)
    assert voltou is not None and voltou.ativo and voltou.substituido_por is None
    relido = store.obter(novo.id)
    assert relido is not None and not relido.ativo and relido.esquecido_em is not None
    assert [f.id for f in store.ativos()] == [antigo.id]


def test_desfazer_um_ativo_nao_faz_nada():
    fato = _gravar()
    assert store.desfazer(fato.id, AGORA) is None


def test_id_que_nao_e_uuid_nunca_vira_caminho():
    for ruim in ("../gastos/2026-10", "abc", "", "A" * 36):
        with pytest.raises(ValueError, match="UUID"):
            store.obter(ruim)
    with pytest.raises(ValueError, match="UUID"):
        _gravar(substitui="../gastos/2026-10")


# --- a busca por significado ------------------------------------------------------------------


def _cosseno(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True)) / (
        math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    )


@pytest.fixture
def ouro():
    ids = []
    for n, f in enumerate(OURO["fatos"]):
        fato = _gravar(f["texto"], vetor=f["vetor"], agora=AGORA + timedelta(seconds=n))
        ids.append(fato.id)
    return ids


def test_o_ouro_acha_o_fato_certo_recall_e_mrr(ouro):
    """O piso é o medido em 2026-10-08 (recall@8 = MRR = 1,000): o conjunto é fácil, e a régua
    pega o que quebra a busca (o prefixo trocado, a dimensão, o filtro), não a qualidade fina."""
    acertos_em_8, rr = 0, 0.0
    for pergunta in OURO["perguntas"]:
        achados = [f.id for f in store.parecidos(pergunta["vetor"], k=regras.POR_TURNO)]
        certo = ouro[pergunta["fato"]]
        if certo in achados:
            acertos_em_8 += 1
            rr += 1 / (achados.index(certo) + 1)
    n = len(OURO["perguntas"])
    assert acertos_em_8 / n == 1.0
    assert rr / n == 1.0


def test_o_find_nearest_da_o_mesmo_top_k_que_a_conta_a_mao(ouro):
    """O índice é descartável (D48): a busca do Firestore e o cosseno à mão concordam."""
    for pergunta in OURO["perguntas"][:6]:
        do_firestore = [f.id for f in store.parecidos(pergunta["vetor"], k=regras.POR_TURNO)]
        a_mao = sorted(
            range(len(OURO["fatos"])),
            key=lambda j: -_cosseno(pergunta["vetor"], OURO["fatos"][j]["vetor"]),
        )[: regras.POR_TURNO]
        assert do_firestore == [ouro[j] for j in a_mao]


def test_parecidos_respeita_k_e_so_traz_ativos(ouro):
    store.esquecer(ouro[0], AGORA)
    achados = store.parecidos(OURO["perguntas"][0]["vetor"], k=3)
    assert len(achados) == 3
    assert ouro[0] not in [f.id for f in achados]
    assert all(f.ativo for f in achados)
    distancias = [f.distancia for f in achados]
    assert distancias == sorted(distancias)


# --- os outros caminhos -----------------------------------------------------------------------


def test_ultima_da_sessao_e_so_a_desta_conversa():
    _gravar("O usuário corre aos sábados.", sessao="aaaa", agora=AGORA)
    ultima = _gravar("O usuário é vegetariano.", sessao="aaaa", agora=AGORA + timedelta(minutes=1))
    _gravar("O usuário toca violão.", sessao="bbbb", agora=AGORA + timedelta(minutes=2))
    achada = store.ultima_da_sessao("aaaa")
    assert achada is not None and achada.id == ultima.id
    store.esquecer(ultima.id, AGORA)
    achada = store.ultima_da_sessao("aaaa")
    assert achada is not None and achada.texto == "O usuário corre aos sábados."
    assert store.ultima_da_sessao("") is None
    assert store.ultima_da_sessao("cccc") is None


def test_por_prefixo_so_devolve_quando_e_unico(monkeypatch):
    ids = iter(
        [
            uuid.UUID("abcdef01-0000-4000-8000-000000000001"),
            uuid.UUID("abcdef01-0000-4000-8000-000000000002"),
            uuid.UUID("12345678-0000-4000-8000-000000000003"),
        ]
    )
    monkeypatch.setattr(store.uuid, "uuid4", lambda: next(ids))
    _gravar("O usuário corre aos sábados.")
    _gravar("O usuário é vegetariano.")
    _gravar("O usuário toca violão.")
    assert store.por_prefixo("12345678") == "12345678-0000-4000-8000-000000000003"
    assert store.por_prefixo("abcdef01") is None  # ambíguo: nunca escolhe
    assert store.por_prefixo("abcde") is None  # curto demais
    assert store.por_prefixo("9999999999") is None
    assert store.por_prefixo("../gastos") is None


def test_criados_entre():
    _gravar("O usuário corre aos sábados.", agora=AGORA - timedelta(days=8))
    dentro = _gravar("O usuário é vegetariano.", agora=AGORA - timedelta(days=2))
    assert [f.id for f in store.criados_entre(AGORA - timedelta(days=7), AGORA)] == [dentro.id]


def test_sem_vetor_e_trocar_vetor():
    com = _gravar()
    sem = _gravar("O usuário é vegetariano.", vetor=None)
    assert [f.id for f in store.sem_vetor()] == [sem.id]
    store.trocar_vetor(sem.id, _vetor(2))
    assert store.sem_vetor() == []
    assert {f.id for f in store.parecidos(_vetor(2), k=1)} == {sem.id}
    assert com.id != sem.id


def test_exportar_e_importar_ida_e_volta_sem_vetor():
    antigo = _gravar("O usuário treina às 7h.", sessao="s1", turno="s1:1")
    _gravar("O usuário treina às 6h.", substitui=antigo.id, agora=AGORA + timedelta(hours=1))
    esquecido = _gravar("O usuário toca violão.")
    store.esquecer(esquecido.id, AGORA)
    copias = store.exportar()
    assert len(copias) == 3
    assert all(set(c) == set(store.CAMPOS_DA_COPIA) for c in copias)
    assert all(isinstance(c["criado_em"], str) for c in copias)

    assert all(store.importar(c) == store.IGUAL for c in copias)  # nunca sobrescreve
    mudada = dict(copias[0], texto="O usuário corre aos sábados.")
    assert store.importar(mudada) == store.DIFERENTE

    for c in copias:  # um banco vazio: tudo volta, com as marcas, sem vetor
        store._ref(c["id"]).delete()
    assert [store.importar(c) for c in copias] == [store.CRIADO] * 3
    assert store.exportar() == copias
    assert len(store.sem_vetor()) == 3


def test_importar_passa_pelo_filtro():
    copia = store.copia(_gravar())
    store._ref(copia["id"]).delete()
    with pytest.raises(store.Recusado):
        store.importar(dict(copia, texto="O saldo do usuário é 1200."))
    assert store.todos() == []
