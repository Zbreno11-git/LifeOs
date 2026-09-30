"""A interface do store das confirmações (Sessão 10c, D60): o que o SQLite do Mac e o Firestore da
nuvem têm de fazer igual. As regras (a validade, o que é "vivo", o limite de tentativas, as
mensagens) ficam em `confirmacao.py`; o store guarda, busca e faz atômico o que precisa ser.

`tests/test_confirmacao.py` é o contrato: roda nas duas implementações (o Firestore no emulador).

O que o store garante, nos dois:
- **ids inteiros e crescentes** na ordem em que as propostas nascem ("a mais recente" é a de maior
  id);
- **um código tem um dono só**: `propor` não sorteia um número reservado. Reservado = de uma
  proposta que ainda não venceu (em qualquer estado) ou usada há menos de `janela_unica`;
- **gastar uma vez só**: `consumir` só devolve a linha a quem a tirou de `aberta`;
- **tentativa errada conta nas propostas abertas da ação**, e a que chega ao limite deixa de estar
  aberta (`substituida`).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

ABERTA, CONSUMIDA, SUBSTITUIDA = "aberta", "consumida", "substituida"


class ErroConfirmacao(Exception):
    codigo = "confirmacao_invalida"


class CodigoInvalido(ErroConfirmacao):
    """Não há proposta com esse código para essa ação (nunca houve, ou foi substituída)."""


class TentativasEsgotadas(CodigoInvalido):
    """O código errado que chegou ao limite: a proposta aberta foi cancelada."""

    codigo = "confirmacao_cancelada"


class Expirado(ErroConfirmacao):
    codigo = "confirmacao_expirada"


class JaUsado(ErroConfirmacao):
    codigo = "confirmacao_ja_usada"


@dataclass(frozen=True)
class Proposta:
    id: int
    acao: str
    codigo: str
    dados: dict[str, Any]
    expira: datetime


@dataclass(frozen=True)
class Registro:
    id: int
    acao: str
    codigo: str
    dados: dict[str, Any]
    consumida_em: datetime | None
    resultado: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Linha:
    """Uma proposta como o store a guarda, em qualquer estado."""

    id: int
    acao: str
    codigo: str
    dados: dict[str, Any]
    estado: str
    criada_em: datetime
    expira_em: datetime
    consumida_em: datetime | None
    resultado: dict[str, Any]
    erros: int


class Confirmacoes(Protocol):
    def propor(
        self,
        acao: str,
        dados: dict[str, Any],
        *,
        criada_em: datetime,
        expira_em: datetime,
        substituir: bool,
        janela_unica: timedelta,
        sortear: Callable[[], str],
        maximo: int,
    ) -> Proposta:
        """Substitui as abertas da ação (se pedido), reserva um código livre e grava a proposta.
        Com `maximo` códigos ou mais reservados, `ErroConfirmacao`."""
        ...

    def abertas(self, acao: str, *, agora: datetime) -> list[Proposta]:
        """As abertas desta ação dentro da validade, da mais antiga à mais nova."""
        ...

    def mais_recente(self, acao: str, codigo: str) -> Linha | None: ...

    def mais_recente_do_codigo(self, codigo: str) -> Linha | None: ...

    def criadas_desde(self, acao: str, desde: datetime) -> int: ...

    def cancelar(self, acao: str) -> None:
        """As abertas da ação viram `substituida`."""
        ...

    def consumir(
        self, proposta_id: int, *, agora: datetime, reservar_ate: datetime
    ) -> Linha | None:
        """Tira a proposta de `aberta` para `consumida` e reserva o código até `reservar_ate`;
        `None` se outra execução chegou antes (ou ela não está aberta)."""
        ...

    def registrar(self, proposta_id: int, resultado: dict[str, Any]) -> None: ...

    def errar(self, acao: str, *, agora: datetime, limite: int) -> int | None:
        """Uma tentativa errada nas abertas da ação (na validade): cada uma soma 1, e a que chega a
        `limite` vira `substituida`. Devolve quantas tentativas ainda restam (0 = cancelou) ou
        `None` se não havia proposta aberta."""
        ...
