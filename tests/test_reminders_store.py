import pytest


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test-viking.db"
    monkeypatch.setattr("lifeos.reminders.store.REMINDERS_DB_PATH", db_path)
    return db_path


def test_add_list_complete(temp_db):
    from lifeos.reminders import store

    reminder = store.add(title="Testar o Viking", tags=["teste"])
    assert reminder.id is not None
    assert reminder.title == "Testar o Viking"
    assert reminder.tags == ["teste"]

    open_reminders = store.list_open()
    assert any(r.id == reminder.id for r in open_reminders)

    completed = store.complete(reminder.id)
    assert completed.completed_at is not None

    open_reminders_after = store.list_open()
    assert all(r.id != reminder.id for r in open_reminders_after)
