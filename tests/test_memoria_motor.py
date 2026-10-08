"""A memória pelo motor (Sessão 13, D66): as rotas do `viking memoria` e o resumo da semana.

As perguntas: só o terminal do dono alcança as rotas? O id curto resolve e o ambíguo nunca escolhe?
Corrigir passa pelo filtro antes de gastar? O teto vale para o embedding de uma rota? O resumo sai
uma vez por semana, na segunda às 9h do fuso do dono, só com anotação, e uma falha dele não para
o envio de lembretes?
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from google import genai
from google.genai import types
from starlette.testclient import TestClient
from tests import test_lembretes_nuvem as nuvem_base
from tests import test_motor as motor_base
from tests.test_lembretes_nuvem import CONTAS, _do_lado_da_nuvem

from lifeos import config, custos
from lifeos.assistant import na_nuvem
from lifeos.memoria import resumo, store, vetores
from lifeos.nuvem import motor

_nuvem = motor_base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google
_contexto_limpo = nuvem_base._contexto_limpo  # autouse: a origem das ações volta ao fim
LA = ZoneInfo("America/Los_Angeles")
# Uma segunda às 9h05 em Seattle (16h05 UTC, no horário de verão).
SEGUNDA = datetime(2026, 10, 12, 16, 5, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _ligada(firestore_limpo, monkeypatch):
    monkeypatch.setattr(config, "MEMORIA", True)
    monkeypatch.setattr(config, "TIMEZONE", LA)
    monkeypatch.setattr(config, "TETO_GEMINI_DIA", 5.0)
    monkeypatch.setattr(config, "TETO_GEMINI_MES", 10.0)


def _eixo(n):
    v = [0.0] * vetores.DIMENSAO
    v[n] = 1.0
    return v


def _gravar(texto, *, agora=None, vetor=None, sessao="s1"):
    with _do_lado_da_nuvem():
        return store.gravar(
            texto, origem="chat", vetor=vetor or _eixo(0), sessao=sessao, agora=agora
        )


class _Embedding:
    def __init__(self):
        self.textos: list[str] = []

    def __call__(self, **kwargs):
        textos = [c.parts[0].text for c in kwargs["contents"]]
        self.textos += textos
        return types.EmbedContentResponse(
            embeddings=[types.ContentEmbedding(values=_eixo(5)) for _ in textos]
        )


@pytest.fixture
def embedding(monkeypatch):
    falso = _Embedding()

    def cliente():
        c = genai.Client(api_key="teste")
        c.models._embed_content = falso
        return c

    monkeypatch.setattr(na_nuvem, "_cliente", cliente)
    return falso


def _pedir(metodo, rota, corpo=None, conta="cli"):
    token = motor_base._token(email=CONTAS[conta])
    with _do_lado_da_nuvem():
        cliente = TestClient(motor.app)
        cabecalho = {"Authorization": f"Bearer {token}"}
        if metodo == "GET":
            return cliente.get(rota, headers=cabecalho)
        return cliente.post(rota, json=corpo or {}, headers=cabecalho)


ROTAS = [
    ("GET", "/memoria"),
    ("POST", "/memoria/esquecer"),
    ("POST", "/memoria/desfazer"),
    ("POST", "/memoria/corrigir"),
    ("POST", "/memoria/reindexar"),
]


@pytest.mark.parametrize("conta", ["maos", "agendador"])
@pytest.mark.parametrize(("metodo", "rota"), ROTAS)
def test_so_o_terminal_do_dono_alcanca_a_memoria(metodo, rota, conta):
    fato = _gravar("O usuário corre aos sábados.")
    resposta = _pedir(metodo, rota, {"id": fato.curto, "texto": "x"}, conta=conta)
    assert resposta.status_code == 403
    with _do_lado_da_nuvem():
        assert [f.ativo for f in store.todos()] == [True]


def test_listar_traz_todos_com_as_marcas():
    _gravar("O usuário corre aos sábados.")
    esquecido = _gravar("O usuário toca violão.")
    with _do_lado_da_nuvem():
        store.esquecer(esquecido.id)
    resposta = _pedir("GET", "/memoria")
    assert resposta.status_code == 200
    fatos = resposta.json()["fatos"]
    assert {f["texto"]: f["ativo"] for f in fatos} == {
        "O usuário corre aos sábados.": True,
        "O usuário toca violão.": False,
    }
    assert all(set(f) == set(store.CAMPOS_DA_COPIA) for f in fatos)


def test_esquecer_e_desfazer_pelo_id_curto():
    fato = _gravar("O usuário corre aos sábados.")
    resposta = _pedir("POST", "/memoria/esquecer", {"id": fato.curto})
    assert resposta.status_code == 200 and resposta.json()["fato"]["ativo"] is False
    resposta = _pedir("POST", "/memoria/desfazer", {"id": fato.curto})
    assert resposta.status_code == 200 and resposta.json()["fato"]["ativo"] is True
    assert _pedir("POST", "/memoria/desfazer", {"id": fato.curto}).status_code == 400


@pytest.mark.parametrize("corpo", [{}, {"id": 5}, {"id": "abc"}, {"id": "zzzzzzzz"}])
def test_id_torto_ou_curto_demais_e_400_sem_mexer(corpo):
    _gravar("O usuário corre aos sábados.")
    resposta = _pedir("POST", "/memoria/esquecer", corpo)
    assert resposta.status_code == 400
    with _do_lado_da_nuvem():
        assert [f.ativo for f in store.todos()] == [True]


def test_corrigir_troca_o_fato_com_vetor_novo(embedding):
    antigo = _gravar("O usuário treina às 7h.")
    resposta = _pedir(
        "POST", "/memoria/corrigir", {"id": antigo.curto, "texto": "O usuário treina às 6h."}
    )
    assert resposta.status_code == 200
    novo = resposta.json()["fato"]
    assert (novo["texto"], novo["origem"], novo["ativo"]) == (
        "O usuário treina às 6h.",
        "viking memoria",
        True,
    )
    with _do_lado_da_nuvem():
        velho = store.obter(antigo.id)
        assert velho is not None and velho.substituido_por == novo["id"]
        assert store.parecidos(_eixo(5), k=1)[0].id == novo["id"]
    assert embedding.textos == [vetores.PREFIXO_FATO + "O usuário treina às 6h."]


def test_corrigir_com_texto_proibido_recusa_antes_de_gastar(embedding):
    antigo = _gravar("O usuário treina às 7h.")
    resposta = _pedir(
        "POST", "/memoria/corrigir", {"id": antigo.curto, "texto": "O saldo do usuário é 1200."}
    )
    assert resposta.status_code == 400
    assert resposta.json()["erro"].endswith("valor em dinheiro")
    assert "1200" not in resposta.text
    assert embedding.textos == []


def test_reindexar_refaz_so_quem_nao_tem_vetor(embedding):
    with _do_lado_da_nuvem():
        sem = store.gravar("O usuário toca violão.", origem="backup", vetor=None)
    _gravar("O usuário corre aos sábados.")
    resposta = _pedir("POST", "/memoria/reindexar")
    assert resposta.json() == {"refeitos": 1}
    assert embedding.textos == [vetores.PREFIXO_FATO + "O usuário toca violão."]
    with _do_lado_da_nuvem():
        assert store.sem_vetor() == []
        assert store.parecidos(_eixo(5), k=1)[0].id == sem.id


def test_o_teto_estourado_para_a_rota_antes_do_embedding(embedding, monkeypatch):
    antigo = _gravar("O usuário treina às 7h.")
    monkeypatch.setattr(config, "TETO_GEMINI_DIA", 0.000001)
    with _do_lado_da_nuvem():
        custos.Teto(mes=10, dia=0.000001, fuso=LA).somar(0.01)
    resposta = _pedir(
        "POST", "/memoria/corrigir", {"id": antigo.curto, "texto": "O usuário treina às 6h."}
    )
    assert resposta.status_code == 503 and "TetoAtingido" in resposta.json()["erro"]
    assert embedding.textos == []


def test_com_a_memoria_desligada_as_rotas_dizem(monkeypatch):
    monkeypatch.setattr(config, "MEMORIA", False)
    assert _pedir("GET", "/memoria").status_code == 503


# --- o resumo da semana ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agora", "devido"),
    [
        (SEGUNDA, True),
        (datetime(2026, 10, 12, 15, 59, tzinfo=UTC), False),  # 8h59 em Seattle
        (datetime(2026, 10, 12, 16, 0, tzinfo=UTC), True),  # 9h em ponto
        (datetime(2026, 10, 12, 2, 0, tzinfo=UTC), False),  # segunda no UTC, domingo lá
        (datetime(2026, 10, 13, 6, 30, tzinfo=UTC), True),  # 23h30 da segunda lá, terça no UTC
        (datetime(2026, 10, 13, 16, 5, tzinfo=UTC), False),  # terça
    ],
)
def test_a_janela_e_a_segunda_depois_das_9h_no_fuso_do_dono(agora, devido):
    assert (resumo.janela(agora) is not None) is devido


def test_a_janela_e_a_semana_que_terminou_nesta_segunda_as_9h():
    inicio, fim = resumo.janela(SEGUNDA)
    assert fim == datetime(2026, 10, 12, 16, 0, tzinfo=UTC)
    assert fim - inicio == timedelta(days=7)


def test_o_resumo_sai_uma_vez_com_os_fatos_da_semana(gmail):
    _gravar("O usuário corre aos sábados.", agora=SEGUNDA - timedelta(days=3))
    _gravar("O usuário é vegetariano.", agora=SEGUNDA - timedelta(days=8))  # semana anterior
    _gravar("O usuário toca violão.", agora=SEGUNDA)  # depois das 9h: o resumo seguinte
    with _do_lado_da_nuvem():
        assert resumo.rodar(SEGUNDA) == "enviado"
        assert resumo.rodar(SEGUNDA + timedelta(minutes=1)) == "já feito"
        assert resumo.estado(SEGUNDA)["estado"] == "enviado"
    (enviado,) = gmail["enviados"]
    assert enviado["mensagem"]["Subject"] == "Viking: o que anotei esta semana (1)"
    corpo = enviado["mensagem"].get_body(("plain",)).get_content()
    assert "O usuário corre aos sábados." in corpo
    assert "vegetariano" not in corpo and "violão" not in corpo


def test_semana_sem_anotacao_nao_manda_e_nao_tenta_de_novo(gmail):
    with _do_lado_da_nuvem():
        assert resumo.rodar(SEGUNDA) == "nada anotado"
        assert resumo.rodar(SEGUNDA + timedelta(minutes=1)) == "já feito"
    assert gmail["enviados"] == []


def test_fora_da_hora_nem_reserva(gmail):
    _gravar("O usuário corre aos sábados.", agora=SEGUNDA - timedelta(days=3))
    terca = SEGUNDA + timedelta(days=1)
    with _do_lado_da_nuvem():
        assert resumo.rodar(terca) == "fora da hora"
        assert resumo.estado(terca) is None
    assert gmail["enviados"] == []


def test_recusado_solta_a_reserva_e_a_proxima_rodada_tenta(gmail):
    _gravar("O usuário corre aos sábados.", agora=SEGUNDA - timedelta(days=3))
    gmail["falhar_send"] = [400]
    with _do_lado_da_nuvem():
        assert resumo.rodar(SEGUNDA) == "recusado"
        assert resumo.estado(SEGUNDA) is None
        assert resumo.rodar(SEGUNDA + timedelta(minutes=1)) == "enviado"
    assert len(gmail["enviados"]) == 1


def test_pode_ter_saido_nao_reenvia(gmail):
    _gravar("O usuário corre aos sábados.", agora=SEGUNDA - timedelta(days=3))
    gmail["falhar_send"] = [500]
    with _do_lado_da_nuvem():
        assert resumo.rodar(SEGUNDA) == "incerto"
        assert resumo.rodar(SEGUNDA + timedelta(minutes=1)) == "já feito"
    assert gmail["enviados"] == []


def test_o_corpo_mostra_o_estado_de_cada_fato():
    agora = SEGUNDA - timedelta(days=2)
    fatos = [
        store.Fato(
            "a" * 8 + "-0000-4000-8000-000000000001",
            "O usuário corre.",
            "chat",
            "",
            "",
            agora,
            True,
        ),
        store.Fato(
            "b" * 8 + "-0000-4000-8000-000000000002",
            "O usuário toca.",
            "chat",
            "",
            "",
            agora,
            False,
            esquecido_em=agora,
        ),
        store.Fato(
            "c" * 8 + "-0000-4000-8000-000000000003",
            "O usuário treina às 7h.",
            "chat",
            "",
            "",
            agora,
            False,
            invalida_em=agora,
        ),
    ]
    texto = resumo.corpo(fatos, *resumo.janela(SEGUNDA))
    assert "- [aaaaaaaa] O usuário corre.\n" in texto
    assert "- [bbbbbbbb] O usuário toca. (esquecido)" in texto
    assert "- [cccccccc] O usuário treina às 7h. (já trocado por outro)" in texto
    assert texto.startswith("O que o Viking anotou de 05/10 a 12/10:")


def _rodada():
    token = motor_base._token(email=CONTAS["agendador"])
    with _do_lado_da_nuvem():
        return TestClient(motor.app).post(
            "/tarefas/lembretes", headers={"Authorization": f"Bearer {token}"}
        )


def test_a_rodada_dos_lembretes_leva_o_resumo(gmail, monkeypatch):
    monkeypatch.setattr(resumo, "rodar", lambda: "enviado")
    assert _rodada().json()["resumo"] == "enviado"


def test_uma_falha_do_resumo_nao_para_os_lembretes(gmail, monkeypatch):
    def quebra():
        raise RuntimeError("O usuário corre aos sábados.")

    monkeypatch.setattr(resumo, "rodar", quebra)
    resposta = _rodada()
    assert resposta.status_code == 200
    assert resposta.json()["resumo"] == "falhou (RuntimeError)"
    assert "sábados" not in resposta.text


# --- a fumaça do deploy: o índice vetorial no ar, sem o Gemini --------------------------------


def test_a_fumaca_da_memoria_so_conta(monkeypatch):
    assert _pedir("GET", "/fumaca/memoria").json() == {"achados": 0}
    _gravar("O usuário corre aos sábados.")
    resposta = _pedir("GET", "/fumaca/memoria")
    assert resposta.json() == {"achados": 1} and "sábados" not in resposta.text
    assert _pedir("GET", "/fumaca/memoria", conta="maos").status_code == 403


def test_sem_o_indice_a_fumaca_da_memoria_falha_alto_so_com_o_tipo(monkeypatch):
    def sem_indice(*_a, **_k):
        raise RuntimeError("FAILED_PRECONDITION: O usuário corre aos sábados.")

    monkeypatch.setattr(store, "parecidos", sem_indice)
    resposta = _pedir("GET", "/fumaca/memoria")
    assert resposta.status_code == 500
    assert resposta.json() == {"erro": "a busca da memória falhou (RuntimeError)"}


def test_um_fato_torto_na_restauracao_e_400_e_nada_grava():
    fato = {
        "id": "../gastos/2026-10",
        "texto": "O usuário corre aos sábados.",
        "origem": "chat",
        "sessao": "",
        "turno": "",
        "criado_em": "2026-10-06T17:00:00.000000+00:00",
        "ativo": True,
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    resposta = _pedir("POST", "/backup/importar", {"acoes": [], "gastos": [], "memoria": [fato]})
    assert resposta.status_code == 400 and "UUID" in resposta.json()["erro"]
    with _do_lado_da_nuvem():
        assert store.todos() == []
