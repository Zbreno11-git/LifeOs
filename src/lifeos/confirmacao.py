"""Confirmação mecânica: o dono aprova uma ação exata digitando um código curto.

Primeiro uso: a limpeza do Gmail (Sessão Gmail 2). A Sessão 5 reaproveita para o freio de
cliques e a exclusão no calendário. O código **nunca passa pelo Gemini**: quem o mostra é o
Viking, direto no terminal, e quem o lê é o laço do chat, antes de mandar a linha ao modelo
(`assistant/agent.py`). Por isso um conteúdo com prompt injection pode, no máximo, fazer o Gemini
*propor* uma ação — aprovar, só quem está no teclado.

Guarda em SQLite (`viking.db`, tabela `confirmacoes`): a ação, os dados exatos aprovados, a
validade e o resultado. Regras:
- o código vale uma vez e por `VALIDADE`;
- uma proposta nova da mesma ação substitui as abertas (um código velho não aprova outra lista);
- um código não se repete na mesma ação dentro de `JANELA_UNICA`, para "desfaz NNNN" não ter
  dois donos.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos.config import REMINDERS_DB_PATH

DB_PATH = REMINDERS_DB_PATH  # o mesmo `viking.db`; os testes trocam este nome
VALIDADE = timedelta(minutes=10)
JANELA_UNICA = timedelta(days=8)  # > os 7 dias do desfazer da limpeza (D27)
DIGITOS = 4
# `[0-9]`, não `\d`: no Python `\d` casa também dígitos de outros alfabetos ("１２３４").
_CODIGO = re.compile(rf"[0-9]{{{DIGITOS}}}")

_SCHEMA = """
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
"""


class ErroConfirmacao(Exception):
    codigo = "confirmacao_invalida"


class CodigoInvalido(ErroConfirmacao):
    """Não há proposta com esse código para essa ação (nunca houve, ou foi substituída)."""


class Expirado(ErroConfirmacao):
    codigo = "confirmacao_expirada"


class JaUsado(ErroConfirmacao):
    codigo = "confirmacao_ja_usada"


@dataclass(frozen=True)
class Proposta:
    id: int
    acao: str
    codigo: str
    dados: dict[str, Any]
    expira: datetime


@dataclass(frozen=True)
class Registro:
    id: int
    acao: str
    codigo: str
    dados: dict[str, Any]
    consumida_em: datetime | None
    resultado: dict[str, Any] = field(default_factory=dict)


def _agora(agora: datetime | None) -> datetime:
    return (agora or datetime.now(UTC)).astimezone(UTC)


@contextmanager
def _sessao():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def normalizar(codigo: str) -> str:
    """O código como o dono digitou, sem espaço; formato errado vira `CodigoInvalido`."""
    limpo = "".join(str(codigo or "").split())
    if not _CODIGO.fullmatch(limpo):
        raise CodigoInvalido(f"o código tem {DIGITOS} dígitos")
    return limpo


def propor(acao: str, dados: dict[str, Any], *, agora: datetime | None = None) -> Proposta:
    agora = _agora(agora)
    expira = agora + VALIDADE
    with _sessao() as conn:
        conn.execute(
            "UPDATE confirmacoes SET estado = 'substituida' WHERE acao = ? AND estado = 'aberta'",
            (acao,),
        )
        recentes = {
            linha["codigo"]
            for linha in conn.execute(
                "SELECT codigo FROM confirmacoes WHERE acao = ? AND criada_em >= ?",
                (acao, (agora - JANELA_UNICA).isoformat()),
            )
        }
        if len(recentes) >= 10**DIGITOS // 2:
            raise ErroConfirmacao("códigos demais em uso para esta ação; tente mais tarde")
        while (codigo := f"{secrets.randbelow(10**DIGITOS):0{DIGITOS}d}") in recentes:
            pass
        cursor = conn.execute(
            "INSERT INTO confirmacoes (acao, codigo, dados, criada_em, expira_em, estado) "
            "VALUES (?, ?, ?, ?, ?, 'aberta')",
            (acao, codigo, json.dumps(dados), agora.isoformat(), expira.isoformat()),
        )
        return Proposta(cursor.lastrowid, acao, codigo, dados, expira)


def cancelar(acao: str) -> None:
    """Invalida as propostas abertas da ação (ex.: uma proposta nova que não tem o que aprovar)."""
    with _sessao() as conn:
        conn.execute(
            "UPDATE confirmacoes SET estado = 'substituida' WHERE acao = ? AND estado = 'aberta'",
            (acao,),
        )


def _registro(linha: sqlite3.Row) -> Registro:
    return Registro(
        id=linha["id"],
        acao=linha["acao"],
        codigo=linha["codigo"],
        dados=json.loads(linha["dados"]),
        consumida_em=(
            datetime.fromisoformat(linha["consumida_em"]) if linha["consumida_em"] else None
        ),
        resultado=json.loads(linha["resultado"]) if linha["resultado"] else {},
    )


def _mais_recente(conn: sqlite3.Connection, acao: str, codigo: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM confirmacoes WHERE acao = ? AND codigo = ? ORDER BY id DESC LIMIT 1",
        (acao, codigo),
    ).fetchone()


def consumir(acao: str, codigo: str, *, agora: datetime | None = None) -> Registro:
    """Gasta o código: devolve os dados exatos que foram aprovados, uma vez só."""
    codigo = normalizar(codigo)
    agora = _agora(agora)
    with _sessao() as conn:
        linha = _mais_recente(conn, acao, codigo)
        if linha is None or linha["estado"] == "substituida":
            raise CodigoInvalido("esse código não corresponde à proposta aberta")
        if linha["estado"] == "consumida":
            raise JaUsado("esse código já foi usado")
        if datetime.fromisoformat(linha["expira_em"]) < agora:
            raise Expirado("o código venceu; peça a lista de novo")
        # `estado = 'aberta'` no WHERE: dois processos com o mesmo código, só um consome.
        cursor = conn.execute(
            "UPDATE confirmacoes SET estado = 'consumida', consumida_em = ? "
            "WHERE id = ? AND estado = 'aberta'",
            (agora.isoformat(), linha["id"]),
        )
        if cursor.rowcount != 1:
            raise JaUsado("esse código já foi usado")
        return _registro(_mais_recente(conn, acao, codigo))


def registrar(registro_id: int, resultado: dict[str, Any]) -> None:
    with _sessao() as conn:
        conn.execute(
            "UPDATE confirmacoes SET resultado = ? WHERE id = ?",
            (json.dumps(resultado), registro_id),
        )


def consumida(
    acao: str, codigo: str, *, janela: timedelta, agora: datetime | None = None
) -> Registro:
    """Uma ação já aprovada e executada, para desfazer dentro da `janela`."""
    codigo = normalizar(codigo)
    agora = _agora(agora)
    with _sessao() as conn:
        linha = _mais_recente(conn, acao, codigo)
    if linha is None or linha["estado"] != "consumida":
        raise CodigoInvalido("não há ação feita com esse código")
    registro = _registro(linha)
    if registro.consumida_em is None or registro.consumida_em + janela < agora:
        raise Expirado("passou o prazo para desfazer")
    return registro
