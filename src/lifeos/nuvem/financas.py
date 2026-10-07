"""O serviço de finanças do Viking no Cloud Run (Sessão 11d, D64): o único que tem a chave da Pluggy.

A chave da Pluggy alcança PIX (medido em 2026-09-26). Por isso, na nuvem, ela mora num serviço
só dela: a mesma imagem do motor com outro comando, a conta `viking-financas@` (a única que lê o
segredo `viking-pluggy`) e nenhum outro segredo. Quem fala com ele é só o `viking-motor@`, pelo
IAM (`run.invoker`) e por este código, na primeira instrução de toda rota (`_quem`, a régua de
`nuvem/identidade.py`).

O que ele faz é pouco, de propósito:
- `POST /responder`: uma das perguntas fechadas de `financas/pergunta.py` → `{"texto": …}`, o
  mesmo texto que o chat do Mac recebe. Nenhum caminho da Pluggy entra no pedido, e nenhum JSON
  da Pluggy sai na resposta (o `paymentData`, com o CPF/CNPJ da contraparte, nem é lido);
- `POST /saude`: o commit, se as credenciais do volume se leem e quantas conexões há. **Sem
  rede**: as provas automáticas do deploy não chamam a Pluggy (o dono, 2026-10-07).

Na nuvem, o cliente da Pluggy só aceita o `POST /auth` (`pluggy._escritas_permitidas`): conectar
um banco é coisa do Mac. O log leva só o tipo de um erro, nunca a pergunta nem a resposta.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from lifeos.nuvem import identidade

log = logging.getLogger("viking.financas")
COMMIT = os.getenv("VIKING_COMMIT", "")
MOTOR = "viking-motor"
MAX_CORPO = 16 * 1024  # uma pergunta tem até 5 campos de 200 caracteres


def quem_pode(rota: str) -> frozenset[str]:
    """Os e-mails que falam com esta rota (`QUEM_FALA`, junto das rotas)."""
    return identidade.contas(QUEM_FALA.get(rota, frozenset()))


async def _quem(request: Request) -> str:
    """A primeira instrução de toda rota: o e-mail de quem pediu, ou 401/403."""
    return await identidade.quem(request, quem_pode)


async def _corpo(request: Request) -> Any:
    """O JSON do pedido, ou `None` se passou do teto ou não é JSON."""
    import json

    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > MAX_CORPO:
        return None
    corpo = await request.body()
    if len(corpo) > MAX_CORPO:
        return None
    try:
        return json.loads(corpo)
    except ValueError:
        return None


def _responder(dados: Any) -> str:
    from lifeos.financas import pergunta

    return pergunta.responder_aqui(pergunta.conferir(dados))


async def responder(request: Request) -> JSONResponse:
    """Uma pergunta fechada → o texto. A pergunta e o texto nunca vão ao log."""
    await _quem(request)
    dados = await _corpo(request)
    if dados is None:
        return JSONResponse({"erro": "o pedido passou do tamanho ou não é JSON"}, 400)
    from lifeos.financas import pergunta

    try:
        pergunta.conferir(dados)
    except pergunta.PerguntaInvalida as exc:  # a mensagem não ecoa conteúdo
        return JSONResponse({"erro": str(exc)}, 400)
    try:
        texto = await run_in_threadpool(_responder, dados)
    except Exception as exc:  # noqa: BLE001 - o log leva só o tipo
        log.error("a resposta de finanças falhou: %s", type(exc).__name__)
        return JSONResponse({"erro": f"o serviço de finanças falhou ({type(exc).__name__})"}, 500)
    return JSONResponse({"texto": texto})


def _saude() -> dict[str, Any]:
    from lifeos.financas import pluggy

    try:
        conexoes = len(pluggy.credenciais().item_ids)
    except (pluggy.ErroPluggy, RuntimeError) as exc:
        log.warning("credenciais da pluggy: %s", type(exc).__name__)
        return {"commit": COMMIT, "credenciais": False, "conexoes": 0}
    return {"commit": COMMIT, "credenciais": True, "conexoes": conexoes}


async def saude(request: Request) -> JSONResponse:
    """O commit, as credenciais lidas e quantas conexões: sem chamar a Pluggy."""
    await _quem(request)
    return JSONResponse(await run_in_threadpool(_saude))


# Quem fala com cada rota: só o motor (D64). O terminal do dono pergunta pelo motor (`/financas`).
QUEM_FALA: dict[str, frozenset[str]] = {
    "/responder": frozenset({MOTOR}),
    "/saude": frozenset({MOTOR}),
}

ROTAS = [
    Route("/responder", responder, methods=["POST"]),
    Route("/saude", saude, methods=["POST"]),
]
app = Starlette(routes=ROTAS)
