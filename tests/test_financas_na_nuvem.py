"""As finanças no chat da nuvem (Sessão 11d, D64): o motor pergunta, o serviço responde, e só o
serviço tem a chave.

De ponta a ponta, em processo: as tools e as rotas do motor chamam `financas/remoto.py`, cujo
`_post` aqui entra no app do serviço de finanças (`nuvem/financas.py`) **num contexto que é o do
serviço**: a URL dele como audience, o volume com as credenciais, `STORE` da nuvem e
`FINANCAS_URL` vazia. Fora desse contexto, `pluggy.cliente` levanta: se o motor usasse a chave,
o teste cairia em vez de ficar verde por outro caminho (erros, classe 4).
"""

import json
import sys
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests
from starlette.testclient import TestClient

from lifeos import cli, config, prazo
from lifeos.financas import pergunta, pluggy, remoto, tools
from lifeos.nuvem import chat_cliente, cliente, financas, motor
from test_financas_dados import (  # noqa: F401 — `_brasilia` e `pluggy_falsa` são fixtures
    ITEM,
    _brasilia,
    pluggy_falsa,
)
from test_motor import PROJETO
from test_motor import URL as URL_DO_MOTOR
from test_motor import _token as token_do_terminal
from test_nuvem_financas import URL as URL_DAS_FINANCAS
from test_nuvem_financas import _token as token_do_motor

AGORA = datetime(2026, 9, 20, 15, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
SEGREDO = "segredo-do-dono-nao-pode-vazar"


@pytest.fixture
def falsa(request):
    return request.getfixturevalue("pluggy_falsa")


@pytest.fixture
def nuvem(monkeypatch, tmp_path, falsa):
    """O motor (sem a chave) e, atrás do `_post`, o serviço de finanças (com ela)."""
    from test_motor import CERTIFICADO

    arquivo = tmp_path / "credenciais.json"
    arquivo.write_text(pluggy.segredo_para_json("id-do-app", SEGREDO, [ITEM]))
    monkeypatch.setattr(
        "google.oauth2.id_token._fetch_certs", lambda _req, _url: {"k1": CERTIFICADO}
    )
    monkeypatch.setattr(tools, "_agora", lambda: AGORA)
    monkeypatch.setattr(motor, "COMMIT", "abc123")
    monkeypatch.setattr(financas, "COMMIT", "abc123")
    # o motor: o projeto, a URL dele, a do serviço, e nenhuma credencial da Pluggy
    for nome, valor in {
        "NUVEM_PROJETO": PROJETO,
        "NUVEM_URL": URL_DO_MOTOR,
        "FINANCAS_URL": URL_DAS_FINANCAS,
        "PLUGGY_ARQUIVO": "",
        "PLUGGY_CLIENT_ID": "",
        "PLUGGY_CLIENT_SECRET": "",
        "PLUGGY_ITEM_IDS": (),
    }.items():
        monkeypatch.setattr(config, nome, valor)

    estado = {"no_servico": False, "posts": [], "chave_usada_no_motor": 0}
    do_servico = {
        "NUVEM_URL": URL_DAS_FINANCAS,
        "FINANCAS_URL": "",
        "PLUGGY_ARQUIVO": str(arquivo),
        "STORE": "firestore",
    }

    @contextmanager
    def no_servico():
        antes = {nome: getattr(config, nome) for nome in do_servico}
        for nome, valor in do_servico.items():
            setattr(config, nome, valor)
        estado["no_servico"] = True
        try:
            yield
        finally:
            for nome, valor in antes.items():
                setattr(config, nome, valor)
            estado["no_servico"] = False

    original = pluggy.cliente

    def cliente_vigiado():
        if not estado["no_servico"]:
            estado["chave_usada_no_motor"] += 1
            raise AssertionError("o motor tentou usar a chave da Pluggy")
        return original()

    monkeypatch.setattr(pluggy, "cliente", cliente_vigiado)
    monkeypatch.setattr(remoto, "_token", lambda: "token-do-metadados")

    servico = TestClient(financas.app)

    def post(url, corpo, token, segundos):
        estado["posts"].append((url, corpo, token, segundos))
        assert token == "token-do-metadados"
        assert url.startswith(URL_DAS_FINANCAS + "/")
        with no_servico():
            resposta = servico.post(
                url.removeprefix(URL_DAS_FINANCAS),
                json=corpo,
                headers={"Authorization": f"Bearer {token_do_motor()}"},
            )
        return resposta.status_code, resposta.content

    monkeypatch.setattr(remoto, "_post", post)
    estado["post"] = post
    estado["no_servico_ctx"] = no_servico
    return estado


def _texto_do_mac(monkeypatch, chamar):
    """O mesmo texto, como o Mac o faz: as credenciais do `.env`, sem serviço."""
    monkeypatch.setattr(config, "FINANCAS_URL", "")
    monkeypatch.setattr(config, "PLUGGY_CLIENT_ID", "id-do-app")
    monkeypatch.setattr(config, "PLUGGY_CLIENT_SECRET", SEGREDO)
    monkeypatch.setattr(config, "PLUGGY_ITEM_IDS", (ITEM,))
    monkeypatch.setattr(pluggy, "cliente", lambda: pluggy.Cliente("id-do-app", SEGREDO))
    return chamar()


# --- as tools no motor: o texto do Mac, pelo serviço ---------------------------------------------

CHAMADAS = [
    ("saldo", lambda: tools.saldos_das_contas()),
    ("gastos", lambda: tools.gastos_do_periodo("2026-09-01", "2026-09-30")),
    ("gastos sem datas", lambda: tools.gastos_do_periodo()),
    ("busca", lambda: tools.buscar_transacoes("pix")),
    ("busca por valor", lambda: tools.buscar_transacoes(valor="80", desde="2026-09-01")),
    ("fatura", lambda: tools.fatura_do_cartao()),
    ("conexões", lambda: tools.responder_conexoes()),
]


@pytest.mark.parametrize(("caso", "chamar"), CHAMADAS)
def test_no_motor_cada_tool_devolve_o_texto_do_mac(nuvem, monkeypatch, caso, chamar):
    no_motor = chamar()
    assert len(nuvem["posts"]) == 1, caso
    assert nuvem["chave_usada_no_motor"] == 0
    assert "Não consegui" not in no_motor and "Não entendi" not in no_motor, no_motor
    assert no_motor == _texto_do_mac(monkeypatch, chamar), caso


def test_o_motor_nunca_usa_a_chave_mesmo_com_ela_no_ambiente(nuvem, monkeypatch):
    """Se a chave aparecesse no ambiente do motor (um deploy errado), as tools ainda perguntariam
    ao serviço: quem decide é a URL do serviço, não a presença da chave."""
    monkeypatch.setattr(config, "PLUGGY_CLIENT_ID", "id-do-app")
    monkeypatch.setattr(config, "PLUGGY_CLIENT_SECRET", SEGREDO)
    monkeypatch.setattr(config, "PLUGGY_ITEM_IDS", (ITEM,))
    for _caso, chamar in CHAMADAS:
        chamar()
    assert nuvem["chave_usada_no_motor"] == 0
    assert len(nuvem["posts"]) == len(CHAMADAS)


def test_a_pergunta_vai_no_formato_fechado(nuvem):
    tools.buscar_transacoes("luz", valor="10")
    ((url, corpo, _token, _segundos),) = nuvem["posts"]
    assert url == URL_DAS_FINANCAS + "/responder"
    assert corpo == {"pergunta": "buscar", "texto": "luz", "desde": "", "ate": "", "valor": "10"}


def test_uma_busca_longa_do_gemini_nao_sai_do_motor(nuvem):
    texto = tools.buscar_transacoes("a" * 500)
    assert texto.startswith("Não entendi o pedido")
    assert nuvem["posts"] == []


# --- o serviço fora ou torto: a frase, nunca um valor ----------------------------------------------


def _falha(excecao):
    def post(*_args):
        raise excecao

    return post


@pytest.mark.parametrize(
    ("caso", "post"),
    [
        ("tempo esgotado", _falha(requests.Timeout("lento"))),
        ("sem conexão", _falha(requests.ConnectionError("caiu"))),
        ("500", lambda *_a: (500, b'{"erro": "x"}')),
        ("403 do Google", lambda *_a: (403, b"<html>")),
        ("não é JSON", lambda *_a: (200, b"R$ 1.234,56")),
        ("texto que não é texto", lambda *_a: (200, b'{"texto": 1234.56}')),
        ("campo a mais", lambda *_a: (200, b'{"texto": "R$ 1", "chave": "x"}')),
        ("lista", lambda *_a: (200, b'["R$ 1"]')),
        ("grande demais", lambda *_a: (200, json.dumps({"texto": "R$ 1" * 20_000}).encode())),
    ],
)
def test_o_servico_fora_ou_torto_vira_a_frase(nuvem, monkeypatch, caso, post):
    monkeypatch.setattr(remoto, "_post", post)
    texto = tools.saldos_das_contas()
    assert texto.startswith("Não consegui falar com a Pluggy agora"), caso
    assert texto.endswith("Nada foi alterado."), caso
    assert "R$" not in texto and "1234" not in texto, caso


def test_sem_o_token_do_metadados_vira_a_frase(nuvem, monkeypatch):
    def sem_token():
        raise OSError("metadados fora")

    monkeypatch.setattr(remoto, "_token", sem_token)
    texto = tools.fatura_do_cartao()
    assert "sem o token para o serviço de finanças (OSError)" in texto
    assert nuvem["posts"] == []


def test_o_pedido_cabe_no_que_resta_do_turno(nuvem):
    with prazo.ate(100):
        tools.saldos_das_contas()
    ((*_, segundos),) = nuvem["posts"]
    assert 39 <= segundos <= 40  # 100 − os 60 s do Gemini que lê a resposta

    nuvem["posts"].clear()
    with prazo.ate(62):
        texto = tools.saldos_das_contas()
    assert nuvem["posts"] == []
    assert "não deu tempo de perguntar ao serviço de finanças" in texto

    tools.saldos_das_contas()  # sem prazo (a rota do terminal): o teto
    assert nuvem["posts"][-1][3] == remoto.PRAZO_MAX_S


# --- o 429 do Cloud Run (sem instância; o pedido não chegou ao serviço) ----------------------------


@pytest.fixture
def esperas(monkeypatch):
    feitas = []
    monkeypatch.setattr(remoto, "_esperar", feitas.append)
    return feitas


def _antes(status, vezes, post):
    """`vezes` respostas `status` do Cloud Run, depois o serviço de verdade."""
    restam = [vezes]

    def antes(url, corpo, token, segundos):
        if restam[0]:
            restam[0] -= 1
            return status, b"Rate exceeded."
        return post(url, corpo, token, segundos)

    return antes


def test_o_429_se_repete_e_a_resposta_chega(nuvem, monkeypatch, esperas):
    monkeypatch.setattr(remoto, "_post", _antes(429, 2, nuvem["post"]))
    no_motor = tools.saldos_das_contas()
    assert esperas == [2.0, 4.0]
    assert len(nuvem["posts"]) == 1  # só o terceiro chegou ao serviço
    assert no_motor == _texto_do_mac(monkeypatch, tools.saldos_das_contas)


def test_o_429_que_nao_passa_para_em_tres_pedidos(nuvem, monkeypatch, esperas):
    pedidos = []
    monkeypatch.setattr(remoto, "_post", lambda *a: pedidos.append(a) or (429, b""))
    texto = tools.saldos_das_contas()
    assert "respondeu 429" in texto
    assert len(pedidos) == 3 and esperas == [2.0, 4.0]


def test_o_429_nao_se_repete_alem_do_prazo_do_turno(nuvem, monkeypatch, esperas):
    pedidos = []
    monkeypatch.setattr(remoto, "_post", lambda *a: pedidos.append(a) or (429, b""))
    with prazo.ate(66):  # 6 s para o pedido: esperar 2 deixaria menos que o mínimo
        texto = tools.saldos_das_contas()
    assert "respondeu 429" in texto
    assert len(pedidos) == 1 and esperas == []


@pytest.mark.parametrize("status", [500, 403, 503])
def test_so_o_429_se_repete(nuvem, monkeypatch, esperas, status):
    pedidos = []
    monkeypatch.setattr(remoto, "_post", lambda *a: pedidos.append(a) or (status, b""))
    assert f"respondeu {status}" in tools.saldos_das_contas()
    assert len(pedidos) == 1 and esperas == []


# --- as rotas do motor ---------------------------------------------------------------------------


def _ao_motor(rota, corpo=None, token=None):
    cliente_http = TestClient(motor.app)
    cabecalhos = {"Authorization": f"Bearer {token or token_do_terminal()}"}
    if corpo is None:
        return cliente_http.get(rota, headers=cabecalhos)
    return cliente_http.post(rota, json=corpo, headers=cabecalhos)


def test_a_rota_do_terminal_devolve_o_texto_do_mac(nuvem, monkeypatch):
    resposta = _ao_motor("/financas", {"pergunta": "saldo"})
    assert resposta.status_code == 200
    assert resposta.json() == {"texto": _texto_do_mac(monkeypatch, tools.saldos_das_contas)}


@pytest.mark.parametrize("rota", ["/financas", "/fumaca/financas"])
@pytest.mark.parametrize("conta", ["viking-maos", "viking-agendador", "viking-motor"])
def test_so_o_terminal_pergunta_as_financas_ao_motor(nuvem, rota, conta):
    token = token_do_terminal(email=f"{conta}@{PROJETO}.iam.gserviceaccount.com")
    corpo = {"pergunta": "saldo"} if rota == "/financas" else None
    assert _ao_motor(rota, corpo, token).status_code == 403
    assert nuvem["posts"] == []


def test_pergunta_torta_ao_motor_400_sem_ir_ao_servico(nuvem):
    resposta = _ao_motor("/financas", {"pergunta": "/payments/requests"})
    assert resposta.status_code == 400
    assert "/payments" not in resposta.text
    assert nuvem["posts"] == []


def test_sem_o_servico_o_motor_diz_409(nuvem, monkeypatch):
    monkeypatch.setattr(config, "FINANCAS_URL", "")
    assert _ao_motor("/financas", {"pergunta": "saldo"}).status_code == 409
    assert _ao_motor("/fumaca/financas").status_code == 409
    assert nuvem["posts"] == []


def test_o_servico_fora_o_motor_diz_502_sem_conteudo(nuvem, monkeypatch, caplog):
    monkeypatch.setattr(remoto, "_post", lambda *_a: (500, b'{"erro": "R$ 1.234,56"}'))
    resposta = _ao_motor("/financas", {"pergunta": "saldo"})
    assert resposta.status_code == 502
    assert resposta.json() == {"erro": "o serviço de finanças respondeu 500"}
    assert "1.234" not in caplog.text


def test_a_fumaca_conta_as_conexoes_sem_chamar_a_pluggy(nuvem, falsa):
    resposta = _ao_motor("/fumaca/financas")
    assert resposta.json() == {"commit": "abc123", "credenciais": True, "conexoes": 1}
    assert [url for url, *_ in nuvem["posts"]] == [URL_DAS_FINANCAS + "/saude"]
    assert falsa["pedidos"] == []


def test_a_fumaca_recusa_resposta_fora_do_formato(nuvem, monkeypatch):
    monkeypatch.setattr(
        remoto, "_post", lambda *_a: (200, b'{"commit": "x", "credenciais": 1, "conexoes": 2}')
    )
    assert _ao_motor("/fumaca/financas").status_code == 502


# --- o terminal do Mac -------------------------------------------------------------------------


def test_a_abertura_com_as_financas_na_nuvem():
    tudo = {"gmail": True, "maos": True, "financas": True}
    assert chat_cliente.abertura(tudo) == (
        "☁️  Viking na nuvem (agenda, lembretes, Gmail, o navegador do Mac, com o `viking maos` "
        "ligado lá e finanças, só leitura)."
    )
    sem_maos = chat_cliente.abertura({"gmail": True, "financas": True})
    assert sem_maos.endswith(". Navegador: `viking chat`.") and "finanças, só leitura" in sem_maos


def _cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["viking", "financas", *args])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


@pytest.mark.parametrize(
    ("args", "pedido"),
    [
        (["--saldo"], {"pergunta": "saldo"}),
        (["--gastos", "--desde", "2026-09-01"], {"pergunta": "gastos", "desde": "2026-09-01"}),
        (
            ["--buscar", "luz", "--valor", "10"],
            {"pergunta": "buscar", "texto": "luz", "valor": "10"},
        ),
        (["--valor", "89,90"], {"pergunta": "buscar", "valor": "89,90"}),
        (["--fatura"], {"pergunta": "fatura"}),
        ([], {"pergunta": "conexoes"}),
    ],
)
def test_viking_financas_nuvem_pede_ao_motor(monkeypatch, capsys, args, pedido):
    pedidos = []

    def perguntar(p):
        pedidos.append(p)
        return "TEXTO DA NUVEM"

    monkeypatch.setattr(cliente, "perguntar_financas", perguntar)
    monkeypatch.setattr(pluggy, "cliente", lambda: pytest.fail("o --nuvem usou a chave do Mac"))
    assert _cli(monkeypatch, *args, "--nuvem") == 0
    assert capsys.readouterr().out == "TEXTO DA NUVEM\n"
    assert pedidos == [pergunta.conferir(pedido)]


def test_conectar_pela_nuvem_e_recusado(monkeypatch, capsys):
    monkeypatch.setattr(cliente, "perguntar_financas", lambda p: pytest.fail("perguntou"))
    assert _cli(monkeypatch, "--conectar", "--nuvem") == 2
    assert "só no Mac" in capsys.readouterr().err


def test_a_nuvem_fora_sai_com_2(monkeypatch, capsys):
    def fora(_p):
        raise cliente.ErroDaNuvem("a nuvem respondeu HTTP 409: o serviço de finanças não está")

    monkeypatch.setattr(cliente, "perguntar_financas", fora)
    assert _cli(monkeypatch, "--saldo", "--nuvem") == 2
    assert "HTTP 409" in capsys.readouterr().err
