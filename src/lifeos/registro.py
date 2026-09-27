"""Registro local do que o Viking fez: cada efeito externo, com o pedido, o resultado e como
desfazer (Sessão 5; auditoria do Codex §7).

Existe para o caso "a ação aconteceu, a chamada seguinte ao Gemini falhou, o dono pediu de novo e
ela aconteceu duas vezes": o laço do chat lê as ações do turno que deu erro e diz o que já foi (ou
pode ter sido) feito. Também responde "o que você fez hoje?" e guarda a cópia que o `desfaz` usa.

Cada efeito passa por `with registro.acao(operacao, parametros) as marca:` na camada de serviço
(calendário, lembretes, Gmail, navegador), então vale igual para chat, MCP e CLI. Estados:
`iniciada` (gravado ANTES do efeito) → `feita` | `falhou` | `incerta`. `incerta` é a exceção que
não prova que nada aconteceu (tempo esgotado, 5xx do Google): o efeito pode ter sido aplicado. Uma
linha que ficou `iniciada` (o processo morreu no meio) é lida como incerta também.

Privacidade: `parametros` e `resultado` passam pela redação das páginas; o `desfazer` é a cópia
bruta (o evento inteiro, para recriá-lo) e nunca é mostrado nem vai ao Gemini. Código de
aprovação nunca entra aqui. Fica em `viking.db` (tabela `acoes`) por `RETENCAO` (decisão do dono:
30 dias); a purga roda a cada abertura.

A tabela não usa `PRAGMA user_version` (é dos lembretes, `reminders/store.py`): nasce com `CREATE
TABLE IF NOT EXISTS`. Migrations formais estão no backlog (§12.6).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import contextvars
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos.browser import _redacao
from lifeos.config import REMINDERS_DB_PATH

DB_PATH = REMINDERS_DB_PATH  # o mesmo `viking.db`; os testes trocam este nome
RETENCAO = timedelta(days=30)
MAX_TEXTO = 300  # por campo de texto guardado (redigido)

# Quem pediu (`chat`, `mcp`, `cli`) e em que turno do chat. Por `contextvars`, e não por
# argumento: não muda a assinatura de nenhuma tool do Gemini. O google-genai chama as tools no
# mesmo thread do `send_message`; o FastMCP copia o contexto para o thread da tool. Sem origem
# definida, grava `desconhecida` — e um teste proíbe que isso aconteça.
ORIGEM: contextvars.ContextVar[str] = contextvars.ContextVar("origem", default="desconhecida")
TURNO: contextvars.ContextVar[str] = contextvars.ContextVar("turno", default="")

FEITA, FALHOU, INCERTA, INICIADA = "feita", "falhou", "incerta", "iniciada"

_SCHEMA = (
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


@dataclass(frozen=True)
class Acao:
    id: int
    turno: str
    origem: str
    operacao: str
    parametros: dict[str, Any]
    estado: str
    resultado: dict[str, Any]
    erro: str
    desfazivel: bool  # há cópia para desfazer e ainda não foi desfeita
    desfeita_em: datetime | None
    criada_em: datetime

    @property
    def pode_ter_acontecido(self) -> bool:
        return self.estado in (INCERTA, INICIADA)


@dataclass
class Marca:
    """O que o bloco `with registro.acao(...)` recebe para anotar o que aconteceu."""

    id: int
    resultado: dict[str, Any] = field(default_factory=dict)
    desfazer: dict[str, Any] | None = None

    def feito(self, resultado: dict[str, Any] | None = None, *, desfazer=None) -> None:
        self.resultado = resultado or {}
        self.desfazer = desfazer


def _agora(agora: datetime | None = None) -> datetime:
    return (agora or datetime.now(UTC)).astimezone(UTC)


def limpo(valor: Any) -> Any:
    """Redação das páginas em todo texto (CPF, cartão, chaves, controles), recursiva."""
    if isinstance(valor, str):
        return _redacao.redigir(_redacao.limpar_controles(valor))[:MAX_TEXTO]
    if isinstance(valor, dict):
        return {str(k): limpo(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [limpo(v) for v in valor]
    return valor


@contextmanager
def _sessao(agora: datetime | None = None) -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for comando in _SCHEMA:
        conn.execute(comando)
    conn.execute("DELETE FROM acoes WHERE criada_em < ?", ((_agora(agora) - RETENCAO).isoformat(),))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _eh_incerta(exc: BaseException) -> bool:
    return bool(getattr(exc, "incerta", False))


@contextmanager
def acao(
    operacao: str, parametros: dict[str, Any], *, agora: datetime | None = None
) -> Iterator[Marca]:
    """Grava `iniciada` antes do efeito; ao sair, `feita`, `falhou` ou `incerta`. A exceção sobe."""
    momento = _agora(agora)
    with _sessao(momento) as conn:
        cursor = conn.execute(
            "INSERT INTO acoes (turno, origem, operacao, parametros, estado, criada_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                TURNO.get(),
                ORIGEM.get(),
                operacao,
                json.dumps(limpo(parametros), ensure_ascii=False),
                INICIADA,
                momento.isoformat(),
            ),
        )
        marca = Marca(cursor.lastrowid)
    try:
        yield marca
    except BaseException as exc:
        estado = INCERTA if _eh_incerta(exc) else FALHOU
        _terminar(marca, estado, erro=type(exc).__name__ + ": " + str(exc))
        raise
    _terminar(marca, FEITA)


def _terminar(marca: Marca, estado: str, *, erro: str = "") -> None:
    with _sessao() as conn:
        conn.execute(
            "UPDATE acoes SET estado = ?, resultado = ?, erro = ?, desfazer = ?, "
            "terminada_em = ? WHERE id = ?",
            (
                estado,
                json.dumps(limpo(marca.resultado), ensure_ascii=False),
                limpo(erro),
                json.dumps(marca.desfazer) if marca.desfazer is not None else None,
                _agora().isoformat(),
                marca.id,
            ),
        )


def _acao(linha: sqlite3.Row) -> Acao:
    return Acao(
        id=linha["id"],
        turno=linha["turno"],
        origem=linha["origem"],
        operacao=linha["operacao"],
        parametros=json.loads(linha["parametros"]),
        estado=linha["estado"],
        resultado=json.loads(linha["resultado"]) if linha["resultado"] else {},
        erro=linha["erro"] or "",
        desfazivel=bool(linha["desfazer"]) and not linha["desfeita_em"],
        desfeita_em=datetime.fromisoformat(linha["desfeita_em"]) if linha["desfeita_em"] else None,
        criada_em=datetime.fromisoformat(linha["criada_em"]),
    )


def do_turno(turno: str) -> list[Acao]:
    """O que o turno fez (ou pode ter feito), na ordem."""
    if not turno:
        return []
    with _sessao() as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE turno = ? ORDER BY id", (turno,)
        ).fetchall()
    return [_acao(linha) for linha in linhas]


def recentes(*, dias: int = 1, limite: int = 50, agora: datetime | None = None) -> list[Acao]:
    """As mais novas primeiro, desde `dias` atrás."""
    desde = _agora(agora) - timedelta(days=max(1, dias))
    with _sessao(agora) as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE criada_em >= ? ORDER BY id DESC LIMIT ?",
            (desde.isoformat(), limite),
        ).fetchall()
    return [_acao(linha) for linha in linhas]


def obter(acao_id: int) -> Acao | None:
    with _sessao() as conn:
        linha = conn.execute("SELECT * FROM acoes WHERE id = ?", (acao_id,)).fetchone()
    return _acao(linha) if linha else None


def ultima_desfazivel(
    operacoes: tuple[str, ...], *, prefixo_turno: str, janela: timedelta, agora=None
) -> Acao | None:
    """A mais nova destas operações, feita nesta sessão (turnos com `prefixo_turno`), dentro da
    `janela` e ainda não desfeita."""
    if not prefixo_turno or not operacoes:
        return None
    desde = _agora(agora) - janela
    marcas = ",".join("?" * len(operacoes))
    with _sessao(agora) as conn:
        # Começo exato do texto, não `LIKE`: `%` e `_` seriam curingas vindos do prefixo.
        linha = conn.execute(
            f"SELECT * FROM acoes WHERE operacao IN ({marcas}) AND estado = ? "
            "AND desfazer IS NOT NULL AND desfeita_em IS NULL AND criada_em >= ? "
            "AND substr(turno, 1, ?) = ? ORDER BY id DESC LIMIT 1",
            (*operacoes, FEITA, desde.isoformat(), len(prefixo_turno), prefixo_turno),
        ).fetchone()
    return _acao(linha) if linha else None


def reivindicar_desfazer(acao_id: int) -> dict[str, Any] | None:
    """Marca como desfeita e devolve a cópia bruta — uma vez só (`UPDATE ... WHERE desfeita_em IS
    NULL`, como `confirmacao.consumir`). `None` se já desfeita, sem cópia ou não feita."""
    with _sessao() as conn:
        cursor = conn.execute(
            "UPDATE acoes SET desfeita_em = ? "
            "WHERE id = ? AND desfeita_em IS NULL AND desfazer IS NOT NULL AND estado = ?",
            (_agora().isoformat(), acao_id, FEITA),
        )
        if cursor.rowcount != 1:
            return None
        linha = conn.execute("SELECT desfazer FROM acoes WHERE id = ?", (acao_id,)).fetchone()
    return json.loads(linha["desfazer"])


def devolver_desfazer(acao_id: int) -> None:
    """O desfazer falhou: a ação volta a ser desfazível."""
    with _sessao() as conn:
        conn.execute("UPDATE acoes SET desfeita_em = NULL WHERE id = ?", (acao_id,))
