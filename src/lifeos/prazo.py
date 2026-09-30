"""O prazo do turno na nuvem (Sessão 10c, D60): um instante-limite que as esperas consultam.

No motor, um turno tem de terminar antes que o Cloud Run o mate (`--timeout=300`) e antes que o
terminal do Mac desista (320 s). Sem prazo, uma chamada do Gmail podia passar de 500 s: até 7
tentativas, cada uma com até 60 s de rede (medido: `googleapiclient` 2.200.0,
`DEFAULT_HTTP_TIMEOUT_SEC = 60`), e as esperas de cota somam 126 s. Quem espera pergunta antes
(`cabe`): uma espera que passaria do limite não começa, e o turno diz que não deu tempo.

No Mac não há prazo (`restante()` é `None`): o dono vê o terminal esperar e pode interromper.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_LIMITE: ContextVar[float | None] = ContextVar("viking_prazo", default=None)


class TempoEsgotado(RuntimeError):
    """O que falta do turno não cabe no prazo: a chamada não começa."""


def _relogio() -> float:
    return time.monotonic()


@contextmanager
def ate(segundos: float) -> Iterator[None]:
    """Durante o bloco, o turno tem `segundos` a partir de agora."""
    token = _LIMITE.set(_relogio() + segundos)
    try:
        yield
    finally:
        _LIMITE.reset(token)


def restante() -> float | None:
    """Quanto falta do prazo; `None` sem prazo (o Mac)."""
    limite = _LIMITE.get()
    return None if limite is None else limite - _relogio()


def cabe(segundos: float) -> bool:
    falta = restante()
    return falta is None or falta >= segundos


def conferir(segundos: float, o_que: str) -> None:
    """`TempoEsgotado` se `o_que` (até `segundos`) não cabe no que falta do prazo."""
    if not cabe(segundos):
        falta = max(restante() or 0.0, 0.0)
        raise TempoEsgotado(
            f"não deu tempo: {o_que} leva até {segundos:.0f} s, e faltam {falta:.0f} s do turno"
        )
