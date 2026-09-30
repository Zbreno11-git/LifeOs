"""O que só o dono vê (Sessão 10c, D60): o código de aprovação, a lista de uma limpeza, o e-mail
inteiro antes de sair. A porta é uma só, e o modelo nunca a atravessa: o que passa por aqui não
volta no retorno de nenhuma tool.

- **No Mac** (`viking chat`, a CLI): vai direto ao terminal, como sempre.
- **Na nuvem** (o motor): o turno liga um coletor (`coletar`), e o texto volta ao terminal do Mac
  no campo `ao_dono` da resposta, fora do texto do modelo e do histórico. No motor o stdout é o
  log do Cloud Run: sem o coletor, `mostrar` **erra alto** em vez de imprimir um código no log.

O terminal que conta é o de quem lê (`interativo`): no Mac, o do próprio processo; na nuvem, o
que o terminal do Mac declarou no pedido. Sem terminal interativo, nenhuma proposta com código
nasce (quem decide é quem propõe: `gmail/envio`, `gmail/limpeza`, `browser/liberacao`).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from lifeos import config

_COLETOR: ContextVar[list[str] | None] = ContextVar("viking_ao_dono", default=None)
_INTERATIVO: ContextVar[bool | None] = ContextVar("viking_interativo", default=None)


class SemCanal(RuntimeError):
    """Na nuvem, sem o coletor do turno: não há por onde mostrar sem cair no log."""


def mostrar(texto: str) -> None:
    coletor = _COLETOR.get()
    if coletor is not None:
        coletor.append(texto)
        return
    if config.STORE == "firestore":
        raise SemCanal("na nuvem, o que só o dono vê sai pelo campo `ao_dono`, nunca pelo log")
    print(texto, file=sys.stdout, flush=True)


@contextmanager
def coletar(*, interativo: bool) -> Iterator[list[str]]:
    """Durante o bloco, o que só o dono vê vai para a lista devolvida, e `interativo()` é o que o
    terminal do Mac declarou."""
    lista: list[str] = []
    coletor, declarado = _COLETOR.set(lista), _INTERATIVO.set(interativo)
    try:
        yield lista
    finally:
        _INTERATIVO.reset(declarado)
        _COLETOR.reset(coletor)


def pela_rede() -> bool:
    """O turno roda no motor, para um terminal do outro lado da rede."""
    return _COLETOR.get() is not None


def interativo() -> bool:
    """Há uma pessoa diante de um terminal para ler um código?"""
    declarado = _INTERATIVO.get()
    if declarado is not None:
        return declarado
    if config.STORE == "firestore":  # na nuvem, sem o pedido dizer: não há quem leia
        return False
    return sys.stdin.isatty() and sys.stdout.isatty()
