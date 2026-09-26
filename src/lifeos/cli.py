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
        fechar=args.fechar,
        on_progress=None if args.quiet else imprimir_progresso,
    )

    if args.json:
        print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))
    else:
        print(formatar(resultado))

    return {"done": 0, "blocked": 1}.get(resultado.status, 2)


def _gmail(args: argparse.Namespace) -> int:
    """Gmail sem passar pelo Gemini: o texto impresso é o mesmo que o chat entrega ao modelo."""
    from lifeos.gmail import service, tools

    if args.login:
        try:
            endereco, total = service.perfil()
        except service.ErroGmail as exc:
            print(f"❌ {tools.mensagem_de_erro(exc)}", file=sys.stderr)
            return 2
        print(f"✅ Login do Gmail ok (só leitura): {endereco}, {total} mensagens na conta.")
        return 0
    if args.buscar is not None:
        print(tools.buscar_emails(args.buscar, args.max))
    elif args.ler:
        print(tools.ler_email(args.ler))
    elif args.raio_x is not None:
        print(tools.raio_x_da_caixa(args.raio_x))
    else:
        print(tools.emails_nao_lidos_de_hoje())
    return 0


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
    navegador.add_argument(
        "--fechar", action="store_true", help="Fecha a aba ao terminar (padrão: deixa aberta)"
    )
    navegador.add_argument("--json", action="store_true", help="Imprime o resultado bruto em JSON")
    navegador.add_argument(
        "--quiet", action="store_true", help="Não imprime o progresso passo a passo"
    )
    navegador.add_argument(
        "--doctor", action="store_true", help="Diagnostica o Browser Harness e sai"
    )

    gmail = subparsers.add_parser(
        "gmail", help="Lê o Gmail pela API, sem o Gemini (padrão: não lidos de hoje)"
    )
    acao = gmail.add_mutually_exclusive_group()
    acao.add_argument("--login", action="store_true", help="Faz/confere o login do Gmail e sai")
    acao.add_argument("--buscar", metavar="CONSULTA", help='Busca do Gmail, ex.: "is:unread"')
    acao.add_argument("--ler", metavar="ID", help="Lê um e-mail pelo ID de uma busca")
    acao.add_argument(
        "--raio-x", type=int, nargs="?", const=30, metavar="DIAS", help="Raio-x da caixa"
    )
    gmail.add_argument("--max", type=int, default=10, help="Máximo de resultados da busca")

    args = parser.parse_args()

    if args.command == "chat":
        from lifeos.assistant.agent import iniciar_assistente

        iniciar_assistente()
    elif args.command == "mcp-server":
        from lifeos.mcp_server.server import main as run_server

        run_server()
    elif args.command == "browser":
        sys.exit(_browser(args, navegador))
    elif args.command == "gmail":
        sys.exit(_gmail(args))


if __name__ == "__main__":
    main()
