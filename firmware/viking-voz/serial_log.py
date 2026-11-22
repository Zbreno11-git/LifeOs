"""Lê o serial da XIAO pelo servidor RFC2217 do Mac e guarda em `logs/serial.log` (H1, D70).

O equivalente do `esp log` / `esp reset-log` do workspace antigo, para o Mac:

    ~/esp32-mac/.venv/bin/python serial_log.py 15            (15 s, sem resetar)
    ~/esp32-mac/.venv/bin/python serial_log.py 15 --reset    (reseta e lê desde o boot)

Só precisa do `pyserial` (vem com o `esptool` da venv do `~/esp32-mac`). Um cliente por vez: não
rode junto com gravar nem com o monitor.
"""

import argparse
import time
from pathlib import Path

import serial  # type: ignore[import-not-found]

URL = "rfc2217://127.0.0.1:4000?ign_set_control"


def main() -> None:
    leitor = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    leitor.add_argument("segundos", type=float, nargs="?", default=10.0)
    leitor.add_argument("--reset", action="store_true")
    leitor.add_argument("--url", default=URL)
    leitor.add_argument("--baud", type=int, default=115200)
    args = leitor.parse_args()
    porta = serial.serial_for_url(args.url, baudrate=args.baud, timeout=0.2, do_not_open=True)
    porta.dtr = False
    porta.rts = False
    porta.open()
    if args.reset:
        porta.rts = True
        time.sleep(0.1)
        porta.rts = False
    destino = Path(__file__).parent / "logs" / "serial.log"
    destino.parent.mkdir(exist_ok=True)
    fim, resto = time.time() + args.segundos, b""
    with destino.open("a") as arquivo:
        arquivo.write(
            f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} captura {args.segundos:.0f}s ---\n"
        )
        while time.time() < fim:
            resto += porta.read(4096)
            *linhas, resto = resto.split(b"\n")
            for linha in linhas:
                texto = f"{time.strftime('%H:%M:%S')} {linha.decode(errors='replace').rstrip()}"
                print(texto, flush=True)
                arquivo.write(texto + "\n")
    porta.close()


if __name__ == "__main__":
    main()
