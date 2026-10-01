"""Trava do navegador entre processos (Sessão 6, auditoria §10.7).

Há um Chrome e um daemon do Browser Harness por máquina. Dois `viking` ao mesmo tempo (o chat e um
`viking browser`, dois terminais) dirigiriam a mesma aba, e o `preparar_navegador` de um reinicia o
daemon no meio da tarefa do outro. `jev_runner._EXECUCAO` só vale dentro de um processo; esta
trava vale entre eles.

`fcntl.flock` num arquivo em `data/`: o kernel solta a trava quando o processo morre, então não
existe trava velha para limpar — e por isso o arquivo **nunca** é apagado (apagar abre uma corrida:
um terceiro processo travaria um arquivo novo enquanto o dono ainda segura o velho). O conteúdo
(quem segura, desde quando, qual tarefa) só serve à mensagem de "ocupado"; quem decide é o kernel.

Sem espera (decisão do dono, 2026-09-27): ocupado → recusa na hora, dizendo quem está usando.

O descritor não passa ao subprocesso do Jev (`Popen` fecha os descritores por padrão): o daemon é
filho do filho e herdaria a trava para sempre. Se o Viking morrer por SIGKILL, o Jev segue até o
próprio `--timeout`. Sem `fcntl` (Windows, trilha pausada), só a trava do processo vale.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from lifeos import registro
from lifeos.browser import _redacao
from lifeos.config import DATA_DIR, TIMEZONE

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows (trilha pausada)
    fcntl = None

TRAVA_PATH = DATA_DIR / "navegador.lock"
MAX_OBJETIVO = 60
_ORIGENS = {
    "chat": "pelo viking chat",
    "cli": "pelo terminal (viking browser)",
    "mcp": "pelo servidor MCP",
    "maos": "pelo viking maos (um pedido do chat da nuvem)",
}


class Indisponivel(RuntimeError):
    """Não deu para abrir ou travar o arquivo (pasta sem permissão, disco cheio, `flock` recusado
    pelo sistema de arquivos). Quem chama recusa navegar: sem trava, dois processos se atropelam."""


@dataclass(frozen=True)
class Ocupado:
    """Quem segura a trava, pelo que ele escreveu no arquivo; campos vazios se não deu para ler."""

    pid: int | None = None
    origem: str = ""
    desde: datetime | None = None
    objetivo: str = ""


def _objetivo(texto) -> str:
    """Redigido (token, CPF), sem controle nem bidi, numa linha, até `MAX_OBJETIVO` caracteres."""
    limpo = _redacao.limpar_controles(_redacao.redigir(str(texto or ""))) or ""
    limpo = " ".join(limpo.split())
    return limpo if len(limpo) <= MAX_OBJETIVO else limpo[: MAX_OBJETIVO - 1] + "…"


def _ler(arquivo) -> Ocupado:
    """O dono como ele se escreveu. Lixo, JSON pela metade (lido enquanto ele escrevia) ou campo
    de tipo errado viram campos vazios, nunca exceção."""
    try:
        arquivo.seek(0)
        dados = json.loads(arquivo.read() or "null")
    except (OSError, ValueError):
        return Ocupado()
    if not isinstance(dados, dict):
        return Ocupado()
    pid = dados.get("pid")
    try:
        desde = (
            datetime.fromisoformat(dados["desde"]) if isinstance(dados.get("desde"), str) else None
        )
    except ValueError:
        desde = None
    return Ocupado(
        pid=pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
        origem=dados.get("origem") if isinstance(dados.get("origem"), str) else "",
        desde=desde,
        objetivo=_objetivo(dados.get("objetivo")),
    )


def descrever(ocupado: Ocupado) -> str:
    """ "o navegador está sendo usado pelo viking chat desde 10:02 (tarefa: «abrir o YouTube»)". O
    objetivo pode ter vindo de uma página (pelo Gemini): quem o mostra ao modelo o neutraliza."""
    quem = _ORIGENS.get(ocupado.origem, "por outro processo do Viking")
    partes = [f"o navegador está sendo usado {quem}"]
    if ocupado.desde is not None:
        partes.append(f"desde {ocupado.desde.astimezone(TIMEZONE):%H:%M}")
    texto = " ".join(partes)
    if ocupado.objetivo:
        texto += f" (tarefa: «{ocupado.objetivo}»)"
    return texto


@contextmanager
def ocupar(objetivo: str, *, caminho=None) -> Iterator[Ocupado | None]:
    """`None` dentro do `with`: a trava é nossa até sair dele (inclusive por exceção). Um `Ocupado`:
    outro processo a segura, e nada foi travado — quem chama recusa a tarefa."""
    caminho = caminho or TRAVA_PATH
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        # "a+": cria se não existe e não apaga o que o dono escreveu antes de sabermos se é nossa.
        arquivo = open(caminho, "a+", encoding="utf-8")  # noqa: SIM115 - fechado logo abaixo
    except OSError as exc:
        raise Indisponivel(f"não consegui abrir {caminho}: {exc}") from exc
    with arquivo:
        if fcntl is not None:
            try:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield _ler(arquivo)
                return
            except OSError as exc:
                raise Indisponivel(f"o sistema recusou a trava em {caminho}: {exc}") from exc
        try:
            arquivo.seek(0)
            arquivo.truncate()
            json.dump(
                {
                    "pid": os.getpid(),
                    "origem": registro.ORIGEM.get(),
                    "desde": datetime.now(TIMEZONE).isoformat(),
                    "objetivo": _objetivo(objetivo),
                },
                arquivo,
                ensure_ascii=False,
            )
            arquivo.flush()
            yield None
        finally:
            # Redundante de propósito: fechar o arquivo (o `with` de fora) já solta a trava, e é
            # isso que vale se algo der errado aqui.
            if fcntl is not None:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
