"""As confirmações no `viking.db` do Mac (tabela `confirmacoes`, migrações 4 e 6): a implementação
de `confirmacao_interface.Confirmacoes` que o chat do Mac, o MCP e a CLI usam. O SQL é o de antes
da Sessão 10c, movido de `confirmacao.py`; a regra continua lá.

A reserva do código não é uma tabela: um número está reservado enquanto alguma linha com ele não
venceu ou foi usada há menos da janela. `propor` lê os reservados e grava a proposta dentro de uma
transação `BEGIN IMMEDIATE`: sem ela, a leitura roda fora de transação (o `banco.conectar` só abre
uma antes do primeiro comando que escreve), e dois processos com `substituir=False` sorteavam o
mesmo número (medido no CI em 2026-09-30, um defeito desde a Sessão 5). Gastar é um `UPDATE ...
WHERE estado = 'aberta'`: só um leva.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from lifeos import banco
from lifeos.confirmacao_interface import (
    ABERTA,
    CONSUMIDA,
    SUBSTITUIDA,
    ErroConfirmacao,
    Linha,
    Proposta,
)


def _linha(linha: sqlite3.Row) -> Linha:
    return Linha(
        id=linha["id"],
        acao=linha["acao"],
        codigo=linha["codigo"],
        dados=json.loads(linha["dados"]),
        estado=linha["estado"],
        criada_em=datetime.fromisoformat(linha["criada_em"]),
        expira_em=datetime.fromisoformat(linha["expira_em"]),
        consumida_em=(
            datetime.fromisoformat(linha["consumida_em"]) if linha["consumida_em"] else None
        ),
        resultado=json.loads(linha["resultado"]) if linha["resultado"] else {},
        erros=linha["erros"],
    )


def propor(
    acao: str,
    dados: dict[str, Any],
    *,
    criada_em: datetime,
    expira_em: datetime,
    substituir: bool,
    janela_unica: timedelta,
    sortear: Callable[[], str],
    maximo: int,
) -> Proposta:
    with banco.conectar() as conn:
        # A trava de escrita antes de ler os reservados: quem vem depois espera esta proposta
        # nascer e já a vê (ver o topo).
        conn.execute("BEGIN IMMEDIATE")
        if substituir:
            conn.execute(
                "UPDATE confirmacoes SET estado = ? WHERE acao = ? AND estado = ?",
                (SUBSTITUIDA, acao, ABERTA),
            )
        reservados = {
            linha["codigo"]
            for linha in conn.execute(
                # Substituída também reserva até vencer: senão a proposta nova podia sortear o
                # número da velha, e o código lido na primeira lista aprovaria a segunda.
                "SELECT codigo FROM confirmacoes "
                "WHERE expira_em >= ? OR (estado = ? AND consumida_em >= ?)",
                (criada_em.isoformat(), CONSUMIDA, (criada_em - janela_unica).isoformat()),
            )
        }
        if len(reservados) >= maximo:
            raise ErroConfirmacao("códigos demais em uso; tente mais tarde")
        while (codigo := sortear()) in reservados:
            pass
        cursor = conn.execute(
            "INSERT INTO confirmacoes (acao, codigo, dados, criada_em, expira_em, estado) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (acao, codigo, json.dumps(dados), criada_em.isoformat(), expira_em.isoformat(), ABERTA),
        )
        assert cursor.lastrowid is not None
        return Proposta(cursor.lastrowid, acao, codigo, dados, expira_em)


def abertas(acao: str, *, agora: datetime) -> list[Proposta]:
    with banco.conectar() as conn:
        linhas = conn.execute(
            "SELECT * FROM confirmacoes WHERE acao = ? AND estado = ? AND expira_em >= ? "
            "ORDER BY id",
            (acao, ABERTA, agora.isoformat()),
        ).fetchall()
    return [
        Proposta(
            linha["id"],
            linha["acao"],
            linha["codigo"],
            json.loads(linha["dados"]),
            datetime.fromisoformat(linha["expira_em"]),
        )
        for linha in linhas
    ]


def mais_recente(acao: str, codigo: str) -> Linha | None:
    with banco.conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM confirmacoes WHERE acao = ? AND codigo = ? ORDER BY id DESC LIMIT 1",
            (acao, codigo),
        ).fetchone()
    return _linha(linha) if linha else None


def mais_recente_do_codigo(codigo: str) -> Linha | None:
    with banco.conectar() as conn:
        linha = conn.execute(
            "SELECT * FROM confirmacoes WHERE codigo = ? ORDER BY id DESC LIMIT 1", (codigo,)
        ).fetchone()
    return _linha(linha) if linha else None


def criadas_desde(acao: str, desde: datetime) -> int:
    with banco.conectar() as conn:
        (total,) = conn.execute(
            "SELECT COUNT(*) FROM confirmacoes WHERE acao = ? AND criada_em >= ?",
            (acao, desde.isoformat()),
        ).fetchone()
    return int(total)


def cancelar(acao: str) -> None:
    with banco.conectar() as conn:
        conn.execute(
            "UPDATE confirmacoes SET estado = ? WHERE acao = ? AND estado = ?",
            (SUBSTITUIDA, acao, ABERTA),
        )


def consumir(proposta_id: int, *, agora: datetime, reservar_ate: datetime) -> Linha | None:
    """A reserva do código é derivada de `consumida_em` (ver o topo): `reservar_ate` já está nela."""
    del reservar_ate
    with banco.conectar() as conn:
        # `estado = 'aberta'` no WHERE: dois processos com o mesmo código, só um consome.
        cursor = conn.execute(
            "UPDATE confirmacoes SET estado = ?, consumida_em = ? WHERE id = ? AND estado = ?",
            (CONSUMIDA, agora.isoformat(), proposta_id, ABERTA),
        )
        if cursor.rowcount != 1:
            return None
        gasta = conn.execute("SELECT * FROM confirmacoes WHERE id = ?", (proposta_id,)).fetchone()
    if gasta is None:  # a mesma transação acabou de gastá-la: não some sem outro erro antes
        raise ErroConfirmacao("a proposta sumiu durante a confirmação")
    return _linha(gasta)


def registrar(proposta_id: int, resultado: dict[str, Any]) -> None:
    with banco.conectar() as conn:
        conn.execute(
            "UPDATE confirmacoes SET resultado = ? WHERE id = ?",
            (json.dumps(resultado), proposta_id),
        )


def errar(acao: str, *, agora: datetime, limite: int) -> int | None:
    with banco.conectar() as conn:
        conn.execute(
            "UPDATE confirmacoes SET erros = erros + 1 "
            "WHERE acao = ? AND estado = ? AND expira_em >= ?",
            (acao, ABERTA, agora.isoformat()),
        )
        (mais,) = conn.execute(
            "SELECT MAX(erros) FROM confirmacoes WHERE acao = ? AND estado = ? AND expira_em >= ?",
            (acao, ABERTA, agora.isoformat()),
        ).fetchone()
        if mais is None:
            return None
        conn.execute(
            "UPDATE confirmacoes SET estado = ? WHERE acao = ? AND estado = ? AND erros >= ?",
            (SUBSTITUIDA, acao, ABERTA, limite),
        )
    return max(limite - int(mais), 0)
