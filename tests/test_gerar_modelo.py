"""O `firmware/viking-voz/gerar_modelo.py` (H2m1, D73): o que vai à placa no teste do modelo da wake
word, e a conferência do que ela respondeu. O que decide se a resposta ao Colab vale é o modelo
certo, a referência que se cumpre e a saída fora do repo público."""

import configparser
import hashlib
import importlib.util
import re
import struct
import sys
from array import array
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FIRMWARE = RAIZ / "firmware" / "viking-voz"
_spec = importlib.util.spec_from_file_location("gerar_modelo_viking", FIRMWARE / "gerar_modelo.py")
gm = importlib.util.module_from_spec(_spec)
sys.modules["gerar_modelo_viking"] = gm
_spec.loader.exec_module(gm)


def _modelo(tamanho: int = 64) -> bytes:
    """Um arquivo com a forma de um `.tflite` (o deslocamento da raiz e a marca TFL3)."""
    return struct.pack("<I", 16) + b"TFL3" + bytes(range(256))[: tamanho - 8]


# --- as regras ---------------------------------------------------------------------------------


def test_os_quadros_esperados_seguem_o_laco_do_treino():
    # o vetor de hoje: 2 s a 16 kHz dão 197 quadros (README_paridade.md), não 200
    assert gm.quadros_esperados(32_000) == 197
    for amostras in (0, 1, 160, 161, 320, 480, 481, 640, 32_000, 32_159):
        total, idx, pedacos = amostras * 2, 0, 0
        while idx + 320 < total:  # o laço do treino, à mão
            pedacos, idx = pedacos + 1, idx + 320
        assert gm.quadros_esperados(amostras) == max(0, pedacos - 2), amostras


def test_o_int8_e_a_conta_do_treino_e_satura_em_vez_de_dar_a_volta():
    escala, zero = 26 / 255, -128
    for raw in range(669):  # abaixo da saturação, igual à referência em float (trunca p/ zero)
        assert gm.int8_do_raw(raw) == int(raw * 0.0390625 / escala + zero), raw
    assert gm.int8_do_raw(0) == -128
    assert gm.int8_do_raw(624) == 111  # o maior raw do vetor de hoje
    assert gm.int8_do_raw(700) == 127  # a referência em Python daria a volta (-123)
    assert gm.int8_do_raw(0xFFFF) == 127


def test_o_modelo_com_outro_sha_e_recusado():
    dados = _modelo()
    certo = hashlib.sha256(dados).hexdigest()
    assert gm.conferir_modelo(dados, certo.upper()) == certo
    errado = ("0" if certo[0] != "0" else "1") + certo[1:]
    with pytest.raises(gm.ErroDoGerador, match="sha256 do modelo"):
        gm.conferir_modelo(dados, errado)
    with pytest.raises(gm.ErroDoGerador, match="64 dígitos"):
        gm.conferir_modelo(dados, certo[:16])  # o prefixo não basta


def test_um_arquivo_sem_a_marca_tfl3_e_recusado():
    dados = b"\x10\x00\x00\x00TFL2" + bytes(56)
    with pytest.raises(gm.ErroDoGerador, match="TFL3"):
        gm.conferir_modelo(dados, hashlib.sha256(dados).hexdigest())


def test_o_cabecalho_do_modelo_volta_aos_mesmos_bytes_e_alinhado():
    dados = _modelo(1000)
    sha = hashlib.sha256(dados).hexdigest()
    texto = gm.cabecalho_modelo(dados, sha, "teste.tflite", gm.Config(970, 5))
    corpo = re.search(r"alignas\(16\) const uint8_t MODELO\[(\d+)\] = \{(.*?)\};", texto, re.DOTALL)
    assert corpo, "o MODELO tem de nascer com alignas(16)"
    de_volta = bytes(int(b, 16) for b in re.findall(r"0x([0-9a-f]{2})", corpo.group(2)))
    assert de_volta == dados and int(corpo.group(1)) == len(dados)
    assert f'MODELO_SHA256[] = "{sha}"' in texto
    assert f"MODELO_TAMANHO = {len(dados)};" in texto
    assert "MODELO_LIMIAR_MILESIMOS = 970;" in texto and "MODELO_JANELA = 5;" in texto


_JSON = '{"micro": {"probability_cutoff": 0.97, "sliding_window_size": 5}}'


def test_o_limiar_e_a_janela_vem_do_json_do_colab():
    assert gm.ler_config(_JSON) == gm.Config(970, 5)
    for errado, motivo in (
        ('{"micro": {"probability_cutoff": 1.2, "sliding_window_size": 5}}', "limiar"),
        ('{"micro": {"probability_cutoff": 0.3, "sliding_window_size": 5}}', "limiar"),
        ('{"micro": {"probability_cutoff": true, "sliding_window_size": 5}}', "limiar"),
        ('{"micro": {"probability_cutoff": 0.97, "sliding_window_size": 0}}', "janela"),
        ('{"micro": {"probability_cutoff": 0.97}}', "não tem"),
        ("não é json", "não tem"),
    ):
        with pytest.raises(gm.ErroDoGerador, match=motivo):
            gm.ler_config(errado)


def test_so_o_modelo_do_uso_sai_com_o_limiar_do_json(tmp_path):
    dados = _modelo()
    (tmp_path / "m.tflite").write_bytes(dados)
    (tmp_path / "m.json").write_text(_JSON.replace("0.97", "0.93"))
    feitos = gm.gerar(
        tmp_path / "m.tflite",
        hashlib.sha256(dados).hexdigest(),
        None,
        tmp_path / "src",
        so_modelo=True,
    )
    assert feitos == [tmp_path / "src" / "modelo.h"]
    assert sorted(x.name for x in (tmp_path / "src").iterdir()) == ["modelo.h"]
    assert "MODELO_LIMIAR_MILESIMOS = 930;" in feitos[0].read_text()
    with pytest.raises(gm.ErroDoGerador, match="--paridade"):
        gm.gerar(tmp_path / "m.tflite", hashlib.sha256(dados).hexdigest(), None, tmp_path)


# --- a referência -------------------------------------------------------------------------------


def _csv(linhas: list[list[int]]) -> str:
    return (
        ",".join(f"c{j}" for j in range(40))
        + "\n"
        + "".join(",".join(map(str, linha)) + "\n" for linha in linhas)
    )


def test_o_csv_fora_do_contrato_e_recusado():
    bom = [[k + j for j in range(40)] for k in range(3)]
    assert gm.ler_csv(_csv(bom), 3, 0, 100) == bom
    with pytest.raises(gm.ErroDoGerador, match="3 quadros, e o WAV dá 4"):
        gm.ler_csv(_csv(bom), 4, 0, 100)
    with pytest.raises(gm.ErroDoGerador, match="40 inteiros"):
        gm.ler_csv(_csv([bom[0][:39]] + bom[1:]), 3, 0, 100)
    with pytest.raises(gm.ErroDoGerador, match="sai de"):
        gm.ler_csv(_csv(bom), 3, 0, 40)  # o maior valor é 2 + 39 = 41
    with pytest.raises(gm.ErroDoGerador, match="cabeçalho"):
        gm.ler_csv("\n".join(",".join(map(str, linha)) for linha in bom), 3, 0, 100)


def test_a_referencia_cujo_int8_diverge_do_cru_e_recusada():
    raw = [[0, 300, 624] + [10] * 37]
    certo = [[gm.int8_do_raw(r) for r in raw[0]]]
    gm.conferir_concordancia(raw, certo)
    errado = [certo[0][:1] + [certo[0][1] + 1] + certo[0][2:]]  # um valor só, a menos de 1
    with pytest.raises(gm.ErroDoGerador, match="em 1 valores"):
        gm.conferir_concordancia(raw, errado)


def test_o_wav_que_nao_e_o_do_contrato_e_recusado():
    with pytest.raises(gm.ErroDoGerador, match="sha256 do WAV"):
        gm.ler_wav(b"RIFF" + bytes(60))


# --- a saída, fora do repo público ------------------------------------------------------------


def test_a_saida_que_o_git_nao_ignora_e_recusada_antes_de_escrever():
    alvo = FIRMWARE / "src" / "nao_ignorado_pelo_git.h"
    try:
        with pytest.raises(gm.ErroDoGerador, match="não o ignora"):
            gm.escrever(alvo, "x")
        assert not alvo.exists()
    finally:  # com a guarda mutada, o arquivo nasce no repo: não pode ficar (2026-11-27)
        alvo.unlink(missing_ok=True)
        alvo.with_suffix(".h.novo").unlink(missing_ok=True)
    gm.conferir_ignorado(FIRMWARE / "src" / "teste_modelo" / "modelo.h")  # o .gitignore cobre
    gm.conferir_ignorado(FIRMWARE / "src" / "modelo.h")


def test_gerar_confere_as_duas_saidas_antes_de_escrever_a_primeira(tmp_path, monkeypatch):
    dados = _modelo()
    (tmp_path / "m.tflite").write_bytes(dados)
    (tmp_path / "m.json").write_text(_JSON)
    escritos = []
    monkeypatch.setattr(gm, "ler_paridade", lambda pasta: gm.Paridade(array("h"), [], []))
    monkeypatch.setattr(gm, "escrever", lambda caminho, texto: escritos.append(caminho))
    with pytest.raises(gm.ErroDoGerador, match="não o ignora"):
        gm.gerar(
            tmp_path / "m.tflite", hashlib.sha256(dados).hexdigest(), tmp_path, FIRMWARE / "src"
        )
    assert escritos == []  # o modelo.h de src/ é ignorado, o paridade.h não: nenhum dos dois sai


def test_a_saida_fora_do_repo_e_aceita(tmp_path):
    gm.escrever(tmp_path / "x" / "y.h", "ok")
    assert (tmp_path / "x" / "y.h").read_text() == "ok"


# --- a conferência do serial -----------------------------------------------------------------------


def _paridade(n: int = 3) -> "gm.Paridade":
    raw = [[(k * 7 + j) % 600 for j in range(40)] for k in range(n)]
    return gm.Paridade(array("h"), raw, [[gm.int8_do_raw(v) for v in linha] for linha in raw])


def _log(quadros: list[list[int]], extra: str = "") -> str:
    linhas = ["== teste ==", "carregou=sim invoke=ok"]
    linhas += [f"FE,{k}," + ",".join(map(str, q)) for k, q in enumerate(quadros)]
    linhas += ["SAIDAS,A,0 1 255", "SAIDAS,B,0 1 255", extra]
    return "\n".join(linhas)


def test_a_conferencia_compara_de_novo_cada_valor_da_placa():
    p = _paridade()
    r = gm.comparar(gm.ler_log(_log(p.raw)), p)
    assert r == {
        "quadros": 3,
        "valores": 120,
        "diferentes": 0,
        "maior_diferenca": 0,
        "int8_diferentes": 0,
    }
    torto = [linha[:] for linha in p.raw]
    torto[1][5] += 30  # 30 de raw mudam o int8
    r = gm.comparar(gm.ler_log(_log(torto)), p)
    assert (r["diferentes"], r["maior_diferenca"], r["int8_diferentes"]) == (1, 30, 1)


def test_um_quadro_repetido_ou_faltando_no_serial_e_erro():
    p = _paridade()
    with pytest.raises(gm.ErroDoGerador, match="duas vezes"):
        gm.ler_log(_log(p.raw, extra="FE,1," + ",".join(map(str, p.raw[1]))))
    with pytest.raises(gm.ErroDoGerador, match="mandou 2 quadros"):
        gm.comparar(gm.ler_log(_log(p.raw[:2])), p)
    with pytest.raises(gm.ErroDoGerador, match="fora da forma"):
        gm.ler_log("FE,0,1,2,3")


def test_as_saidas_do_modelo_saem_por_rodada():
    resposta = gm.ler_log(_log(_paridade().raw))
    assert resposta.saidas == {"A": [0, 1, 255], "B": [0, 1, 255]}
    with pytest.raises(gm.ErroDoGerador, match="rodada A"):
        gm.ler_log("SAIDAS,A,1\nSAIDAS,A,2")


# --- as bibliotecas -------------------------------------------------------------------------------


def test_as_bibliotecas_vem_de_commits_fixos():
    script = (FIRMWARE / "buscar_libs.sh").read_text()
    commits = dict(re.findall(r"^(TFLM|MF|NN)_COMMIT=(\S+)", script, re.MULTILINE))
    assert commits == {
        "TFLM": "df8722334a80ceabc609c1e72968f417cd9437f1",  # a tag v1.4.3
        "MF": "96bd69cfad79aa67697e176570d3dd87052c3def",  # a tag v2.0.2
        "NN": "ace42ac7721119cd543fc40ffe719e601fa8f20f",  # a tag v1.5.0 do esp-nn
    }
    assert 'if [[ "$visto" != "$3" ]]' in script  # e o commit baixado é conferido


# --- os dois firmwares --------------------------------------------------------------------------


def _ini() -> configparser.ConfigParser:
    ini = configparser.ConfigParser()
    ini.read(FIRMWARE / "platformio.ini")
    return ini


def test_o_firmware_de_uso_nao_leva_o_teste_do_modelo_e_segue_o_padrao():
    ini = _ini()
    assert ini["platformio"]["default_envs"].strip() == "xiao_s3"  # um `pio run` solto é o uso
    uso = ini["env:xiao_s3"]
    assert "-<teste_modelo/>" in uso["build_src_filter"].split()
    # a escuta (H2m2) usa os kernels do ESP-NN, os que o C5 provou iguais aos de referência na placa;
    # as mesmas definições do teste que os provou (sem elas, o esp_nn.h escolheria a versão genérica)
    assert {x.strip() for x in uso["lib_ignore"].split(",")} == {"tflm"}
    assert set(_ini()["env:xiao_s3_modelo_nn"]["build_flags"].split()) <= set(
        uso["build_flags"].split()
    )
    for env in ("env:xiao_s3_modelo", "env:xiao_s3_modelo_nn"):
        assert ini[env]["build_src_filter"].split() == ["+<teste_modelo/>"]


def test_cada_teste_do_modelo_usa_uma_variante_do_tflm_so():
    # As duas libs dão os mesmos cabeçalhos: sem o lib_ignore, o LDF escolheria uma qualquer.
    ini = _ini()
    ignora = {
        env: {x.strip() for x in ini[env]["lib_ignore"].split(",")}
        for env in ("env:xiao_s3_modelo", "env:xiao_s3_modelo_nn")
    }
    assert ignora == {
        "env:xiao_s3_modelo": {"tflm_nn", "esp-nn"},
        "env:xiao_s3_modelo_nn": {"tflm"},
    }
    flags = set(ini["env:xiao_s3_modelo_nn"]["build_flags"].split())
    # o esp_nn.h escolhe a versão do S3 por estas duas, e o TFLM entra nos kernels esp_nn pelo ESP_NN
    assert {"-DESP_NN", "-DCONFIG_NN_OPTIMIZED", "-DCONFIG_IDF_TARGET_ESP32S3=1"} <= flags


def test_o_teste_do_modelo_leva_as_definicoes_do_tflm_no_env_inteiro():
    # Elas mudam o tamanho das estruturas do TFLM: na lib só, o programa e a lib discordariam.
    flags = _ini()["env:xiao_s3_modelo"]["build_flags"].split()
    assert {
        "-DTF_LITE_STATIC_MEMORY",
        "-DFLATBUFFERS_LOCALE_INDEPENDENT=0",
        "-DFLATBUFFERS_PREFER_PRINTF=1",
    } <= set(flags)


def test_o_programa_de_teste_registra_uma_operacao_por_vaga_do_resolver():
    fonte = (FIRMWARE / "src" / "teste_modelo" / "main.cpp").read_text()
    vagas = re.findall(r"constexpr int OPERACOES = (\d+);", fonte)
    assert vagas == ["13"]  # as 13 do viking_v1, lidas do .tflite em 2026-11-23 e 2026-11-27
    adicionadas = re.findall(r"resolver\.(Add\w+)\(\)", fonte)
    assert len(adicionadas) == len(set(adicionadas)) == 13


def test_a_conferencia_le_o_log_do_serial_log_so_pela_ultima_captura():
    p = _paridade()
    velho = [linha[:] for linha in p.raw]
    velho[0][0] += 1  # uma captura antiga, com um quadro diferente, fica para trás

    def com_hora(texto: str) -> str:
        return "\n".join(f"18:44:{k % 60:02d} {x}" for k, x in enumerate(texto.split("\n")))

    arquivo = (
        "--- 2026-11-27 18:40:00 captura 40s ---\n"
        + com_hora(_log(velho))
        + "\n--- 2026-11-27 18:45:00 captura 40s ---\n"
        + com_hora(_log(p.raw))
    )
    r = gm.comparar(gm.ler_log(gm.ultima_captura(arquivo)), p)
    assert (r["quadros"], r["diferentes"]) == (3, 0)
    with pytest.raises(gm.ErroDoGerador, match="duas vezes"):  # sem o corte, as duas se somariam
        gm.ler_log(arquivo)


# --- a escuta do uso e o teste da H2m1 fazem a mesma conta -------------------------------------


def _funcao(fonte: str, assinatura: str) -> str:
    """O corpo de uma função C++ (da assinatura até a chave que fecha no começo da linha)."""
    i = fonte.index(assinatura)
    return fonte[i : fonte.index("\n}\n", i) + 2]


def _sem_espacos(texto: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", texto))


def test_a_escuta_faz_a_mesma_conta_que_o_teste_provado_igual_ao_python():
    # O teste da H2m1 deu 7.880 de 7.880 no frontend e 65 de 65 no modelo (o Colab, 2026-11-27).
    # A escuta do uso é outra cópia: se uma mudar sem a outra, a prova deixa de valer para o uso.
    teste = (FIRMWARE / "src" / "teste_modelo" / "main.cpp").read_text()
    escuta = (FIRMWARE / "src" / "escuta.cpp").read_text()
    for funcao in ("void configurar(FrontendConfig &c)", "int8_t int8DoRaw(uint16_t raw)"):
        assert _sem_espacos(_funcao(teste, funcao)) == _sem_espacos(_funcao(escuta, funcao)), funcao
    ops = [sorted(re.findall(r"resolver\.(Add\w+)\(\)", f)) for f in (teste, escuta)]
    assert ops[0] == ops[1] and len(ops[0]) == 13
    # a configuração é a do pymicro-features 2.0.2 (README_paridade.md), escrita à mão aqui
    corpo = _sem_espacos(_funcao(escuta, "void configurar(FrontendConfig &c)"))
    for linha in (
        "c.window.size_ms=30;",
        "c.window.step_size_ms=10;",
        "c.filterbank.num_channels=40;",
        "c.filterbank.lower_band_limit=125.0f;",
        "c.filterbank.upper_band_limit=7500.0f;",
        "c.pcan_gain_control.strength=0.95f;",
        "c.log_scale.scale_shift=6;",
    ):
        assert linha in corpo, linha


def test_o_firmware_de_uso_so_ouve_com_o_modelo():
    # Sem o src/modelo.h, nada da escuta compila (medido em 2026-11-27: os mesmos 9.572 símbolos,
    # cada um do mesmo tamanho, que o firmware de antes).
    escuta_h = (FIRMWARE / "src" / "escuta.h").read_text()
    assert '#if __has_include("modelo.h")\n#define TEM_ESCUTA 1' in escuta_h
    escuta = (FIRMWARE / "src" / "escuta.cpp").read_text()
    assert escuta.index("#if TEM_ESCUTA") < escuta.index('#include "modelo.h"')
    principal = (FIRMWARE / "src" / "main.cpp").read_text()
    assert '#include "modelo.h"' not in principal  # o modelo (62 KB) entra uma vez, pela escuta
