"""Ouvir as vozes candidatas do Viking (Sessão H1, C6, D70), no Mac do dono.

Gera 3 frases em português do Brasil em cada voz e toca uma por uma no alto-falante (`afplay` no
Mac, `aplay` no Linux), com o tempo de cada chamada e o gasto estimado. Gasta de verdade: cada
frase é uma chamada ao TTS do Gemini (≈ US$ 0,0004 por frase pela tarifa de 2026-11-21; as 3
frases em 5 vozes, menos de US$ 0,01). Só com o ok do dono.

    python scripts/vozes.py                      (as vozes de VOZES)
    python scripts/vozes.py --vozes Kore,Puck    (só estas)
    python scripts/vozes.py --sotaque            (a Charon nas 4 variantes do sotaque: sem nada,
                                                  o idioma pt-BR, o estilo, os dois; 12 frases,
                                                  ≈ US$ 0,01)

A chave é a `GEMINI_API_KEY` do `.env` deste computador. Nenhum áudio fica em disco: o arquivo
temporário de cada frase é apagado depois de tocar. Os nomes das vozes vêm da página de geração de
fala; um nome que o modelo não aceite aparece como erro, e o script segue para a próxima voz.
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

from lifeos import config, custos
from lifeos.assistant import turno as turno_nucleo
from lifeos.assistant import voz

VOZES = ("Kore", "Puck", "Charon", "Aoede", "Leda")
FRASES = (
    "Pronto, a luz do estúdio está acesa.",
    (
        "Amanhã às três e meia da tarde você tem dentista, e às sete o treino. Quer que eu lembre "
        "uma hora antes?"
    ),
    (
        "Li o e-mail para a Ana: almoço amanhã ao meio-dia, no lugar de sempre. Se estiver certo, "
        "toque duas vezes no botão para enviar."
    ),
)


def _tocar(pcm: bytes) -> None:
    tocador = shutil.which("afplay") or shutil.which("aplay")
    if tocador is None:
        print("   (sem afplay nem aplay: não toquei)")
        return
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(voz.TAXA_DE_SAIDA)
        arquivo.writeframes(pcm)
    descritor, caminho = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(descritor, "wb") as temporario:
            temporario.write(saida.getvalue())
        subprocess.run([tocador, caminho], check=False)
    finally:
        os.unlink(caminho)


# O sotaque (C6, 2026-11-22): (nome, idioma, estilo). O dono ouve e escolhe; o escolhido vira o
# `voz.IDIOMA` e o `voz.ESTILO`.
SOTAQUES = (
    ("1. sem idioma e sem estilo (como você ouviu antes)", None, None),
    ("2. idioma pt-BR", "pt-BR", None),
    ("3. estilo brasileiro", None, voz.ESTILO_BRASILEIRO),
    ("4. idioma pt-BR + estilo brasileiro", "pt-BR", voz.ESTILO_BRASILEIRO),
)


def main(argv: list[str]) -> int:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("--vozes", default=None)
    leitor.add_argument("--sotaque", action="store_true")
    args = leitor.parse_args(argv)
    nomes = [v.strip() for v in (args.vozes or "").split(",") if v.strip()]
    if args.sotaque:
        rodadas = [
            (f"{nome} · {rotulo}", nome, idioma, estilo)
            for nome in (nomes or [voz.VOZ])
            for rotulo, idioma, estilo in SOTAQUES
        ]
    else:
        rodadas = [(nome, nome, None, None) for nome in (nomes or list(VOZES))]
    if not config.GEMINI_API_KEY:
        print("❌ falta a GEMINI_API_KEY no .env deste computador")
        return 1
    from google import genai
    from google.genai import types

    cliente = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=60_000, api_version=turno_nucleo.VERSAO_DA_API),
    )
    sessao = custos.Sessao()
    custos.instrumentar(cliente, sessao=sessao)
    print(f"modelo: {voz.MODELO_DE_FALAR}")
    for titulo, nome, idioma, estilo in rodadas:
        voz.VOZ, voz.IDIOMA, voz.ESTILO = nome, idioma, estilo
        print(f"\n== {titulo} ==")
        for frase in FRASES:
            inicio = time.monotonic()
            try:
                pcm = voz.falar_frase(cliente, frase)
            except Exception as exc:  # noqa: BLE001 - a voz não existe, a rede: segue
                print(f"   ❌ {type(exc).__name__}: {str(exc)[:160]}")
                break
            gasto = time.monotonic() - inicio
            segundos = len(pcm) / 2 / voz.TAXA_DE_SAIDA
            print(f"   {gasto:.1f} s para {segundos:.1f} s de fala: {frase[:50]}…")
            _tocar(pcm)
    print(f"\ngasto estimado: {sessao.total_formatado()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
