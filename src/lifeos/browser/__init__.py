from lifeos.browser.client import connect, new_tab, page_info
from lifeos.browser.supervisor import BrowserUnavailableError, ensure_ready


async def browser_goal(url: str, goal: str) -> str:
    """
    Abre `url` e reporta o estado inicial da página para um objetivo em linguagem natural.

    Implementação parcial: garante que o Browser Harness está pronto (ver `supervisor.ensure_ready`),
    abre a aba e retorna o estado inicial. O loop de decisão via Jev (clicar/digitar/rolar até o
    `goal` ser atingido — ver docs/arquitetura/browser-automation-stack.md) ainda não está integrado
    aqui; é o próximo passo deste módulo, não deste milestone de estrutura.
    """
    async with connect() as client:
        await ensure_ready(client)
        await new_tab(client, url)
        info = await page_info(client)
        return (
            f"Aba aberta em {url}. Estado inicial: {info}\n"
            f"(objetivo '{goal}' ainda não é perseguido automaticamente — loop de decisão via Jev "
            "pendente, ver docs/arquitetura/browser-automation-stack.md)"
        )


__all__ = [
    "BrowserUnavailableError",
    "browser_goal",
    "connect",
    "ensure_ready",
    "new_tab",
    "page_info",
]
