"""A interface do store do registro de ações (Sessão 10b, D59): o que o SQLite do Mac e o Firestore
da nuvem têm de fazer igual. A regra (estados, redação, o que é "incerta", a retenção de 30 dias)
fica em `registro.py`; o store só guarda e busca.

`tests/test_registro.py` é o contrato: roda nas duas implementações (o Firestore no emulador).

Regras que valem para todas:
- **ids inteiros e crescentes** na ordem em que as ações nascem (o `desfaz` e o aviso depois de um
  erro leem por eles). O SQLite usa o `INTEGER PRIMARY KEY`; o Firestore não tem contador;
- **o texto é gravado literal** (parâmetros, resultado e a cópia para desfazer vão como JSON);
- **só lê o que nasceu desde `desde`**: quem chama passa o corte da retenção, e um store que apaga
  com atraso (a TTL do Firestore) continua sem devolver o que venceu;
- **desfazer uma vez só**: `reivindicar_desfazer` só devolve a cópia a quem chegou primeiro.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

FEITA, FALHOU, INCERTA, INICIADA = "feita", "falhou", "incerta", "iniciada"


@dataclass(frozen=True)
class Acao:
    id: int
    turno: str
    origem: str
    operacao: str
    parametros: dict[str, Any]
    estado: str
    resultado: dict[str, Any]
    erro: str
    desfazivel: bool  # há cópia para desfazer e ainda não foi desfeita
    desfeita_em: datetime | None
    criada_em: datetime

    @property
    def pode_ter_acontecido(self) -> bool:
        return self.estado in (INCERTA, INICIADA)


class Registro(Protocol):
    def purgar(self, antes_de: datetime) -> None:
        """Apaga o que nasceu antes de `antes_de` (o Firestore deixa para a TTL)."""
        ...

    def iniciar(
        self, *, turno: str, origem: str, operacao: str, parametros: str, criada_em: datetime
    ) -> int:
        """Grava a ação como `iniciada` e devolve o id."""
        ...

    def terminar(
        self,
        acao_id: int,
        *,
        estado: str,
        resultado: str,
        erro: str,
        desfazer: str | None,
        terminada_em: datetime,
    ) -> None: ...

    def do_turno(self, turno: str, *, desde: datetime) -> list[Acao]:
        """Na ordem em que nasceram."""
        ...

    def recentes(self, *, desde: datetime, limite: int) -> list[Acao]:
        """As mais novas primeiro."""
        ...

    def contaveis(self, operacao: str, *, desde: datetime) -> list[Acao]:
        """Desta operação, tudo menos `falhou`, na ordem em que nasceram."""
        ...

    def obter(self, acao_id: int, *, desde: datetime) -> Acao | None: ...

    def ultima_desfazivel(
        self, operacoes: tuple[str, ...], *, prefixo_turno: str, desde: datetime
    ) -> Acao | None:
        """A mais nova destas operações, `feita`, com cópia, não desfeita, de turno que começa
        exatamente com `prefixo_turno` (texto, não curinga)."""
        ...

    def reivindicar_desfazer(self, acao_id: int, *, agora: datetime) -> str | None:
        """Marca como desfeita e devolve a cópia (JSON) — só a quem chegou primeiro."""
        ...

    def devolver_desfazer(self, acao_id: int) -> None:
        """O desfazer falhou: a ação volta a ser desfazível."""
        ...
