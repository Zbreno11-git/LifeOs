"""O `viking.db`: o único lugar que abre o SQLite, e as migrations dele (Sessão 9).

Três módulos guardam dados no mesmo arquivo: os lembretes (`reminders/store.py`), o registro de
ações (`registro.py`) e as confirmações (`confirmacao.py`). Antes da 9 cada um abria o caminho da
config por conta própria, e o isolamento dos testes trocava dois dos três: a suíte gravou um
lembrete no banco de verdade a cada rodada (132 no VPS, medido em 2026-09-29). Agora todos abrem
por `conectar()`, e os testes trocam só `CAMINHO` (`tests/test_banco.py` proíbe `sqlite3.connect`
fora daqui).

**Migrations (D56).** Uma lista só, para o arquivo inteiro (`MIGRACOES`), e um ledger
(`migracoes`: número, nome, checksum, quando). O `PRAGMA user_version` é um por arquivo e não
cabia três módulos; o `1` que os bancos de antes da 9 têm fica lá, inerte. As 1–4 recriam o
formato de `5d0ace4` com `IF NOT EXISTS`: num banco daquele formato não mudam nada e só entram no
ledger; num banco novo, criam tudo. Um caminho só para os dois.

Regras, cada uma com teste em `tests/test_banco_migracoes.py`:
- **uma migração publicada não se edita, nem o comentário:** cria-se a seguinte. O checksum de
  cada uma fica no ledger e é conferido a cada abertura; divergiu, erra dizendo o número;
- **tudo o que está pendente roda numa transação só** (`BEGIN IMMEDIATE`, com a conexão em
  autocommit para o Python não abrir nem fechar transação por conta própria): uma falha no meio
  volta o banco ao que era. Cada passo é um `execute`: o `executescript` **comita sozinho** a
  transação aberta (medido em 2026-09-29, Python 3.12);
- o ledger é relido **depois** da trava: dois processos abrindo juntos, o segundo espera e acha
  tudo aplicado;
- **banco mais novo que o código** (número que esta versão não conhece) não abre;
- **backup antes de migrar** um banco que já tem tabelas, em `viking.db.antes-da-migracao-N` (N =
  a primeira pendente), sem sobrescrever. É feito com a trava segurada e por **outra** conexão:
  pela mesma, o `backup` com a transação aberta trava para sempre (medido); a outra lê só o que
  está comitado, então a cópia é o banco exato de antes.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hashlib
import inspect
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lifeos import config
from lifeos.config import REMINDERS_DB_PATH

CAMINHO: Path = REMINDERS_DB_PATH  # os testes trocam este nome (`tests/conftest.py`)
ESPERA_S = 5.0  # outro processo escrevendo (chat, MCP, `viking aprovar`): espera, depois erra

_LEDGER = """
CREATE TABLE IF NOT EXISTS migracoes (
    numero INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    checksum TEXT NOT NULL,
    aplicada_em TEXT NOT NULL
)
"""


class ErroDeBanco(Exception):
    """O `viking.db` não está num estado que esta versão do Viking sabe usar."""


class BancoMaisNovo(ErroDeBanco):
    pass


class MigracaoAlterada(ErroDeBanco):
    pass


Passo = tuple[str, ...] | Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migracao:
    numero: int
    nome: str
    passo: Passo  # comandos SQL, um `execute` cada, ou uma função que recebe a conexão

    @property
    def checksum(self) -> str:
        fonte = (
            "\n;\n".join(self.passo)
            if isinstance(self.passo, tuple)
            else inspect.getsource(self.passo)
        )
        return hashlib.sha256(fonte.encode("utf-8")).hexdigest()

    def aplicar(self, conn: sqlite3.Connection) -> None:
        if isinstance(self.passo, tuple):
            for comando in self.passo:
                conn.execute(comando)
        else:
            self.passo(conn)


# --- as migrations: publicada não se edita ----------------------------------------------------

_M1_LEMBRETES = (
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
)


def _m2_prazos_em_utc(conn: sqlite3.Connection) -> None:
    """O `due_at` gravado antes da Sessão 2 podia estar sem fuso ou em outro offset, e ordenava
    como texto errado. Sem fuso quer dizer o fuso configurado do Viking (o que valia quando foi
    gravado). Idempotente: um valor já em UTC não muda. Era o `user_version` 1 dos lembretes."""
    for linha in conn.execute("SELECT id, due_at FROM reminders WHERE due_at IS NOT NULL"):
        try:
            prazo = datetime.fromisoformat(linha[1])
        except ValueError:
            continue  # texto que não é data: não é esta migração que o conserta
        if prazo.tzinfo is None:
            prazo = prazo.replace(tzinfo=config.TIMEZONE)
        normalizado = prazo.astimezone(UTC).isoformat()
        if normalizado != linha[1]:
            conn.execute("UPDATE reminders SET due_at = ? WHERE id = ?", (normalizado, linha[0]))


_M3_ACOES = (
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
)

_M4_CONFIRMACOES = (
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


def _m5_lembretes_com_uuid_e_envio(conn: sqlite3.Connection) -> None:
    """Lembretes com id UUID (o Firestore da Sessão 10 não tem contador, e um id gerado no cliente
    deixa repetir o `add` sem duplicar) e as colunas da reserva de envio. Trocar a chave primária
    no SQLite é reconstruir a tabela: cria a nova, copia, apaga a velha, renomeia (tudo dentro da
    transação de `migrar`). Os instantes voltam em UTC de largura fixa (`timespec=microseconds`):
    comparar texto só é certo com um formato só. Texto que não é data fica como está."""

    def instante(texto: str | None) -> str | None:
        if texto is None:
            return None
        try:
            valor = datetime.fromisoformat(texto)
        except ValueError:
            return texto
        if valor.tzinfo is None:
            return texto  # não se adivinha o fuso de um valor antigo
        return valor.astimezone(UTC).isoformat(timespec="microseconds")

    conn.execute(
        """
CREATE TABLE lembretes_v5 (
    id TEXT PRIMARY KEY NOT NULL,
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
    updated_at TEXT NOT NULL,
    enviado_em TEXT,
    envio_estado TEXT,
    envio_reservado_por TEXT,
    envio_reservado_ate TEXT
)
"""
    )
    antigas = conn.execute(
        "SELECT type, title, body, tags, due_at, completed_at, source, external_id, metadata, "
        "created_at, updated_at FROM reminders ORDER BY id"
    ).fetchall()
    for tipo, titulo, corpo, tags, prazo, feito, fonte, externo, meta, criado, mudado in antigas:
        conn.execute(
            "INSERT INTO lembretes_v5 (id, type, title, body, tags, due_at, completed_at, "
            "source, external_id, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                tipo,
                titulo,
                corpo,
                tags,
                instante(prazo),
                instante(feito),
                fonte,
                externo,
                meta,
                instante(criado),
                instante(mudado),
            ),
        )
    conn.execute("DROP TABLE reminders")
    conn.execute("ALTER TABLE lembretes_v5 RENAME TO reminders")
    conn.execute("CREATE INDEX idx_reminders_due_at ON reminders (due_at)")
    conn.execute(
        "CREATE INDEX idx_reminders_a_enviar ON reminders (due_at) "
        "WHERE completed_at IS NULL AND enviado_em IS NULL"
    )


# Sessão 10c (D60): quantos códigos errados a proposta já recebeu; no limite, ela é cancelada.
_M6_TENTATIVAS = ("ALTER TABLE confirmacoes ADD COLUMN erros INTEGER NOT NULL DEFAULT 0",)

# Sessão 11 (D61): onde moram os lembretes deste Mac. Uma linha só (`id = 1`): sem ela, aqui;
# "migrando", as gravações daqui param (a cópia para a nuvem está em curso); "migrado", o Mac lê e
# grava na nuvem, pelo motor, e a tabela `reminders` vira a cópia congelada de antes.
_M7_LEMBRETES_NA_NUVEM = (
    """
CREATE TABLE lembretes_na_nuvem (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    estado TEXT NOT NULL CHECK (estado IN ('migrando', 'migrado')),
    em TEXT NOT NULL
)
""",
)


MIGRACOES: tuple[Migracao, ...] = (
    Migracao(1, "lembretes: tabela e índice de prazo", _M1_LEMBRETES),
    Migracao(2, "lembretes: prazos em UTC", _m2_prazos_em_utc),
    Migracao(3, "registro: tabela de ações", _M3_ACOES),
    Migracao(4, "confirmações: tabela", _M4_CONFIRMACOES),
    Migracao(5, "lembretes: id UUID e reserva de envio", _m5_lembretes_com_uuid_e_envio),
    Migracao(6, "confirmações: tentativas erradas", _M6_TENTATIVAS),
    Migracao(7, "lembretes: a marca de que moram na nuvem", _M7_LEMBRETES_NA_NUVEM),
)


# --- aplicar ----------------------------------------------------------------------------------


def _pendentes(conn: sqlite3.Connection) -> list[Migracao]:
    """O que falta aplicar; erra se o banco é mais novo que o código ou se uma aplicada mudou."""
    tem_ledger = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'migracoes'"
    ).fetchone()
    aplicadas = (
        {n: c for n, c in conn.execute("SELECT numero, checksum FROM migracoes")}
        if tem_ledger
        else {}
    )
    conhecidas = {m.numero: m for m in MIGRACOES}
    if desconhecidas := sorted(set(aplicadas) - set(conhecidas)):
        raise BancoMaisNovo(
            f"o banco {CAMINHO.name} foi migrado por uma versão mais nova do Viking (migração "
            f"{desconhecidas[-1]}; esta conhece até a {max(conhecidas)}). Atualize com `git pull`; "
            "nada foi lido nem escrito."
        )
    for numero, checksum in aplicadas.items():
        if conhecidas[numero].checksum != checksum:
            raise MigracaoAlterada(
                f"a migração {numero} ({conhecidas[numero].nome}) mudou depois de aplicada neste "
                "banco. Uma migração publicada não se edita: desfaça a mudança e crie a seguinte."
            )
    return [m for m in MIGRACOES if m.numero not in aplicadas]


def _tem_tabelas(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name != 'migracoes' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchone()
        is not None
    )


def caminho_do_backup(numero: int) -> Path:
    return CAMINHO.with_name(f"{CAMINHO.name}.antes-da-migracao-{numero}")


def _copiar(numero: int) -> None:
    """A cópia do banco antes da migração `numero`, por outra conexão (ver o topo do módulo).
    Grava num arquivo `.parcial` e renomeia: uma cópia interrompida nunca parece completa."""
    destino = caminho_do_backup(numero)
    if destino.exists():
        return  # a mais antiga fica: é o banco de antes da primeira tentativa
    parcial = destino.with_name(destino.name + ".parcial")
    leitor = sqlite3.connect(CAMINHO, timeout=ESPERA_S)
    try:
        copia = sqlite3.connect(parcial)
        try:
            leitor.backup(copia)
        finally:
            copia.close()
    finally:
        leitor.close()
    os.replace(parcial, destino)


def migrar(conn: sqlite3.Connection) -> None:
    """Deixa o banco na última migração. `conn` em autocommit (`isolation_level=None`)."""
    if not _pendentes(conn):
        return  # o caminho de toda abertura: uma leitura do ledger, sem trava
    conn.execute("BEGIN IMMEDIATE")
    try:
        pendentes = _pendentes(conn)  # relido com a trava: outro processo pode ter migrado
        if pendentes and _tem_tabelas(conn):
            _copiar(pendentes[0].numero)
        conn.execute(_LEDGER)
        for migracao in pendentes:
            migracao.aplicar(conn)
            conn.execute(
                "INSERT INTO migracoes (numero, nome, checksum, aplicada_em) VALUES (?, ?, ?, ?)",
                (
                    migracao.numero,
                    migracao.nome,
                    migracao.checksum,
                    datetime.now(UTC).isoformat(timespec="microseconds"),
                ),
            )
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    """Uma conexão ao `viking.db` já migrado: `commit` ao sair sem erro, `close` sempre.

    Na nuvem (`VIKING_STORE=firestore`) recusa: o motor guarda tudo no Firestore, e um SQLite
    aberto lá seria um banco efêmero, por instância, que some a cada partida (Sessão 10b)."""
    if config.STORE == "firestore":
        raise RuntimeError(
            "o viking.db não abre na nuvem (VIKING_STORE=firestore): este caminho devia usar o "
            "store do Firestore"
        )
    CAMINHO.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CAMINHO, timeout=ESPERA_S, isolation_level=None)
    try:
        conn.row_factory = sqlite3.Row
        migrar(conn)
        conn.isolation_level = "DEFERRED"  # o de sempre para quem usa: BEGIN implícito antes do DML
        yield conn
        conn.commit()
    finally:
        conn.close()
