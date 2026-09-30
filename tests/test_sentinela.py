"""O verificador de código vazado (`tests/sentinela.py`): pega o código solto e ignora o que só
contém os mesmos dígitos."""

import pytest
from tests.sentinela import aparece


@pytest.mark.parametrize(
    "texto",
    ["confirma 4821", "4821", "código: 4821.", "(4821)", "desfaz 4821\n", "'4821'", "x 4821 y"],
)
def test_pega_o_codigo_solto(texto):
    assert aparece("4821", texto)


@pytest.mark.parametrize(
    "texto",
    [
        "2026-09-30 06:57:07.148214+00:00",
        "id=1759215427148214000",
        "uuid a4821bcd-0000",
        "44821",
        "48210",
        "sem nada",
    ],
)
def test_ignora_os_mesmos_digitos_dentro_de_outro_numero(texto):
    assert not aparece("4821", texto)
