"""O alto-falante deste laptop (D70, até o amplificador do aparelho chegar na H1b).

O áudio do motor chega em pedaços (PCM 24 kHz, mono, 16 bits) e vai direto ao `aplay` (ALSA, o
`alsa-utils` do Debian), sem passar por disco. Um áudio por vez; um teto de tempo mata o `aplay`
se ele travar (uma placa de som ocupada, um pedaço que nunca chega).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Iterable, Sequence

COMANDO = ("aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", "24000", "-c", "1", "-")
MAX_S = 180  # a fala mais longa (12 frases) com folga


class Tocador:
    def __init__(self, comando: Sequence[str] = COMANDO, max_s: float = MAX_S):
        self.comando = list(comando)
        self.max_s = max_s
        self._um_por_vez = threading.Lock()

    def tocar(self, pedacos: Iterable[bytes]) -> int:
        """Toca até o fim (ou até o teto de tempo) e devolve quantos bytes foram ao alto-falante.
        Um erro do lado de quem manda os pedaços para o áudio e sobe."""
        with self._um_por_vez:
            processo = subprocess.Popen(  # o comando é fixo, sem shell
                self.comando, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL
            )
            relogio = threading.Timer(self.max_s, processo.kill)
            relogio.start()
            enviados = 0
            try:
                assert processo.stdin is not None
                for pedaco in pedacos:
                    processo.stdin.write(pedaco)
                    enviados += len(pedaco)
                processo.stdin.close()
                processo.wait()
            except BrokenPipeError:
                pass  # o `aplay` morreu (o teto, ou a placa): o que foi, foi
            finally:
                relogio.cancel()
                if processo.poll() is None:
                    processo.kill()
                    processo.wait()
            return enviados
