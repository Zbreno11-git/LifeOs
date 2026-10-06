"""O registro de ações no `viking.db` (tabela `acoes`): a implementação do Mac de
`registro_interface.Registro`. A regra mora em `registro.py`; aqui só se guarda e se busca.

A tabela nasce e muda só pelas migrations de `lifeos/banco.py` (Sessão 9).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from lifeos import banco
from lifeos.registro_interface import (
    CAMPOS_DA_COPIA,
    CRIADA,
    DIFERENTE,
    FALHOU,
    FEITA,
    IGUAL,
    INSTANTES_DA_COPIA,
    Acao,
    texto_do_instante,
)


@contextmanager
def _sessao() -> Iterator[sqlite3.Connection]:
    with banco.conectar() as conn:
        yield conn


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


def purgar(antes_de: datetime) -> None:
    with _sessao() as conn:
        conn.execute("DELETE FROM acoes WHERE criada_em < ?", (antes_de.isoformat(),))


def iniciar(*, turno: str, origem: str, operacao: str, parametros: str, criada_em: datetime) -> int:
    with _sessao() as conn:
        cursor = conn.execute(
            "INSERT INTO acoes (turno, origem, operacao, parametros, estado, criada_em) "
            "VALUES (?, ?, ?, ?, 'iniciada', ?)",
            (turno, origem, operacao, parametros, criada_em.isoformat()),
        )
        if cursor.lastrowid is None:  # um INSERT sem erro sempre tem rowid; se faltar, erra alto
            raise sqlite3.DatabaseError("o registro da ação não voltou do banco")
        return cursor.lastrowid


def terminar(
    acao_id: int,
    *,
    estado: str,
    resultado: str,
    erro: str,
    desfazer: str | None,
    terminada_em: datetime,
) -> None:
    with _sessao() as conn:
        conn.execute(
            "UPDATE acoes SET estado = ?, resultado = ?, erro = ?, desfazer = ?, "
            "terminada_em = ? WHERE id = ?",
            (estado, resultado, erro, desfazer, terminada_em.isoformat(), acao_id),
        )


def do_turno(turno: str, *, desde: datetime) -> list[Acao]:
    with _sessao() as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE turno = ? AND criada_em >= ? ORDER BY id",
            (turno, desde.isoformat()),
        ).fetchall()
    return [_acao(linha) for linha in linhas]


def recentes(*, desde: datetime, limite: int) -> list[Acao]:
    with _sessao() as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE criada_em >= ? ORDER BY id DESC LIMIT ?",
            (desde.isoformat(), limite),
        ).fetchall()
    return [_acao(linha) for linha in linhas]


def contaveis(operacao: str, *, desde: datetime) -> list[Acao]:
    with _sessao() as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE operacao = ? AND criada_em >= ? AND estado != ? ORDER BY id",
            (operacao, desde.isoformat(), FALHOU),
        ).fetchall()
    return [_acao(linha) for linha in linhas]


def obter(acao_id: int, *, desde: datetime) -> Acao | None:
    with _sessao() as conn:
        linha = conn.execute(
            "SELECT * FROM acoes WHERE id = ? AND criada_em >= ?", (acao_id, desde.isoformat())
        ).fetchone()
    return _acao(linha) if linha else None


def ultima_desfazivel(
    operacoes: tuple[str, ...], *, prefixo_turno: str, desde: datetime
) -> Acao | None:
    marcas = ",".join("?" * len(operacoes))
    with _sessao() as conn:
        # Começo exato do texto, não `LIKE`: `%` e `_` seriam curingas vindos do prefixo.
        linha = conn.execute(
            f"SELECT * FROM acoes WHERE operacao IN ({marcas}) AND estado = ? "
            "AND desfazer IS NOT NULL AND desfeita_em IS NULL AND criada_em >= ? "
            "AND substr(turno, 1, ?) = ? ORDER BY id DESC LIMIT 1",
            (*operacoes, FEITA, desde.isoformat(), len(prefixo_turno), prefixo_turno),
        ).fetchone()
    return _acao(linha) if linha else None


def reivindicar_desfazer(acao_id: int, *, agora: datetime) -> str | None:
    with _sessao() as conn:
        cursor = conn.execute(
            "UPDATE acoes SET desfeita_em = ? "
            "WHERE id = ? AND desfeita_em IS NULL AND desfazer IS NOT NULL AND estado = ?",
            (agora.isoformat(), acao_id, FEITA),
        )
        if cursor.rowcount != 1:
            return None
        linha = conn.execute("SELECT desfazer FROM acoes WHERE id = ?", (acao_id,)).fetchone()
    return linha["desfazer"]


def devolver_desfazer(acao_id: int) -> None:
    with _sessao() as conn:
        conn.execute("UPDATE acoes SET desfeita_em = NULL WHERE id = ?", (acao_id,))


def _copia(linha: sqlite3.Row) -> dict[str, Any]:
    copia = {campo: linha[campo] for campo in CAMPOS_DA_COPIA}
    for campo in INSTANTES_DA_COPIA:
        texto = copia[campo]
        copia[campo] = texto_do_instante(datetime.fromisoformat(texto)) if texto else None
    return copia


def exportar(*, desde: datetime) -> list[dict[str, Any]]:
    with _sessao() as conn:
        linhas = conn.execute(
            "SELECT * FROM acoes WHERE criada_em >= ? ORDER BY id", (desde.isoformat(),)
        ).fetchall()
    return [_copia(linha) for linha in linhas]


def importar(copia: dict[str, Any]) -> str:
    """No Mac, só o `viking backup --conferir` grava cópia, num `viking.db` temporário (D63). Os
    instantes voltam ao texto que `iniciar` grava (`isoformat()` em UTC)."""
    valores = dict(copia)
    for campo in INSTANTES_DA_COPIA:
        texto = valores[campo]
        valores[campo] = datetime.fromisoformat(texto).isoformat() if texto else None
    colunas = ", ".join(CAMPOS_DA_COPIA)
    marcas = ", ".join("?" * len(CAMPOS_DA_COPIA))
    with _sessao() as conn:
        cursor = conn.execute(
            f"INSERT INTO acoes ({colunas}) VALUES ({marcas}) ON CONFLICT (id) DO NOTHING",
            tuple(valores[campo] for campo in CAMPOS_DA_COPIA),
        )
        if cursor.rowcount == 1:
            return CRIADA
        linha = conn.execute("SELECT * FROM acoes WHERE id = ?", (copia["id"],)).fetchone()
    return IGUAL if linha is not None and _copia(linha) == copia else DIFERENTE
