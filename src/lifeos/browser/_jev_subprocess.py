"""Runner do Jev, executado DENTRO do ambiente do jev-ultrafast (nunca no do Viking).

Só pode importar stdlib + `jev_ultrafast` + o módulo irmão `_redacao` (também só stdlib). Jamais
`import lifeos`: o Viking fala com este script por subprocesso, e o único contrato entre os dois é
o JSONL impresso no stdout.

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

if __package__:
    # Testes: importado como `lifeos.browser._jev_subprocess`.
    from . import _redacao
else:
    # Subprocesso: rodando como script, com o diretório dele em sys.path[0].
    import _redacao

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
    if msg.startswith("dominio-bloqueado"):
        return "dominio_bloqueado"
    if msg.startswith("protecao-indisponivel"):
        return "protecao_indisponivel"
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


def instalar_protecao(bloqueados):
    """Envolve as duas únicas saídas de conteúdo de página do Jev para modelos remotos: `choose`
    (decisões, OpenRouter) e `field_context` (contexto do modelo de texto — `field_text` recebe o
    que ela monta). O Jev as chama como globais de `jev_ultrafast.agent`, então trocar o nome ali
    intercepta toda chamada; `tests/test_jev_subprocess_main.py` confere esse contrato no código
    real do Jev.

    A checagem de domínio mora aqui, antes de toda saída, e não no laço de passos: o primeiro
    `choose` roda dentro de `run()` antes do primeiro yield, então um redirecionamento na página
    inicial escaparia de uma checagem no laço.

    Fecha em falha: se o Jev mudar e as funções sumirem, recusamos navegar em vez de navegar sem
    redação.
    """
    try:
        import jev_ultrafast.agent as agente
    except ImportError as exc:
        raise RuntimeError(f"protecao-indisponivel: sem jev_ultrafast.agent ({exc})") from exc

    choose = getattr(agente, "choose", None)
    field_context = getattr(agente, "field_context", None)
    if not callable(choose) or not callable(field_context):
        # RuntimeError, não TypeError: é o mesmo "proteção indisponível" do ramo acima.
        raise RuntimeError(  # noqa: TRY004
            "protecao-indisponivel: jev_ultrafast.agent sem choose/field_context"
        )

    def _checar(page):
        dominio = _redacao.dominio_bloqueado((page or {}).get("url") or "", bloqueados)
        if dominio:
            raise RuntimeError(f"dominio-bloqueado: {dominio}")

    def choose_protegido(page, goal, history):
        _checar(page)
        return choose(_redacao.pagina(page), goal, history)

    def field_context_protegido(goal, action, page, history):
        _checar(page)
        return field_context(goal, action, _redacao.pagina(page), history)

    agente.choose = choose_protegido
    agente.field_context = field_context_protegido


def _normalizar(url):
    """Reduz a URL a esquema+host+caminho: /watch?v=A e /watch?v=B viram o mesmo estado.

    Sem isso, um executor que alterna entre a página de resultados e um vídeo *diferente* a cada
    volta nunca repete a assinatura exata — e o detector de ciclo não enxerga o loop. Foi
    exatamente o que aconteceu com "abre o segundo resultado" em 2026-09-20: cinco vídeos
    distintos, mesma estrutura busca→vídeo→busca→vídeo.
    """
    if not url:
        return None
    return url.split("?", 1)[0].split("#", 1)[0].rstrip("/")


def _oscilando(assinaturas, periodos=(2, 3, 4)):
    """Detecta ciclo A→B→A→B (período 2) ou mais longo (3, 4 estados) se repetindo.

    O guard do próprio Jev só pega o caso oposto — página que NÃO muda 3 vezes seguidas. Aqui a
    página muda a cada ação, mas entre um conjunto pequeno e fixo de estados, o que é o sintoma de
    um objetivo que nenhuma ação satisfaz. Sem isso o executor roda até o teto de 60 ações queimando
    tempo e chamadas de modelo.

    Assinatura de estado = (url, ação) em vez de só a URL: digitar num campo de busca costuma não
    mudar a URL, então URL sozinha não distingue "digitando" de "clicando resultado" — sem a ação
    junto, um ciclo período-3 real pode parecer período-1 (mesma URL sempre) e não ser detectado.

    Exige 3 repetições completas do ciclo antes de cortar (não 2), para não confundir com uma
    sequência legítima que por acaso revisita os mesmos poucos estados uma vez.

    Casos observados ao vivo em 2026-09-20: período 2 ("abra X e me diga o link principal", vira
    pergunta-como-objetivo) e período 3 (busca no YouTube reiniciando a cada tentativa de clicar um
    resultado que ainda não carregou).
    """
    for p in periodos:
        precisa = p * 3
        if len(assinaturas) < precisa:
            continue
        janela = assinaturas[-precisa:]
        ciclos = [tuple(janela[i * p : (i + 1) * p]) for i in range(3)]
        if ciclos[0] == ciclos[1] == ciclos[2] and len(set(ciclos[0])) > 1:
            return True
    return False


def _uso(state):
    """Soma o `usage` de toda chamada paga: as decisões (inclusive a última, que não executa ação)
    e as de geração de texto. Somamos qualquer campo numérico que o provedor mandar, em vez de
    assumir nomes, porque o endpoint de decisões é alpha e pode mudar o formato."""
    total = {}
    chamadas = 0
    for lista in ("decisions", "text_calls"):
        for entrada in (state or {}).get(lista) or []:
            chamadas += 1
            for chave, valor in (entrada.get("usage") or {}).items():
                if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                    total[chave] = total.get(chave, 0) + valor
    total["chamadas"] = chamadas
    return total


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
            "text": (e.get("text") or "")[:80] or None,
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
    parser.add_argument("--fechar", action="store_true", help="fecha a aba ao terminar")
    parser.add_argument("--max-acoes", type=int, default=30, dest="max_acoes")
    parser.add_argument("--bloquear", action="append", default=[], metavar="DOMINIO")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    # Import depois do argparse de propósito: erro de uso não deve exigir o ambiente do Jev.
    from jev_ultrafast import Agent

    emit(type="start", url=args.url, goals=args.goals)
    prazo = time.monotonic() + args.timeout
    agent = None
    state = None
    assinaturas = []
    amplas = []

    try:
        instalar_protecao(args.bloquear)
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
            # Estado terminal vence os guardas abaixo: concluir exatamente na ação-limite, ou
            # num estado que por acaso fecha um ciclo de assinaturas, é sucesso — não
            # step_budget nem loop_detected. Cair fora do laço aqui reusa o emit de "result"
            # de sucesso logo depois dele, com o mesmo kept_open/usage que o caminho normal.
            if state.get("status") in {"done", "blocked"}:
                break
            url_passo = (state.get("page") or {}).get("url")
            ultimo = historico[-1] if historico else {}
            assinaturas.append((url_passo, ultimo.get("action")))
            # A lista ampla pega o loop "estrutural": mesmo vaivém entre tipos de página, ainda que
            # o alvo clicado mude toda vez.
            amplas.append((_normalizar(url_passo), ultimo.get("kind")))
            if _passos(state) >= args.max_acoes:
                emit(
                    type="error",
                    code="step_budget",
                    exception="LimiteDeAcoes",
                    message=f"parei em {args.max_acoes} ações sem concluir",
                    steps=_passos(state),
                    elapsed_ms=state.get("elapsed_ms"),
                    history=historico,
                    usage=_uso(state),
                    kept_open=not args.fechar,
                    **_pagina(state),
                )
                return EXIT_ERROR

            if _oscilando(assinaturas) or _oscilando(amplas):
                emit(
                    type="error",
                    code="loop_detected",
                    exception="LoopDetected",
                    message=f"ciclo detectado, ultimos estados: {assinaturas[-3:]}",
                    steps=_passos(state),
                    elapsed_ms=state.get("elapsed_ms"),
                    history=historico,
                    usage=_uso(state),
                    kept_open=not args.fechar,
                    **_pagina(state),
                )
                return EXIT_ERROR

            if _interrompido or time.monotonic() >= prazo:
                emit(
                    type="error",
                    code="timeout_terminated" if _interrompido else "timeout",
                    exception="Timeout",
                    message=f"Interrompido apos {args.timeout:.0f}s de limite.",
                    steps=_passos(state),
                    elapsed_ms=state.get("elapsed_ms"),
                    history=historico,
                    usage=_uso(state),
                    kept_open=not args.fechar,
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
            usage=_uso(state),
            kept_open=not args.fechar,
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
        codigo = classificar(exc)
        emit(
            type="error",
            code=codigo,
            exception=type(exc).__name__,
            message=str(exc)[:MAX_MESSAGE],
            steps=_passos(final),
            elapsed_ms=(final or {}).get("elapsed_ms"),
            history=_historico(final),
            usage=_uso(final),
            # Só há aba pra manter aberta se um Agent chegou a ser construído (ex.: o health
            # check pode falhar antes disso, e aí não existe nenhuma aba).
            kept_open=agent is not None and not args.fechar,
            # A página de um domínio bloqueado não sai deste processo nem pro Viking.
            **({} if codigo == "dominio_bloqueado" else _pagina(final)),
        )
        return EXIT_ERROR

    finally:
        if agent is not None:
            if args.fechar:
                try:
                    agent.close()
                except Exception as exc:  # noqa: BLE001 - fechar a aba e best-effort
                    print(f"jev-runner: falha ao fechar a aba: {exc}", file=sys.stderr)
            else:
                # O Jev abre a aba em segundo plano e a fecharia ao sair. Num assistente que dirige
                # o navegador do próprio usuário isso é o avesso do esperado: ele pede "abre o
                # YouTube" e a aba some. Por padrão mantemos a aba e a trazemos para a frente.
                try:
                    from browser_harness.helpers import cdp

                    cdp("Target.activateTarget", targetId=agent.browser.target)
                except Exception as exc:  # noqa: BLE001 - best-effort
                    print(f"jev-runner: nao consegui focar a aba: {exc}", file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - crash antes de conseguir classificar
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(EXIT_USAGE)
