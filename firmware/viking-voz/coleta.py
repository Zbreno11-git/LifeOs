"""A coleta da wake word (H2): o áudio do aparelho, pela USB, vira WAVs no Mac, fora do repo.

O firmware é um só (D71): a placa liga no uso, este programa pede a coleta ao abrir a porta
(`VKC1 COLETA`, repetido como sinal de vida) e o uso ao fechar (`VKC1 USO`). Na coleta, a XIAO manda
sem parar um quadro por bloco de 32 ms (ver `coletar()` em `src/main.cpp`). Este programa confere
cada quadro (o checksum, o seq e o tempo) e grava em `~/viking-wakeword/` (nunca dentro do repo, que
é público), numa pasta por sessão, como o agente do Colab pediu:

    ~/esp32-mac/.venv/bin/python coleta.py medir --minutos 1
    ~/esp32-mac/.venv/bin/python coleta.py takes --sessao 2026-11-23_c1_takes --n 10 \\
        --dica "50 cm, voz normal"
    ~/esp32-mac/.venv/bin/python coleta.py takes --sessao 2026-11-23_c1_parecidas --negativo \\
        --frases "Hey King;Hey vizinho"
    ~/esp32-mac/.venv/bin/python coleta.py sala  --sessao 2026-11-23_c1_estudio --minutos 60
    ~/esp32-mac/.venv/bin/python coleta.py pacote --prefixo 2026-11-23_c1

Cada WAV (PCM 16 bits, mono, 16 kHz) tem um `.seq.json` ao lado, com `lacunas` (vazio = nenhum
quadro perdido). Um arquivo com lacuna não serve para teste. Só precisa do `pyserial` (a venv do
`~/esp32-mac`); as funções de conferência são puras, e `tests/test_coleta.py` as testa sem a placa.
Um cliente por vez na porta: não rode junto com gravar nem com o `serial_log.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import signal
import struct
import subprocess
import sys
import time
import wave
import zipfile
from array import array
from dataclasses import dataclass, field
from pathlib import Path

URL = "rfc2217://127.0.0.1:4000?ign_set_control"
REPO = Path(__file__).resolve().parents[2]
RAIZ_PADRAO = Path("~/viking-wakeword").expanduser()

# O quadro do firmware (`coletar()` em `src/main.cpp`; `tests/test_coleta.py` confere os dois lados).
MAGICO = b"VKC1"
BLOCO = 512
TAXA = 16_000
CABECALHO = struct.Struct("<IIHH")  # seq, t_us, n, flags
QUADRO_BYTES = len(MAGICO) + CABECALHO.size + BLOCO * 2 + 4
US_POR_BLOCO = BLOCO * 1_000_000 // TAXA  # 32000

# Um take: do "FALE" na tela, 0,5 s antes (a sala antes da frase, pedida pelo agente do Colab) até
# 3,0 s depois. No piloto (2026-11-22) o dono começou a falar 0,7 a 1,4 s depois do "FALE", e com
# 2,5 s um take ficou com só ~0,2 s de sala no fim; o agente do Colab pediu ~0,5 s de sala depois.
ANTES_S = 0.5
DEPOIS_S = 3.0
# O buraco que o seq não vê (o DMA do I2S transbordou com o laço parado) deixa o tempo do aparelho
# **para sempre** adiantado em relação às amostras: um degrau no afastamento de uma reta (a taxa
# real do I2S, medida pelo próprio arquivo). Uma reta só dividiria o degrau ao meio; a régua é a
# média do afastamento nos `JANELA` blocos depois de cada ponto contra a dos `JANELA` antes. Uma
# trava curta que o DMA recupera (o tempo sobe e volta) se dilui na média. A tolerância fica acima
# do tremor medido e abaixo de um pedaço de fala (a medir no C3 da H2: o `medir` imprime os dois).
TOLERANCIA_S = 0.12
JANELA = 30  # blocos (~1 s)
# A sala vai para o disco a cada segundo, numa parte nova a cada 10 min: uma queda perde no máximo a
# parte em curso (antes, a hora inteira ficava na memória até o fim).
PARTE_S = 600
# Os pedidos à placa (`lerPedido()` em `src/main.cpp`). Na coleta, o de coleta se repete a cada
# SINAL_S: sem ele por 30 s a placa volta ao uso sozinha (o Mac travou ou dormiu).
PEDIDO_COLETA = b"VKC1 COLETA\n"
PEDIDO_USO = b"VKC1 USO\n"
SINAL_S = 2.0
ENTRAR_S = 45.0  # o boot (a Wi-Fi até 15 s, o NTP até 10 s) e a entrada na coleta
VOLTAR_S = 45.0  # o reinício até o PRONTO do uso
SESSAO = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9_]+$")


def fnv1a32(dados: bytes) -> int:
    h = 2166136261
    for b in dados:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


@dataclass
class Quadro:
    seq: int
    t_us: int
    flags: int
    amostras: array


@dataclass
class Leitor:
    """Recebe bytes em pedaços quaisquer e devolve os quadros válidos. O que não é quadro é texto (o
    boot, as linhas `coleta: status`); um quadro com checksum errado é contado e jogado fora, e a
    leitura se reencontra pelo próximo mágico."""

    resto: bytearray = field(default_factory=bytearray)
    checksums_errados: int = 0
    texto: list[str] = field(default_factory=list)
    _linha: bytearray = field(default_factory=bytearray)

    def _texto(self, dados: bytes) -> None:
        for b in dados:
            if b == 0x0A:
                linha = self._linha.decode(errors="replace").strip()
                if linha:
                    self.texto.append(linha)
                self._linha.clear()
            elif b != 0x0D:
                self._linha.append(b)

    def alimentar(self, dados: bytes) -> list[Quadro]:
        self.resto += dados
        quadros: list[Quadro] = []
        while True:
            i = self.resto.find(MAGICO)
            if i < 0:
                # guarda o fim só se ele for o começo de um mágico: guardar sempre 3 bytes segurava
                # o fim da última linha (o PRONTO, depois do qual a placa não manda mais nada)
                guardar = next(
                    (k for k in range(len(MAGICO) - 1, 0, -1) if self.resto.endswith(MAGICO[:k])), 0
                )
                corte = len(self.resto) - guardar
                self._texto(bytes(self.resto[:corte]))
                del self.resto[:corte]
                return quadros
            self._texto(bytes(self.resto[:i]))
            del self.resto[:i]
            if len(self.resto) < QUADRO_BYTES:
                return quadros
            bruto = bytes(self.resto[:QUADRO_BYTES])
            corpo = bruto[len(MAGICO) : -4]
            (soma,) = struct.unpack("<I", bruto[-4:])
            seq, t_us, n, flags = CABECALHO.unpack_from(corpo)
            if n != BLOCO or fnv1a32(corpo) != soma:
                self.checksums_errados += 1
                del self.resto[: len(MAGICO)]  # procura o próximo mágico depois deste
                continue
            amostras = array("h")
            amostras.frombytes(corpo[CABECALHO.size :])
            if sys.byteorder == "big":
                amostras.byteswap()
            quadros.append(Quadro(seq, t_us, flags, amostras))
            del self.resto[:QUADRO_BYTES]


@dataclass
class Continuidade:
    """O seq e o tempo de um arquivo: as lacunas (quadros perdidos), no formato combinado com o
    agente do Colab (`[seq que faltou, amostra no WAV]`), e o afastamento do tempo de uma reta."""

    blocos: int = 0
    primeiro_seq: int | None = None
    ultimo_seq: int | None = None
    lacunas: list[list[int]] = field(default_factory=list)
    perdidos: int = 0
    _tempos: list[tuple[int, int]] = field(default_factory=list)  # (amostra no WAV, t_us contínuo)
    _ultimo_t: int | None = None
    _t_continuo: int = 0

    def anotar(self, q: Quadro) -> None:
        amostra = self.blocos * BLOCO
        if self.ultimo_seq is not None and q.seq != (self.ultimo_seq + 1) & 0xFFFFFFFF:
            faltaram = (q.seq - self.ultimo_seq - 1) & 0xFFFFFFFF
            self.lacunas.append([(self.ultimo_seq + 1) & 0xFFFFFFFF, amostra])
            self.perdidos += faltaram
        if self.primeiro_seq is None:
            self.primeiro_seq = q.seq
        if self._ultimo_t is not None:
            # o micros() dá a volta a cada ~71 min: a diferença em 32 bits, lida com sinal (um tempo
            # que andasse para trás viraria negativo, não uma volta inteira)
            passo = (q.t_us - self._ultimo_t) & 0xFFFFFFFF
            self._t_continuo += passo - (1 << 32) if passo >= 1 << 31 else passo
        self._ultimo_t = q.t_us
        self._tempos.append((amostra, self._t_continuo))
        self.ultimo_seq = q.seq
        self.blocos += 1

    def tempo(self) -> dict:
        """A taxa real (a reta do tempo do aparelho contra as amostras) e o maior afastamento dela.
        Um buraco que o seq não vê (o DMA do I2S transbordou) é um degrau nessa reta."""
        if len(self._tempos) < 3:
            return {
                "taxa_medida_hz": None,
                "maior_afastamento_s": 0.0,
                "maior_degrau_s": 0.0,
                "suspeita_de_buraco": False,
            }
        n = len(self._tempos)
        mx = sum(a for a, _ in self._tempos) / n
        my = sum(t for _, t in self._tempos) / n
        sxx = sum((a - mx) ** 2 for a, _ in self._tempos)
        inclinacao = sum((a - mx) * (t - my) for a, t in self._tempos) / sxx  # µs por amostra
        resto = [(t - (my + inclinacao * (a - mx))) / 1e6 for a, t in self._tempos]
        degrau = 0.0
        if n >= 2 * JANELA + 1:
            soma = [0.0]
            for r in resto:
                soma.append(soma[-1] + r)
            for k in range(JANELA, n - JANELA + 1):
                antes = (soma[k] - soma[k - JANELA]) / JANELA
                depois = (soma[k + JANELA] - soma[k]) / JANELA
                degrau = max(degrau, abs(depois - antes))
        return {
            "taxa_medida_hz": round(1e6 / inclinacao, 2),
            "maior_afastamento_s": round(max(abs(r) for r in resto), 4),
            "maior_degrau_s": round(degrau, 4),
            "suspeita_de_buraco": degrau > TOLERANCIA_S,
        }

    def resumo(self, **extra) -> dict:
        return {
            "blocos": self.blocos,
            "primeiro_seq": self.primeiro_seq,
            "ultimo_seq": self.ultimo_seq,
            "lacunas": self.lacunas,
            "perdidos": self.perdidos,
            **self.tempo(),
            **extra,
        }


def destino_seguro(raiz: Path, sessao: str, tipo: str) -> Path:
    """A pasta da sessão; recusa um nome torto e qualquer destino dentro do repo (público)."""
    if not SESSAO.match(sessao):
        raise ValueError(f"a sessão tem de ser AAAA-MM-DD_descricao (minúsculas): {sessao!r}")
    if tipo not in ("real_positive", "real_negative"):
        raise ValueError(f"tipo desconhecido: {tipo!r}")
    pasta = (raiz / tipo / sessao).resolve()
    if pasta.is_relative_to(REPO):
        raise ValueError(f"recusado: {pasta} fica dentro do repo, que é público")
    return pasta


def recorte_do_take(fale_em: int, total: int) -> tuple[int, int]:
    """As amostras de um take: de 0,5 s antes do "FALE" até 3,0 s depois (fale_em = a amostra em
    que a tela mostrou o "FALE")."""
    inicio = max(0, fale_em - int(ANTES_S * TAXA))
    fim = min(total, fale_em + int(DEPOIS_S * TAXA))
    return inicio, fim


def niveis(amostras: array) -> dict:
    quadro = TAXA // 10
    rms = [
        (sum(a * a for a in amostras[i : i + quadro]) / quadro) ** 0.5
        for i in range(0, len(amostras) - quadro + 1, quadro)
    ]
    return {
        "pico": max((abs(a) for a in amostras), default=0),
        "rms_100ms_max": round(max(rms, default=0.0)),
        "rms_100ms_min": round(min(rms, default=0.0)),
        "saturadas": sum(1 for a in amostras if a >= 32767 or a <= -32768),
    }


def juntar_niveis(antes: dict | None, novo: dict) -> dict:
    """Os níveis de um arquivo gravado aos pedaços, sem reler o arquivo."""
    if antes is None:
        return novo
    return {
        "pico": max(antes["pico"], novo["pico"]),
        "rms_100ms_max": max(antes["rms_100ms_max"], novo["rms_100ms_max"]),
        "rms_100ms_min": min(antes["rms_100ms_min"], novo["rms_100ms_min"]),
        "saturadas": antes["saturadas"] + novo["saturadas"],
    }


# A faixa que o modelo ouve: o micro_frontend do treino vê de 125 a 7500 Hz. No piloto
# (2026-11-22), 62% da energia da sala estava abaixo de 125 Hz (o ronco, medido pelo agente do
# Colab), e um nível medido sem esse corte engana. O barulho antes da fala se mede na faixa.
BANDA_HZ = 125
# a janela do take em volta do "FALE" (que aparece em 0,5 s), antes da reação de quem fala; a
# mesma que o agente do Colab mediu
PRE_FALA_S = (0.45, 0.70)
# a janela sobre o fundo do take: no piloto, 9 takes deram 1,00 e o com barulho, 1,67 (pelo Colab)
PRE_FALA_LIMITE = 1.4


def na_banda(amostras) -> list[float]:
    """Um passa-alta de 2ª ordem (Butterworth, pelas fórmulas do RBJ) em BANDA_HZ."""
    w0 = 2 * math.pi * BANDA_HZ / TAXA
    alfa, c = math.sin(w0) / (2 * math.sqrt(0.5)), math.cos(w0)
    a0 = 1 + alfa
    b0, b1, b2 = (1 + c) / 2 / a0, -(1 + c) / a0, (1 + c) / 2 / a0
    a1, a2 = -2 * c / a0, (1 - alfa) / a0
    x1 = x2 = y1 = y2 = 0.0
    saida = []
    for x in amostras:
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        saida.append(y)
    return saida


def _rms(valores) -> float:
    return (sum(v * v for v in valores) / len(valores)) ** 0.5 if valores else 0.0


def pre_fala(take) -> dict:
    """O barulho antes da fala, para o agente do Colab descartar o take sem ouvir: a janela
    PRE_FALA_S sobre o fundo do take (o p10 dos trechos de 100 ms), os dois na faixa do modelo."""
    banda, quadro = na_banda(take), TAXA // 10
    trechos = sorted(_rms(banda[i : i + quadro]) for i in range(0, len(banda) - quadro + 1, quadro))
    fundo = trechos[len(trechos) // 10] if trechos else 0.0
    inicio, fim = (int(s * TAXA) for s in PRE_FALA_S)
    janela = _rms(banda[inicio:fim])
    razao = janela / fundo if fundo else math.inf
    return {
        "fundo_na_banda": round(fundo, 1),
        "pre_fala_razao": round(razao, 2),
        "pre_fala_barulho": razao > PRE_FALA_LIMITE,
    }


def gravar_wav(caminho: Path, amostras: array) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = array("h", amostras)
    if sys.byteorder == "big":
        dados.byteswap()
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(dados.tobytes())


def gravar_seq(caminho_wav: Path, resumo: dict) -> Path:
    destino = caminho_wav.with_suffix(".seq.json")
    destino.write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n")
    return destino


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


# --- a placa ------------------------------------------------------------------------------------


def abrir_porta(url: str):
    import serial  # type: ignore[import-not-found]

    porta = serial.serial_for_url(url, baudrate=115200, timeout=0.05, do_not_open=True)
    porta.dtr = False
    porta.rts = False
    porta.open()
    return porta


class Placa:
    """A XIAO na porta (pelo servidor RFC2217 do Mac). Abrir a porta reinicia a placa no uso;
    `entrar` pede a coleta e só volta com o ganho dito e um quadro recebido; `fechar` pede o uso e
    espera o PRONTO. Se este programa morrer sem fechar, a placa volta ao uso sozinha (30 s)."""

    def __init__(self, porta):
        self.porta = porta
        self.leitor = Leitor()
        self.ganho: int | None = None
        self.pronta = False  # o PRONTO do uso
        self.na_coleta = False
        self.ultimo_sinal = 0.0
        # o que o próprio firmware conta (a linha `coleta: status`): o maior tempo de volta do laço
        # abaixo de 32 ms prova que o DMA do I2S nunca transbordou
        self.firmware: dict[str, int] = {}

    def _pedir(self, pedido: bytes) -> None:
        self.porta.write(pedido)
        self.porta.flush()
        self.ultimo_sinal = time.monotonic()

    def ler(self) -> list[Quadro]:
        if self.na_coleta and time.monotonic() - self.ultimo_sinal >= SINAL_S:
            self._pedir(PEDIDO_COLETA)
        quadros = self.leitor.alimentar(self.porta.read(8192))
        for linha in self.leitor.texto:
            # a entrada na coleta diz o ganho, e a linha de status repete (a sala do piloto saiu com
            # "ganho": null porque a linha única se perdeu)
            casou = re.search(r"^coleta:.*\bganho=(\d+)", linha)
            if casou:
                self.ganho = int(casou.group(1))
            if linha.startswith("coleta: status"):
                for nome, valor in re.findall(r"(\w+)=(\d+)", linha):
                    if nome == "maior_volta_us":
                        valor = max(int(valor), self.firmware.get(nome, 0))
                    self.firmware[nome] = int(valor)
            if "PRONTO" in linha:
                self.pronta = True
            if not linha.startswith("coleta: status") and (
                linha.startswith("coleta:") or "wifi" in linha or "ERRO" in linha
            ):
                print(f"  [placa] {linha}", flush=True)
        self.leitor.texto.clear()
        return quadros

    def entrar(self, prazo_s: float = ENTRAR_S) -> None:
        fim = time.monotonic() + prazo_s
        while time.monotonic() < fim:
            if time.monotonic() - self.ultimo_sinal >= 0.5:
                self._pedir(PEDIDO_COLETA)
            if self.ler() and self.ganho is not None:
                self.na_coleta = True
                # o que se perdeu ou veio torto antes daqui (o boot) não é do arquivo
                self.leitor.checksums_errados = 0
                return
        raise SystemExit(
            f"a placa não entrou na coleta em {prazo_s:.0f} s: o firmware é o único (D71)? Outro "
            "programa está na porta? (`lsof -nP -iTCP:4000`)"
        )

    def fechar(self) -> bool:
        """Pede o uso, espera o PRONTO e fecha a porta; True se a placa confirmou a volta."""
        self.na_coleta, self.pronta = False, False
        try:
            fim = time.monotonic() + VOLTAR_S
            self._pedir(PEDIDO_USO)
            while not self.pronta and time.monotonic() < fim:
                self.ler()
        except OSError as e:  # o serial.SerialException é um OSError (a USB saiu)
            print(f"  [placa] a porta caiu ao fechar: {e}", flush=True)
        finally:
            self.porta.close()
        print(
            "  [placa] de volta ao uso (PRONTO): a voz do estúdio está ligada"
            if self.pronta
            else "  [placa] ⚠️ não vi o PRONTO: confira a placa (sem sinal ela reinicia em 30 s)",
            flush=True,
        )
        return self.pronta


def abrir(url: str) -> Placa:
    placa = Placa(abrir_porta(url))
    try:
        placa.entrar()
    except BaseException:
        placa.porta.close()
        raise
    return placa


def _extra(placa: Placa) -> dict:
    return {
        "checksums_errados": placa.leitor.checksums_errados,
        "ganho": placa.ganho,
        "firmware": dict(placa.firmware),
        "taxa_nominal_hz": TAXA,
        "commit_do_repo": _commit(),
    }


def _veredito(resumo: dict) -> str:
    ruim = resumo["lacunas"] or resumo.get("checksums_errados") or resumo.get("suspeita_de_buraco")
    if ruim:
        return (
            "❌ com lacuna, checksum errado ou buraco de tempo: esse arquivo não serve para teste"
        )
    if resumo.get("ganho") is None:
        return "⚠️ contínuo, mas a placa não disse o ganho: confira o firmware antes de usar"
    return "✅ contínuo: nenhum quadro perdido"


def medir(args: argparse.Namespace) -> int:
    placa = abrir(args.url)
    cont = Continuidade()
    fim = time.time() + args.minutos * 60
    try:
        while time.time() < fim:
            for q in placa.ler():
                cont.anotar(q)
    finally:
        placa.fechar()
    resumo = cont.resumo(**_extra(placa))
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    print(_veredito(resumo))
    return 0 if _veredito(resumo).startswith("✅") else 1


class Parte:
    """Um arquivo da sala, escrito no disco a cada segundo: o cabeçalho do WAV vale a qualquer
    momento (o `writeframes` o corrige a cada pedaço), e o `.seq.json` nasce ao fechar."""

    def __init__(self, pasta: Path, numero: int, seq_anterior: int | None):
        pasta.mkdir(parents=True, exist_ok=True)
        self.caminho = pasta / f"parte_{numero:03d}.wav"
        while self.caminho.exists():  # nunca sobrescreve uma parte de outra rodada na mesma sessão
            numero += 1
            self.caminho = pasta / f"parte_{numero:03d}.wav"
        self.numero = numero
        self.seq_anterior = seq_anterior
        self.cont, self.pendente, self.niveis = Continuidade(), array("h"), None
        self.escritas = 0
        self.saturou_em: list[int] = []  # os segundos do arquivo com amostra saturada
        self._wav = wave.open(str(self.caminho), "wb")  # noqa: SIM115 - fecha em `fechar`
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(TAXA)

    def anotar(self, q: Quadro) -> None:
        self.cont.anotar(q)
        self.pendente.extend(q.amostras)
        while len(self.pendente) >= TAXA:
            self._escrever(self.pendente[:TAXA])
            del self.pendente[:TAXA]

    def _escrever(self, pedaco: array) -> None:
        nv = niveis(pedaco)
        if nv["saturadas"]:
            self.saturou_em.append(self.escritas // TAXA)
        if len(pedaco) >= TAXA // 10:  # menos que um quadro não tem RMS (viraria um mínimo 0)
            self.niveis = juntar_niveis(self.niveis, nv)
        elif self.niveis:
            self.niveis["pico"] = max(self.niveis["pico"], nv["pico"])
            self.niveis["saturadas"] += nv["saturadas"]
        dados = array("h", pedaco)
        if sys.byteorder == "big":
            dados.byteswap()
        self._wav.writeframes(dados.tobytes())
        self.escritas += len(pedaco)

    def fechar(self, extra: dict) -> dict:
        if self.pendente:
            self._escrever(self.pendente)
            self.pendente = array("h")
        self._wav.close()
        seguida = None
        if self.seq_anterior is not None and self.cont.primeiro_seq is not None:
            seguida = self.cont.primeiro_seq == (self.seq_anterior + 1) & 0xFFFFFFFF
        resumo = self.cont.resumo(
            **extra,
            **(self.niveis or niveis(array("h"))),
            saturou_em_s=self.saturou_em,
            segue_a_parte_anterior=seguida,
        )
        gravar_seq(self.caminho, resumo)
        return resumo


def sala(args: argparse.Namespace) -> int:
    pasta = destino_seguro(Path(args.raiz), args.sessao, "real_negative")
    placa = abrir(args.url)
    parte, ruins, seq_anterior, checksums = None, 0, None, 0

    def fechar_parte() -> None:
        nonlocal parte, ruins, seq_anterior, checksums
        extra = _extra(placa)
        # os errados desta parte, não os da rodada inteira
        extra["checksums_errados"], checksums = (
            placa.leitor.checksums_errados - checksums,
            placa.leitor.checksums_errados,
        )
        resumo = parte.fechar(extra)
        veredito = _veredito(resumo)
        if resumo["segue_a_parte_anterior"] is False:
            veredito += " (⚠️ perdeu quadros na emenda com a parte anterior)"
        ruins += not veredito.startswith("✅")
        print(
            f"  {parte.caminho.name}: {parte.escritas / TAXA:.1f} s · saturadas "
            f"{resumo['saturadas']} · {veredito}",
            flush=True,
        )
        seq_anterior, parte = parte.cont.ultimo_seq, None

    print(
        f"gravando a sala em {pasta} por {args.minutos:g} min (Ctrl-C para parar antes)", flush=True
    )
    numero, fim = 1, time.time() + args.minutos * 60
    try:
        while time.time() < fim:
            for q in placa.ler():
                if parte is None:
                    parte = Parte(pasta, numero, seq_anterior)
                    numero = parte.numero + 1
                parte.anotar(q)
                if parte.cont.blocos * BLOCO >= PARTE_S * TAXA:
                    fechar_parte()
    except KeyboardInterrupt:
        print("\n(parado)")
    finally:
        if parte is not None:
            fechar_parte()
        placa.fechar()
    return 1 if ruins else 0


def frases_da_rodada(frase: str, frases: str | None, n: int) -> list[str]:
    """Uma frase por take: a lista separada por `;`, ou a mesma frase `n` vezes."""
    if frases is None:
        return [frase] * n
    lista = [f.strip() for f in frases.split(";") if f.strip()]
    if not lista:
        raise ValueError("--frases veio sem nenhuma frase")
    return lista


def takes(args: argparse.Namespace) -> int:
    tipo = "real_negative" if args.negativo else "real_positive"
    pasta = destino_seguro(Path(args.raiz), args.sessao, tipo)
    frases = frases_da_rodada(args.frase, args.frases, args.n)
    placa = abrir(args.url)
    amostras, cont = array("h"), Continuidade()
    ruins, feitos, barulhentos = 0, 0, []

    def esperar(segundos: float) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            for q in placa.ler():
                cont.anotar(q)
                amostras.extend(q.amostras)

    # uma rodada nova na mesma sessão continua a numeração (nunca apaga a anterior)
    base = len(list(pasta.glob("take_*.wav"))) if pasta.exists() else 0
    if args.dica:
        print(f"\n   ===  {args.dica}  ===", flush=True)
    print(f"{len(frases)} takes em {pasta}: olhe para a tela; fale quando aparecer FALE.")
    try:
        esperar(1.0)  # a sala antes do primeiro
        for i, frase in enumerate(frases, 1):
            dica = f" · {args.dica}" if args.dica else ""
            print(f"\ntake {i}/{len(frases)}{dica} — prepare-se… «{frase}»", flush=True)
            esperar(1.5)
            for contagem in ("3", "2", "1"):
                print(f"   {contagem}", flush=True)
                esperar(1.0)
            fale_em = len(amostras)
            print(f"   >>>>>>>>>>  FALE AGORA: {frase}  <<<<<<<<<<", flush=True)
            esperar(DEPOIS_S + 0.3)
            inicio, fim = recorte_do_take(fale_em, len(amostras))
            take = array("h", amostras[inicio:fim])
            wav = pasta / f"take_{base + i:03d}.wav"
            if wav.exists():
                raise SystemExit(f"recusado: {wav} já existe (nada sobrescreve um take)")
            gravar_wav(wav, take)
            primeiro_bloco = inicio // BLOCO
            lacunas = [lac for lac in cont.lacunas if inicio <= lac[1] < fim]
            resumo = {
                **cont.resumo(**_extra(placa)),
                "lacunas": [[s, a - inicio] for s, a in lacunas],
                "blocos": (fim - inicio + BLOCO - 1) // BLOCO,
                "primeiro_bloco_da_sessao": primeiro_bloco,
                "frase": frase,
                "dica": args.dica,
                "antes_s": ANTES_S,
                "depois_s": DEPOIS_S,
                **niveis(take),
                **pre_fala(take),
            }
            gravar_seq(wav, resumo)
            nv = niveis(take)
            if resumo["pre_fala_barulho"]:
                barulhentos.append(wav.name)
            veredito = _veredito(resumo)
            ruins += not veredito.startswith("✅")
            feitos += 1
            print(
                f"   {wav.name}: pico {nv['pico']} · rms100 máx {nv['rms_100ms_max']} · "
                f"saturadas {nv['saturadas']} · antes da fala {resumo['pre_fala_razao']}× o fundo · "
                f"{veredito}",
                flush=True,
            )
    except KeyboardInterrupt:
        print("\n(parado)")
    finally:
        placa.fechar()
    print(f"\n{feitos} takes em {pasta}; {ruins} com problema.")
    if barulhentos:
        # o agente do Colab descarta estes sem ouvir (a janela antes da fala acima do fundo)
        print(f"com barulho antes da fala: {', '.join(barulhentos)}")
    return 1 if ruins else 0


# --- o pacote para o Colab ------------------------------------------------------------------------


SINAL_DO_LEIA_ME = (
    "PCM 16 bits, mono, 16 kHz, do microfone do aparelho (INMP441 na XIAO ESP32-S3), pela USB, pelo "
    "mesmo `converter()` do uso: `>> 8`, passa-alta 0,995, `(int)(y/256)*GANHO`, corte em int16. "
    "**GANHO = 2, congelado.**"
)
COLUNAS_DO_LEIA_ME = (
    "| arquivo | s | lacunas | checksums ruins | ganho | pico | saturadas | p10 / p50 / p99 | frase "
    "| dica | antes da fala |"
)


def _ler_wav(caminho: Path) -> array:
    with wave.open(str(caminho), "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, TAXA):
            raise ValueError(f"{caminho}: não é PCM 16 bits, mono, 16 kHz")
        amostras = array("h")
        amostras.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        amostras.byteswap()
    return amostras


def niveis_na_faixa(amostras) -> dict:
    """O RMS de 100 ms na faixa do modelo (p10, p50 e p99): é assim que se trocam níveis com o
    Colab (a sala tem 62% da energia abaixo de 125 Hz, que o modelo não vê)."""
    banda, quadro = na_banda(amostras), TAXA // 10
    rms = sorted(_rms(banda[i : i + quadro]) for i in range(0, len(banda) - quadro + 1, quadro))
    if not rms:
        return {"p10": 0.0, "p50": 0.0, "p99": 0.0}
    return {f"p{p}": round(rms[min(len(rms) - 1, len(rms) * p // 100)], 1) for p in (10, 50, 99)}


def montar_pacote(raiz: Path, prefixo: str, notas: str = "") -> Path:
    """O zip de uma sessão (as pastas `<prefixo>_*`), com o LEIA-ME e os SHA256SUMS, relido e
    conferido antes de valer. Um WAV sem `.seq.json` recusa o pacote: ninguém sabe se ele presta."""
    if not SESSAO.match(prefixo):
        raise ValueError(f"o prefixo tem de ser AAAA-MM-DD_cN: {prefixo!r}")
    raiz = raiz.resolve()
    if raiz.is_relative_to(REPO):
        raise ValueError(f"recusado: {raiz} fica dentro do repo, que é público")
    destino = raiz / f"{prefixo}.zip"
    if destino.exists():
        raise ValueError(f"recusado: {destino} já existe (nada sobrescreve um pacote)")
    wavs = sorted(
        w
        for tipo in ("real_positive", "real_negative")
        for pasta in (raiz / tipo).glob(f"{prefixo}_*")
        for w in pasta.glob("*.wav")
    )
    if not wavs:
        raise ValueError(f"nenhum WAV de {prefixo} em {raiz}")
    linhas, ruins, barulhentos, estudio_s = [], [], [], 0.0
    for w in wavs:
        seq = w.with_suffix(".seq.json")
        if not seq.exists():
            raise ValueError(f"{w} não tem o .seq.json (a gravação caiu?): não entra no pacote")
        dados, amostras = json.loads(seq.read_text()), _ler_wav(w)
        rel = w.relative_to(raiz).as_posix()
        if not _veredito(dados).startswith("✅"):
            ruins.append(rel)
        if dados.get("pre_fala_barulho"):
            barulhentos.append(rel)
        if "frase" not in dados:
            estudio_s += len(amostras) / TAXA
        faixa = niveis_na_faixa(amostras)
        linhas.append(
            f"| `{rel}` | {len(amostras) / TAXA:.2f} | {len(dados['lacunas'])} | "
            f"{dados.get('checksums_errados')} | {dados.get('ganho')} | {dados.get('pico')} | "
            f"{dados.get('saturadas')} | {faixa['p10']} / {faixa['p50']} / {faixa['p99']} | "
            f"{dados.get('frase', '—')} | {dados.get('dica') or '—'} | "
            f"{dados.get('pre_fala_razao', '—')} |"
        )
    leia_me = "\n".join(
        [
            f"# Coleta da wake word «Hey Viking» — {prefixo}",
            "",
            SINAL_DO_LEIA_ME,
            f"Cada take: o «FALE» em {ANTES_S:.2f} s, e mais {DEPOIS_S:.1f} s depois dele.",
            "",
            f"- arquivos: {len(wavs)}; estúdio normal: {estudio_s / 60:.1f} min",
            f"- com lacuna, checksum errado, buraco de tempo ou sem o ganho: {ruins or 'nenhum'}",
            f"- com barulho antes da fala (> {PRE_FALA_LIMITE}× o fundo): {barulhentos or 'nenhum'}",
            *(["", "## Observações", "", notas.strip()] if notas.strip() else []),
            "",
            "## Os arquivos (os níveis são RMS de 100 ms **na faixa**, acima de 125 Hz)",
            "",
            COLUNAS_DO_LEIA_ME,
            "|---|---|---|---|---|---|---|---|---|---|---|",
            *linhas,
            "",
        ]
    )
    conteudo = {"LEIA-ME.md": leia_me.encode()}
    for w in wavs:
        for arquivo in (w, w.with_suffix(".seq.json")):
            conteudo[arquivo.relative_to(raiz).as_posix()] = arquivo.read_bytes()
    somas = {nome: hashlib.sha256(dados).hexdigest() for nome, dados in conteudo.items()}
    conteudo["SHA256SUMS"] = "".join(f"{s}  {n}\n" for n, s in sorted(somas.items())).encode()
    parcial = destino.with_suffix(".zip.parcial")
    with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in conteudo.items():
            z.writestr(f"{prefixo}/{nome}", dados)
    with zipfile.ZipFile(parcial) as z:  # relido do disco: o que vale é o que está no zip
        for nome, soma in somas.items():
            if hashlib.sha256(z.read(f"{prefixo}/{nome}")).hexdigest() != soma:
                raise ValueError(f"o zip não devolveu o mesmo {nome}")
    parcial.rename(destino)
    return destino


def pacote(args: argparse.Namespace) -> int:
    notas = Path(args.notas).read_text() if args.notas else ""
    destino = montar_pacote(Path(args.raiz), args.prefixo, notas)
    with zipfile.ZipFile(destino) as z:
        print(z.read(f"{args.prefixo}/LEIA-ME.md").decode())
    print(f"✅ {destino} ({destino.stat().st_size / 1e6:.1f} MB), relido e conferido")
    return 0


def main(argv: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--url", default=URL)
    sub = leitor.add_subparsers(dest="modo", required=True)
    m = sub.add_parser("medir", help="só confere a continuidade, sem gravar")
    m.add_argument("--minutos", type=float, default=2)
    s = sub.add_parser("sala", help="a sala contínua (negativos)")
    s.add_argument("--sessao", required=True)
    s.add_argument("--minutos", type=float, required=True)
    s.add_argument("--raiz", default=str(RAIZ_PADRAO))
    t = sub.add_parser("takes", help="takes guiados pela tela")
    t.add_argument("--sessao", required=True)
    t.add_argument("--n", type=int, default=10)
    t.add_argument("--frase", default="Hey Viking")
    t.add_argument("--frases", help="uma por take, separadas por ; (no lugar de --frase e --n)")
    t.add_argument("--dica", default="", help="a distância e o tom: na tela e no .seq.json")
    t.add_argument("--negativo", action="store_true", help="casos difíceis: vão para real_negative")
    t.add_argument("--raiz", default=str(RAIZ_PADRAO))
    z = sub.add_parser("pacote", help="o zip da sessão para o Colab")
    z.add_argument("--prefixo", required=True)
    z.add_argument("--notas", help="um arquivo de texto com as observações da sessão")
    z.add_argument("--raiz", default=str(RAIZ_PADRAO))
    args = leitor.parse_args(argv)

    def parar(*_):  # fechar a janela ou matar o processo salva o que há, como o Ctrl-C
        raise KeyboardInterrupt

    for sinal in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sinal, parar)
    modos = {"medir": medir, "sala": sala, "takes": takes, "pacote": pacote}
    return modos[args.modo](args)


if __name__ == "__main__":
    sys.exit(main())
