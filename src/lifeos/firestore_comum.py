"""O que todo store do Firestore usa (Sessão 10b): o cliente, a troca que só grava se o documento
não mudou, e a conversão dos instantes. Os consumidores são os lembretes
(`reminders/store_firestore.py`), o registro de ações (`registro_firestore.py`) e o teto de gasto
(`custos.py`); três cópias do mesmo laço divergiriam.

Só roda onde o extra `nuvem` está instalado (Linux: o motor, o VPS, o CI); o import do SDK é
preguiçoso. Sob pytest, nenhum cliente nasce sem `FIRESTORE_EMULATOR_HOST`: o VPS tem o login do
dono vivo, e um cliente sem emulador gravaria no Firestore de verdade.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lifeos import config

if TYPE_CHECKING:
    from google.cloud.firestore import Client, DocumentReference

_CLIENTE: Client | None = None


def cliente() -> Client:
    global _CLIENTE
    if _CLIENTE is None:
        emulador = os.getenv("FIRESTORE_EMULATOR_HOST")
        if "pytest" in sys.modules and not emulador:
            raise RuntimeError(
                "sob pytest o Firestore só abre no emulador (FIRESTORE_EMULATOR_HOST)"
            )
        projeto = config.NUVEM_PROJETO or ("viking-emulador" if emulador else "")
        if not projeto:
            raise RuntimeError(
                "VIKING_NUVEM_PROJETO vazio: o Firestore não sabe em que projeto abrir"
            )
        from google.cloud import firestore

        _CLIENTE = firestore.Client(project=projeto, database="(default)")
    return _CLIENTE


def instante(momento: datetime) -> datetime:
    """Só instantes: sem fuso é recusado (a borda converte)."""
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("horário sem fuso: o store só grava instantes (converta na borda)")
    return momento.astimezone(UTC)


def lido(valor: Any) -> datetime | None:
    """O `Timestamp` do Firestore volta como uma subclasse de `datetime`: vira um `datetime` comum
    em UTC, com os microssegundos."""
    if valor is None:
        return None
    utc = valor.astimezone(UTC)
    return datetime(
        utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second, utc.microsecond, tzinfo=UTC
    )


TENTATIVAS = 20  # cada volta perdida é uma escrita de outra execução que deu certo


class PerdeuADisputa(RuntimeError):
    """O documento mudou entre a leitura e a escrita em todas as tentativas."""


def trocar(ref: DocumentReference, decidir: Any) -> Any:
    """Comparar e trocar: lê sem travar, `decidir(snap)` devolve `(mudança ou None, resposta)`, e a
    mudança só grava se o documento não mudou desde a leitura (`last_update_time`). Se mudou, outra
    execução gravou antes: lê de novo e decide sobre o estado novo.

    Não é transação de propósito (medido no emulador em 2026-09-29): com 16 execuções juntas, a
    transação trava o documento para cada leitor, as escritas se esperam até "Transaction lock
    timeout", e em 5 de 10 rodadas quem desistia não achava vencedor nenhum. Aqui cada volta
    perdida quer dizer que outra execução gravou, então a disputa sempre termina."""
    import random
    import time

    from google.api_core.exceptions import Aborted, FailedPrecondition

    for tentativa in range(TENTATIVAS):
        snap = ref.get()
        mudanca, resposta = decidir(snap)
        if mudanca is None:
            return resposta
        opcao = cliente().write_option(last_update_time=snap.update_time)
        try:
            ref.update(mudanca, option=opcao)
        except FailedPrecondition:
            continue  # outra execução gravou depois da leitura: o estado novo decide
        except Aborted:
            # A escrita não foi aplicada (escritas juntas no mesmo documento; o emulador responde
            # "Transaction lock timeout"), mas isso não prova que outra venceu: espera um pouco,
            # com sorteio para as execuções não voltarem juntas, e relê.
            time.sleep(random.uniform(0, 0.05 * 2 ** min(tentativa, 5)))
            continue
        return resposta
    raise PerdeuADisputa(f"o documento {ref.id} mudou em todas as {TENTATIVAS} tentativas")
