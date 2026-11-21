"""O servidor da ponte na rede de casa (D70): só o aparelho do estúdio fala com ele.

HTTPS com o certificado próprio da ponte (fixado no firmware: o aparelho não aceita outro), e todo
pedido com o token do aparelho no `Authorization: Bearer`, comparado em tempo constante, como
**primeira instrução** de cada rota. Nada daqui fica aberto para a internet: o laptop não
encaminha porta, e o túnel que ele tem não deve apontar para cá.

- `GET /saude`: o aparelho confere a ponte (o token e o certificado), sem nada a mais;
- `POST /falar`: o WAV de uma fala (até `MAX_WAV`), e a resposta é o estado para o LED depois de a
  fala terminar no alto-falante;
- `POST /toque`: os dois toques no botão (a aprovação aberta, se houver).

O áudio nunca vai a disco nem ao log; o log leva só o estado e o tipo de erro.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from lifeos.casa.ponte import Ocupada, Ponte, Resultado

log = logging.getLogger("viking.casa")
MAX_WAV = 1024 * 1024  # o mesmo teto do motor (`assistant/voz.MAX_WAV`)


class _Recusado(Exception):
    def __init__(self, resposta: JSONResponse):
        self.resposta = resposta


def _conferir(request: Request) -> None:
    """A primeira instrução de toda rota: o token do aparelho, ou 401."""
    esperado: str = request.app.state.token
    cabecalho = request.headers.get("authorization", "")
    dado = cabecalho.removeprefix("Bearer ").strip() if cabecalho.startswith("Bearer ") else ""
    if not dado or not esperado or not hmac.compare_digest(dado.encode(), esperado.encode()):
        raise _Recusado(JSONResponse({"estado": "erro", "erro": "sem acesso"}, 401))


def _estado(resultado: Resultado) -> JSONResponse:
    log.info("fala: %s %s", resultado.estado, resultado.origem)
    return JSONResponse({"estado": resultado.estado, "origem": resultado.origem})


async def _rodar(request: Request, trabalho: Any, *args: Any) -> JSONResponse:
    ponte: Ponte = request.app.state.ponte
    try:
        resultado = await run_in_threadpool(getattr(ponte, trabalho), *args)
    except Ocupada:
        return JSONResponse({"estado": "ocupado"}, 429)
    except Exception as exc:  # noqa: BLE001 - o log leva só o tipo, nunca o que foi dito
        log.error("a ponte falhou: %s", type(exc).__name__)
        return JSONResponse({"estado": "erro", "erro": type(exc).__name__}, 500)
    return _estado(resultado)


async def saude(request: Request) -> JSONResponse:
    _conferir(request)
    return JSONResponse({"ok": True})


async def falar(request: Request) -> JSONResponse:
    _conferir(request)
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > MAX_WAV:
        return JSONResponse({"estado": "erro", "erro": "áudio grande demais"}, 413)
    wav = await request.body()
    if len(wav) > MAX_WAV:
        return JSONResponse({"estado": "erro", "erro": "áudio grande demais"}, 413)
    if not wav:
        return JSONResponse({"estado": "vazio"}, 400)
    return await _rodar(request, "falou", wav)


async def toque(request: Request) -> JSONResponse:
    _conferir(request)
    return await _rodar(request, "tocou_duas_vezes")


async def _recusado(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, _Recusado)
    return exc.resposta


ROTAS = [
    Route("/saude", saude, methods=["GET"]),
    Route("/falar", falar, methods=["POST"]),
    Route("/toque", toque, methods=["POST"]),
]


def app(ponte: Ponte, token: str) -> Starlette:
    if len(token) < 32:
        raise ValueError("o token do aparelho é curto demais")
    aplicacao = Starlette(routes=ROTAS, exception_handlers={_Recusado: _recusado})
    aplicacao.state.ponte = ponte
    aplicacao.state.token = token
    return aplicacao
