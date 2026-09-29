"""O `viking.db`: o único lugar que abre o SQLite (Sessão 9).

Três módulos guardam dados no mesmo arquivo: os lembretes (`reminders/store.py`), o registro de
ações (`registro.py`) e as confirmações (`confirmacao.py`). Antes da 9 cada um abria o caminho da
config por conta própria, e o isolamento dos testes trocava dois dos três: a suíte gravou um
lembrete no banco de verdade a cada rodada (132 no VPS, medido em 2026-09-29). Agora todos abrem
por `conectar()`, e os testes trocam só `CAMINHO` (`tests/test_banco.py` proíbe `sqlite3.connect`
fora daqui).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from lifeos.config import REMINDERS_DB_PATH

CAMINHO: Path = REMINDERS_DB_PATH  # os testes trocam este nome (`tests/conftest.py`)
ESPERA_S = 5.0  # outro processo escrevendo (chat, MCP, `viking aprovar`): espera, depois erra


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Uma conexão ao `viking.db`: `commit` ao sair sem erro, `close` sempre."""
    CAMINHO.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CAMINHO, timeout=ESPERA_S)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
