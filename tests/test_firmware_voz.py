"""O firmware do aparelho (`firmware/viking-voz/src/main.cpp`) contra os tetos do Python (H1, D70).

O teto da gravação mora no C++ e o do WAV na ponte e no motor: nada os ligava. No E2E de
2026-11-22 o teto subiu de 15 para 30 s (o ditado de um endereço era cortado sem aviso); se um
dia subir além do que o motor aceita, toda fala longa voltaria 413 e nenhum teste diria. Este teste
lê as constantes do firmware e confere o WAV que ele monta contra `voz.MAX_WAV` e o da ponte.
"""

import re
from pathlib import Path

from lifeos.assistant import voz
from lifeos.casa import servidor

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "viking-voz" / "src" / "main.cpp"
CABECALHO_WAV = 44  # o `montarWav`: RIFF + fmt + data


def _constante(nome: str) -> int:
    achados = re.findall(rf"constexpr \w+ {nome} = (\d+);", FIRMWARE.read_text())
    assert len(achados) == 1, f"{nome}: {achados}"
    return int(achados[0])


def test_a_gravacao_mais_longa_do_firmware_cabe_no_motor_e_na_ponte():
    taxa, segundos = _constante("TAXA"), _constante("MAX_GRAVACAO_S")
    maior_wav = CABECALHO_WAV + taxa * segundos * 2  # 16 bits, mono
    assert taxa == voz.TAXA_DE_ENTRADA
    assert maior_wav <= voz.MAX_WAV
    assert maior_wav <= servidor.MAX_WAV


def test_o_aviso_do_fim_da_gravacao_vem_antes_do_fim():
    assert 0 < _constante("AVISO_S") < _constante("MAX_GRAVACAO_S")
