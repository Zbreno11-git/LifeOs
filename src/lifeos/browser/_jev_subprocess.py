"""Runner do Jev, executado DENTRO do ambiente do jev-ultrafast (nunca no do Viking).

Só pode importar stdlib + `jev_ultrafast`. Jamais `import lifeos`: o Viking fala com este script
por subprocesso, e o único contrato entre os dois é o JSONL impresso no stdout.

Protocolo (uma linha JSON por evento, stdout; stderr fica para ruído humano):
  {"schema":1,"type":"start",  ...}
  {"schema":1,"type":"step",   ...}   zero ou mais
  {"schema":1,"type":"result", ...}   terminal
  {"schema":1,"type":"error",  ...}   terminal (alternativo)

Exit codes: 0 done · 1 blocked · 2 erro classificado · 3 crash antes de classificar ·
4 interrompido por prazo/sinal. Erro de uso do argparse sai com 2 e SEM linha JSON nenhuma --
o lado Viking trata o JSONL como fonte da verdade e so recorre ao exit code quando nao ha
linha terminal.
"""

import argparse
import json
import signal
import sys
import time

SCHEMA = 1
MAX_TEXT = 1200
MAX_LABEL = 80
MAX_HISTORY = 15
MAX_MESSAGE = 600

EXIT_DONE = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2
EXIT_USAGE = 3
EXIT_INTERRUPTED = 4

_interrompido = False


def _on_signal(_signum, _frame):
    global _interrompido
    _interrompido = True


def emit(**evento):
    sys.stdout.write(json.dumps({"schema": SCHEMA, **evento}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def classificar(exc):
    msg = str(exc)
    nome = type(exc).__name__
    if isinstance(exc, KeyError) and ("TYPESAFE_API_KEY" in msg or "OPENROUTER_API_KEY" in msg):
        return "model_key_missing"
    if "browser-not-ready" in msg:
        return "browser_not_ready"
    if "chrome-not-running" in msg:
        return "chrome_not_running"
    if "permission-blocked" in msg:
        return "chrome_permission"
    if "daemon-starting" in msg or "didn't come up" in msg:
        return "daemon_down"
    if "TEXT_MODEL_API_KEY" in msg:
        return "text_model_key_missing"
    if "returned HTTP 401" in msg or "returned HTTP 403" in msg:
        return "model_auth"
    if "returned HTTP" in msg:
        return "model_http"
    if "Model unavailable" in msg or "Model connection failed" in msg:
        return "model_unreachable"
    if "budget" in msg:
        return "step_budget"
    if nome == "StalePage" or "did not settle" in msg:
        return "page_unstable"
    if isinstance(exc, (TimeoutError, ConnectionRefusedError, FileNotFoundError)):
        return "harness_ipc"
    if nome in {"ValueError", "RuntimeError"} and "Invalid" in msg:
        return "model_bad_answer"
    return "unknown"


def _probe():
    """Chamada CDP real. É ela que reata a conexão quando o daemon está vivo mas solto."""
    from browser_harness.helpers import page_info

    page_info()


def preparar_navegador():
    """Garante daemon vivo + conexão de navegador ativa + probe CDP bem-sucedido.

    `daemon vivo != navegador pronto`: o daemon pode continuar de pé com zero conexões ativas e,
    nesse estado, a primeira chamada CDP morre com `_IPCResponseTimeout` depois de 5s. Um probe
    costuma reatar sozinho; se não reatar, reiniciamos o daemon uma vez e desistimos. As
    retentativas são limitadas de propósito — ver docs/arquitetura/browser-automation-stack.md,
    seções 10 e 11 (incidente real: daemon vivo com 0 conexões).
    """
    from browser_harness.admin import daemon_browser_ready, ensure_daemon, restart_daemon

    ensure_daemon()
    try:
        _probe()
        return "ok"
    except Exception as exc:  # noqa: BLE001 - qualquer falha aqui significa "nao pronto"
        print(f"jev-runner: probe inicial falhou ({exc}); tentando reatar", file=sys.stderr)

    if daemon_browser_ready():
        try:
            _probe()
            return "reatado"
        except Exception as exc:  # noqa: BLE001
            print(f"jev-runner: reattach falhou ({exc}); reiniciando o daemon", file=sys.stderr)

    restart_daemon()
    ensure_daemon()
    try:
        _probe()
    except Exception as exc:
        raise RuntimeError(
            f"browser-not-ready: probe CDP falhou apos reiniciar o daemon: {exc}"
        ) from exc
    return "reiniciado"


def _pagina(state):
    page = (state or {}).get("page") or {}
    texto = page.get("text") or ""
    return {
        "url": page.get("url"),
        "title": page.get("title"),
        "page_text": texto[:MAX_TEXT],
        "page_text_truncated": len(texto) > MAX_TEXT,
    }


def _rotulo(entrada):
    valor = entrada.get("action") or entrada.get("operation") or ""
    return str(valor)[:MAX_LABEL]


def _historico(state):
    entradas = (state or {}).get("history") or []
    return [
        {
            "step": e.get("step"),
            "action": _rotulo(e),
            "kind": e.get("kind"),
            "url": e.get("url"),
        }
        for e in entradas[-MAX_HISTORY:]
    ]


def _passos(state):
    return len((state or {}).get("history") or [])


def main():
    parser = argparse.ArgumentParser(prog="jev-runner")
    parser.add_argument("--url", required=True)
    parser.add_argument("--goal", action="append", dest="goals", required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Import depois do argparse de propósito: erro de uso não deve exigir o ambiente do Jev.
    from jev_ultrafast import Agent

    emit(type="start", url=args.url, goals=args.goals)
    prazo = time.monotonic() + args.timeout
    agent = None
    state = None

    try:
        emit(type="health", state=preparar_navegador())
        agent = Agent(args.url, args.goals)
        state = agent.snapshot()
        for state in agent.run():
            historico = _historico(state)
            emit(
                type="step",
                n=_passos(state),
                status=state.get("status"),
                elapsed_ms=state.get("elapsed_ms"),
                last_action=historico[-1]["action"] if historico else None,
                kind=historico[-1]["kind"] if historico else None,
                url=(state.get("page") or {}).get("url"),
            )
            if _interrompido or time.monotonic() >= prazo:
                emit(
                    type="error",
                    code="timeout_terminated" if _interrompido else "timeout",
                    exception="Timeout",
                    message=f"Interrompido apos {args.timeout:.0f}s de limite.",
                    steps=_passos(state),
                    elapsed_ms=state.get("elapsed_ms"),
                    history=historico,
                    **_pagina(state),
                )
                return EXIT_INTERRUPTED

        status = (state or {}).get("status")
        emit(
            type="result",
            status=status,
            goals=args.goals,
            steps=_passos(state),
            elapsed_ms=(state or {}).get("elapsed_ms"),
            history=_historico(state),
            **_pagina(state),
        )
        return EXIT_DONE if status == "done" else EXIT_BLOCKED

    except BaseException as exc:  # noqa: BLE001 - tudo vira uma linha de erro classificada
        # MAX_STEPS levanta no MEIO do gerador, entao o estado final vem do snapshot,
        # nao do ultimo yield (que nao inclui o passo que falhou).
        final = state
        if agent is not None:
            try:
                final = agent.snapshot()
            except Exception:  # noqa: BLE001
                final = state
        emit(
            type="error",
            code=classificar(exc),
            exception=type(exc).__name__,
            message=str(exc)[:MAX_MESSAGE],
            steps=_passos(final),
            elapsed_ms=(final or {}).get("elapsed_ms"),
            history=_historico(final),
            **_pagina(final),
        )
        return EXIT_ERROR

    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception as exc:  # noqa: BLE001 - fechar a aba e best-effort
                print(f"jev-runner: falha ao fechar a aba: {exc}", file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - crash antes de conseguir classificar
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(EXIT_USAGE)
