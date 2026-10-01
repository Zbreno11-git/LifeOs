"""Apaga os lembretes "Pagar conta" que a suíte de testes gravou no `viking.db` (Sessão 9).

De 2026-09-27 (Sessão 5) a 2026-09-29, cada `python -m pytest` gravava e concluía um "Pagar
conta" no banco de verdade (`docs/erros.md`, classe 6). O dono pediu para apagar (2026-09-29),
depois do backup. O critério é o do lixo, exato:
- título "Pagar conta", corpo vazio, tags `[]`, sem prazo, `source` "manual" (o chat grava
  "viking-cli", o MCP "mcp");
- concluído menos de 1 s depois de criado (o teste concluía na mesma chamada: ≤ 0,014 s no VPS).

    python scripts/limpar_lembretes_de_teste.py              (só conta; nada muda)
    python scripts/limpar_lembretes_de_teste.py --aplicar    (apaga, numa transação)

Abre o banco pelo `lifeos.banco` (o que também migra, com o backup automático). Não mostra
título nem id de nenhum outro lembrete: a saída é colada em conversa. Depois que os lembretes do
Mac migraram para a nuvem (Sessão 11, D61), o `--aplicar` recusa: o `viking.db` é a cópia de
antes, e apagar nela não tiraria nada da nuvem.
"""

import argparse
import sys
from datetime import datetime, timedelta

from lifeos import banco
from lifeos.reminders import onde

LIMITE = timedelta(seconds=1)


def _lixo(conn) -> list[str]:
    candidatos = conn.execute(
        "SELECT id, created_at, completed_at FROM reminders "
        "WHERE title = 'Pagar conta' AND body = '' AND tags = '[]' AND due_at IS NULL "
        "AND source = 'manual' AND completed_at IS NOT NULL"
    ).fetchall()
    return [
        reminder_id
        for reminder_id, criado, feito in candidatos
        if timedelta(0) <= datetime.fromisoformat(feito) - datetime.fromisoformat(criado) < LIMITE
    ]


def main(argv: list[str]) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--aplicar", action="store_true", help="apaga (sem isto, só conta)")
    args = leitor.parse_args(argv)
    with banco.conectar() as conn:
        (total,) = conn.execute("SELECT count(*) FROM reminders").fetchone()
        lixo = _lixo(conn)
        print(
            f"Achei {len(lixo)} lembrete(s) de teste ('Pagar conta' concluído em menos de 1 s), "
            f"de {total} no banco."
        )
        if not args.aplicar:
            print(
                "Nada apagado. Para apagar: python scripts/limpar_lembretes_de_teste.py --aplicar"
            )
            return 0
    if onde.estado() is not None:
        print(
            "Nada apagado: os lembretes deste Mac migraram para a nuvem, e o viking.db é a cópia "
            "de antes (apagar aqui não tiraria nada de lá)."
        )
        return 1
    with banco.conectar() as conn:
        lixo = _lixo(conn)
        conn.executemany("DELETE FROM reminders WHERE id = ?", [(i,) for i in lixo])
        (depois,) = conn.execute("SELECT count(*) FROM reminders").fetchone()
    print(f"Apaguei {len(lixo)}. Lembretes no banco: {total} antes, {depois} depois.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
