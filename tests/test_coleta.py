"""O `firmware/viking-voz/coleta.py` (H2): a conferência dos quadros da coleta da wake word, sem a
placa. O que decide se um WAV serve para o treino é o checksum, o seq e o tempo; e nada de voz pode
cair dentro do repo, que é público."""

import importlib.util
import json
import re
import struct
import sys
import wave
from array import array
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FIRMWARE = RAIZ / "firmware" / "viking-voz" / "src" / "main.cpp"
_spec = importlib.util.spec_from_file_location(
    "coleta_viking", RAIZ / "firmware" / "viking-voz" / "coleta.py"
)
coleta = importlib.util.module_from_spec(_spec)
sys.modules["coleta_viking"] = coleta
_spec.loader.exec_module(coleta)


def _quadro(seq: int, t_us: int, amostras=None, flags: int = 0) -> bytes:
    """Um quadro como o `coletar()` do firmware monta (little-endian)."""
    amostras = amostras if amostras is not None else [seq % 100] * coleta.BLOCO
    corpo = struct.pack("<IIHH", seq, t_us, len(amostras), flags) + struct.pack(
        f"<{len(amostras)}h", *amostras
    )
    return b"VKC1" + corpo + struct.pack("<I", coleta.fnv1a32(corpo))


def _sequencia(n: int, *, pular_seq=(), salto_de_tempo_em=None, t0=0) -> list:
    cont, quadros = coleta.Continuidade(), []
    t = t0
    for k in range(n):
        if k in pular_seq:
            t += coleta.US_POR_BLOCO
            continue
        if salto_de_tempo_em is not None and k == salto_de_tempo_em:
            t += 200_000  # 200 ms sumiram sem o seq pular (o DMA do I2S transbordou)
        quadros.append(coleta.Quadro(k, t & 0xFFFFFFFF, 0, array("h", [0] * coleta.BLOCO)))
        t += coleta.US_POR_BLOCO
    for q in quadros:
        cont.anotar(q)
    return cont


def test_o_fnv1a_bate_com_os_valores_conhecidos():
    assert coleta.fnv1a32(b"") == 0x811C9DC5
    assert coleta.fnv1a32(b"a") == 0xE40C292C
    assert coleta.fnv1a32(b"foobar") == 0xBF9CF968


def test_um_quadro_inteiro_vira_um_quadro_com_os_campos_certos():
    amostras = list(range(-256, 256))
    leitor = coleta.Leitor()
    (q,) = leitor.alimentar(_quadro(7, 123_456, amostras, flags=1))
    assert (q.seq, q.t_us, q.flags) == (7, 123_456, 1)
    assert list(q.amostras) == amostras
    assert leitor.checksums_errados == 0


def test_quadros_em_pedacos_quaisquer_saem_inteiros_e_na_ordem():
    dados = b"".join(_quadro(s, s * 32_000) for s in range(3))
    leitor, saida = coleta.Leitor(), []
    for i in range(0, len(dados), 7):
        saida += leitor.alimentar(dados[i : i + 7])
    assert [q.seq for q in saida] == [0, 1, 2]


def test_o_texto_entre_os_quadros_vira_linha_e_nao_estraga_os_quadros():
    dados = (
        b"== Viking voz (H1) ==\r\ncoleta: ganho=2 taxa=16000\n"
        + _quadro(0, 0)
        + b"\ncoleta: status seq=1 descartados=0\n"
        + _quadro(1, 32_000)
    )
    leitor = coleta.Leitor()
    quadros = leitor.alimentar(dados)
    assert [q.seq for q in quadros] == [0, 1]
    assert "coleta: ganho=2 taxa=16000" in leitor.texto
    assert "coleta: status seq=1 descartados=0" in leitor.texto


def test_um_quadro_com_checksum_errado_e_contado_e_jogado_fora():
    ruim = bytearray(_quadro(1, 32_000))
    ruim[40] ^= 0xFF  # uma amostra trocada no caminho
    leitor = coleta.Leitor()
    quadros = leitor.alimentar(_quadro(0, 0) + bytes(ruim) + _quadro(2, 64_000))
    assert [q.seq for q in quadros] == [0, 2]
    assert leitor.checksums_errados == 1


def test_a_sequencia_limpa_nao_tem_lacuna_nem_buraco_e_mede_a_taxa():
    resumo = _sequencia(200).resumo()
    assert resumo["lacunas"] == [] and resumo["perdidos"] == 0
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["taxa_medida_hz"] == pytest.approx(16_000, rel=1e-6)
    assert (resumo["blocos"], resumo["primeiro_seq"], resumo["ultimo_seq"]) == (200, 0, 199)


def test_um_quadro_perdido_vira_lacuna_no_formato_combinado():
    resumo = _sequencia(50, pular_seq={10}).resumo()
    # [o seq que faltou, a amostra do WAV onde o buraco fica]: 10 blocos recebidos antes dele
    assert resumo["lacunas"] == [[10, 10 * coleta.BLOCO]]
    assert resumo["perdidos"] == 1


def test_um_buraco_de_tempo_sem_o_seq_pular_e_suspeita():
    resumo = _sequencia(300, salto_de_tempo_em=150).resumo()
    assert resumo["lacunas"] == []
    assert resumo["suspeita_de_buraco"] is True


def test_uma_trava_curta_que_o_dma_recupera_nao_e_buraco():
    # o laço parou 80 ms depois do bloco 99; o DMA guardou o áudio, e as leituras seguintes vieram
    # 1 ms uma da outra até alcançar o tempo certo: o tempo sempre anda para a frente, e nenhuma
    # amostra se perdeu
    cont, fim_da_trava = coleta.Continuidade(), 100 * coleta.US_POR_BLOCO + 80_000
    for k in range(300):
        t = k * coleta.US_POR_BLOCO
        if k >= 100:
            t = max(t, fim_da_trava + (k - 100) * 1_000)
        cont.anotar(coleta.Quadro(k, t, 0, array("h", [0] * coleta.BLOCO)))
    resumo = cont.resumo()
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["maior_afastamento_s"] >= 0.07  # o tremor aparece, mas não é degrau


def test_um_tempo_que_anda_para_tras_nao_vira_uma_volta_do_micros():
    cont = coleta.Continuidade()
    for k, t in enumerate([0, 32_000, 64_000, 60_000, 96_000]):
        cont.anotar(coleta.Quadro(k, t, 0, array("h", [0] * coleta.BLOCO)))
    assert cont._t_continuo == 96_000  # não 2**32 a mais


def test_o_micros_que_da_a_volta_nao_vira_buraco():
    resumo = _sequencia(100, t0=2**32 - 5 * coleta.US_POR_BLOCO).resumo()
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["taxa_medida_hz"] == pytest.approx(16_000, rel=1e-6)


def test_o_take_tem_meio_segundo_antes_do_fale_e_tres_depois():
    assert coleta.recorte_do_take(5 * 16_000, 10 * 16_000) == (72_000, 128_000)
    assert coleta.recorte_do_take(1_000, 10 * 16_000) == (0, 49_000)  # no começo, corta no zero


def test_o_wav_e_o_seq_json_saem_no_formato_combinado(tmp_path):
    amostras = array("h", [0, 1, -1, 32767, -32768] * 100)
    wav = tmp_path / "s" / "take_001.wav"
    coleta.gravar_wav(wav, amostras)
    with wave.open(str(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16_000)
        lidas = array("h", w.readframes(w.getnframes()))
    assert list(lidas) == list(amostras)
    json_ = coleta.gravar_seq(wav, _sequencia(3).resumo(ganho=2))
    assert json_.name == "take_001.seq.json"
    dados = json.loads(json_.read_text())
    assert {"blocos", "primeiro_seq", "ultimo_seq", "lacunas", "ganho"} <= dados.keys()


def test_nenhum_destino_dentro_do_repo_e_o_nome_da_sessao_tem_forma(tmp_path):
    with pytest.raises(ValueError, match="dentro do repo"):
        coleta.destino_seguro(RAIZ / "data", "2026-11-22_piloto", "real_positive")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        coleta.destino_seguro(tmp_path, "piloto", "real_positive")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        coleta.destino_seguro(tmp_path, "2026-11-22_../../x", "real_positive")
    pasta = coleta.destino_seguro(tmp_path, "2026-11-22_piloto", "real_negative")
    assert pasta == (tmp_path / "real_negative" / "2026-11-22_piloto").resolve()


def test_os_niveis_contam_a_saturacao_e_o_rms_por_100_ms():
    amostras = array("h", [1000] * 1600 + [0] * 1600 + [32767] * 10)
    nv = coleta.niveis(amostras)
    assert (nv["pico"], nv["rms_100ms_max"], nv["rms_100ms_min"], nv["saturadas"]) == (
        32767,
        1000,
        0,
        10,
    )


def test_o_quadro_do_coleta_py_e_o_do_firmware():
    fonte = FIRMWARE.read_text()
    assert "constexpr char MAGICO[4] = {'V', 'K', 'C', '1'};" in fonte
    assert coleta.MAGICO == b"VKC1"
    assert "constexpr int QUADRO_BYTES = 4 + 4 + 4 + 2 + 2 + BLOCO * 2 + 4;" in fonte
    assert coleta.QUADRO_BYTES == 4 + 4 + 4 + 2 + 2 + coleta.BLOCO * 2 + 4
    bloco = re.findall(r"constexpr int BLOCO = (\d+);", fonte)
    taxa = re.findall(r"constexpr uint32_t TAXA = (\d+);", fonte)
    assert bloco == [str(coleta.BLOCO)] and taxa == [str(coleta.TAXA)]
    # o Mac lê o ganho gravado na placa desta linha do boot
    assert 'Serial.printf("coleta: ganho=%d' in fonte


def test_o_ganho_vem_do_boot_e_da_linha_de_status():
    placa = object.__new__(coleta.Placa)
    placa.leitor, placa.ganho, placa.firmware = coleta.Leitor(), None, {}
    # a linha de status chega entre dois quadros, como na placa
    dados = b"coleta: status ganho=2 seq=9\n" + _quadro(9, 0)
    placa.porta = type("P", (), {"read": lambda self, n: dados})()
    placa.ler()
    assert placa.ganho == 2
    fonte = FIRMWARE.read_text()
    assert 'Serial.printf("\\ncoleta: status ganho=%d' in fonte


def test_um_arquivo_sem_o_ganho_nao_sai_como_bom():
    resumo = _sequencia(10).resumo(ganho=None)
    assert not coleta._veredito(resumo).startswith("✅")
    assert coleta._veredito(_sequencia(10).resumo(ganho=2)).startswith("✅")


def test_o_ganho_esta_congelado_em_2():
    """O dono congelou o ganho em 2 (2026-11-22): mudar é retreinar a wake word. Quem mudar este
    número tem de avisar o agente do Colab antes (o comentário do `GANHO` no firmware)."""
    assert re.findall(r"constexpr int GANHO = (\d+);", FIRMWARE.read_text()) == ["2"]
