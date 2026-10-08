"""O detector de custo quadrático (`tests/crescimento.py`) separa o linear do quadrático.

Sem este teste, uma régua que nunca cai (o piso alto demais, a razão alta demais) deixaria verdes os
testes de "texto gigante não explode" com um ReDoS de verdade no código (medido em 2026-10-08: com a
entrada pequena abaixo do piso, a regex quadrática deu 5,5× e passou).
"""

import re

import pytest
from tests import crescimento


def _regex(padrao, tamanho):
    def executar(k):
        texto = "a" * (tamanho * k)
        return lambda: re.findall(padrao, texto)

    return executar


def test_o_custo_quadratico_cai():
    # `a*b` em "aaa…": cada posição consome o resto e falha (o ReDoS clássico, ~16×)
    with pytest.raises(AssertionError, match="quadrático"):
        crescimento.cresce_linear(_regex(r"a*b", 5_000))


def test_o_custo_linear_passa():
    crescimento.cresce_linear(_regex(r"b", 2_000_000))
