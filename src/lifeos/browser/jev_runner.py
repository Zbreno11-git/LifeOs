"""Executa o Jev (jev-ultrafast) como subprocesso e traduz o JSONL dele em `BrowserResult`.

Por que subprocesso e não import: o Jev não tem timeout de wall-clock nem cancelamento — seus
limites internos levantam exceção e a única parada limpa é entre os `yield`s do gerador. Rodando
como processo separado, ganhamos prazo + kill, e o pin `browser-harness==0.1.13` fica fora da venv
do Viking. Ver docs/arquitetura/viking-visao-e-arquitetura.md, seção 4.2.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lifeos.config import (
    BROWSER_MAX_ACOES,
    BROWSER_TIMEOUT_S,
    JEV_DIR,
    JEV_ENV_FILE,
    UV_BIN,
)

SCRIPT_PATH = Path(__file__).with_name("_jev_subprocess.py")
GRACE_S = 20.0
KILL_GRACE_S = 5.0
STDERR_LINHAS = 200

_EXECUCAO = threading.Lock()
_FIM = object()


@dataclass(frozen=True)
class BrowserResult:
    status: str  # "done" | "blocked" | "error"
    goals: tuple[str, ...]
    url: str | None = None
    title: str | None = None
    steps: int = 0
    elapsed_ms: int = 0
    history: tuple[dict, ...] = field(default_factory=tuple)
    page_text: str | None = None
    kept_open: bool = False
    usage: dict = field(default_factory=dict)
    error_code: str | None = None
    error_detail: str | None = None
    stderr_tail: str | None = None


def build_command(
    url: str,
    goals: Sequence[str],
    *,
    timeout_s: float,
    fechar: bool = False,
    jev_dir: Path | None = None,
    env_file: Path | None = None,
    uv_bin: str | None = None,
) -> list[str]:
    jev_dir = Path(jev_dir or JEV_DIR)
    env_file = Path(env_file) if env_file is not None else Path(JEV_ENV_FILE)
    cmd = [uv_bin or UV_BIN, "run", "--directory", str(jev_dir)]
    if env_file.is_file():
        cmd += ["--env-file", str(env_file)]
    cmd += ["python", str(SCRIPT_PATH), "--url", url]
    for goal in goals:
        cmd += ["--goal", goal]
    cmd += ["--timeout", str(timeout_s), "--max-acoes", str(BROWSER_MAX_ACOES)]
    if fechar:
        cmd.append("--fechar")
    return cmd


def parse_event(linha: str) -> dict | None:
    linha = linha.strip()
    if not linha or not linha.startswith("{"):
        return None
    try:
        evento = json.loads(linha)
    except json.JSONDecodeError:
        return None
    return evento if isinstance(evento, dict) and "type" in evento else None


def result_from(
    eventos: Sequence[dict],
    returncode: int | None,
    stderr_tail: str | None,
    goals: Sequence[str],
) -> BrowserResult:
    terminais = [e for e in eventos if e.get("type") in {"result", "error"}]
    base = {
        "goals": tuple(goals),
        "stderr_tail": stderr_tail or None,
    }
    if not terminais:
        passos = [e for e in eventos if e.get("type") == "step"]
        return BrowserResult(
            status="error",
            steps=len(passos),
            error_code="bad_output" if returncode == 0 else "runner_crash",
            error_detail=stderr_tail or f"o executor saiu com codigo {returncode} sem resultado",
            **base,
        )

    final = terminais[-1]
    comum = {
        "url": final.get("url"),
        "title": final.get("title"),
        "steps": final.get("steps") or 0,
        "elapsed_ms": final.get("elapsed_ms") or 0,
        "history": tuple(final.get("history") or ()),
        "page_text": final.get("page_text") or None,
        "kept_open": bool(final.get("kept_open")),
        "usage": dict(final.get("usage") or {}),
    }
    if final["type"] == "error":
        return BrowserResult(
            status="error",
            error_code=final.get("code") or "unknown",
            error_detail=final.get("message"),
            **comum,
            **base,
        )
    return BrowserResult(
        status="done" if final.get("status") == "done" else "blocked",
        **comum,
        **base,
    )


def _erro(codigo: str, detalhe: str, goals: Sequence[str]) -> BrowserResult:
    return BrowserResult(
        status="error", goals=tuple(goals), error_code=codigo, error_detail=detalhe
    )


def _ler_stdout(stream, fila: queue.Queue) -> None:
    try:
        for linha in stream:
            fila.put(linha)
    finally:
        fila.put(_FIM)


def _ler_stderr(stream, buffer: deque) -> None:
    for linha in stream:
        buffer.append(linha)


def _matar(proc: subprocess.Popen) -> None:
    """SIGTERM no grupo (o `uv run` é pai do python real), depois SIGKILL.

    O daemon do browser-harness fica de fora do grupo de propósito: ele deve sobreviver.
    """
    if proc.poll() is not None:
        return
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
    except (OSError, ValueError):
        proc.terminate()
    try:
        proc.wait(timeout=KILL_GRACE_S)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (OSError, ValueError):
        proc.kill()


def _popen_kwargs() -> dict:
    if hasattr(os, "setsid"):
        return {"start_new_session": True}
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    return {"creationflags": flags} if flags else {}


def run_jev(
    url: str,
    goals: Sequence[str],
    *,
    timeout_s: float | None = None,
    fechar: bool = False,
    on_progress: Callable[[dict], None] | None = None,
) -> BrowserResult:
    """Roda um objetivo no navegador. Bloqueia; devolve sempre um `BrowserResult`."""
    goals = list(goals)
    limite = float(timeout_s if timeout_s is not None else BROWSER_TIMEOUT_S)

    if not _EXECUCAO.acquire(blocking=False):
        return _erro("busy", "ja existe uma tarefa de navegador em andamento", goals)
    try:
        if shutil.which(UV_BIN) is None:
            return _erro("uv_missing", f"nao encontrei o executavel '{UV_BIN}' no PATH", goals)
        if not (Path(JEV_DIR) / "pyproject.toml").is_file():
            return _erro("jev_dir_missing", str(JEV_DIR), goals)

        cmd = build_command(url, goals, timeout_s=limite, fechar=fechar)
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_popen_kwargs(),
        )

        fila: queue.Queue = queue.Queue()
        erros: deque = deque(maxlen=STDERR_LINHAS)
        threading.Thread(target=_ler_stdout, args=(proc.stdout, fila), daemon=True).start()
        threading.Thread(target=_ler_stderr, args=(proc.stderr, erros), daemon=True).start()

        eventos: list[dict] = []
        prazo = time.monotonic() + limite + GRACE_S
        estourou = False
        interrompido = False

        try:
            while True:
                restante = prazo - time.monotonic()
                if restante <= 0:
                    estourou = True
                    break
                try:
                    item = fila.get(timeout=min(1.0, restante))
                except queue.Empty:
                    continue
                if item is _FIM:
                    break
                evento = parse_event(item)
                if evento is None:
                    continue
                eventos.append(evento)
                if evento.get("type") in {"step", "health"} and on_progress is not None:
                    on_progress(evento)
        except KeyboardInterrupt:
            interrompido = True

        if estourou or interrompido:
            _matar(proc)
        try:
            returncode = proc.wait(timeout=KILL_GRACE_S + 5)
        except subprocess.TimeoutExpired:
            _matar(proc)
            returncode = proc.poll()

        stderr_tail = "".join(erros)[-2000:] or None
        # Se nos matamos o processo e ele nao chegou a reportar nada, a causa verdadeira e o
        # prazo -- nao o "crash" que a ausencia de linha terminal sugeriria.
        tem_terminal = any(e.get("type") in {"result", "error"} for e in eventos)
        if (estourou or interrompido) and not tem_terminal:
            return _erro(
                "timeout_terminated" if interrompido else "timeout",
                f"interrompido apos {limite:.0f}s",
                goals,
            )
        return result_from(eventos, returncode, stderr_tail, goals)
    finally:
        _EXECUCAO.release()
