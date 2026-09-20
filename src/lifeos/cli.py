"""Ponto de entrada `viking` — CLI do assistente e do servidor MCP.

Ver docs/arquitetura/viking-visao-e-arquitetura.md.
"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="viking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "chat", help="Inicia o assistente de chat (calendário + navegador + lembretes)"
    )
    subparsers.add_parser(
        "mcp-server", help="Inicia o servidor MCP do Viking (calendário + lembretes)"
    )

    args = parser.parse_args()

    if args.command == "chat":
        from lifeos.assistant.agent import iniciar_assistente

        iniciar_assistente()
    elif args.command == "mcp-server":
        from lifeos.mcp_server.server import main as run_server

        run_server()


if __name__ == "__main__":
    main()
