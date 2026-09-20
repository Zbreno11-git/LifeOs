"""Ponto de entrada `viking` — assistente de chat, navegador e servidor MCP.

Ver docs/arquitetura/viking-visao-e-arquitetura.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict


def _doctor() -> int:
    """Diagnóstico do Browser Harness, usando a ferramenta do próprio fornecedor."""
    from lifeos.config import JEV_DIR, UV_BIN

    cmd = [UV_BIN, "run", "--directory", str(JEV_DIR), "browser-harness", "doctor"]
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(f"❌ Não encontrei o executável '{UV_BIN}' no PATH.", file=sys.stderr)
        return 2


def _browser(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.doctor:
        return _doctor()
    if not args.url or not args.goals:
        parser.error("--url e --goal são obrigatórios (ou use --doctor)")

    from lifeos.browser import formatar, imprimir_progresso, run_jev
    from lifeos.browser.jev_runner import BrowserResult

    resultado: BrowserResult = run_jev(
        args.url,
        args.goals,
        timeout_s=args.timeout,
        on_progress=None if args.quiet else imprimir_progresso,
    )

    if args.json:
        print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))
    else:
        print(formatar(resultado))

    return {"done": 0, "blocked": 1}.get(resultado.status, 2)


def main() -> None:
    parser = argparse.ArgumentParser(prog="viking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "chat", help="Inicia o assistente de chat (calendário + navegador + lembretes)"
    )
    subparsers.add_parser(
        "mcp-server", help="Inicia o servidor MCP do Viking (calendário + lembretes)"
    )
    navegador = subparsers.add_parser(
        "browser", help="Executa um objetivo num navegador real (executor Jev)"
    )
    navegador.add_argument("--url", help="URL inicial (obrigatório, exceto com --doctor)")
    navegador.add_argument(
        "--goal",
        action="append",
        dest="goals",
        metavar="OBJETIVO",
        help="Objetivo em linguagem natural; repita para uma lista ordenada",
    )
    navegador.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Segundos até interromper (padrão: VIKING_BROWSER_TIMEOUT_S, 180)",
    )
    navegador.add_argument("--json", action="store_true", help="Imprime o resultado bruto em JSON")
    navegador.add_argument(
        "--quiet", action="store_true", help="Não imprime o progresso passo a passo"
    )
    navegador.add_argument(
        "--doctor", action="store_true", help="Diagnostica o Browser Harness e sai"
    )

    args = parser.parse_args()

    if args.command == "chat":
        from lifeos.assistant.agent import iniciar_assistente

        iniciar_assistente()
    elif args.command == "mcp-server":
        from lifeos.mcp_server.server import main as run_server

        run_server()
    elif args.command == "browser":
        sys.exit(_browser(args, navegador))


if __name__ == "__main__":
    main()
