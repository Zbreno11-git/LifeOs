"""O servidor da ponte na rede de casa (D70): só o aparelho do estúdio fala com ele.

HTTPS com o certificado próprio da ponte (fixado no firmware: o aparelho não aceita outro), e todo
pedido com o token do aparelho no `Authorization: Bearer`, comparado em tempo constante, como
**primeira instrução** de cada rota. Nada daqui fica aberto para a internet: o laptop não
encaminha porta, e o túnel que ele tem não deve apontar para cá.

- `GET /saude`: o aparelho confere a ponte (o token e o certificado), sem nada a mais;
- `POST /falar`: o WAV de uma fala (até `MAX_WAV`); a ponte aceita na hora (202, "pensando") e
  trabalha numa thread — o turno e a fala podem levar minutos, e o `HTTPClient` do Arduino espera
  no máximo ~65 s (o prazo dele é `uint16_t` em ms: medido na compilação em 2026-11-21);
- `POST /toque`: os dois toques no botão (a aprovação aberta, se houver), do mesmo jeito;
- `GET /estado`: o aparelho pergunta a cada segundo até sair do "pensando" (o LED do resultado).

O áudio nunca vai a disco nem ao log; o log leva só o estado e o tipo de erro.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import hmac
import logging
import threading
from typing import Any

from starlette.applications import Starlette
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


class Trabalho:
    """Um trabalho da ponte por vez, numa thread; o estado é o que o `GET /estado` responde."""

    PENSANDO = "pensando"

    def __init__(self, ponte: Ponte):
        self.ponte = ponte
        self.estado = "ocioso"
        self.origem = ""
        self._trava = threading.Lock()
        self._thread: threading.Thread | None = None

    def comecar(self, nome: str, *args: Any) -> bool:
        """Começa `ponte.<nome>(*args)` numa thread; `False` se já há um em curso."""
        with self._trava:
            if self.estado == self.PENSANDO:
                return False
            self.estado, self.origem = self.PENSANDO, ""
            self._thread = threading.Thread(target=self._rodar, args=(nome, *args), daemon=True)
            self._thread.start()
            return True

    def _rodar(self, nome: str, *args: Any) -> None:
        try:
            resultado: Resultado = getattr(self.ponte, nome)(*args)
            estado, origem = resultado.estado, resultado.origem
        except Ocupada:
            estado, origem = "ocupado", ""
        except Exception as exc:  # noqa: BLE001 - o log leva só o tipo, nunca o que foi dito
            log.error("a ponte falhou: %s", type(exc).__name__)
            estado, origem = "erro", ""
        log.info("fala: %s %s", estado, origem)
        with self._trava:
            self.estado, self.origem = estado, origem

    def esperar(self, prazo_s: float) -> None:
        """Para os testes: espera a thread terminar."""
        if self._thread is not None:
            self._thread.join(prazo_s)


def _comecar(request: Request, nome: str, *args: Any) -> JSONResponse:
    trabalho: Trabalho = request.app.state.trabalho
    if not trabalho.comecar(nome, *args):
        return JSONResponse({"estado": "ocupado"}, 429)
    return JSONResponse({"estado": Trabalho.PENSANDO}, 202)


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
    return _comecar(request, "falou", wav)


async def toque(request: Request) -> JSONResponse:
    _conferir(request)
    return _comecar(request, "tocou_duas_vezes")


async def estado(request: Request) -> JSONResponse:
    _conferir(request)
    trabalho: Trabalho = request.app.state.trabalho
    return JSONResponse({"estado": trabalho.estado, "origem": trabalho.origem})


async def _recusado(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, _Recusado)
    return exc.resposta


ROTAS = [
    Route("/saude", saude, methods=["GET"]),
    Route("/falar", falar, methods=["POST"]),
    Route("/toque", toque, methods=["POST"]),
    Route("/estado", estado, methods=["GET"]),
]


def app(ponte: Ponte, token: str) -> Starlette:
    if len(token) < 32:
        raise ValueError("o token do aparelho é curto demais")
    aplicacao = Starlette(routes=ROTAS, exception_handlers={_Recusado: _recusado})
    aplicacao.state.trabalho = Trabalho(ponte)
    aplicacao.state.token = token
    return aplicacao
