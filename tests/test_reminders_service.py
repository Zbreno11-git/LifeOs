import pytest


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test-viking.db"
    monkeypatch.setattr("lifeos.reminders.store.REMINDERS_DB_PATH", db_path)
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
    assert reminder.due_at.date() == date(2026, 9, 25)


def test_criar_lembrete_com_quando_data_e_hora(temp_db):
    from datetime import date

    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", quando="2026-09-25T14:00")

    assert reminder.due_at is not None
    assert reminder.due_at.hour == 14
    assert reminder.due_at.date() == date(2026, 9, 25)


def test_criar_lembrete_com_quando_invalido_levanta_erro(temp_db):
    from lifeos.reminders import service

    with pytest.raises(service.QuandoInvalido) as exc_info:
        service.criar_lembrete("Testar", quando="sexta-feira")

    assert "sexta-feira" in exc_info.value.args


def test_criar_lembrete_propaga_source(temp_db):
    from lifeos.reminders import service

    reminder = service.criar_lembrete("Testar", source="mcp")

    assert reminder.source == "mcp"
