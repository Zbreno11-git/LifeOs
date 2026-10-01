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


def test_o_terminal_do_dono_entra(cliente, monkeypatch):
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "")
    resposta = _get(cliente, "/versao", _token())
    assert resposta.status_code == 200
    assert resposta.json() == {
        "commit": "abc123",
        "gmail": False,
        "maos": True,
        "envio_de_lembretes": False,
    }
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "/segredos/gmail/token.json")
    assert _get(cliente, "/versao", _token()).json()["gmail"] is True


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
        ("as mãos do Mac", {"email": f"viking-maos@{PROJETO}.iam.gserviceaccount.com"}),
        ("o agendador", {"email": f"viking-agendador@{PROJETO}.iam.gserviceaccount.com"}),
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
    assert len(endpoints) >= 6 and "chat" in endpoints
    for nome in endpoints:
        corpo = funcoes[nome].body  # todo endpoint é `async` (o trabalho vai para uma thread)
        if isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
            corpo = corpo[1:]  # a docstring
        primeira = ast.unparse(corpo[0])
        assert primeira == "await _quem(request)", (nome, primeira)
    # e nenhuma rota fora da lista (um `app.add_route` escondido)
    assert "add_route" not in Path(motor.__file__).read_text()


def test_toda_rota_tem_quem_fala_e_so_ela():
    """Sessão 11 (D61): cada rota diz quem fala com ela, e o mapa não tem rota que não existe."""
    caminhos = {rota.path for rota in motor.ROTAS}
    assert set(motor.QUEM_FALA) == caminhos
    assert all(motor.QUEM_FALA[c] for c in caminhos)
    assert all(
        conta in {motor.CLI, motor.MAOS, motor.AGENDADOR}
        for c in caminhos
        for conta in motor.QUEM_FALA[c]
    )


def test_rota_fora_do_mapa_nao_tem_ninguem(monkeypatch):
    assert motor.quem_pode("/nao-existe") == frozenset()
    assert motor.quem_pode("/versao/") == frozenset()  # a barra a mais não é a mesma porta


@pytest.mark.parametrize("rota", ["/versao", "/lembretes", "/fumaca/segredos"])
def test_as_maos_e_o_agendador_nao_entram_nas_portas_do_terminal(cliente, rota):
    for conta in ("viking-maos", "viking-agendador"):
        token = _token(email=f"{conta}@{PROJETO}.iam.gserviceaccount.com")
        assert _get(cliente, rota, token).status_code == 403, (conta, rota)


# --- Sessão 10b: o chat, e as fumaças do registro e dos segredos ----------------------------


def _post(cliente, corpo, token=None, **extra):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post("/chat", content=corpo, headers=cabecalhos | extra)


@pytest.fixture
def turno_falso(monkeypatch):
    recebidos = []

    def turno(dados):
        recebidos.append(dados)
        if dados.get("mensagem") == "torto":
            raise ValueError("a mensagem tem de ser um texto")
        if dados.get("mensagem") == "quebra":
            raise RuntimeError("segredo do dono: Dentista secreto")
        return {"resposta": "ok", "historico": [], "nota": "", "erro": ""}

    monkeypatch.setattr(motor, "_turno", turno)
    return recebidos


def test_chat_sem_token_e_de_outra_conta_nao_chega_ao_turno(cliente, turno_falso):
    corpo = b'{"mensagem": "oi"}'
    assert _post(cliente, corpo).status_code == 401
    assert _post(cliente, corpo, _token(email="intruso@example.com")).status_code == 403
    maos = _token(email=f"viking-maos@{PROJETO}.iam.gserviceaccount.com")
    assert _post(cliente, corpo, maos).status_code == 403  # as mãos não leem a conversa
    assert turno_falso == []


def test_chat_do_terminal_roda_o_turno(cliente, turno_falso):
    resposta = _post(cliente, b'{"mensagem": "oi"}', _token())
    assert resposta.status_code == 200 and resposta.json()["resposta"] == "ok"
    assert turno_falso == [{"mensagem": "oi"}]


def test_chat_so_aceita_post(cliente, turno_falso):
    assert _get(cliente, "/chat", _token()).status_code == 405


def test_corpo_grande_demais_e_recusado_sem_ler(cliente, turno_falso, monkeypatch):
    monkeypatch.setattr(motor, "MAX_CORPO", 100)
    grande = b'{"mensagem": "' + b"x" * 200 + b'"}'
    assert _post(cliente, grande, _token()).status_code == 413
    assert turno_falso == []


def test_corpo_que_nao_e_json_e_400(cliente, turno_falso):
    resposta = _post(cliente, b"isto nao e json", _token())
    assert resposta.status_code == 400 and "JSON" in resposta.json()["erro"]


def test_pedido_torto_e_400_e_falha_e_500_sem_conteudo_no_log(cliente, turno_falso, caplog):
    caplog.set_level(logging.DEBUG)
    torto = _post(cliente, b'{"mensagem": "torto"}', _token())
    assert torto.status_code == 400
    quebra = _post(cliente, b'{"mensagem": "quebra"}', _token())
    assert quebra.status_code == 500
    assert quebra.json() == {"erro": "o motor falhou (RuntimeError)"}
    assert "Dentista" not in caplog.text and "quebra" not in caplog.text


def test_fumaca_do_registro_exerce_cada_consulta(cliente):
    resposta = _get(cliente, "/fumaca/registro", _token())
    assert resposta.status_code == 200
    assert set(resposta.json()) == {
        "do_turno",
        "recentes",
        "contaveis",
        "ultima_desfazivel",
        "obter",
    }


def test_fumaca_dos_segredos_so_diz_se_le(cliente, monkeypatch, tmp_path):
    chave = tmp_path / "chave"
    chave.write_text("AIza-segredo-de-teste\n")
    monkeypatch.setattr(config, "GEMINI_CHAVE_ARQUIVO", str(chave))
    monkeypatch.setattr(config, "AGENDA_TOKEN_ARQUIVO", "")
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "")
    monkeypatch.setattr(config, "_SEGREDOS", {})
    resposta = _get(cliente, "/fumaca/segredos", _token())
    assert resposta.status_code == 200
    assert resposta.json() == {"gemini": True, "agenda": False, "gmail": False}
    assert "AIza" not in resposta.text


def test_corpo_em_partes_sem_tamanho_declarado_tambem_tem_teto(cliente, turno_falso, monkeypatch):
    """Sem `Content-Length` (o corpo chega em partes) só a segunda conferência barra."""
    monkeypatch.setattr(motor, "MAX_CORPO", 100)

    def partes():
        yield b'{"mensagem": "'
        yield b"x" * 200
        yield b'"}'

    resposta = cliente.post(
        "/chat", content=partes(), headers={"Authorization": f"Bearer {_token()}"}
    )
    assert resposta.status_code == 413
    assert turno_falso == []
