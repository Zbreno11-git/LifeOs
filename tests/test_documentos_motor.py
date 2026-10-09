"""Os documentos pelo motor (Sessão 14, D68): as rotas do `viking documentos`, o `--reindexar` e o
resumo da semana.

As perguntas: só o terminal do dono alcança as rotas? Aprender embute cada trecho com o título e
guarda, e um arquivo recusado não gasta nada? O teto, o prazo e o Gemini fora param sem deixar
documento pela metade na busca, e o erro diz só o tipo? O id curto resolve? O `--reindexar` refaz
os trechos restaurados? O resumo de segunda conta os documentos da semana?
"""

import logging
from datetime import timedelta

import pytest

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from tests import test_memoria_motor as base
from tests.test_lembretes_nuvem import _do_lado_da_nuvem

from lifeos import config, custos
from lifeos.documentos import cortes, store
from lifeos.memoria import resumo

_nuvem = base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google
_contexto_limpo = base._contexto_limpo
_ligada = base._ligada  # autouse: a memória ligada, o teto e o fuso
embedding = base.embedding
_pedir = base._pedir

TREINO = "# Perna\n\nAgachamento, quatro séries de oito.\n\n# Costas\n\nBarra fixa até a falha.\n"
APRENDER = {"nome": "treino.md", "tema": "treino", "texto": TREINO}

ROTAS = [
    ("GET", "/documentos"),
    ("POST", "/documentos/aprender"),
    ("POST", "/documentos/esquecer"),
    ("POST", "/documentos/desfazer"),
]


def _ativos():
    with _do_lado_da_nuvem():
        return store.ativos()


@pytest.mark.parametrize("conta", ["maos", "agendador"])
@pytest.mark.parametrize(("metodo", "rota"), ROTAS)
def test_so_o_terminal_do_dono_alcanca_os_documentos(embedding, metodo, rota, conta):
    resposta = _pedir(metodo, rota, APRENDER | {"id": "abcdef12"}, conta=conta)
    assert resposta.status_code == 403
    assert embedding.textos == [] and _ativos() == []


def test_aprender_embute_cada_trecho_com_o_titulo_e_guarda(embedding):
    resposta = _pedir("POST", "/documentos/aprender", APRENDER)
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["substituido"] is None
    assert (dados["documento"]["nome"], dados["documento"]["n_trechos"]) == ("treino.md", 2)
    assert embedding.textos == [
        "title: treino.md — Perna | text: Agachamento, quatro séries de oito.",
        "title: treino.md — Costas | text: Barra fixa até a falha.",
    ]
    listados = _pedir("GET", "/documentos").json()["documentos"]
    assert [d["id"] for d in listados] == [dados["documento"]["id"]]
    assert all(set(d) == set(store.CAMPOS_DA_COPIA) for d in listados)
    assert "Agachamento" not in _pedir("GET", "/documentos").text  # a lista não leva trecho


def test_aprender_de_novo_substitui_e_o_desfazer_devolve(embedding):
    velho = _pedir("POST", "/documentos/aprender", APRENDER).json()["documento"]
    novo = _pedir("POST", "/documentos/aprender", APRENDER | {"texto": "# Perna\n\nNovo."}).json()
    assert novo["substituido"]["id"] == velho["id"]
    assert [d.id for d in _ativos()] == [novo["documento"]["id"]]
    resposta = _pedir("POST", "/documentos/desfazer", {"id": velho["id"][:8]})
    assert resposta.status_code == 200 and resposta.json()["documento"]["ativo"] is True
    assert [d.id for d in _ativos()] == [velho["id"]]


def test_esquecer_pelo_id_curto_e_desfazer_de_novo_e_400(embedding):
    documento = _pedir("POST", "/documentos/aprender", APRENDER).json()["documento"]
    resposta = _pedir("POST", "/documentos/esquecer", {"id": documento["id"][:8]})
    assert resposta.status_code == 200 and resposta.json()["documento"]["ativo"] is False
    assert _ativos() == []
    assert _pedir("POST", "/documentos/desfazer", {"id": documento["id"][:8]}).status_code == 200
    assert _pedir("POST", "/documentos/desfazer", {"id": documento["id"][:8]}).status_code == 400
    assert _pedir("POST", "/documentos/esquecer", {"id": "abc"}).status_code == 400


@pytest.mark.parametrize(
    ("mudar", "motivo"),
    [
        ({"nome": "treino.pdf"}, "só arquivos .md ou .txt"),
        ({"nome": "/Users/x/treino.md"}, "sem a pasta"),
        ({"tema": ""}, "sem letras"),
        ({"texto": "a" * (cortes.MAX_BYTES + 1)}, "mais de 1.000.000 bytes"),
        ({"texto": "a\x00b"}, "binário"),
        ({"texto": "# Só título\n"}, "não tem texto"),
        ({"extra": 1}, "nome, tema e texto"),
    ],
)
def test_um_arquivo_recusado_nao_gasta_nada(embedding, mudar, motivo):
    resposta = _pedir("POST", "/documentos/aprender", APRENDER | mudar)
    assert resposta.status_code == 400 and motivo in resposta.json()["erro"]
    assert embedding.textos == []
    with _do_lado_da_nuvem():
        assert store.todos() == []


def test_o_corpo_acima_do_teto_do_motor_e_400(embedding):
    resposta = _pedir("POST", "/documentos/aprender", APRENDER | {"texto": "a" * (5 * 1024 * 1024)})
    assert resposta.status_code == 400 and embedding.textos == []


def test_o_teto_estourado_para_antes_do_embedding(embedding, monkeypatch):
    monkeypatch.setattr(config, "TETO_GEMINI_DIA", 0.000001)
    with _do_lado_da_nuvem():
        custos.Teto(mes=10, dia=0.000001, fuso=base.LA).somar(0.01)
    resposta = _pedir("POST", "/documentos/aprender", APRENDER)
    assert resposta.status_code == 503 and "TetoAtingido" in resposta.json()["erro"]
    assert embedding.textos == [] and _ativos() == []


def test_o_gemini_fora_no_meio_deixa_nada_na_busca_e_o_log_so_o_tipo(
    embedding, monkeypatch, caplog
):
    def quebra(**_kwargs):
        raise ConnectionError("Agachamento vazou no erro")

    monkeypatch.setattr(base._Embedding, "__call__", lambda _self, **kw: quebra(**kw))
    with caplog.at_level(logging.DEBUG):
        resposta = _pedir("POST", "/documentos/aprender", APRENDER)
    assert resposta.status_code == 503 and "ConnectionError" in resposta.json()["erro"]
    assert "Agachamento" not in resposta.text + caplog.text
    assert _ativos() == []
    with _do_lado_da_nuvem():
        (documento,) = store.todos()
    assert documento.estado == store.APRENDENDO and documento.apagar_em is not None


def test_com_a_memoria_desligada_as_rotas_dizem(monkeypatch):
    monkeypatch.setattr(config, "MEMORIA", False)
    assert _pedir("GET", "/documentos").status_code == 503
    assert _pedir("POST", "/documentos/aprender", APRENDER).status_code == 503


def test_reindexar_refaz_os_trechos_sem_vetor(embedding):
    with _do_lado_da_nuvem():
        documento, _ = store.aprender(
            "treino.md", "treino", TREINO, embutir=lambda t: [base._eixo(1) for _ in t]
        )
        (primeiro, *_) = store.trechos_de(documento.id)
        store._ref_do_trecho(primeiro.id).update(
            {"vetor": None, "vetor_modelo": None, "vetor_dim": None}
        )
    resposta = _pedir("POST", "/memoria/reindexar")
    assert resposta.json() == {"refeitos": 0, "trechos": 1}
    assert embedding.textos == [
        "title: treino.md — Perna | text: Agachamento, quatro séries de oito."
    ]
    with _do_lado_da_nuvem():
        assert store.sem_vetor() == []


def test_a_fumaca_conta_os_trechos_do_tema_dela_sem_o_texto(embedding):
    _pedir("POST", "/documentos/aprender", APRENDER | {"tema": "fumaca"})
    resposta = _pedir("GET", "/fumaca/memoria")
    assert resposta.json()["trechos"] == 1 and "Agachamento" not in resposta.text


# --- o resumo da semana ------------------------------------------------------------------------


def test_o_resumo_conta_os_documentos_da_semana(gmail):
    with _do_lado_da_nuvem():
        store.aprender(
            "treino.md",
            "treino",
            TREINO,
            embutir=lambda t: [base._eixo(1) for _ in t],
            agora=base.SEGUNDA - timedelta(days=2),
        )
        assert resumo.rodar(base.SEGUNDA) == "enviado"
    (enviado,) = gmail["enviados"]
    assert enviado["mensagem"]["Subject"] == "Viking: o que anotei esta semana (1)"
    corpo = enviado["mensagem"].get_body(("plain",)).get_content()
    assert "treino.md (tema treino, 2 trecho(s))" in corpo
    assert "Agachamento" not in corpo  # o texto do documento nunca vai ao e-mail
