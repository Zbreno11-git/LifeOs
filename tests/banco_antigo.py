"""Um `viking.db` no formato de `5d0ace4` (antes da Sessão 9), com dados, para testar migração.

O DDL abaixo é **cópia literal** do que os três módulos criavam naquele commit
(`git show 5d0ace4:src/lifeos/reminders/store.py`, `registro.py`, `confirmacao.py`), mais o
`PRAGMA user_version = 1` que a migração dos lembretes deixava. Não derivar de `banco.MIGRACOES`:
um teste de "o formato antigo migra" que gerasse o formato antigo com o código novo provaria só
que o código novo concorda consigo mesmo (erros, classe 4). Conferido em 2026-09-29 contra um
banco criado pelo próprio código de `5d0ace4` (mesmo `sqlite_master`).

Os dados cobrem o que o banco do dono pode ter: lembrete aberto com prazo (UTC, como o código de
então gravava), sem prazo, concluído, com tags e metadados; ações nos quatro estados; confirmações
aberta, consumida e substituída.
"""

import sqlite3
from pathlib import Path

DDL_5D0ACE4 = (
    """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    due_at TEXT,
    completed_at TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    external_id TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
""",
    "CREATE INDEX IF NOT EXISTS idx_reminders_due_at ON reminders (due_at)",
    """
    CREATE TABLE IF NOT EXISTS acoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turno TEXT NOT NULL,
        origem TEXT NOT NULL,
        operacao TEXT NOT NULL,
        parametros TEXT NOT NULL,
        estado TEXT NOT NULL,
        resultado TEXT,
        erro TEXT,
        desfazer TEXT,
        desfeita_em TEXT,
        criada_em TEXT NOT NULL,
        terminada_em TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_acoes_criada_em ON acoes(criada_em)",
    """
CREATE TABLE IF NOT EXISTS confirmacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acao TEXT NOT NULL,
    codigo TEXT NOT NULL,
    dados TEXT NOT NULL,
    criada_em TEXT NOT NULL,
    expira_em TEXT NOT NULL,
    estado TEXT NOT NULL,
    consumida_em TEXT,
    resultado TEXT
)
""",
)

LEMBRETES = [
    # (type, title, body, tags, due_at, completed_at, source, external_id, metadata, criado)
    ("reminder", "Dentista", "levar o raio-x", '["saude"]', "2026-10-01T13:00:00+00:00", None,
     "manual", None, "{}", "2026-09-20T10:00:00.000001+00:00"),
    ("note", "Ideia", "", "[]", None, None, "mcp", None, "{}", "2026-09-21T11:30:00+00:00"),
    ("reminder", "Pagar luz", "", "[]", "2026-09-25T15:00:00+00:00",
     "2026-09-25T16:00:00.5+00:00", "manual", None, "{}", "2026-09-22T09:00:00+00:00"),
    ("finance_transaction", "Mercado", "", "[]", None, None, "pluggy", "txn_1",
     '{"valor": -84.2}', "2026-09-23T08:00:00+00:00"),
]  # fmt: skip

ACOES = [
    # (turno, origem, operacao, parametros, estado, resultado, erro, desfazer, desfeita, criada)
    ("t1", "chat", "calendario.apagar", '{"id": "abc"}', "feita", '{"ok": true}', None,
     '{"evento": {"summary": "x"}}', None, "2026-09-28T10:00:00+00:00"),
    ("t2", "mcp", "lembrete.criar", '{"titulo": "Ideia"}', "falhou", "{}", "Erro: x", None, None,
     "2026-09-28T11:00:00+00:00"),
    ("t3", "cli", "gmail.enviar", '{"livre": true}', "incerta", "{}", "FalhaDaApi: 503", None,
     None, "2026-09-28T12:00:00+00:00"),
    ("t4", "chat", "navegador.executar", '{"url": "https://example.com"}', "iniciada", None, None,
     None, None, "2026-09-28T13:00:00+00:00"),
]  # fmt: skip

CONFIRMACOES = [
    # (acao, codigo, dados, criada, expira, estado, consumida_em, resultado)
    ("gmail.arquivar", "1234", '{"ids": ["m1"]}', "2026-09-28T10:00:00+00:00",
     "2026-09-28T10:10:00+00:00", "consumida", "2026-09-28T10:05:00+00:00", '{"feitos": 1}'),
    ("gmail.arquivar", "5678", '{"ids": []}', "2026-09-28T11:00:00+00:00",
     "2026-09-28T11:10:00+00:00", "substituida", None, None),
    ("calendario.apagar", "9012", '{"id": "e1"}', "2026-09-28T12:00:00+00:00",
     "2026-09-28T13:00:00+00:00", "aberta", None, None),
]  # fmt: skip


def criar(caminho: Path, *, user_version: int = 1) -> Path:
    """O banco de `5d0ace4`, com os dados acima."""
    conn = sqlite3.connect(caminho)
    for comando in DDL_5D0ACE4:
        conn.execute(comando)
    for tipo, titulo, corpo, tags, prazo, feito, fonte, externo, meta, criado in LEMBRETES:
        conn.execute(
            "INSERT INTO reminders (type, title, body, tags, due_at, completed_at, source, "
            "external_id, metadata, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (tipo, titulo, corpo, tags, prazo, feito, fonte, externo, meta, criado, criado),
        )
    conn.executemany(
        "INSERT INTO acoes (turno, origem, operacao, parametros, estado, resultado, erro, "
        "desfazer, desfeita_em, criada_em) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ACOES,
    )
    conn.executemany(
        "INSERT INTO confirmacoes (acao, codigo, dados, criada_em, expira_em, estado, "
        "consumida_em, resultado) VALUES (?,?,?,?,?,?,?,?)",
        CONFIRMACOES,
    )
    conn.execute(f"PRAGMA user_version = {int(user_version)}")
    conn.commit()
    conn.close()
    return caminho


def linhas(caminho: Path, tabela: str) -> list[tuple]:
    """Todas as linhas de uma tabela, pela ordem do id, como tuplas (para comparar conteúdo)."""
    conn = sqlite3.connect(caminho)
    try:
        return conn.execute(f"SELECT * FROM {tabela} ORDER BY id").fetchall()
    finally:
        conn.close()


def despejo(caminho: Path) -> list[str]:
    """O banco inteiro como SQL (schema e dados): igualdade de despejo = banco igual."""
    conn = sqlite3.connect(caminho)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()
