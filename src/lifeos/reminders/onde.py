"""Onde moram os lembretes deste Mac (Sessão 11, D61): a marca da migração 7 do `viking.db`.

- **sem a marca:** no `viking.db`, como sempre;
- **"migrando":** a cópia para a nuvem está em curso (`viking lembretes --migrar --executar`), e as
  gravações daqui param (uma gravação no meio ficaria fora da cópia);
- **"migrado":** o Mac lê e grava na nuvem, pelo motor (`reminders/service.py`); a tabela
  `reminders` vira a cópia congelada de antes, e o envio por e-mail é só da nuvem.

A marca mora no banco, e não numa variável de ambiente que se esqueça. No motor
(`VIKING_STORE=firestore`) não há marca nem `viking.db`: os lembretes já são os da nuvem.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from datetime import UTC, datetime

from lifeos import banco, config

MIGRANDO, MIGRADO = "migrando", "migrado"


class MigracaoEmCurso(RuntimeError):
    """A cópia para a nuvem não terminou: nada se grava aqui até ela terminar."""


def estado() -> str | None:
    if config.STORE == "firestore":
        return None
    with banco.conectar() as conn:
        linha = conn.execute("SELECT estado FROM lembretes_na_nuvem WHERE id = 1").fetchone()
    return linha[0] if linha else None


def marcar(novo: str) -> None:
    if novo not in (MIGRANDO, MIGRADO):
        raise ValueError(f"estado desconhecido: {novo!r}")
    em = datetime.now(UTC).isoformat(timespec="microseconds")
    with banco.conectar() as conn:
        conn.execute(
            "INSERT INTO lembretes_na_nuvem (id, estado, em) VALUES (1, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET estado = excluded.estado, em = excluded.em",
            (novo, em),
        )


def na_nuvem() -> bool:
    """Os lembretes deste Mac moram na nuvem? `MigracaoEmCurso` no meio da cópia."""
    agora = estado()
    if agora == MIGRANDO:
        raise MigracaoEmCurso(
            "a cópia dos lembretes para a nuvem não terminou: rode de novo `viking lembretes "
            "--migrar --executar` (ela retoma de onde parou); até lá, nada se grava aqui"
        )
    return agora == MIGRADO
