"""As coleções `documentos` e `trechos` (Sessão 14, D68), no emulador do Firestore.

As perguntas: um documento pela metade nunca aparece na consulta? O mesmo arquivo no mesmo tema
substitui (e noutro tema não)? Esquecer tira da busca na hora, e o desfazer devolve sem deixar duas
versões ativas, mesmo numa cadeia? O tema filtra de verdade? O texto nunca muda? O backup vai e
volta sem sobrescrever? E a avaliação fixa (o conjunto de ouro do C1, com os vetores medidos) passa
no limiar do dono pelo `find_nearest` de verdade?
"""

import json
import math
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lifeos import firestore_comum
from lifeos.documentos import cortes, store
from lifeos.memoria import vetores

AGORA = datetime(2026, 10, 9, 15, 0, tzinfo=UTC)
OURO = json.loads((Path(__file__).parent / "dados" / "documentos_ouro.json").read_text())
# O limiar do dono (2026-10-09, depois do C1): recall@5 = 1,0 e MRR >= 0,95.
RECALL_5, MRR = 1.0, 0.95

TREINO = """# Perna

Agachamento livre, quatro séries de oito.

## Joelho

Se doer, reduzir a amplitude.

# Costas

Barra fixa até a falha.
"""


@pytest.fixture(autouse=True)
def _limpo(firestore_limpo):
    yield


def _eixo(n: int) -> list[float]:
    v = [0.0] * vetores.DIMENSAO
    v[n % vetores.DIMENSAO] = 1.0
    return v


class _Embutir:
    """Um vetor por texto, determinístico (o eixo do hash do texto), e conta os pedidos."""

    def __init__(self):
        self.pedidos: list[list[str]] = []

    def __call__(self, textos):
        self.pedidos.append(list(textos))
        return [_eixo(sum(map(ord, t))) for t in textos]


def _aprender(nome="treino.md", tema="treino", texto=TREINO, agora=AGORA, **kw):
    kw.setdefault("embutir", _Embutir())
    return store.aprender(nome, tema, texto, agora=agora, **kw)


def _todos_os_trechos():
    return [store._trecho(s) for s in store._trechos().stream()]


def test_aprender_guarda_o_documento_e_os_trechos_na_busca():
    embutir = _Embutir()
    documento, substituido = _aprender(embutir=embutir)
    assert substituido is None
    assert documento.estado == store.APRENDIDO and documento.ativo
    assert documento.apagar_em is None and documento.aprendido_em == AGORA
    assert (documento.nome, documento.tema, documento.n_trechos) == ("treino.md", "treino", 3)
    assert documento.bytes == len(TREINO.encode()) and len(documento.impressao) == 64
    trechos = store.trechos_de(documento.id)
    assert [t.texto for t in trechos] == [t.texto for t in cortes.cortar(TREINO)]
    assert all(t.ativo and t.apagar_em is None and t.tema_lido == "treino" for t in trechos)
    assert all(t.vetor_modelo == vetores.MODELO for t in trechos)
    # o que se embute leva o arquivo e o caminho dos títulos
    assert (
        embutir.pedidos[0][1]
        == "title: treino.md — Perna › Joelho | text: Se doer, reduzir a amplitude."
    )
    assert store.temas() == {"treino": ("treino", ["treino.md"])}


def test_os_lotes_de_embedding_tem_o_tamanho_certo():
    texto = "\n\n".join(f"# S{n}\n\nparágrafo {n}" for n in range(45))
    embutir = _Embutir()
    documento, _ = _aprender(texto=texto, embutir=embutir)
    assert [len(p) for p in embutir.pedidos] == [20, 20, 5]
    assert documento.n_trechos == len(store.trechos_de(documento.id)) == 45


def test_o_aprender_que_cai_no_meio_deixa_nada_na_busca():
    chamadas = []

    def embutir(textos):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise TimeoutError("o prazo do turno")
        return [_eixo(1) for _ in textos]

    texto = "\n\n".join(f"# S{n}\n\nparágrafo {n}" for n in range(30))
    with pytest.raises(TimeoutError):
        _aprender(texto=texto, embutir=embutir)
    (documento,) = store.todos()
    assert documento.estado == store.APRENDENDO and not documento.ativo
    assert documento.apagar_em == AGORA + store.APRENDER_VALE  # a TTL limpa
    trechos = _todos_os_trechos()
    assert len(trechos) == 20 and not any(t.ativo for t in trechos)
    assert all(t.apagar_em == AGORA + store.APRENDER_VALE for t in trechos)
    assert store.consultar("treino", _eixo(1)) == []
    assert store.temas() == {}


def test_a_consulta_confere_o_documento_de_cada_trecho():
    """Um trecho ativo de um documento que não está (uma 2ª fase que caiu no meio) não volta."""
    documento, _ = _aprender()
    store._ref(documento.id).update({"ativo": False})
    assert all(t.ativo for t in store.trechos_de(documento.id))
    assert store.consultar("treino", _eixo(0)) == []


def test_a_consulta_filtra_o_tema_e_devolve_os_mais_perto_primeiro():
    embutir = _Embutir()
    documento, _ = _aprender(embutir=embutir)
    _aprender("python.txt", "python", "Use with para abrir arquivos.", embutir=_Embutir())
    alvo = embutir.pedidos[0][2]  # o texto embutido do trecho de costas
    achados = store.consultar("Treino", _eixo(sum(map(ord, alvo))))
    assert achados[0].texto == "Barra fixa até a falha." and achados[0].distancia == pytest.approx(
        0
    )
    assert {t.documento for t in achados} == {documento.id}  # nada do python
    assert len(achados) == 3
    assert store.consultar("natação", _eixo(0)) == []
    assert store.consultar("", _eixo(0)) == []


def test_a_consulta_traz_no_maximo_5():
    texto = "\n\n".join(f"# S{n}\n\nparágrafo {n}" for n in range(8))
    _aprender(texto=texto, embutir=lambda textos: [_eixo(3) for _ in textos])
    assert len(store.consultar("treino", _eixo(3))) == store.POR_CONSULTA == 5


def test_o_mesmo_arquivo_no_mesmo_tema_substitui_e_noutro_tema_nao():
    velho, _ = _aprender()
    outro_tema, substituido = _aprender(tema="corrida", agora=AGORA + timedelta(minutes=1))
    assert substituido is None
    novo, substituido = _aprender(texto="# Perna\n\nNovo texto.", agora=AGORA + timedelta(hours=1))
    assert substituido is not None and substituido.id == velho.id
    velho_agora = store.obter(velho.id)
    assert not velho_agora.ativo and velho_agora.substituido_por == novo.id
    assert velho_agora.invalida_em == AGORA + timedelta(hours=1)
    assert not any(t.ativo for t in store.trechos_de(velho.id))
    assert store.trechos_de(velho.id)[0].texto.startswith("Agachamento")  # nunca muda
    assert {d.id for d in store.ativos()} == {novo.id, outro_tema.id}


def test_esquecer_tira_da_busca_na_hora_e_o_desfazer_traz_antes_do_prazo():
    documento, _ = _aprender()
    esquecido = store.esquecer(documento.id, AGORA)
    assert not esquecido.ativo and esquecido.apagar_em == AGORA + store.APAGAR_DEPOIS
    assert all(
        not t.ativo and t.apagar_em == esquecido.apagar_em for t in store.trechos_de(documento.id)
    )
    assert store.consultar("treino", _eixo(0)) == [] and store.temas() == {}
    # esquecer de novo não recomeça o prazo
    assert store.esquecer(documento.id, AGORA + timedelta(days=1)).apagar_em == esquecido.apagar_em
    assert store.devolver(documento.id, AGORA + store.APAGAR_DEPOIS) is None
    devolvido = store.devolver(documento.id, AGORA + timedelta(days=2))
    assert devolvido.ativo and devolvido.apagar_em is None
    assert all(t.ativo and t.apagar_em is None for t in store.trechos_de(documento.id))


def test_desfazer_a_troca_devolve_o_velho_e_esquece_o_novo():
    velho, _ = _aprender()
    novo, _ = _aprender(texto="# Perna\n\nNovo.", agora=AGORA + timedelta(hours=1))
    store.devolver(velho.id, AGORA + timedelta(hours=2))
    assert [d.id for d in store.ativos()] == [velho.id]
    assert store.obter(novo.id).esquecido_em is not None
    assert all(t.ativo for t in store.trechos_de(velho.id))
    assert not any(t.ativo for t in store.trechos_de(novo.id))


def test_desfazer_no_meio_de_uma_cadeia_deixa_um_so_ativo():
    """A trocado por B, B por C: desfazer A esquece C (a lição da 13b, erros classe 7)."""
    a, _ = _aprender()
    b, _ = _aprender(texto="# P\n\nb", agora=AGORA + timedelta(minutes=1))
    c, _ = _aprender(texto="# P\n\nc", agora=AGORA + timedelta(minutes=2))
    store.devolver(a.id, AGORA + timedelta(minutes=3))
    assert [d.id for d in store.ativos()] == [a.id]
    assert store.obter(c.id).esquecido_em is not None
    assert store.obter(b.id).esquecido_em is None  # já estava fora


def test_um_aprender_que_nao_terminou_nao_se_devolve():
    with pytest.raises(TimeoutError):
        _aprender(embutir=lambda _t: (_ for _ in ()).throw(TimeoutError("prazo")))
    (documento,) = store.todos()
    assert store.devolver(documento.id, AGORA) is None
    assert store.esquecer(str(uuid.uuid4()), AGORA) is None


@pytest.mark.parametrize(
    ("nome", "tema", "texto", "motivo"),
    [
        ("notas.pdf", "treino", TREINO, "só arquivos"),
        ("treino.md", "", TREINO, "sem letras"),
        ("treino.md", "treino", "a\x00b", "binário"),
        ("treino.md", "treino", "# Só título\n", "não tem texto"),
        ("treino.md", "treino", "x" * (cortes.MAX_BYTES + 1), "bytes"),
    ],
)
def test_aprender_recusa_antes_de_gravar(nome, tema, texto, motivo):
    embutir = _Embutir()
    with pytest.raises(cortes.Recusado, match=motivo):
        store.aprender(nome, tema, texto, embutir=embutir, agora=AGORA)
    assert store.todos() == [] and embutir.pedidos == []


def test_vetor_a_menos_nao_grava():
    with pytest.raises(vetores.VetorInvalido):
        _aprender(embutir=lambda textos: [_eixo(0)] * (len(textos) - 1))
    assert _todos_os_trechos() == []


def test_por_prefixo_nunca_escolhe_entre_dois():
    documento, _ = _aprender()
    assert store.por_prefixo(documento.curto) == documento.id
    assert store.por_prefixo(documento.id[:3]) is None
    assert store.por_prefixo("zzzzzzzz") is None


def test_da_semana_tem_os_aprendidos_e_os_esquecidos():
    fim = AGORA + timedelta(days=7)
    aprendido, _ = _aprender()
    esquecido, _ = _aprender("velho.md", agora=AGORA + timedelta(hours=1))
    store.esquecer(esquecido.id, AGORA + timedelta(days=1))
    assert {d.id for d in store.da_semana(AGORA, fim)} == {aprendido.id, esquecido.id}
    assert store.da_semana(fim, fim + timedelta(days=7)) == []


def test_sem_vetor_e_trocar_vetor():
    documento, _ = _aprender()
    (primeiro, *_) = store.trechos_de(documento.id)
    store._ref_do_trecho(primeiro.id).update(
        {"vetor": None, "vetor_modelo": None, "vetor_dim": None}
    )
    assert [t.id for t in store.sem_vetor()] == [primeiro.id]
    store.trocar_vetor(primeiro.id, _eixo(5))
    assert store.sem_vetor() == []


def test_copia_e_importar_ida_e_volta_sem_sobrescrever():
    documento, _ = _aprender()
    documentos, trechos = store.exportar()
    assert [d["id"] for d in documentos] == [documento.id] and len(trechos) == 3
    assert set(documentos[0]) == set(store.CAMPOS_DA_COPIA)
    assert set(trechos[0]) == set(store.CAMPOS_DA_COPIA_DO_TRECHO)
    store._ref(documento.id).delete()
    for t in trechos:
        store._ref_do_trecho(t["id"]).delete()
    assert store.importar(documentos[0]) == store.CRIADO
    assert [store.importar_trecho(t) for t in trechos] == [store.CRIADO] * 3
    assert store.exportar() == (documentos, trechos)
    assert store.importar(documentos[0]) == store.IGUAL
    assert store.importar_trecho(trechos[0]) == store.IGUAL
    assert store.importar(dict(documentos[0], tema="outro")) == store.DIFERENTE
    assert store.importar_trecho(dict(trechos[0], texto="outro")) == store.DIFERENTE
    # o restaurado volta sem vetor: o `--reindexar` refaz
    assert len(store.sem_vetor()) == 3


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("nome", "x.pdf"), ("tema", ""), ("estado", "outro"), ("origem", "e-mail")],
)
def test_importar_confere_o_documento(campo, valor):
    documento, _ = _aprender()
    (copia,), _ = store.exportar()
    store._ref(documento.id).delete()
    with pytest.raises(cortes.Recusado):
        store.importar(dict(copia, **{campo: valor}))
    assert store.obter(documento.id) is None


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("texto", ""),
        ("texto", "a\x00b"),
        ("texto", "x" * (store.MAX_TEXTO_DO_TRECHO + 1)),
        ("documento", "x"),
    ],
)
def test_importar_confere_o_trecho(campo, valor):
    _aprender()
    _, (copia, *_) = store.exportar()
    store._ref_do_trecho(copia["id"]).delete()
    with pytest.raises(cortes.Recusado):
        store.importar_trecho(dict(copia, **{campo: valor}))


# --- a avaliação fixa (o conjunto de ouro do C1, medido em 2026-10-09) --------------------------


def test_o_ouro_tem_a_forma_medida():
    assert OURO["modelo"] == vetores.MODELO and OURO["dimensao"] == vetores.DIMENSAO
    assert OURO["max_trecho"] == cortes.MAX_TRECHO
    assert OURO["prefixo_pergunta"] == vetores.PREFIXO_PERGUNTA
    assert (len(OURO["trechos"]), len(OURO["perguntas"]), len(OURO["fora"])) == (18, 22, 6)
    # o corte de hoje dá os mesmos trechos que foram medidos (senão, medir de novo)
    for tema, doc in OURO["documentos"].items():
        medidos = [t["texto"] for t in OURO["trechos"] if t["tema"] == tema]
        assert [t.texto for t in cortes.cortar(doc["texto"])] == medidos


def test_a_avaliacao_fixa_passa_no_limiar_do_dono():
    """Pelo `find_nearest` do emulador, com os vetores medidos: recall@5 e MRR do dono."""
    ids = {}
    for tema, doc in OURO["documentos"].items():
        medidos = iter([t["vetor"] for t in OURO["trechos"] if t["tema"] == tema])
        documento, _ = store.aprender(
            doc["arquivo"],
            tema,
            doc["texto"],
            embutir=lambda textos, medidos=medidos: [next(medidos) for _ in textos],
            agora=AGORA,
        )
        ids[tema] = {t.ordem: t.id for t in store.trechos_de(documento.id)}
    ranks = []
    for pergunta in OURO["perguntas"]:
        achados = store.consultar(pergunta["tema"], pergunta["vetor"])
        certo = ids[pergunta["tema"]][pergunta["trecho"]]
        ordem = [t.id for t in achados]
        ranks.append(ordem.index(certo) + 1 if certo in ordem else math.inf)
    recall_5 = sum(r <= 5 for r in ranks) / len(ranks)
    mrr = sum(1 / r for r in ranks) / len(ranks)
    assert recall_5 >= RECALL_5 and mrr >= MRR, (recall_5, mrr, ranks)


def test_o_limiar_e_o_do_dono():
    assert (RECALL_5, MRR) == (1.0, 0.95)


def test_instantes_sao_os_do_firestore():
    documento, _ = _aprender()
    assert documento.criado_em == firestore_comum.instante(AGORA)
