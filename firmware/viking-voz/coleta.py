"""A coleta da wake word (H2): o áudio do aparelho, pela USB, vira WAVs no Mac, fora do repo.

Com o firmware de coleta gravado (`pio run -e xiao_s3_coleta -t upload`), a XIAO manda sem parar um
quadro por bloco de 32 ms (ver `coletar()` em `src/main.cpp`). Este programa confere cada quadro (o
checksum, o seq e o tempo) e grava em `~/viking-wakeword/` (nunca dentro do repo, que é público),
numa pasta por sessão, como o agente do Colab pediu:

    ~/esp32-mac/.venv/bin/python coleta.py medir --minutos 2
    ~/esp32-mac/.venv/bin/python coleta.py sala  --sessao 2026-11-22_estudio_tarde --minutos 1
    ~/esp32-mac/.venv/bin/python coleta.py takes --sessao 2026-11-22_piloto --n 10
    ~/esp32-mac/.venv/bin/python coleta.py takes --sessao 2026-11-23_casos --n 20 \\
        --frase "Hey King" --negativo

Cada WAV (PCM 16 bits, mono, 16 kHz) tem um `.seq.json` ao lado, com `lacunas` (vazio = nenhum
quadro perdido). Um arquivo com lacuna não serve para teste. Só precisa do `pyserial` (a venv do
`~/esp32-mac`); as funções de conferência são puras, e `tests/test_coleta.py` as testa sem a placa.
Um cliente por vez na porta: não rode junto com gravar nem com o `serial_log.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import time
import wave
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
# 2,5 s depois (a reação e a frase cabem com folga).
ANTES_S = 0.5
DEPOIS_S = 2.5
# O buraco que o seq não vê (o DMA do I2S transbordou com o laço parado) deixa o tempo do aparelho
# **para sempre** adiantado em relação às amostras: um degrau no afastamento de uma reta (a taxa
# real do I2S, medida pelo próprio arquivo). Uma reta só dividiria o degrau ao meio; a régua é a
# média do afastamento nos `JANELA` blocos depois de cada ponto contra a dos `JANELA` antes. Uma
# trava curta que o DMA recupera (o tempo sobe e volta) se dilui na média. A tolerância fica acima
# do tremor medido e abaixo de um pedaço de fala (a medir no C3 da H2: o `medir` imprime os dois).
TOLERANCIA_S = 0.12
JANELA = 30  # blocos (~1 s)
PARTE_S = 3600  # a sala vira um arquivo por hora
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
                # guarda o fim, que pode ser o começo de um mágico
                corte = max(0, len(self.resto) - (len(MAGICO) - 1))
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
    """As amostras de um take: de 0,5 s antes do "FALE" até 2,5 s depois (fale_em = a amostra em
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


class Placa:
    """A porta da XIAO (pelo servidor RFC2217 do Mac). Abrir reinicia a placa: o boot vem como
    texto, e o `coleta: ganho=N` dele diz o ganho que está gravado."""

    def __init__(self, url: str):
        import serial  # type: ignore[import-not-found]

        self.porta = serial.serial_for_url(url, baudrate=115200, timeout=0.05, do_not_open=True)
        self.porta.dtr = False
        self.porta.rts = False
        self.porta.open()
        self.leitor = Leitor()
        self.ganho: int | None = None
        # o que o próprio firmware conta (a linha `coleta: status`): o maior tempo de volta do laço
        # abaixo de 32 ms prova que o DMA do I2S nunca transbordou
        self.firmware: dict[str, int] = {}

    def ler(self) -> list[Quadro]:
        quadros = self.leitor.alimentar(self.porta.read(8192))
        for linha in self.leitor.texto:
            casou = re.search(r"coleta: ganho=(\d+)", linha)
            if casou:
                self.ganho = int(casou.group(1))
            if linha.startswith("coleta: status"):
                for nome, valor in re.findall(r"(\w+)=(\d+)", linha):
                    if nome == "maior_volta_us":
                        valor = max(int(valor), self.firmware.get(nome, 0))
                    self.firmware[nome] = int(valor)
            if linha.startswith("coleta:") or "wifi" in linha or "ERRO" in linha:
                print(f"  [placa] {linha}", flush=True)
        self.leitor.texto.clear()
        return quadros

    def fechar(self) -> None:
        self.porta.close()


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
    return "✅ contínuo: nenhum quadro perdido"


def medir(args: argparse.Namespace) -> int:
    placa = Placa(args.url)
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


def sala(args: argparse.Namespace) -> int:
    pasta = destino_seguro(Path(args.raiz), args.sessao, "real_negative")
    placa = Placa(args.url)
    fim = time.time() + args.minutos * 60
    parte, ruins = 0, 0

    def fechar_parte(amostras: array, cont: Continuidade) -> None:
        nonlocal parte, ruins
        parte += 1
        wav = pasta / f"parte_{parte:03d}.wav"
        while wav.exists():  # nunca sobrescreve uma parte de outra rodada na mesma sessão
            parte += 1
            wav = pasta / f"parte_{parte:03d}.wav"
        gravar_wav(wav, amostras)
        resumo = cont.resumo(**_extra(placa), **niveis(amostras))
        gravar_seq(wav, resumo)
        veredito = _veredito(resumo)
        ruins += not veredito.startswith("✅")
        print(f"  {wav.name}: {len(amostras) / TAXA:.1f} s · {veredito}", flush=True)

    amostras, cont = array("h"), Continuidade()
    print(
        f"gravando a sala em {pasta} por {args.minutos} min (Ctrl-C para parar antes)", flush=True
    )
    try:
        while time.time() < fim:
            for q in placa.ler():
                cont.anotar(q)
                amostras.extend(q.amostras)
                if len(amostras) >= PARTE_S * TAXA:
                    fechar_parte(amostras, cont)
                    amostras, cont = array("h"), Continuidade()
    except KeyboardInterrupt:
        print("\n(parado)")
    finally:
        placa.fechar()
        if amostras:
            fechar_parte(amostras, cont)
    return 1 if ruins else 0


def takes(args: argparse.Namespace) -> int:
    tipo = "real_negative" if args.negativo else "real_positive"
    pasta = destino_seguro(Path(args.raiz), args.sessao, tipo)
    placa = Placa(args.url)
    amostras, cont = array("h"), Continuidade()
    ruins, feitos = 0, 0

    def esperar(segundos: float) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            for q in placa.ler():
                cont.anotar(q)
                amostras.extend(q.amostras)

    # uma rodada nova na mesma sessão continua a numeração (nunca apaga a anterior)
    base = len(list(pasta.glob("take_*.wav"))) if pasta.exists() else 0
    print(f"takes de «{args.frase}» em {pasta}: olhe para a tela; fale quando aparecer FALE.")
    esperar(3.0)  # o boot e a sala antes do primeiro
    try:
        for i in range(1, args.n + 1):
            print(f"\ntake {i}/{args.n} — prepare-se…", flush=True)
            esperar(1.5)
            for contagem in ("3", "2", "1"):
                print(f"   {contagem}", flush=True)
                esperar(1.0)
            fale_em = len(amostras)
            print(f"   >>>>>>>>>>  FALE AGORA: {args.frase}  <<<<<<<<<<", flush=True)
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
                "frase": args.frase,
                "antes_s": ANTES_S,
                "depois_s": DEPOIS_S,
                **niveis(take),
            }
            gravar_seq(wav, resumo)
            nv = niveis(take)
            veredito = _veredito(resumo)
            ruins += not veredito.startswith("✅")
            feitos += 1
            print(
                f"   {wav.name}: pico {nv['pico']} · rms100 máx {nv['rms_100ms_max']} · "
                f"saturadas {nv['saturadas']} · {veredito}",
                flush=True,
            )
    except KeyboardInterrupt:
        print("\n(parado)")
    finally:
        placa.fechar()
    print(f"\n{feitos} takes em {pasta}; {ruins} com problema.")
    return 1 if ruins else 0


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
    t.add_argument("--negativo", action="store_true", help="casos difíceis: vão para real_negative")
    t.add_argument("--raiz", default=str(RAIZ_PADRAO))
    args = leitor.parse_args(argv)
    return {"medir": medir, "sala": sala, "takes": takes}[args.modo](args)


if __name__ == "__main__":
    sys.exit(main())
