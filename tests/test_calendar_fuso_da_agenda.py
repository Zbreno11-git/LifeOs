"""O fuso do Viking contra o da agenda do Google (Sessão 6, depois do teste no Mac).

No Mac, sem `VIKING_TIMEZONE`, o Viking usou o fuso do relógio da máquina (-08:00): "amanhã às
10h" virou 10:00-08:00 e a agenda mostrou 15:00. A D39 não pegou — para ela aquele era o fuso do
dono. Os dois fusos têm de concordar; quando não concordam, o chat avisa o dono na abertura.
"""

import ast
import inspect
import json
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from lifeos import google_auth
from lifeos.assistant import agent
from lifeos.calendar import service, tools
from lifeos.calendar.tools import aviso_de_fuso

AGORA = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
MENOS_OITO = timezone(timedelta(hours=-8))


@pytest.fixture()
def agenda(monkeypatch):
    def configurar(fuso_do_viking, fuso_da_agenda):
        monkeypatch.setattr(tools, "TIMEZONE", fuso_do_viking)
        monkeypatch.setattr(service, "fuso_da_agenda", lambda: fuso_da_agenda)

    return configurar


def test_viking_no_fuso_da_maquina_e_agenda_em_brasilia_avisa(agenda):
    agenda(MENOS_OITO, "America/Sao_Paulo")
    assert aviso_de_fuso(AGORA) == (
        "⚠️  Fuso: o Viking está em -08:00 e a sua agenda do Google em America/Sao_Paulo "
        "(-03:00). Um horário sem fuso vai para -08:00. Se o certo é o da agenda, ponha "
        "VIKING_TIMEZONE=America/Sao_Paulo no .env."
    )


@pytest.mark.parametrize(
    ("do_viking", "da_agenda"),
    [
        (ZoneInfo("America/Sao_Paulo"), "America/Sao_Paulo"),
        (timezone(timedelta(hours=-3)), "America/Sao_Paulo"),
        (ZoneInfo("America/Anchorage"), "America/Anchorage"),
    ],
)
def test_mesmo_fuso_nao_avisa(agenda, do_viking, da_agenda):
    agenda(do_viking, da_agenda)
    assert aviso_de_fuso(AGORA) == ""


@pytest.mark.parametrize("da_agenda", [None, "", "Nao/Existe"])
def test_sem_ler_a_agenda_nao_avisa(agenda, da_agenda):
    agenda(MENOS_OITO, da_agenda)
    assert aviso_de_fuso(AGORA) == ""


def test_falha_do_google_nao_derruba_o_chat(monkeypatch):
    def falha():
        raise service.FalhaDaApi("503", incerta=True)

    monkeypatch.setattr(service, "fuso_da_agenda", falha)
    assert aviso_de_fuso(AGORA) == ""


def test_fuso_da_agenda_le_a_configuracao_do_google(monkeypatch):
    class Configuracao:
        def get(self, setting):
            assert setting == "timezone"
            return type("R", (), {"execute": lambda self: {"value": "America/Sao_Paulo"}})()

    class Servico:
        def settings(self):
            return Configuracao()

    monkeypatch.setattr(service, "get_calendar_service_sem_login", Servico)
    assert service.fuso_da_agenda() == "America/Sao_Paulo"


def test_sem_token_valido_nao_le_a_agenda(monkeypatch):
    monkeypatch.setattr(service, "get_calendar_service_sem_login", lambda: None)
    assert service.fuso_da_agenda() is None


def _token(caminho, expira):
    caminho.write_text(
        json.dumps(
            {
                "token": "t",
                "refresh_token": "r",
                "client_id": "c",
                "client_secret": "s",
                "scopes": ["https://www.googleapis.com/auth/calendar"],
                "expiry": expira.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    )
    return caminho


def test_token_vencido_nao_renova_nem_abre_login(tmp_path, monkeypatch):
    """A abertura do chat não pode abrir a tela de login do Google nem renovar o token: o conftest
    derruba o teste se o login for chamado, e a renovação derruba aqui."""
    monkeypatch.setattr(
        google_auth.Credentials, "refresh", lambda *a: pytest.fail("renovou o token")
    )
    vencido = _token(tmp_path / "t.json", datetime.now(UTC) - timedelta(hours=1))
    escopos = ["https://www.googleapis.com/auth/calendar"]
    assert google_auth.credenciais_sem_login(escopos, vencido) is None
    assert google_auth.credenciais_sem_login(escopos, tmp_path / "nao-existe.json") is None


def test_token_valido_e_usado(tmp_path):
    valido = _token(tmp_path / "t.json", datetime.now(UTC) + timedelta(hours=1))
    creds = google_auth.credenciais_sem_login(["https://www.googleapis.com/auth/calendar"], valido)
    assert creds is not None
    assert creds.valid


def test_o_chat_mostra_o_aviso_ao_abrir():
    """O laço do chat precisa do Gemini de verdade; aqui, a leitura do código: a abertura chama
    `aviso_de_fuso()` e imprime o que vier."""
    arvore = ast.parse(inspect.getsource(agent))
    chamadas = [
        n for n in ast.walk(arvore)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "aviso_de_fuso"
    ]  # fmt: skip
    assert len(chamadas) == 1
