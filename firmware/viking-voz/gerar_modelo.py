"""O modelo da wake word e o vetor de paridade, prontos para o firmware (H2m1, D73), e a conferência do
que a placa respondeu.

    python firmware/viking-voz/gerar_modelo.py gerar --tflite viking_v1/hey_viking.tflite \\
        --sha256 c96061bf... --paridade ~/viking-wakeword/parity_v2
    python firmware/viking-voz/gerar_modelo.py conferir LOG_DO_SERIAL --paridade ... --saida PASTA

`gerar` escreve `src/teste_modelo/modelo.h` (o `.tflite` em bytes, `alignas(16)`, com o sha256) e
`src/teste_modelo/paridade.h` (o WAV de referência e os quadros esperados do frontend, crus e em
int8). Recusa: um `.tflite` com outro sha256 que o combinado (o modelo errado na placa responderia
a pergunta errada), um arquivo sem a marca `TFL3`, um vetor de paridade fora do contrato do
`README_paridade.md`, e uma saída que o git não ignora: o modelo foi treinado com a voz do dono e o
repo é público (D73).

`conferir` lê o log do serial do programa de teste, tira dele os quadros que a placa calculou e as
saídas do modelo, compara de novo com a referência (sem confiar no "0 diferentes" que a placa
imprimiu) e grava, fora do repo, o CSV e as saídas para o agente do Colab.

Só biblioteca padrão: roda com qualquer Python 3.11 do Mac.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import subprocess
import sys
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SAIDA_PADRAO = AQUI / "src" / "teste_modelo"

TAXA = 16000
CANAIS = 40
PEDACO = 160  # 10 ms: o passo do frontend do treino
PEDACO_BYTES = PEDACO * 2
JANELA_EM_PEDACOS = 3  # 30 ms: a primeira feature só sai no 3º pedaço
MAX_RAW = 0xFFFF
TETO_DO_MODELO = 1 << 20  # 1 MiB: o de hoje tem 62.304 bytes; muito mais é outro arquivo

# O contrato do vetor (README_paridade.md, 2026-11-22): o sha do WAV e os três CSV.
WAV_SHA256 = "8016ee17cd7405684a376159a4d745ef67aa97de4bdeda3561a879ae89b7266e"
WAV = "ref_2s_16k_mono_s16.wav"
CSV_RAW = "ref_features_raw_uint16.csv"
CSV_INT8 = "ref_features_int8_model_input.csv"


class ErroDoGerador(Exception):
    """O que o gerador recusa, com o motivo para o terminal."""


# --- as regras -------------------------------------------------------------------------------------


def quadros_esperados(amostras: int) -> int:
    """Quantos quadros o laço do treino tira de `amostras`: ele só entrega um pedaço de 160 enquanto
    `idx + 320 < total de bytes` (o último fica de fora), e o 1º quadro sai no 3º pedaço."""
    total = amostras * 2
    pedacos = 0 if total <= PEDACO_BYTES else (total - PEDACO_BYTES - 1) // PEDACO_BYTES + 1
    return max(0, pedacos - (JANELA_EM_PEDACOS - 1))


def int8_do_raw(raw: int) -> int:
    """A entrada do modelo `viking_v1` (escala 26/255, zero −128) em inteiros, como o firmware faz:
    `(raw*1275 − 425984) / 3328`, com a divisão truncada para o zero (a do C) e saturada em int8.
    A referência do Python dá a volta (wrap) acima de 127; o firmware satura."""
    num = raw * 1275 - 425984
    q = -(-num // 3328) if num < 0 else num // 3328
    return max(-128, min(127, q))


def conferir_modelo(dados: bytes, sha256: str) -> str:
    """O `.tflite` combinado, ou um erro. Devolve o sha256 dele."""
    esperado = sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", esperado):
        raise ErroDoGerador("o --sha256 tem de ser os 64 dígitos hexadecimais inteiros")
    if not 8 <= len(dados) <= TETO_DO_MODELO:
        raise ErroDoGerador(f"o modelo tem {len(dados)} bytes: fora de 8 a {TETO_DO_MODELO}")
    if dados[4:8] != b"TFL3":
        raise ErroDoGerador("o arquivo não tem a marca TFL3 de um modelo TFLite")
    visto = hashlib.sha256(dados).hexdigest()
    if visto != esperado:
        raise ErroDoGerador(f"o sha256 do modelo é {visto}, e o combinado é {esperado}")
    return visto


def ler_wav(dados: bytes) -> array:
    """As amostras do WAV de referência, se ele for o do contrato (o sha, 16 kHz, mono, 16 bits)."""
    visto = hashlib.sha256(dados).hexdigest()
    if visto != WAV_SHA256:
        raise ErroDoGerador(f"o sha256 do WAV é {visto}, e o do README_paridade é {WAV_SHA256}")
    with wave.open(io.BytesIO(dados)) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, TAXA):
            raise ErroDoGerador("o WAV não é mono, 16 bits, 16 kHz")
        amostras = array("h", w.readframes(w.getnframes()))
    if sys.byteorder != "little":
        amostras.byteswap()
    return amostras


def ler_csv(texto: str, linhas: int, minimo: int, maximo: int) -> list[list[int]]:
    """Um CSV de `linhas` × 40 inteiros em [minimo, maximo], com o cabeçalho c0..c39."""
    leitor = list(csv.reader(io.StringIO(texto)))
    if not leitor or leitor[0] != [f"c{j}" for j in range(CANAIS)]:
        raise ErroDoGerador("o CSV não começa pelo cabeçalho c0..c39")
    corpo = [linha for linha in leitor[1:] if linha]
    if len(corpo) != linhas:
        raise ErroDoGerador(f"o CSV tem {len(corpo)} quadros, e o WAV dá {linhas}")
    valores = []
    for k, linha in enumerate(corpo):
        if len(linha) != CANAIS or not all(re.fullmatch(r"-?\d+", v) for v in linha):
            raise ErroDoGerador(f"o quadro {k} do CSV não tem 40 inteiros")
        numeros = [int(v) for v in linha]
        if not all(minimo <= v <= maximo for v in numeros):
            raise ErroDoGerador(f"o quadro {k} do CSV sai de [{minimo}, {maximo}]")
        valores.append(numeros)
    return valores


@dataclass(frozen=True)
class Paridade:
    amostras: array
    raw: list[list[int]]
    int8: list[list[int]]


def conferir_concordancia(raw: list[list[int]], int8: list[list[int]]) -> None:
    """Os dois CSV têm de concordar pela fórmula do firmware: senão a placa seria comparada com uma
    referência que nem a própria referência cumpre (a 1ª versão do CSV int8, com a fórmula do
    ESPHome, divergia em 31% dos valores; README_paridade.md)."""
    errados = sum(
        int8_do_raw(r) != q
        for lr, lq in zip(raw, int8, strict=True)
        for r, q in zip(lr, lq, strict=True)
    )
    if errados:
        raise ErroDoGerador(f"o CSV int8 diverge da fórmula sobre o CSV cru em {errados} valores")


def ler_paridade(pasta: Path) -> Paridade:
    amostras = ler_wav((pasta / WAV).read_bytes())
    n = quadros_esperados(len(amostras))
    raw = ler_csv((pasta / CSV_RAW).read_text(), n, 0, MAX_RAW)
    int8 = ler_csv((pasta / CSV_INT8).read_text(), n, -128, 127)
    conferir_concordancia(raw, int8)
    return Paridade(amostras, raw, int8)


# --- os cabeçalhos ---------------------------------------------------------------------------------


def _bytes_em_linhas(dados: bytes, por_linha: int = 16) -> str:
    return "\n".join(
        "    " + ", ".join(f"0x{b:02x}" for b in dados[i : i + por_linha]) + ","
        for i in range(0, len(dados), por_linha)
    )


def cabecalho_modelo(dados: bytes, sha256: str, origem: str) -> str:
    return (
        "// Gerado por firmware/viking-voz/gerar_modelo.py: não editar, não comitar (o .gitignore\n"
        "// recusa; o modelo foi treinado com a voz do dono e o repo é público, D73).\n"
        f"// Origem: {origem}\n"
        "#pragma once\n#include <stddef.h>\n#include <stdint.h>\n\n"
        f'constexpr char MODELO_SHA256[] = "{sha256}";\n'
        f"constexpr size_t MODELO_TAMANHO = {len(dados)};\n"
        "// O TFLM lê o modelo no lugar: o flatbuffer pede o alinhamento.\n"
        f"alignas(16) const uint8_t MODELO[{len(dados)}] = {{\n{_bytes_em_linhas(dados)}\n}};\n"
    )


def _matriz(nome: str, tipo: str, valores: list[list[int]]) -> str:
    linhas = ",\n".join("    {" + ", ".join(str(v) for v in linha) + "}" for linha in valores)
    return f"const {tipo} {nome}[PARIDADE_QUADROS][{CANAIS}] = {{\n{linhas}\n}};\n"


def cabecalho_paridade(p: Paridade) -> str:
    amostras = ",\n".join(
        "    " + ", ".join(str(v) for v in p.amostras[i : i + 16])
        for i in range(0, len(p.amostras), 16)
    )
    return (
        "// Gerado por firmware/viking-voz/gerar_modelo.py: não editar, não comitar.\n"
        "// O vetor de paridade do frontend (~/viking-wakeword/parity_v2, README_paridade.md).\n"
        "#pragma once\n#include <stddef.h>\n#include <stdint.h>\n\n"
        f'constexpr char PARIDADE_WAV_SHA256[] = "{WAV_SHA256}";\n'
        f"constexpr size_t PARIDADE_AMOSTRAS = {len(p.amostras)};\n"
        f"constexpr int PARIDADE_QUADROS = {len(p.raw)};\n"
        f"constexpr int PARIDADE_CANAIS = {CANAIS};\n"
        f"const int16_t PARIDADE_WAV[PARIDADE_AMOSTRAS] = {{\n{amostras}\n}};\n"
        + _matriz("PARIDADE_RAW", "uint16_t", p.raw)
        + _matriz("PARIDADE_INT8", "int8_t", p.int8)
    )


def conferir_ignorado(caminho: Path) -> None:
    """Recusa escrever no repo o que o git não ignora (o repo é público)."""
    try:
        caminho.resolve().relative_to(RAIZ)
    except ValueError:
        return  # fora do repo
    feito = subprocess.run(
        ["git", "-C", str(RAIZ), "check-ignore", "-q", str(caminho)], check=False
    )
    if feito.returncode != 0:
        raise ErroDoGerador(f"{caminho} está no repo e o git não o ignora: nada foi escrito")


def escrever(caminho: Path, texto: str) -> None:
    conferir_ignorado(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".novo")
    temporario.write_text(texto)
    temporario.replace(caminho)


def gerar(tflite: Path, sha256: str, paridade: Path, saida: Path) -> list[Path]:
    dados = tflite.read_bytes()
    sha = conferir_modelo(dados, sha256)
    p = ler_paridade(paridade)
    feitos = [saida / "modelo.h", saida / "paridade.h"]
    for caminho in feitos:  # confere os dois antes de escrever o primeiro
        conferir_ignorado(caminho)
    escrever(feitos[0], cabecalho_modelo(dados, sha, tflite.name))
    escrever(feitos[1], cabecalho_paridade(p))
    return feitos


# --- a conferência do que a placa respondeu ----------------------------------------------------


@dataclass(frozen=True)
class Resposta:
    quadros: dict[int, list[int]]
    saidas: dict[str, list[int]]
    linhas: list[str]


def ler_log(texto: str) -> Resposta:
    """As linhas `FE,k,v0..v39` (os quadros da placa) e `SAIDAS,R,q0 q1 ...` (as saídas do modelo
    numa rodada R) do serial. Um quadro repetido ou fora da forma é erro, não se ignora."""
    quadros: dict[int, list[int]] = {}
    saidas: dict[str, list[int]] = {}
    linhas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha.startswith("FE,"):
            partes = linha.split(",")
            if len(partes) != 2 + CANAIS or not all(re.fullmatch(r"\d+", v) for v in partes[1:]):
                raise ErroDoGerador(f"linha de quadro fora da forma: {linha[:60]}")
            k = int(partes[1])
            if k in quadros:
                raise ErroDoGerador(f"o quadro {k} veio duas vezes")
            quadros[k] = [int(v) for v in partes[2:]]
        elif linha.startswith("SAIDAS,"):
            _, rodada, valores = linha.split(",", 2)
            if rodada in saidas:
                raise ErroDoGerador(f"a rodada {rodada} veio duas vezes")
            saidas[rodada] = [int(v) for v in valores.split()]
        elif linha:
            linhas.append(linha)
    return Resposta(quadros, saidas, linhas)


def comparar(resposta: Resposta, p: Paridade) -> dict[str, int]:
    n = len(p.raw)
    if sorted(resposta.quadros) != list(range(n)):
        raise ErroDoGerador(
            f"a placa mandou {len(resposta.quadros)} quadros, e são {n} (0 a {n - 1})"
        )
    diferentes = maior = int8_diferentes = 0
    for k in range(n):
        for placa, ref, q in zip(resposta.quadros[k], p.raw[k], p.int8[k], strict=True):
            if placa != ref:
                diferentes += 1
                maior = max(maior, abs(placa - ref))
            if int8_do_raw(placa) != q:
                int8_diferentes += 1
    return {
        "quadros": n,
        "valores": n * CANAIS,
        "diferentes": diferentes,
        "maior_diferenca": maior,
        "int8_diferentes": int8_diferentes,
    }


def conferir(log: Path, paridade: Path, saida: Path) -> dict[str, int]:
    resposta = ler_log(log.read_text(errors="replace"))
    resultado = comparar(resposta, ler_paridade(paridade))
    conferir_ignorado(saida / "x")
    saida.mkdir(parents=True, exist_ok=True)
    with (saida / "placa_features_raw_uint16.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"c{j}" for j in range(CANAIS)])
        w.writerows(resposta.quadros[k] for k in sorted(resposta.quadros))
    (saida / "placa_saidas_q.txt").write_text(
        "".join(f"{r}: {' '.join(map(str, q))}\n" for r, q in sorted(resposta.saidas.items()))
    )
    return resultado


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="comando", required=True)
    g = sub.add_parser("gerar")
    g.add_argument("--tflite", type=Path, required=True)
    g.add_argument("--sha256", required=True)
    g.add_argument("--paridade", type=Path, required=True)
    g.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    c = sub.add_parser("conferir")
    c.add_argument("log", type=Path)
    c.add_argument("--paridade", type=Path, required=True)
    c.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        if a.comando == "gerar":
            for caminho in gerar(a.tflite, a.sha256, a.paridade.expanduser(), a.saida):
                print(f"escrito: {caminho} ({caminho.stat().st_size} bytes)")
        else:
            r = conferir(a.log, a.paridade.expanduser(), a.saida.expanduser())
            print(
                f"frontend: {r['quadros']}x{CANAIS}, {r['diferentes']} diferentes de "
                f"{r['valores']} (maior diferença {r['maior_diferenca']}); int8: "
                f"{r['int8_diferentes']} de {r['valores']} diferentes"
            )
            return 0 if r["diferentes"] == 0 and r["int8_diferentes"] == 0 else 1
    except (ErroDoGerador, OSError) as exc:
        print(f"RECUSADO: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
