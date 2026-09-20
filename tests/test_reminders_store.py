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


def test_lembrete_com_prazo_aparece_primeiro(temp_db):
    """list_open ordena por prazo; sem prazo vai para o fim."""
    from datetime import UTC, datetime

    from lifeos.reminders import store

    store.add(title="sem prazo")
    store.add(title="semana que vem", due_at=datetime(2026, 9, 27, tzinfo=UTC))
    store.add(title="amanhã", due_at=datetime(2026, 9, 21, tzinfo=UTC))

    titulos = [r.title for r in store.list_open()]
    assert titulos == ["amanhã", "semana que vem", "sem prazo"]


def test_schema_aceita_registro_externo_tipo_pluggy(temp_db):
    """O gancho de compatibilidade com finanças precisa continuar valendo."""
    from lifeos.reminders import store

    r = store.add(
        title="Mercado",
        type="finance_transaction",
        source="pluggy",
        external_id="txn_123",
        metadata={"valor": -84.2, "moeda": "BRL"},
    )
    lido = store.get(r.id)
    assert lido.type == "finance_transaction"
    assert lido.external_id == "txn_123"
    assert lido.metadata["valor"] == -84.2
