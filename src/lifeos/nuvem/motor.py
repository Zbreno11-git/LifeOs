"""O motor do Viking no Cloud Run (Sessão 10, D58).

Fechado por duas paredes, e a segunda não confia na primeira:
1. **o IAM do Cloud Run** (`--no-allow-unauthenticated`, `run.invoker` só para o `viking-cli@`):
   um pedido sem token válido nem chega aqui, e não é cobrado;
2. **este código**, na primeira instrução de toda rota (`_quem`): verifica a assinatura do token
   de identidade (emitido pelo Google, com a audience = a URL deste serviço) e confere o e-mail
   numa lista (`quem_pode`). Se alguém afrouxasse o IAM, um token forjado ou de outra conta
   continuaria recusado. `tests/test_motor.py` lê o código e reprova rota sem `_quem` na frente.

O cliente manda o token em `Authorization: Bearer` (o `X-Serverless-Authorization` chega ao
contêiner **sem** a assinatura, segundo a documentação do Cloud Run lida em 2026-09-29, e aí não
daria para verificar). Nada de conteúdo na URL: o log de pedidos do Cloud Run guarda a URL e não o
corpo (lido em 2026-09-29); e este módulo não loga título nem corpo de nada.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from lifeos import config
from lifeos.reminders import service
from lifeos.reminders.models import Reminder

log = logging.getLogger("viking.motor")
COMMIT = os.getenv("VIKING_COMMIT", "")
EMISSORES = ("https://accounts.google.com", "accounts.google.com")


def quem_pode() -> frozenset[str]:
    """As identidades que falam com o motor. Hoje só o terminal do dono (`viking-cli@`); as mãos
    do Mac (`viking-maos@`) entram na S11."""
    if not config.NUVEM_PROJETO:
        return frozenset()
    return frozenset({f"viking-cli@{config.NUVEM_PROJETO}.iam.gserviceaccount.com"})


_SESSAO: Any = None


def _verificar(token: str) -> dict[str, Any]:
    """Os dados do token, depois de conferir assinatura (os certificados do Google), emissor,
    validade e audience. Levanta `ValueError` se qualquer um falhar."""
    global _SESSAO
    import google.auth.transport.requests
    import requests
    from google.oauth2 import id_token

    if not config.NUVEM_URL:
        raise ValueError("VIKING_NUVEM_URL vazio: sem audience, nenhum token vale")
    if _SESSAO is None:
        _SESSAO = requests.Session()  # reaproveita a conexão com os certificados do Google
    requisicao = google.auth.transport.requests.Request(session=_SESSAO)
    dados = dict(id_token.verify_token(token, requisicao, audience=config.NUVEM_URL))
    if dados.get("iss") not in EMISSORES:
        raise ValueError("emissor que não é o Google")
    return dados


def _quem(request: Request) -> str:
    """A primeira instrução de toda rota: o e-mail de quem pediu, ou 401/403."""
    cabecalho = request.headers.get("authorization", "")
    tipo, _, token = cabecalho.partition(" ")
    if tipo.lower() != "bearer" or not token:
        raise HTTPException(401, "sem token")
    try:
        dados = _verificar(token)
    except ValueError:
        raise HTTPException(401, "token recusado") from None
    email = dados.get("email", "")
    if not dados.get("email_verified") or email not in quem_pode():
        log.warning("identidade recusada")  # sem o e-mail: o log é do projeto, não do dono
        raise HTTPException(403, "identidade sem acesso")
    return email


def _instante(momento: Any) -> str | None:
    return momento.isoformat() if momento is not None else None


def _lembrete(lembrete: Reminder) -> dict[str, Any]:
    """Instantes em UTC, ISO 8601 com fuso: o fuso do dono é do cliente (a borda)."""
    return {
        "id": lembrete.id,
        "type": lembrete.type,
        "title": lembrete.title,
        "body": lembrete.body,
        "tags": lembrete.tags,
        "due_at": _instante(lembrete.due_at),
        "created_at": _instante(lembrete.created_at),
        "enviado_em": _instante(lembrete.enviado_em),
        "envio_estado": lembrete.envio_estado,
    }


async def versao(request: Request) -> JSONResponse:
    _quem(request)
    return JSONResponse({"commit": COMMIT})


async def lembretes(request: Request) -> JSONResponse:
    _quem(request)
    return JSONResponse({"lembretes": [_lembrete(r) for r in service.pendentes()]})


async def fumaca_vencidos(request: Request) -> JSONResponse:
    """Só leitura: exerce a consulta dos vencidos na produção, que pede o índice composto (o
    emulador não pede). Devolve só a contagem."""
    _quem(request)
    from datetime import UTC, datetime, timedelta

    agora = datetime.now(UTC)
    return JSONResponse(
        {"vencidos_24h": len(service.store.vencidos(agora - timedelta(hours=24), agora))}
    )


ROTAS = [
    Route("/versao", versao, methods=["GET"]),
    Route("/lembretes", lembretes, methods=["GET"]),
    Route("/fumaca/vencidos", fumaca_vencidos, methods=["GET"]),
]
app = Starlette(routes=ROTAS)
