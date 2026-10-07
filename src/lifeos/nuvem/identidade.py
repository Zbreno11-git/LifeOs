"""Quem chama um serviço do Viking na nuvem: a segunda parede, a do código (Sessões 10, 11, 11d).

Os dois serviços do Cloud Run (o motor, `nuvem/motor.py`, e o de finanças, `nuvem/financas.py`,
D64) chamam `quem(request, quem_pode)` na primeira instrução de toda rota: verifica a assinatura
do token de identidade (emitido pelo Google, com a audience = a URL **deste** serviço,
`config.NUVEM_URL`) e confere o e-mail na lista **daquela rota**, que cada serviço declara no seu
`QUEM_FALA`. Um lugar só para os dois: a régua que um teste confere vale igual para o serviço que
guarda a chave da Pluggy.

O cliente manda o token em `Authorization: Bearer` (o `X-Serverless-Authorization` chega ao
contêiner **sem** a assinatura, segundo a documentação do Cloud Run lida em 2026-09-29). O log
nunca leva o e-mail: é do projeto, não do dono.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lifeos import config

log = logging.getLogger("viking.identidade")
EMISSORES = ("https://accounts.google.com", "accounts.google.com")


def contas(nomes: frozenset[str]) -> frozenset[str]:
    """Os e-mails das contas de serviço do projeto do Viking; sem projeto, ninguém."""
    if not config.NUVEM_PROJETO:
        return frozenset()
    return frozenset(f"{c}@{config.NUVEM_PROJETO}.iam.gserviceaccount.com" for c in nomes)


_SESSAO: Any = None


def verificar(token: str) -> dict[str, Any]:
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


async def quem(request: Request, quem_pode: Callable[[str], frozenset[str]]) -> str:
    """O e-mail de quem pediu, ou 401/403. A verificação busca os certificados do Google (rede):
    roda numa thread."""
    cabecalho = request.headers.get("authorization", "")
    tipo, _, token = cabecalho.partition(" ")
    if tipo.lower() != "bearer" or not token:
        raise HTTPException(401, "sem token")
    try:
        dados = await run_in_threadpool(verificar, token)
    except ValueError:
        raise HTTPException(401, "token recusado") from None
    email = dados.get("email", "")
    if not dados.get("email_verified") or email not in quem_pode(request.url.path):
        log.warning("identidade recusada")  # sem o e-mail: o log é do projeto, não do dono
        raise HTTPException(403, "identidade sem acesso")
    return email
