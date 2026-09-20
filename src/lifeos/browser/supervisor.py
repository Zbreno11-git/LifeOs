"""Checagem de saúde do Browser Harness antes de executar uma tarefa.

Achado documentado em docs/fontes/browser-harness.md e
docs/arquitetura/browser-automation-stack.md: o daemon pode reportar "vivo" com zero conexões
ativas de navegador (`daemon alive != browser ready`). Um health check real precisa de um probe
de verdade (aqui, `browser_page_info`), não só o processo estar de pé.
"""

from __future__ import annotations

from lifeos.browser.client import page_info


class BrowserUnavailableError(RuntimeError):
    """O Browser Harness está rodando mas não tem um navegador pronto para uso."""


async def ensure_ready(client, retries: int = 1) -> None:
    """Confirma que o navegador está pronto, tentando de novo `retries` vezes antes de desistir."""
    last_error: Exception | None = None
    for _ in range(retries + 1):
        try:
            await page_info(client)
            return
        except Exception as exc:  # noqa: BLE001 - qualquer falha de MCP/CDP conta como "não pronto"
            last_error = exc
    raise BrowserUnavailableError(
        "Browser Harness não respondeu a um probe de página — o daemon pode estar vivo sem um "
        "navegador ativo. Ver docs/fontes/browser-harness.md."
    ) from last_error
