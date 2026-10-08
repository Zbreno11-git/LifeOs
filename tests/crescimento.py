"""Detector de custo quadrático (ReDoS) que não depende da velocidade da máquina (2026-10-08).

Os testes de "texto gigante não explode" tinham um limite fixo (`< 2` s). No Mac do dono (2017,
Intel), o caso da chave privada levou 2,09 s, e o VPS faz o mesmo em 0,44 s, com o custo linear
(medido: o dobro de linhas, o dobro do tempo). O que eles querem pegar é o **crescimento**: com 4× a
entrada, o custo linear leva ~4× o tempo e o quadrático ~16×, em qualquer máquina.
"""

from __future__ import annotations

import time
from collections.abc import Callable

FATOR = 4  # a entrada grande tem 4× a pequena
RAZAO_MAX = 8.0  # o linear dá ~4 e o quadrático ~16: o meio, com folga para o ruído
PISO_S = 0.005  # abaixo disso o relógio mede ruído: a pequena conta pelo menos isso


def _melhor_de(funcao: Callable[[], object], vezes: int = 2) -> float:
    melhor = float("inf")
    for _ in range(vezes):
        inicio = time.perf_counter()
        funcao()
        melhor = min(melhor, time.perf_counter() - inicio)
    return melhor


def razao(executar: Callable[[int], Callable[[], object]]) -> float:
    """`executar(k)` monta a entrada de tamanho `k` (fora do relógio) e devolve o que se mede."""
    pequena, grande = executar(1), executar(FATOR)
    return _melhor_de(grande) / max(_melhor_de(pequena), PISO_S)


def cresce_linear(executar: Callable[[int], Callable[[], object]]) -> None:
    medida = razao(executar)
    assert medida < RAZAO_MAX, f"com {FATOR}× a entrada, {medida:.1f}× o tempo (quadrático?)"
