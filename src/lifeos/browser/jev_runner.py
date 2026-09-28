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
import secrets
import shutil
import signal
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from lifeos import registro
from lifeos.browser import _redacao, trava
from lifeos.config import (
    BROWSER_BLOQUEADOS,
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
    # Recusa do freio: a digital do clique (esquema+host, categoria, rótulo normalizado) e a URL
    # redigida da página, e se o subprocesso a julgou liberável. `liberado`: nesta execução o
    # subprocesso deixou passar o clique liberado (`--liberar-uma`).
    acao_sensivel: dict | None = None
    liberavel: bool = False
    liberado: bool = False


def build_command(
    url: str,
    goals: Sequence[str],
    *,
    timeout_s: float,
    fechar: bool = False,
    jev_dir: Path | None = None,
    env_file: Path | None = None,
    uv_bin: str | None = None,
    max_acoes: int | None = None,
    liberar: dict | None = None,
) -> list[str]:
    """URL e objetivos vão **colados** (`--goal=...`): um objetivo escrito pelo Gemini que comece
    com "--" ("--liberar-uma=...") continua sendo objetivo. `--liberar-uma` só sai daqui com
    `liberar`, que só o caminho de aprovação passa (`liberacao.clicar_aprovado`)."""
    cmd = _uv_run(jev_dir, env_file, uv_bin)
    cmd += ["python", str(SCRIPT_PATH), f"--url={url}"]
    cmd += [f"--goal={goal}" for goal in goals]
    teto = max_acoes if max_acoes is not None else BROWSER_MAX_ACOES
    cmd += ["--timeout", str(timeout_s), "--max-acoes", str(teto)]
    for dominio in BROWSER_BLOQUEADOS:
        cmd += ["--bloquear", dominio]
    if fechar:
        cmd.append("--fechar")
    if liberar is not None:
        cmd.append(f"--liberar-uma={json.dumps(liberar, sort_keys=True)}")
    return cmd


def _uv_run(jev_dir: Path | None, env_file: Path | None, uv_bin: str | None) -> list[str]:
    """`uv run` no clone do Jev, com o `.env` dele: é de lá, e só de lá, que vêm as chaves do Jev
    (D7). Fonte única para a tarefa e para o `--doctor`."""
    jev_dir = Path(jev_dir or JEV_DIR)
    env_file = Path(env_file) if env_file is not None else Path(JEV_ENV_FILE)
    cmd = [uv_bin or UV_BIN, "run", "--directory", str(jev_dir)]
    if env_file.is_file():
        cmd += ["--env-file", str(env_file)]
    return cmd


def comando_doctor() -> list[str]:
    return [*_uv_run(None, None, None), "browser-harness", "doctor"]


# O que o Jev, o `uv` e o daemon do Browser Harness recebem do ambiente do Viking (Sessão 6, D41):
# uma lista do que PODE passar, então uma chave nova do Viking já nasce bloqueada. Ficam de fora,
# entre outras, GEMINI_*, PLUGGY_*, GOOGLE_*, VIKING_* e as do próprio Jev (OPENROUTER_*, TYPESAFE_*,
# TEXT_MODEL*): medido com o uv 0.12.10 em 2026-09-27, o ambiente do pai VENCE o `--env-file`, e
# uma cópia velha no ambiente do Viking esconderia a do `.env` do Jev. Também VIRTUAL_ENV, CONDA_*
# e PYTHON*, que são da venv do Viking e confundiriam o `uv` do Jev. O daemon herda o ambiente da
# tarefa que o subiu e sobrevive a ela: o que passar daqui fica nele até ele reiniciar.
AMBIENTE_NOMES = frozenset(
    {
        "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "TZ",
        "CHROME_PATH",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
        "SSL_CERT_FILE", "SSL_CERT_DIR",
        "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS",
    }
)  # fmt: skip
AMBIENTE_PREFIXOS = ("LC_", "XDG_", "UV_", "BH_", "BU_", "BROWSER_HARNESS_")
# Dentro do prefixo e mesmo assim fora: qual `.env` o Jev lê é escolha do Viking (`_uv_run`). Medido
# com o uv 0.12.10 em 2026-09-27: sem o `--env-file` (o `.env` do Jev não existe), um UV_ENV_FILE
# herdado é lido; e UV_NO_ENV_FILE desliga o `.env` do Jev em silêncio.
AMBIENTE_EXCETO = frozenset({"UV_ENV_FILE", "UV_NO_ENV_FILE"})


def ambiente_do_jev(nonce: str = "", origem: Mapping[str, str] | None = None) -> dict[str, str]:
    """O ambiente de um subprocesso do Jev: só o que está na lista acima, mais o nonce desta
    execução. Um `VIKING_JEV_NONCE` que já estivesse no ambiente do Viking não passa."""
    origem = os.environ if origem is None else origem
    env = {
        nome: valor
        for nome, valor in origem.items()
        if nome not in AMBIENTE_EXCETO
        and (nome in AMBIENTE_NOMES or nome.startswith(AMBIENTE_PREFIXOS))
    }
    if nonce:
        env["VIKING_JEV_NONCE"] = nonce
    return env


SCHEMA = 1
TIPOS = frozenset({"start", "health", "step", "liberado", "result", "error"})


def parse_event(linha: str, nonce: str) -> dict | None:
    """O evento, se a linha é do protocolo DESTA execução; `None` para qualquer outra coisa.

    Estrito (Sessão 6, auditoria §10.10): `schema` 1, o `nonce` sorteado para esta execução, `type`
    conhecido e os campos que decidem o resultado com o tipo certo. Uma dependência que imprima um
    JSON parecido no stdout não produz um terminal falso: sem o nonce, é ruído.
    """
    linha = linha.strip()
    if not nonce or not linha or not linha.startswith("{"):
        return None
    try:
        evento = json.loads(linha)
    except json.JSONDecodeError:
        return None
    if not isinstance(evento, dict) or evento.get("nonce") != nonce:
        return None
    schema = evento.get("schema")
    if type(schema) is not int or schema != SCHEMA or evento.get("type") not in TIPOS:
        return None
    if evento["type"] == "result" and not isinstance(evento.get("status"), str):
        return None
    if evento["type"] == "error" and not isinstance(evento.get("code"), str):
        return None
    return evento


_CAMPOS_DIGITAL = ("esquema_host", "categoria", "rotulo")


def _acao_sensivel(evento: dict) -> dict | None:
    """A digital da recusa, só com os campos esperados e todos texto; qualquer outra forma é
    ignorada (sem digital não há proposta de liberação)."""
    bruto = evento.get("acao_sensivel")
    if not isinstance(bruto, dict):
        return None
    campos = (*_CAMPOS_DIGITAL, "url")
    if not all(isinstance(bruto.get(c), str) for c in campos):
        return None
    return {c: bruto[c] for c in campos}


def _limpo(texto: str | None) -> str | None:
    return _redacao.limpar_controles(_redacao.redigir(texto))


def _url_limpa(url: str | None) -> str | None:
    return _redacao.limpar_controles(_redacao.redigir_url(url))


def _passo_limpo(passo: dict) -> dict:
    """Só transforma as chaves que o passo já tem — não inventa `text: None` onde não havia."""
    limpo = dict(passo)
    rotulo = passo.get("action")
    if "action" in limpo:
        limpo["action"] = _limpo(rotulo)
    if "text" in limpo:
        digitado = _redacao.mascarar_digitado(rotulo, passo["text"])
        limpo["text"] = _redacao.limpar_controles(digitado)
    if "url" in limpo:
        limpo["url"] = _url_limpa(passo["url"])
    return limpo


def _higienizar(resultado: BrowserResult) -> BrowserResult:
    """Ponto único por onde passa tudo que veio da página antes de chegar ao Gemini, ao terminal
    ou ao `--json`: redige documento/cartão/token, esconde o que foi digitado em campo sensível e
    tira caracteres de controle (`json.dumps(ensure_ascii=False)` escapa C0, mas NÃO C1)."""
    return replace(
        resultado,
        url=_url_limpa(resultado.url),
        title=_limpo(resultado.title),
        page_text=_limpo(resultado.page_text),
        history=tuple(_passo_limpo(p) for p in resultado.history),
        error_detail=_limpo(resultado.error_detail),
        stderr_tail=_limpo(resultado.stderr_tail),
        acao_sensivel=(
            {**resultado.acao_sensivel, "url": _url_limpa(resultado.acao_sensivel["url"])}
            if resultado.acao_sensivel
            else None
        ),
    )


def result_from(
    eventos: Sequence[dict],
    returncode: int | None,
    stderr_tail: str | None,
    goals: Sequence[str],
) -> BrowserResult:
    return _higienizar(_montar_resultado(eventos, returncode, stderr_tail, goals))


def _montar_resultado(
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
        "liberado": any(e.get("type") == "liberado" for e in eventos),
    }
    if final["type"] == "error":
        acao_sensivel = _acao_sensivel(final)
        return BrowserResult(
            status="error",
            error_code=final.get("code") or "unknown",
            error_detail=final.get("message"),
            acao_sensivel=acao_sensivel,
            liberavel=acao_sensivel is not None and final.get("liberavel") is True,
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


def _avisar(on_progress: Callable[[dict], None] | None, evento: dict) -> None:
    """Progresso é cosmético: um callback que levanta (stderr fechado, por exemplo) não pode
    escapar do laço principal — se escapasse, ninguém mataria o subprocesso e ele ficaria
    dirigindo a Chrome do usuário sem supervisão nenhuma."""
    if on_progress is None:
        return
    try:
        on_progress(evento)
    except Exception:  # noqa: BLE001, S110 - progresso nunca pode derrubar a tarefa
        pass


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
    max_acoes: int | None = None,
    liberar: dict | None = None,
) -> BrowserResult:
    """Roda um objetivo no navegador. Bloqueia; devolve sempre um `BrowserResult` — inclusive se
    o subprocesso não conseguir nem iniciar (`spawn_failed`) ou se `on_progress` levantar. Em
    qualquer caminho de saída, o processo filho é aguardado ou morto antes do retorno: nenhuma
    exceção escapa deixando o Jev sozinho dirigindo a Chrome do usuário.
    """
    goals = list(goals)
    limite = float(timeout_s if timeout_s is not None else BROWSER_TIMEOUT_S)

    # Antes de tudo, inclusive do lock: um site bloqueado nem chega a abrir aba. Redirecionamentos
    # e links no meio da tarefa são pegos dentro do subprocesso (`instalar_protecao`). O esquema
    # vem primeiro: `file:` e `view-source:` nem são "site" (D8, furo fechado na Sessão 8).
    if not _redacao.esquema_permitido(url):
        return _erro(
            "endereco_recusado", _redacao.redigir_url(_redacao.limpar_controles(url))[:120], goals
        )
    bloqueado = _redacao.dominio_bloqueado(url, BROWSER_BLOQUEADOS)
    if bloqueado:
        return _erro("dominio_bloqueado", bloqueado, goals)

    if not _EXECUCAO.acquire(blocking=False):
        return _erro("busy", "ja existe uma tarefa de navegador em andamento", goals)
    try:
        if shutil.which(UV_BIN) is None:
            return _erro("uv_missing", f"nao encontrei o executavel '{UV_BIN}' no PATH", goals)
        if not (Path(JEV_DIR) / "pyproject.toml").is_file():
            return _erro("jev_dir_missing", str(JEV_DIR), goals)

        # A trava entre processos (outro `viking` usando o mesmo Chrome): sem espera, e antes de
        # qualquer coisa que abra o subprocesso — o preflight dele reiniciaria o daemon do outro.
        try:
            with trava.ocupar(goals[0] if goals else "") as ocupado:
                if ocupado is not None:
                    return _erro("busy", trava.descrever(ocupado), goals)
                return _executar(url, goals, limite, fechar, on_progress, max_acoes, liberar)
        except trava.Indisponivel as exc:
            # "Sempre devolve BrowserResult" (§10.8): e sem trava não se navega.
            return _erro("trava_indisponivel", str(exc), goals)
    finally:
        _EXECUCAO.release()


def _executar(url, goals, limite, fechar, on_progress, max_acoes, liberar) -> BrowserResult:
    cmd = build_command(
        url, goals, timeout_s=limite, fechar=fechar, max_acoes=max_acoes, liberar=liberar
    )
    # Registrado só daqui em diante: as recusas acima não abriram nada. A digital liberada
    # entra no registro; o código que a aprovou nunca chega aqui.
    parametros = {"url": _redacao.redigir_url(url), "objetivos": goals}
    if liberar is not None:
        parametros["liberar"] = liberar
    with registro.acao("navegador.executar", parametros) as marca:
        resultado = _rodar(cmd, goals, limite, on_progress, secrets.token_hex(8))
        marca.feito(
            {
                "status": resultado.status,
                "erro": resultado.error_code or "",
                "passos": resultado.steps,
                "liberado": resultado.liberado,
            }
        )
    return resultado


def _rodar(
    cmd: list[str],
    goals: list[str],
    limite: float,
    on_progress: Callable[[dict], None] | None,
    nonce: str,
) -> BrowserResult:
    """O subprocesso do Jev, do `Popen` ao resultado; o processo nunca fica vivo depois."""
    try:
        proc = subprocess.Popen(
            cmd,
            env=ambiente_do_jev(nonce),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **_popen_kwargs(),
        )
    except OSError as exc:
        return _erro("spawn_failed", f"nao consegui iniciar o executor: {exc}", goals)

    # Tudo a partir daqui roda sob um processo filho vivo — o finally garante que ele é
    # aguardado ou morto não importa por onde a gente saia (retorno normal ou exceção
    # inesperada). Sem isso, um erro imprevisto no laço abaixo vazava o processo e a aba.
    try:
        fila: queue.Queue = queue.Queue()
        erros: deque = deque(maxlen=STDERR_LINHAS)
        threading.Thread(target=_ler_stdout, args=(proc.stdout, fila), daemon=True).start()
        threading.Thread(target=_ler_stderr, args=(proc.stderr, erros), daemon=True).start()

        eventos: list[dict] = []
        inicio = time.monotonic()
        prazo = inicio + limite + GRACE_S
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
                evento = parse_event(item, nonce)
                if evento is None:
                    continue
                eventos.append(evento)
                if evento.get("type") in {"step", "health"}:
                    _avisar(on_progress, evento)
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
            # Tempo REAL decorrido, não o limite configurado: um Ctrl-C aos 3s não pode
            # dizer "interrompido após 180s".
            decorrido = time.monotonic() - inicio
            return _erro(
                "timeout_terminated" if interrompido else "timeout",
                f"interrompido apos {decorrido:.0f}s",
                goals,
            )
        return result_from(eventos, returncode, stderr_tail, goals)
    finally:
        if proc.poll() is None:
            _matar(proc)
