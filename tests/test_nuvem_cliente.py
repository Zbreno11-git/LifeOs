"""O cliente da nuvem no Mac (Sessão 10, D58): `viking lembretes --nuvem`.

Sem rede: a sessão HTTP é trocada por um dublê. O que se prova: o token pedido é o do
`viking-cli@`, com a audience = a URL do motor, o e-mail dentro e a cota no projeto do Viking;
cada falha vira uma linha para o dono (e saída 1), nunca um traceback nem o token; os instantes
chegam com fuso e saem no fuso do dono; um título com controle de terminal sai limpo.
"""

import sys
from zoneinfo import ZoneInfo

import pytest

from lifeos import config
from lifeos.nuvem import cliente

PROJETO = "viking-teste"
URL = "https://motor-42.southamerica-east1.run.app"


@pytest.fixture(autouse=True)
def _nuvem(monkeypatch):
    monkeypatch.setattr(config, "NUVEM_PROJETO", PROJETO)
    monkeypatch.setattr(config, "NUVEM_URL", URL)
    monkeypatch.setattr(config, "TIMEZONE", ZoneInfo("America/Los_Angeles"))


class _Resposta:
    def __init__(self, status, dados=None, texto=""):
        self.status_code, self._dados, self.text = status, dados, texto

    def json(self):
        if self._dados is None:
            raise ValueError("não é JSON")
        return self._dados


class _Sessao:
    """Uma resposta para tudo, menos o `/versao` (o que o motor tem: `versao`), que o `--nuvem`
    pergunta antes da lista (Sessão 11) e não entra em `pedidos`."""

    def __init__(self, resposta=None, erro=None, versao=None):
        self.resposta, self.erro, self.pedidos = resposta, erro, []
        self.versao = {"envio_de_lembretes": False} if versao is None else versao

    def request(self, metodo, url, json=None, timeout=None):
        if self.erro:
            raise self.erro
        if url == f"{URL}/versao":
            return _Resposta(200, self.versao)
        self.pedidos.append((url, timeout) if metodo == "GET" else (metodo, url, json, timeout))
        return self.resposta


def _lembrete(**mudancas):
    item = {
        "id": "1f0c0e7e-0000-4000-8000-000000000001",
        "type": "reminder",
        "title": "Dentista",
        "body": "",
        "tags": [],
        "due_at": "2026-10-01T17:00:00+00:00",
        "created_at": "2026-09-29T12:00:00+00:00",
        "enviado_em": None,
        "envio_estado": None,
    }
    item.update(mudancas)
    return item


def _rodar(monkeypatch):
    from lifeos import cli

    monkeypatch.setattr(sys, "argv", ["viking", "lembretes", "--nuvem"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


def test_lista_no_fuso_do_dono(monkeypatch, capsys):
    sessao = _Sessao(_Resposta(200, {"lembretes": [_lembrete()]}))
    monkeypatch.setattr(cliente, "_sessao", lambda: sessao)

    assert _rodar(monkeypatch) == 0

    assert sessao.pedidos == [(f"{URL}/lembretes", cliente.PRAZO_S)]
    saida = capsys.readouterr().out
    assert "☁️" in saida and "- Dentista (01/10/2026 10:00)" in saida  # 17:00Z = 10:00 em Seattle


def test_titulo_com_controle_de_terminal_sai_limpo(monkeypatch, capsys):
    titulo = "Dentista" + chr(0x1B) + "]0;hack" + chr(7)
    sessao = _Sessao(_Resposta(200, {"lembretes": [_lembrete(title=titulo)]}))
    monkeypatch.setattr(cliente, "_sessao", lambda: sessao)
    assert _rodar(monkeypatch) == 0
    assert chr(0x1B) not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("resposta", "erro", "trecho"),
    [
        (_Resposta(403, texto="Forbidden"), None, "recusou a identidade (HTTP 403)"),
        (_Resposta(401, texto="token recusado"), None, "recusou a identidade (HTTP 401)"),
        (_Resposta(500), None, "HTTP 500"),
        (_Resposta(200, None), None, "não é JSON"),
        (_Resposta(200, ["lista"]), None, "formato inesperado"),
        (_Resposta(200, {"lembretes": [{"id": "x"}]}), None, "formato inesperado"),
        (
            _Resposta(200, {"lembretes": [_lembrete(due_at="2026-10-01T17:00:00")]}),
            None,
            "sem fuso",
        ),
    ],
)
def test_cada_falha_vira_uma_linha_e_saida_1(monkeypatch, capsys, resposta, erro, trecho):
    monkeypatch.setattr(cliente, "_sessao", lambda: _Sessao(resposta, erro))
    assert _rodar(monkeypatch) == 1
    saida = capsys.readouterr()
    assert trecho in saida.err and "Traceback" not in saida.err
    assert saida.out == ""


def test_rede_fora_vira_uma_linha(monkeypatch, capsys):
    import requests

    monkeypatch.setattr(cliente, "_sessao", lambda: _Sessao(erro=requests.ConnectionError("x")))
    assert _rodar(monkeypatch) == 1
    assert "não respondeu" in capsys.readouterr().err


def test_sem_configuracao_diz_o_que_falta(monkeypatch, capsys):
    monkeypatch.setattr(config, "NUVEM_URL", "")
    assert _rodar(monkeypatch) == 1
    assert "VIKING_NUVEM_URL" in capsys.readouterr().err


def test_o_token_e_do_viking_cli_com_audience_e_cota_no_viking(monkeypatch):
    """O `_sessao` de verdade, com o Google trocado por dublês que gravam o que receberam."""
    import google.auth
    from google.auth import impersonated_credentials

    gravado = {}

    class Dono:
        def with_quota_project(self, projeto):
            gravado["cota"] = projeto
            return self

    def credenciais(**kwargs):
        gravado["terminal"] = kwargs
        return "terminal"

    def id_token(alvo, **kwargs):
        gravado["id_token"] = (alvo, kwargs)
        return "id-token"

    monkeypatch.setattr(google.auth, "default", lambda scopes: (Dono(), "outro-projeto"))
    monkeypatch.setattr(impersonated_credentials, "Credentials", credenciais)
    monkeypatch.setattr(impersonated_credentials, "IDTokenCredentials", id_token)
    monkeypatch.setattr(
        "google.auth.transport.requests.AuthorizedSession", lambda token: ("sessao", token)
    )

    assert cliente._sessao() == ("sessao", "id-token")
    assert gravado["cota"] == PROJETO  # não o projeto padrão do gcloud do dono
    assert (
        gravado["terminal"]["target_principal"] == f"viking-cli@{PROJETO}.iam.gserviceaccount.com"
    )
    assert gravado["terminal"]["lifetime"] <= 3600
    assert gravado["id_token"] == ("terminal", {"target_audience": URL, "include_email": True})


def test_sem_login_do_google_cloud_diz_o_comando(monkeypatch, capsys):
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    def sem_login(scopes):
        raise DefaultCredentialsError("nada")

    monkeypatch.setattr(google.auth, "default", sem_login)
    assert _rodar(monkeypatch) == 1
    assert "gcloud auth application-default login" in capsys.readouterr().err


def test_nuvem_e_enviar_nao_andam_juntos(monkeypatch):
    from lifeos import cli

    monkeypatch.setattr(sys, "argv", ["viking", "lembretes", "--nuvem", "--enviar"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 2  # o argparse recusa antes de qualquer coisa


# --- o turno de chat (Sessão 10b) ---------------------------------------------------------


def test_turno_de_chat_vai_por_post_com_a_conversa_no_corpo_e_o_prazo_longo():
    sessao = _Sessao(_Resposta(200, {"resposta": "ok", "historico": []}))
    pedido = {"mensagem": "oi", "historico": [], "nota": "", "sessao": "ab", "numero": 1}
    assert cliente.turno_de_chat(sessao, pedido)["resposta"] == "ok"
    ((metodo, url, corpo, prazo),) = sessao.pedidos
    assert (metodo, url, corpo) == ("POST", f"{URL}/chat", pedido)
    assert prazo == cliente.PRAZO_CHAT_S > 300  # acima do --timeout do motor


def test_erro_do_motor_chega_com_o_motivo():
    sessao = _Sessao(_Resposta(413, {"erro": "a conversa passou do tamanho que o motor aceita"}))
    with pytest.raises(cliente.ErroDaNuvem, match="HTTP 413: a conversa passou do tamanho"):
        cliente.turno_de_chat(sessao, {})


def test_prazo_esgotado_avisa_que_o_motor_pode_ter_agido():
    import requests

    sessao = _Sessao(erro=requests.Timeout("lento"))
    with pytest.raises(cliente.ErroDaNuvem, match="pode ter agido"):
        cliente.turno_de_chat(sessao, {})


@pytest.mark.parametrize("ligado", [False, True])
def test_o_aviso_do_email_segue_o_envio_da_nuvem(monkeypatch, capsys, ligado):
    """Sem o agendador, a lista avisa que o e-mail não sai; com ele ligado, o aviso some (Sessão
    11): o texto não promete o que o mecanismo não faz, nem nega o que ele faz."""
    versao = {"envio_de_lembretes": ligado}
    sessao = _Sessao(_Resposta(200, {"lembretes": [_lembrete()]}), versao=versao)
    monkeypatch.setattr(cliente, "_sessao", lambda: sessao)
    assert _rodar(monkeypatch) == 0
    aviso = "o aviso por e-mail destes ainda não está ligado na nuvem"
    assert (aviso in capsys.readouterr().out) is not ligado
