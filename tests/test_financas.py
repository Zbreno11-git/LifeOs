"""Pluggy: conectar e conferir, sem Pluggy de verdade (a trava do `conftest` bloqueia a rede).

A chave da Pluggy alcança PIX, muda transação e apaga conexão. As perguntas aqui: alguma escrita
escapa da lista? O segredo aparece em algum texto? A página local aceita um ID que não veio da
janela da Pluggy?
"""

import ast
import io
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from lifeos import cli
from lifeos.financas import conectar, pluggy

ITEM = "0f8c2a3e-1b2c-4d5e-8f90-123456789abc"
OUTRO = "11111111-2222-4333-8444-555555555555"
SEGREDO = "segredo-do-dono-nao-pode-vazar"


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture()
def api(monkeypatch):
    """Pluggy falsa: `rotas[(método, caminho)] = (status, corpo)`; `pedidos` registra tudo."""
    estado = {
        "pedidos": [],
        "rotas": {
            ("POST", "/auth"): (200, {"apiKey": "chave-1"}),
            ("POST", "/connect_token"): (200, {"accessToken": "token-curto"}),
            ("GET", f"/items/{ITEM}"): (
                200,
                {"id": ITEM, "status": "UPDATED", "connector": {"name": "MeuPluggy"}},
            ),
            ("GET", "/accounts"): (200, {"results": [{"name": "Conta", "type": "BANK"}]}),
        },
    }

    def abrir(pedido):
        url = pedido.full_url.removeprefix(pluggy.API)
        caminho = url.split("?")[0]
        corpo = json.loads(pedido.data) if pedido.data else None
        estado["pedidos"].append((pedido.get_method(), url, dict(pedido.header_items()), corpo))
        status, resposta = estado["rotas"].get((pedido.get_method(), caminho), (404, {}))
        dados = json.dumps(resposta).encode()
        if status >= 400:
            raise urllib.error.HTTPError(pedido.full_url, status, "erro", {}, io.BytesIO(dados))
        return _Resposta(dados)

    monkeypatch.setattr(pluggy, "_abrir", abrir)
    return estado


def _cliente(relogio=None):
    return pluggy.Cliente("id-do-app", SEGREDO, **({"relogio": relogio} if relogio else {}))


# --- só lê, por construção -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("POST", "/payments/requests"),
        ("POST", "/payments/requests/pix-qr"),
        ("DELETE", f"/items/{ITEM}"),
        ("PATCH", "/transactions/x"),
        ("POST", "/webhooks"),
        ("PUT", f"/items/{ITEM}"),
        ("POST", "/items"),
    ],
)
def test_escrita_fora_da_lista_e_recusada_antes_da_rede(api, metodo, caminho):
    with pytest.raises(PermissionError):
        pluggy._pedir(metodo, caminho, chave="x")
    assert api["pedidos"] == []


def test_codigo_de_financas_so_chama_a_pluggy_com_get_ou_as_duas_escritas():
    """Lido do código: toda chamada a `_pedir` com método literal diferente de GET tem de ser uma
    das duas escritas permitidas — e ninguém fora de `pluggy.py` chama a rede."""
    pasta = Path(pluggy.__file__).parent
    for arquivo in pasta.glob("*.py"):
        arvore = ast.parse(arquivo.read_text())
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call) and getattr(no.func, "id", None) == "_pedir":
                primeiro, segundo = no.args[:2]
                assert isinstance(primeiro, ast.Constant), "método de `_pedir` tem de ser fixo"
                if primeiro.value != "GET":
                    assert isinstance(segundo, ast.Constant), "escrita com caminho montado"
                    assert (primeiro.value, segundo.value) in pluggy._ESCRITAS_PERMITIDAS
            if isinstance(no, ast.Attribute) and no.attr == "urlopen":
                assert arquivo.name == "pluggy.py"
    assert pluggy._ESCRITAS_PERMITIDAS == {("POST", "/auth"), ("POST", "/connect_token")}


# --- chave e segredo -------------------------------------------------------------------------


def test_chave_reaproveitada_e_renovada_antes_de_vencer(api):
    agora = {"t": 0.0}
    cliente = _cliente(relogio=lambda: agora["t"])
    cliente.conexao(ITEM)
    cliente.conexao(ITEM)
    assert [p[1] for p in api["pedidos"]].count("/auth") == 1
    assert api["pedidos"][1][2]["X-api-key"] == "chave-1"
    agora["t"] = pluggy.VALIDADE_CHAVE_S
    cliente.conexao(ITEM)
    assert [p[1] for p in api["pedidos"]].count("/auth") == 2


def test_segredo_nunca_aparece_em_erro_nem_em_repr(api):
    api["rotas"][("POST", "/auth")] = (
        401,
        {"message": f"clientSecret {SEGREDO} inválido", "codeDescription": "INVALID_CREDENTIALS"},
    )
    cliente = _cliente()
    with pytest.raises(pluggy.FalhaDaPluggy) as erro:
        cliente.conexao(ITEM)
    assert "401" in str(erro.value) and "INVALID_CREDENTIALS" in str(erro.value)
    assert SEGREDO not in str(erro.value) and SEGREDO not in repr(cliente)
    assert erro.value.__cause__ is None and erro.value.__suppress_context__


def test_sem_credenciais_diz_onde_por():
    with pytest.raises(pluggy.SemCredenciais, match="PLUGGY_CLIENT_ID"):
        pluggy.Cliente("", "")


@pytest.mark.parametrize("ruim", ["", "../payments/requests", f"{ITEM}/../../x", "abc", None])
def test_id_estranho_nao_vira_caminho(api, ruim):
    with pytest.raises(pluggy.EntradaInvalida):
        _cliente().conexao(ruim)
    assert api["pedidos"] == []


def test_id_em_maiusculas_e_normalizado():
    assert pluggy.id_valido(ITEM.upper()) == ITEM


def test_token_de_conexao(api):
    assert _cliente().token_de_conexao() == "token-curto"
    metodo, url, cabecalhos, corpo = api["pedidos"][-1]
    assert (metodo, url, corpo) == ("POST", "/connect_token", {})
    assert cabecalhos["X-api-key"] == "chave-1"


def test_resposta_sem_json_vira_falha_clara(api, monkeypatch):
    monkeypatch.setattr(pluggy, "_abrir", lambda _p: _Resposta(b"<html>"))
    with pytest.raises(pluggy.FalhaDaPluggy, match="não é JSON"):
        _cliente().conexao(ITEM)


def _falhando(estado, vezes, erro):
    """Troca o `_abrir` da Pluggy falsa por um que falha `vezes` vezes antes de responder."""
    responder = pluggy._abrir

    def abrir(pedido):
        estado["tentativas"] = estado.get("tentativas", 0) + 1
        if estado["tentativas"] <= vezes:
            raise erro
        return responder(pedido)

    return abrir


def test_leitura_com_falha_de_conexao_e_tentada_de_novo(api, monkeypatch):
    esperas = []
    monkeypatch.setattr(pluggy, "_esperar", esperas.append)
    cliente = _cliente()
    cliente._chave_valida()  # a chave antes, para contar só o GET
    monkeypatch.setattr(pluggy, "_abrir", _falhando(api, 2, urllib.error.URLError("timed out")))
    assert cliente.conexao(ITEM)["status"] == "UPDATED"
    assert (api["tentativas"], esperas) == (3, list(pluggy.ESPERAS_S))


def test_leitura_que_nao_volta_diz_o_motivo_e_as_tentativas(api, monkeypatch):
    cliente = _cliente()
    cliente._chave_valida()
    monkeypatch.setattr(pluggy, "_abrir", _falhando(api, 9, urllib.error.URLError("timed out")))
    with pytest.raises(pluggy.FalhaDaPluggy) as erro:
        cliente.conexao(ITEM)
    assert str(erro.value) == "sem resposta da Pluggy (URLError: timed out, 3 tentativas)"
    assert SEGREDO not in str(erro.value) and "chave-1" not in str(erro.value)


def test_escrita_com_falha_de_conexao_nunca_repete(api, monkeypatch):
    monkeypatch.setattr(pluggy, "_abrir", _falhando(api, 1, urllib.error.URLError("reset")))
    with pytest.raises(pluggy.FalhaDaPluggy, match=r"^sem resposta da Pluggy \(URLError: reset\)$"):
        _cliente().token_de_conexao()  # o POST /auth falhou uma vez: não tenta de novo
    assert api["tentativas"] == 1


def test_erro_http_nao_repete(api):
    with pytest.raises(pluggy.FalhaDaPluggy, match="404"):
        _cliente().conexao(OUTRO)
    assert [p[1] for p in api["pedidos"]].count(f"/items/{OUTRO}") == 1


# --- a página local ---------------------------------------------------------------------------


def test_pagina_ja_abre_no_meupluggy_sem_sandbox():
    texto = conectar.pagina("tok", "seg")
    assert '"connectorIds": [200]' in texto and '"selectedConnectorId": 200' in texto
    assert '"includeSandbox": false' in texto
    assert conectar.SCRIPT in texto and "new PluggyConnect(opcoes).init()" in texto


def test_token_malicioso_nao_fecha_o_script():
    texto = conectar.pagina('x"</script><script>alert(1)</script>', "seg")
    assert "</script><script>alert" not in texto
    assert texto.count("</script>") == 2  # a do script externo e a do nosso


# --- o servidor local, de verdade, em 127.0.0.1 ------------------------------------------------


def _rodar(acoes, **opcoes):
    """Sobe `servir` e executa `acoes(url)` no navegador de mentira."""
    visto = {}

    def abrir(url):
        visto["url"] = url
        threading.Thread(target=acoes, args=(url,), daemon=True).start()

    resultado = conectar.servir("tok", abrir=abrir, **opcoes)
    return resultado, visto["url"]


def _post(url, corpo):
    dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=dados, method="POST")) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def test_widget_devolve_o_id_ao_terminal():
    codigos = {}

    def acoes(url):
        codigos["pagina"] = _get(url)
        codigos["errado"] = _get(url.rsplit("/", 1)[0] + "/outro")[0]
        codigos["ok"] = _post(url + "/ok", {"id": ITEM})

    resultado, url = _rodar(acoes, espera_s=5)
    assert url.startswith("http://127.0.0.1:")
    assert codigos["pagina"][0] == 200 and "PluggyConnect" in codigos["pagina"][1]
    assert codigos["errado"] == 404 and codigos["ok"] == 204
    assert resultado.item_id == ITEM


def test_id_mandado_por_outra_aba_sem_o_segredo_e_ignorado():
    """Outra página aberta no navegador poderia mandar POST para a porta local: sem o caminho
    aleatório, 404 — e o terminal continua esperando."""
    codigos = {}

    def acoes(url):
        porta = url.split("/")[2]
        codigos["sem_segredo"] = _post(f"http://{porta}/ok", {"id": OUTRO})
        codigos["segredo_errado"] = _post(f"http://{porta}/xyz/ok", {"id": OUTRO})

    resultado, _ = _rodar(acoes, espera_s=0.5)
    assert codigos == {"sem_segredo": 404, "segredo_errado": 404}
    assert resultado.item_id is None


@pytest.mark.parametrize("corpo", [{"id": "../../x"}, {"id": None}, b"nao-json", ["lista"]])
def test_id_invalido_do_widget_e_recusado(corpo):
    codigos = {}

    def acoes(url):
        codigos["resposta"] = _post(url + "/ok", corpo)

    resultado, _ = _rodar(acoes, espera_s=0.5)
    assert codigos["resposta"] == 400 and resultado.item_id is None


def test_corpo_grande_recusado():
    codigos = {}

    def acoes(url):
        codigos["resposta"] = _post(url + "/ok", b"x" * (conectar.MAX_CORPO + 1))

    _rodar(acoes, espera_s=0.5)
    assert codigos["resposta"] == 413


def test_fechou_antes_do_id_chegar_ainda_pega_o_id():
    """O widget chama onSuccess e onClose; os avisos são assíncronos e o "fechou" pode chegar
    primeiro. Sem a tolerância, o terminal diria "fechou sem conectar" com a conexão criada."""

    def acoes(url):
        _post(url + "/fechou", {})
        time.sleep(0.5)  # o ID chega depois: sem a tolerância, o servidor já teria fechado
        _post(url + "/ok", {"id": ITEM})

    resultado, _ = _rodar(acoes, espera_s=5, tolerancia_s=3)
    assert resultado.item_id == ITEM


def test_fechou_sem_conectar():
    resultado, _ = _rodar(lambda url: _post(url + "/fechou", {}), espera_s=5, tolerancia_s=0.2)
    assert resultado.fechou and resultado.item_id is None


def test_erro_do_widget_chega_ao_terminal():
    resultado, _ = _rodar(lambda url: _post(url + "/erro", {"mensagem": "x" * 500}), espera_s=5)
    assert resultado.erro == "x" * 200


# --- CLI -------------------------------------------------------------------------------------


def _financas(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["viking", "financas", *args])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


@pytest.fixture()
def credenciais(monkeypatch, api):
    monkeypatch.setattr("lifeos.config.PLUGGY_CLIENT_ID", "id-do-app")
    monkeypatch.setattr("lifeos.config.PLUGGY_CLIENT_SECRET", SEGREDO)
    return api


def test_cli_conectar_mostra_a_linha_do_env_somando_o_que_ja_tinha(
    credenciais, monkeypatch, capsys
):
    monkeypatch.setattr("lifeos.config.PLUGGY_ITEM_IDS", (OUTRO,))
    resultado = conectar.Resultado()
    resultado.item_id = ITEM
    monkeypatch.setattr(conectar, "servir", lambda token, abrir: resultado)
    assert _financas(monkeypatch, "--conectar") == 0
    saida = capsys.readouterr().out
    assert "✅ Conectado: MeuPluggy: UPDATED" in saida
    assert f"PLUGGY_ITEM_IDS={OUTRO},{ITEM}" in saida
    assert SEGREDO not in saida


def test_cli_conectar_janela_fechada_sai_com_1(credenciais, monkeypatch, capsys):
    resultado = conectar.Resultado()
    resultado.fechou = True
    monkeypatch.setattr(conectar, "servir", lambda token, abrir: resultado)
    assert _financas(monkeypatch, "--conectar") == 1
    assert "fechada sem conectar" in capsys.readouterr().out


def test_cli_conferir_sem_ids_explica(credenciais, monkeypatch, capsys):
    monkeypatch.setattr("lifeos.config.PLUGGY_ITEM_IDS", ())
    assert _financas(monkeypatch) == 1
    assert "viking financas --conectar" in capsys.readouterr().out


def test_cli_conferir_mostra_cada_conexao_e_falha_alto(credenciais, monkeypatch, capsys):
    monkeypatch.setattr("lifeos.config.PLUGGY_ITEM_IDS", (ITEM, OUTRO))
    assert _financas(monkeypatch) == 2  # OUTRO dá 404 na Pluggy falsa
    saida = capsys.readouterr().out
    assert "MeuPluggy: UPDATED" in saida and "1 conta(s)" in saida
    assert "❌ 11111111…: a Pluggy respondeu 404" in saida


def test_cli_sem_credenciais_sai_com_2(monkeypatch, capsys):
    monkeypatch.setattr("lifeos.config.PLUGGY_CLIENT_ID", "")
    assert _financas(monkeypatch) == 2
    assert "PLUGGY_CLIENT_ID" in capsys.readouterr().err


def test_nenhum_teste_fala_com_a_pluggy_de_verdade():
    with pytest.raises(AssertionError, match="Google de verdade|use o fake"):
        pluggy._abrir(None)
