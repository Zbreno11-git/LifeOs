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


def test_due_at_naive_e_gravado_e_lido_de_volta_no_fuso_configurado(temp_db, monkeypatch):
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from lifeos.reminders import store

    fuso = ZoneInfo("America/Sao_Paulo")
    monkeypatch.setattr(store, "TIMEZONE", fuso)

    naive = datetime(2026, 9, 25, 14, 0)  # noqa: DTZ001 - naive de propósito: é o caso testado
    r = store.add(title="Consulta", due_at=naive)

    lido = store.get(r.id)
    assert lido.due_at.tzinfo is not None
    assert lido.due_at.hour == 14  # volta no MESMO horário local que foi digitado
    assert lido.due_at.astimezone(UTC) == naive.replace(tzinfo=fuso).astimezone(UTC)


def test_due_at_aware_com_offset_diferente_e_normalizado_para_utc(temp_db):
    import sqlite3
    from datetime import datetime, timedelta, timezone

    from lifeos.reminders import store

    tz_mais_2 = timezone(timedelta(hours=2))
    r = store.add(title="Reunião", due_at=datetime(2026, 9, 25, 9, 0, tzinfo=tz_mais_2))

    conn = sqlite3.connect(temp_db)
    bruto = conn.execute("SELECT due_at FROM reminders WHERE id = ?", (r.id,)).fetchone()[0]
    conn.close()
    assert bruto == "2026-09-25T07:00:00+00:00"


def test_lembretes_com_fusos_diferentes_ordenam_pelo_instante_real(temp_db):
    """Reproduz o bug medido na auditoria: sob o esquema antigo, "08:00+00:00" (texto) vinha antes
    de "09:00+02:00", embora este último seja 07:00Z — o horário real mais cedo."""
    from datetime import UTC, datetime, timedelta, timezone

    from lifeos.reminders import store

    tz_mais_2 = timezone(timedelta(hours=2))
    store.add(title="mais cedo (fuso +02:00)", due_at=datetime(2026, 9, 25, 9, 0, tzinfo=tz_mais_2))
    store.add(title="mais tarde (UTC)", due_at=datetime(2026, 9, 25, 8, 0, tzinfo=UTC))

    titulos = [r.title for r in store.list_open()]
    assert titulos == ["mais cedo (fuso +02:00)", "mais tarde (UTC)"]


def test_migracao_normaliza_registro_gravado_antes_da_normalizacao(temp_db, monkeypatch):
    """Simula um `due_at` gravado por uma versão anterior do Viking (naive, sem offset) — nunca
    passou por `store.add()`, então só a migração automática pode consertar."""
    import sqlite3
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from lifeos.reminders import store

    monkeypatch.setattr(store, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))

    conn = sqlite3.connect(temp_db)
    conn.execute(store._SCHEMA)
    agora = datetime.now(UTC).isoformat()
    conn.execute(
        """INSERT INTO reminders
               (type, title, body, tags, due_at, source, external_id, metadata,
                created_at, updated_at)
           VALUES ('reminder', 'Legado', '', '[]', ?, 'manual', NULL, '{}', ?, ?)""",
        ("2026-09-25T14:00:00", agora, agora),
    )
    conn.commit()
    conn.close()

    store.list_open()  # abre uma sessão -> dispara a migração automática

    conn = sqlite3.connect(temp_db)
    bruto = conn.execute("SELECT due_at FROM reminders WHERE title = 'Legado'").fetchone()[0]
    conn.close()
    assert bruto == "2026-09-25T17:00:00+00:00"  # 14h em -03:00 é 17h UTC


def test_migracao_e_idempotente(temp_db):
    import sqlite3

    from lifeos.reminders import store

    store.add(title="Normal")  # garante que tabela/versão existam

    conn = sqlite3.connect(temp_db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()

    store.list_open()  # uma segunda sessão não deve refazer nem alterar nada

    conn = sqlite3.connect(temp_db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()


def test_indice_de_due_at_existe(temp_db):
    import sqlite3

    from lifeos.reminders import store

    store.add(title="Qualquer")  # garante a criação do schema
    conn = sqlite3.connect(temp_db)
    indices = [row[1] for row in conn.execute("PRAGMA index_list(reminders)").fetchall()]
    conn.close()
    assert "idx_reminders_due_at" in indices
