"""O backup pela nuvem (Sessão 11c, D63): `POST /tarefas/backup` no motor em processo, com o
Firestore do emulador e o Drive falso.

As perguntas: só o agendador dispara? O arquivo que sobe se lê de volta, com as três coleções? A
resposta e o log ficam sem título? Uma falha do Drive deixa o "último backup" como estava (a falha
aparece como backup velho, nunca como sucesso)?
"""

import logging
from datetime import UTC, datetime

import pytest
from tests.drive_falso import DriveFalso
from tests.sentinela import aparece

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from starlette.testclient import TestClient
from tests import test_motor as motor_base
from tests.test_lembretes_nuvem import CONTAS, _contexto_limpo, _do_lado_da_nuvem  # noqa: F401

from lifeos import config, custos, registro
from lifeos.backup import drive, formato, rodada
from lifeos.nuvem import motor

_nuvem = motor_base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google
TITULO = "Consulta secreta 5823"


@pytest.fixture
def falso(firestore_limpo, monkeypatch):
    dublê = DriveFalso()
    monkeypatch.setattr(drive, "_servico", lambda: dublê)
    monkeypatch.setattr(config, "DRIVE_TOKEN_ARQUIVO", "/segredos/drive/token.json")
    return dublê


def _backup(conta="agendador"):
    token = motor_base._token(email=CONTAS[conta])
    with _do_lado_da_nuvem():
        return TestClient(motor.app).post(
            "/tarefas/backup", headers={"Authorization": f"Bearer {token}"}
        )


def _versao():
    token = motor_base._token(email=CONTAS["cli"])
    with _do_lado_da_nuvem():
        return TestClient(motor.app).get("/versao", headers={"Authorization": f"Bearer {token}"})


def _um_de_cada():
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title=TITULO, due_at=datetime(2026, 10, 8, 15, tzinfo=UTC))
        token = registro.ORIGEM.set("chat")
        with registro.acao("lembrete.criar", {"titulo": TITULO}) as marca:
            marca.feito()
        registro.ORIGEM.reset(token)
        custos.Teto(mes=10, dia=1, fuso=UTC).somar(0.01)


@pytest.mark.parametrize("conta", ["cli", "maos"])
def test_so_o_agendador_dispara_o_backup(falso, conta):
    _um_de_cada()
    assert _backup(conta).status_code == 403
    assert falso.arquivos == []


def test_o_backup_sobe_um_arquivo_que_se_le_de_volta(falso, caplog):
    _um_de_cada()
    with caplog.at_level(logging.INFO):
        resposta = _backup()
    assert resposta.status_code == 200
    (arquivo,) = falso.de_backup()
    assert resposta.json() == {
        "arquivo": arquivo["name"],
        "lembretes": 1,
        "acoes": 1,
        "gastos": 1,
    }
    assert not aparece("5823", resposta.text) and not aparece("5823", caplog.text)
    backup = formato.de_bytes(arquivo["conteudo"])
    assert [r.title for r in backup.lembretes] == [TITULO]
    assert [a["operacao"] for a in backup.acoes] == ["lembrete.criar"]
    assert [g["mes"] for g in backup.gastos] == [f"{datetime.now(UTC):%Y-%m}"]


def test_o_ultimo_backup_aparece_no_versao(falso):
    antes = _versao().json()
    assert (antes["backup"], antes["backup_em"]) == (True, None)
    assert _backup().status_code == 200
    depois = _versao().json()
    assert depois["backup"] is True
    assert datetime.fromisoformat(depois["backup_em"]) > datetime.now(UTC).replace(hour=0)


def test_sem_o_token_do_drive_o_versao_diz_que_nao_ha_backup(falso, monkeypatch):
    monkeypatch.setattr(config, "DRIVE_TOKEN_ARQUIVO", "")
    assert (_versao().json()["backup"], _versao().json()["backup_em"]) == (False, None)


@pytest.mark.parametrize(("status", "estado"), [(500, "incerta"), (403, "falhou")])
def test_drive_que_falha_nao_marca_o_backup(falso, caplog, status, estado):
    _um_de_cada()
    falso.falhar_no_create = status
    with caplog.at_level(logging.INFO):
        resposta = _backup()
    assert resposta.status_code == 500
    assert resposta.json() == {"erro": "o backup falhou (FalhaDoDrive)"}
    assert not aparece("5823", caplog.text)
    with _do_lado_da_nuvem():
        assert rodada.ultimo() is None
        (acao,) = [a for a in registro.recentes() if a.operacao == "backup.drive"]
    assert acao.estado == estado
    assert _versao().json()["backup_em"] is None
