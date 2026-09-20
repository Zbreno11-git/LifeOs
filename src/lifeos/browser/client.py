"""Cliente MCP do Viking para o Browser Harness — as "mãos" do assistente.

Ver docs/arquitetura/viking-visao-e-arquitetura.md (seção 4.2) e docs/fontes/browser-harness.md.
Nomes de tool e comando de lançamento confirmados por testes reais registrados em
docs/arquitetura/browser-automation-stack.md: `browser_page_info`, `browser_new_tab`, lançado via
`uvx --python 3.12 --from 'browser-harness[mcp]' browser-harness-mcp`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

BROWSER_HARNESS_COMMAND = "uvx"
BROWSER_HARNESS_ARGS = [
    "--python",
    "3.12",
    "--from",
    "browser-harness[mcp]",
    "browser-harness-mcp",
]


@asynccontextmanager
async def connect():
    """Abre uma sessão MCP com o servidor local do Browser Harness."""
    params = StdioServerParameters(command=BROWSER_HARNESS_COMMAND, args=BROWSER_HARNESS_ARGS)
    async with Client(stdio_client(params)) as client:
        yield client


async def page_info(client) -> str:
    result = await client.call_tool("browser_page_info", {})
    return result.content


async def new_tab(client, url: str) -> str:
    result = await client.call_tool("browser_new_tab", {"url": url})
    return result.content
