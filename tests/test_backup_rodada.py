"""O backup pela nuvem (Sessão 11c, D63): `POST /tarefas/backup` no motor em processo, com o
Firestore do emulador e o Drive falso.

As perguntas: só o agendador dispara? O arquivo que sobe se lê de volta, com as três coleções? A
resposta e o log ficam sem título? Uma falha do Drive deixa o "último backup" como estava (a falha
aparece como backup velho, nunca como sucesso)? E, desde a resposta do dono de 2026-10-07: um dia
sem mudança não cria arquivo, mas conta como backup em dia; qualquer mudança, um arquivo apagado à
mão ou um que não se lê criam um novo?
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
        "novo": True,
        "lembretes": 1,
        "acoes": 1,
        "gastos": 1,
        "memoria": 0,
        "receitas": 0,
        "documentos": 0,
        "trechos": 0,
    }
    assert not aparece("5823", resposta.text) and not aparece("5823", caplog.text)
    backup = formato.de_bytes(arquivo["conteudo"])
    assert [r.title for r in backup.lembretes] == [TITULO]
    assert [a["operacao"] for a in backup.acoes] == ["lembrete.criar"]
    assert [g["mes"] for g in backup.gastos] == [f"{datetime.now(UTC):%Y-%m}"]


def test_o_ultimo_backup_aparece_no_versao(falso):
    antes = _versao().json()
    assert (antes["backup"], antes["backup_em"]) == (True, None)
    # o instante de antes da rodada (até 2026-10-08 era "hoje com a hora trocada por 0", que entre
    # 00:00 e 01:00 UTC é o próprio agora: o teste caía nessa hora)
    inicio = datetime.now(UTC)
    assert _backup().status_code == 200
    depois = _versao().json()
    assert depois["backup"] is True
    assert datetime.fromisoformat(depois["backup_em"]) >= inicio


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


# --- um arquivo novo só quando algo mudou (resposta do dono, 2026-10-07) -----------------------


def _ultimo_estado():
    with _do_lado_da_nuvem():
        return rodada._ref().get().to_dict()


def test_sem_mudanca_nao_cria_arquivo_mas_o_backup_fica_em_dia(falso):
    _um_de_cada()
    primeiro = _backup().json()
    antes = _ultimo_estado()["ultimo"]
    segundo = _backup()
    assert segundo.status_code == 200
    assert segundo.json() == {**primeiro, "novo": False}
    assert len(falso.de_backup()) == 1
    estado = _ultimo_estado()
    assert estado["novo"] is False and estado["arquivo"] == primeiro["arquivo"]
    assert estado["ultimo"] > antes  # o aviso de 48 h e a prova do deploy seguem este instante
    with _do_lado_da_nuvem():
        enviados = [a for a in registro.recentes() if a.operacao == "backup.drive"]
    assert len(enviados) == 1  # conferir não é um efeito externo: não entra no registro


def _lembrete_novo():
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title="Outro lembrete")


def _concluir():
    with _do_lado_da_nuvem() as nuvem:
        (lembrete,) = nuvem.todos()
        nuvem.complete(lembrete.id)


def _gasto():
    with _do_lado_da_nuvem():
        custos.Teto(mes=10, dia=1, fuso=UTC).somar(0.02)


def _fato_novo():
    from lifeos.memoria import store as memoria_store

    with _do_lado_da_nuvem():
        memoria_store.gravar("O usuário corre aos sábados.", origem="chat", vetor=None)


def _receita_nova():
    from lifeos.memoria import receitas

    with _do_lado_da_nuvem():
        receitas.propor("fechamento", ["veja a agenda"], sessao="s1")


def _documento_novo():
    from lifeos.documentos import store as documentos_store

    with _do_lado_da_nuvem():
        documentos_store.aprender(
            "treino.md", "treino", "Agachamento.", embutir=lambda t: [[1.0] + [0.0] * 767]
        )


@pytest.mark.parametrize(
    "mudar", [_lembrete_novo, _concluir, _gasto, _fato_novo, _receita_nova, _documento_novo]
)
def test_qualquer_mudanca_cria_um_arquivo_novo(falso, mudar):
    _um_de_cada()
    assert _backup().json()["novo"] is True
    mudar()
    resposta = _backup().json()
    assert resposta["novo"] is True
    assert len(falso.de_backup()) == 2
    novo = formato.de_bytes(falso.de_backup()[-1]["conteudo"])
    colecoes = ("lembretes", "acoes", "gastos", "memoria", "receitas", "documentos", "trechos")
    assert novo.contagens() == {k: resposta[k] for k in colecoes}


def test_o_mais_novo_apagado_a_mao_vira_um_novo(falso):
    _um_de_cada()
    _backup()
    falso.arquivos = [a for a in falso.arquivos if a["mimeType"] != "application/json"]
    assert _backup().json()["novo"] is True
    assert len(falso.de_backup()) == 1


def test_o_mais_novo_que_nao_se_le_vira_um_novo(falso, caplog):
    _um_de_cada()
    _backup()
    falso.de_backup()[0]["conteudo"] = b'{"formato": "outra coisa"}'
    with caplog.at_level(logging.WARNING):
        assert _backup().json()["novo"] is True
    assert len(falso.de_backup()) == 2
    assert formato.de_bytes(falso.de_backup()[-1]["conteudo"]).lembretes
    assert "não se lê" in caplog.text


def test_drive_que_falha_ao_conferir_nao_marca_o_backup(falso, monkeypatch):
    _um_de_cada()
    _backup()
    antes = _ultimo_estado()

    def falha(_id):
        raise drive.FalhaDoDrive("HTTP 503")

    monkeypatch.setattr(drive, "baixar", falha)
    _lembrete_novo()
    resposta = _backup()
    assert resposta.status_code == 500
    assert resposta.json() == {"erro": "o backup falhou (FalhaDoDrive)"}
    assert _ultimo_estado() == antes and len(falso.de_backup()) == 1
