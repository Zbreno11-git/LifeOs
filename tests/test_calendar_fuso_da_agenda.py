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
    def configurar(fuso_do_viking, fuso_da_agenda, escolhido=False):
        monkeypatch.setattr(tools, "TIMEZONE", fuso_do_viking)
        monkeypatch.setattr(tools, "TIMEZONE_ESCOLHIDO", escolhido)
        monkeypatch.setattr(service, "fuso_da_agenda", lambda: fuso_da_agenda)

    return configurar


PACIFICO = ZoneInfo("America/Los_Angeles")


def test_horario_da_agenda_chega_no_fuso_do_dono(monkeypatch):
    """A agenda do dono está em São Paulo e ele no fuso do Pacífico: o Google devolve 15:00-03:00,
    que é 11:00 dele. Sem converter, o Gemini disse "às 15:00" (Mac, 2026-09-27)."""
    monkeypatch.setattr(service, "TIMEZONE", PACIFICO)
    evento = service._evento_de(
        {
            "id": "e1",
            "summary": "Teste Viking",
            "start": {"dateTime": "2026-09-28T15:00:00-03:00"},
            "end": {"dateTime": "2026-09-28T16:00:00-03:00"},
        }
    )
    assert (evento.inicio, evento.fim) == ("2026-09-28T11:00:00-07:00", "2026-09-28T12:00:00-07:00")


@pytest.mark.parametrize("valor", ["2026-09-28", "sem data", None, "2026-09-28T10:00:00"])
def test_dia_inteiro_e_texto_estranho_passam_como_vieram(monkeypatch, valor):
    monkeypatch.setattr(service, "TIMEZONE", PACIFICO)
    assert service.no_fuso_do_dono(valor) == valor


def test_fuso_adivinhado_pela_maquina_e_agenda_noutro_avisa(agenda):
    agenda(MENOS_OITO, "America/Sao_Paulo")
    assert aviso_de_fuso(AGORA) == (
        "⚠️  Fuso: sem VIKING_TIMEZONE no .env, o Viking usa o do relógio desta máquina (-08:00), "
        "e a sua agenda do Google está em America/Sao_Paulo (-03:00). Os horários que você pedir "
        "vão para -08:00. Ponha no .env o fuso de onde você está (nome IANA, ex.: "
        "VIKING_TIMEZONE=America/Los_Angeles ou America/Sao_Paulo)."
    )


def test_fuso_escolhido_no_env_nao_avisa_mesmo_com_a_agenda_noutro(agenda):
    """O dono escolheu o fuso dele e a agenda está noutro: é configuração, não erro; os horários
    lidos da agenda já chegam convertidos."""
    agenda(ZoneInfo("America/Los_Angeles"), "America/Sao_Paulo", escolhido=True)
    assert aviso_de_fuso(AGORA) == ""


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


def test_token_vencido_renova_em_silencio(tmp_path, monkeypatch):
    """Só com o token válido o aviso nunca aparecia: ele vence em 1 h (no Mac, o chat abriu 2 h
    depois do último uso). Renovar é uma chamada sem tela; o login, o conftest derruba."""

    def renova(self, _pedido):
        self.token = "novo"
        self.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)

    monkeypatch.setattr(google_auth.Credentials, "refresh", renova)
    vencido = _token(tmp_path / "t.json", datetime.now(UTC) - timedelta(hours=1))
    creds = google_auth.credenciais_sem_login(["https://www.googleapis.com/auth/calendar"], vencido)
    assert creds is not None
    assert creds.token == "novo"


def test_renovacao_recusada_nao_abre_login(tmp_path, monkeypatch):
    def recusa(self, _pedido):
        raise google_auth.RefreshError("revogado")

    monkeypatch.setattr(google_auth.Credentials, "refresh", recusa)
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
