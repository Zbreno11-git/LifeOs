from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

# O caso real (medido em 2026-09-28): o dono está em Seattle, não em Brasília nem em UTC como o VPS.
# Sem fixar, um teste de "14h" passaria aqui só porque o VPS está em UTC.
DONO = ZoneInfo("America/Los_Angeles")


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test-viking.db"
    monkeypatch.setattr("lifeos.banco.CAMINHO", db_path)
    monkeypatch.setattr("lifeos.config.TIMEZONE", DONO)
    return db_path


def test_criar_lembrete_sem_quando(temp_db):
    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", corpo="corpo", tags="a, b", source="viking-cli")

    assert reminder.due_at is None
    assert reminder.title == "Testar"
    assert reminder.body == "corpo"
    assert reminder.tags == ["a", "b"]
    assert reminder.source == "viking-cli"


def test_criar_lembrete_com_quando_so_data(temp_db):
    from datetime import date

    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", quando="2026-09-25")

    assert reminder.due_at is not None
    assert reminder.due_at.astimezone(DONO).date() == date(2026, 9, 25)


def test_criar_lembrete_com_quando_data_e_hora(temp_db):

    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", quando="2026-09-25T14:00")

    assert reminder.due_at == datetime(2026, 9, 25, 21, 0, tzinfo=UTC)  # 14h em Seattle (-07:00)


def test_criar_lembrete_com_quando_invalido_levanta_erro(temp_db):
    from lifeos.reminders import service

    with pytest.raises(service.QuandoInvalido) as exc_info:
        service.criar_lembrete("Testar", quando="sexta-feira")

    assert "sexta-feira" in exc_info.value.args


def test_criar_lembrete_propaga_source(temp_db):
    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", source="mcp")

    assert reminder.source == "mcp"


# --- a borda: o fuso do dono entra e sai aqui, o store só vê UTC ------------------------------


def test_horario_com_fuso_explicito_e_respeitado(temp_db):
    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", quando="2026-09-25T14:00-03:00")

    assert reminder.due_at == datetime(2026, 9, 25, 17, 0, tzinfo=UTC)


def test_chat_mostra_titulo_e_prazo_no_fuso_do_dono_sem_numero(temp_db):
    from lifeos.assistant.agent import criar_lembrete, listar_lembretes

    criado = criar_lembrete("Dentista", quando="2026-09-25T14:00")
    lista = listar_lembretes()

    assert criado.startswith("✅ Lembrete criado: 'Dentista' (para 2026-09-25 14:00) [id: ")
    assert lista.startswith("- Dentista (para 2026-09-25 14:00) [id: ")
    assert "#" not in criado + lista


def test_chat_conclui_pelo_id_da_listagem(temp_db):
    from lifeos.assistant.agent import concluir_lembrete, listar_lembretes
    from lifeos.reminders import service

    service.criar_lembrete("Pagar luz")
    reminder_id = listar_lembretes().split("[id: ")[1].rstrip("]")

    assert concluir_lembrete(f" {reminder_id} ") == "✅ Lembrete concluído: 'Pagar luz'."
    assert listar_lembretes() == "Nenhum lembrete pendente."
    assert concluir_lembrete("um-id-inventado").startswith("Não encontrei esse lembrete")


def test_mcp_devolve_o_prazo_no_fuso_do_dono(temp_db):
    from lifeos.mcp_server.server import _lembrete_para_dict
    from lifeos.reminders import service

    reminder = service.criar_lembrete("Dentista", quando="2026-09-25T14:00")

    assert _lembrete_para_dict(reminder)["due_at"] == "2026-09-25T14:00:00-07:00"
