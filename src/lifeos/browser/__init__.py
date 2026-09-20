"""Automação de navegador do Viking — as "mãos" do assistente.

O trabalho real é feito pelo Jev (jev-ultrafast) rodando como subprocesso no ambiente dele; ver
`jev_runner` para o porquê, e docs/arquitetura/browser-automation-stack.md para a validação do
stack (Browser Harness + CDP + Chrome).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from lifeos.browser.jev_runner import BrowserResult, run_jev
from lifeos.browser.mensagens import formatar

_SAUDE = {
    "reatado": "   ↳ conexão com o Chrome tinha caído; reatei e segui.",
    "reiniciado": "   ↳ daemon do Browser Harness estava travado; reiniciei antes de começar.",
}


def imprimir_progresso(evento: dict) -> None:
    """Escreve o progresso no stderr — nunca volta pro modelo, então não custa token."""
    if evento.get("type") == "health":
        aviso = _SAUDE.get(evento.get("state", ""))
        if aviso:
            print(aviso, file=sys.stderr)
        return
    acao = evento.get("last_action") or evento.get("status") or ""
    segundos = (evento.get("elapsed_ms") or 0) / 1000
    print(f"   ↳ {evento.get('n', 0)} ações · {segundos:.1f}s · {acao}", file=sys.stderr)


def executar_no_navegador(
    url: str,
    objetivo: str | Sequence[str],
    *,
    timeout_s: float | None = None,
    manter_aberta: bool = True,
    silencioso: bool = False,
) -> str:
    """Persegue um objetivo em linguagem natural num navegador real e resume o que aconteceu."""
    objetivos = [objetivo] if isinstance(objetivo, str) else list(objetivo)
    resultado = run_jev(
        url,
        objetivos,
        timeout_s=timeout_s,
        fechar=not manter_aberta,
        on_progress=None if silencioso else imprimir_progresso,
    )
    return formatar(resultado)


__all__ = ["BrowserResult", "executar_no_navegador", "formatar", "imprimir_progresso", "run_jev"]
