"""O motor da nuvem (Sessão 10, D58): a segunda parede, depois do IAM do Cloud Run.

A verificação é a de verdade (`google.oauth2.id_token.verify_token`): os tokens são assinados aqui
com uma chave RSA gerada por teste, e a busca dos certificados do Google devolve a chave pública
dela. Assim um token de outra chave, de outra audience, vencido, de outro emissor ou de outra
conta cai pelo mesmo caminho que cairia no Cloud Run. Nada sai para a rede.
"""

import ast
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from starlette.testclient import TestClient

from lifeos import config
from lifeos.nuvem import motor
from lifeos.reminders import service

PROJETO = "viking-teste"
URL = "https://motor-123.southamerica-east1.run.app"
CLI = f"viking-cli@{PROJETO}.iam.gserviceaccount.com"


def _chave():
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = privada.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    publica = (
        privada.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return crypt.RSASigner.from_string(pem, key_id="k1"), publica


GOOGLE, CERTIFICADO = _chave()
INTRUSO, _ = _chave()


@pytest.fixture(autouse=True)
def _nuvem(monkeypatch):
    monkeypatch.setattr(config, "NUVEM_PROJETO", PROJETO)
    monkeypatch.setattr(config, "NUVEM_URL", URL)
    monkeypatch.setattr(
        "google.oauth2.id_token._fetch_certs", lambda _req, _url: {"k1": CERTIFICADO}
    )
    monkeypatch.setattr(motor, "COMMIT", "abc123")


def _token(assinante=GOOGLE, **mudancas):
    agora = int(time.time())
    dados = {
        "iss": "https://accounts.google.com",
        "aud": URL,
        "email": CLI,
        "email_verified": True,
        "iat": agora,
        "exp": agora + 3600,
        "sub": "1",
    }
    dados.update(mudancas)
    return jwt.encode(assinante, dados).decode()


@pytest.fixture
def cliente():
    return TestClient(motor.app)


def _get(cliente, rota, token=None, cabecalho=None):
    cabecalhos = {"Authorization": cabecalho or f"Bearer {token}"} if (token or cabecalho) else {}
    return cliente.get(rota, headers=cabecalhos)


def test_o_terminal_do_dono_entra(cliente):
    resposta = _get(cliente, "/versao", _token())
    assert resposta.status_code == 200
    assert resposta.json() == {"commit": "abc123"}


@pytest.mark.parametrize(
    ("caso", "cabecalho"),
    [
        ("sem cabeçalho", None),
        ("outro esquema", "Basic dXNlcjpzZW5oYQ=="),
        ("bearer vazio", "Bearer "),
        ("lixo", "Bearer nao.e.um.jwt"),
    ],
)
def test_sem_token_valido_401(cliente, caso, cabecalho):
    resposta = cliente.get("/versao", headers={"Authorization": cabecalho} if cabecalho else {})
    assert resposta.status_code == 401, caso


@pytest.mark.parametrize(
    ("caso", "token"),
    [
        ("assinado por outra chave", lambda: _token(INTRUSO)),
        ("outra audience", lambda: _token(aud="https://outro.run.app")),
        ("vencido", lambda: _token(iat=int(time.time()) - 7200, exp=int(time.time()) - 3600)),
        ("outro emissor", lambda: _token(iss="https://evil.example.com")),
        (
            "assinatura removida (o X-Serverless-Authorization)",
            lambda: _token().rsplit(".", 1)[0] + ".SIGNATURE_REMOVED_BY_GOOGLE",
        ),
    ],
)
def test_token_que_nao_vale_401(cliente, caso, token):
    assert _get(cliente, "/versao", token()).status_code == 401, caso


@pytest.mark.parametrize(
    ("caso", "mudancas"),
    [
        ("o dono em pessoa (não é o terminal)", {"email": "dono@example.com"}),
        (
            "outra conta de serviço do projeto",
            {"email": f"viking-motor@{PROJETO}.iam.gserviceaccount.com"},
        ),
        ("o cli@ de outro projeto", {"email": "viking-cli@outro.iam.gserviceaccount.com"}),
        ("e-mail não verificado", {"email_verified": False}),
        ("sem e-mail", {"email": None}),
    ],
)
def test_token_valido_de_quem_nao_pode_403(cliente, caso, mudancas):
    assert _get(cliente, "/versao", _token(**mudancas)).status_code == 403, caso


def test_sem_url_configurada_ninguem_entra(cliente, monkeypatch):
    monkeypatch.setattr(config, "NUVEM_URL", "")
    assert _get(cliente, "/versao", _token()).status_code == 401


def test_sem_projeto_configurado_ninguem_entra(cliente, monkeypatch):
    monkeypatch.setattr(config, "NUVEM_PROJETO", "")
    assert _get(cliente, "/versao", _token()).status_code == 403


def test_lembretes_em_utc_e_a_recusa_nao_loga_conteudo(cliente, caplog):
    service.criar_lembrete("Dentista secreto", quando="2026-10-01T10:00:00-03:00")
    caplog.set_level(logging.DEBUG)

    resposta = _get(cliente, "/lembretes", _token())
    recusa = _get(cliente, "/lembretes", _token(email="intruso@example.com"))

    assert resposta.status_code == 200
    ((lembrete),) = resposta.json()["lembretes"]
    assert lembrete["title"] == "Dentista secreto"
    assert lembrete["due_at"] == datetime(2026, 10, 1, 13, 0, tzinfo=UTC).isoformat()
    assert recusa.status_code == 403
    assert "Dentista" not in caplog.text and "intruso" not in caplog.text


def test_fumaca_dos_vencidos_so_conta(cliente):
    service.criar_lembrete("Pagar luz", quando=datetime.now(UTC).isoformat())
    resposta = _get(cliente, "/fumaca/vencidos", _token())
    assert resposta.json() == {"vencidos_24h": 1}


def test_toda_rota_comeca_por_quem(cliente):
    """A guarda é a primeira instrução (skill `seguranca` §1): lendo o código, toda função que é
    endpoint de uma rota começa por `_quem(request)` (depois da docstring, se houver). Uma rota
    nova sem ela reprova aqui, não em produção."""
    arvore = ast.parse(Path(motor.__file__).read_text())
    funcoes = {n.name: n for n in ast.walk(arvore) if isinstance(n, ast.AsyncFunctionDef)}
    endpoints = [rota.endpoint.__name__ for rota in motor.ROTAS]
    assert len(endpoints) >= 3
    for nome in endpoints:
        corpo = funcoes[nome].body
        if isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
            corpo = corpo[1:]  # a docstring
        primeira = ast.unparse(corpo[0])
        assert primeira == "_quem(request)", (nome, primeira)
    # e nenhuma rota fora da lista (um `app.add_route` escondido)
    assert "add_route" not in Path(motor.__file__).read_text()
