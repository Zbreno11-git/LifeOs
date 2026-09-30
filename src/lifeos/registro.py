"""Registro local do que o Viking fez: cada efeito externo, com o pedido, o resultado e como
desfazer (Sessão 5; auditoria do Codex §7).

Existe para o caso "a ação aconteceu, a chamada seguinte ao Gemini falhou, o dono pediu de novo e
ela aconteceu duas vezes": o laço do chat lê as ações do turno que deu erro e diz o que já foi (ou
pode ter sido) feito. Também responde "o que você fez hoje?" e guarda a cópia que o `desfaz` usa.

Cada efeito passa por `with registro.acao(operacao, parametros) as marca:` na camada de serviço
(calendário, lembretes, Gmail, navegador), então vale igual para chat, MCP e CLI. Estados:
`iniciada` (gravado ANTES do efeito) → `feita` | `falhou` | `incerta`. `incerta` é a exceção que
não prova que nada aconteceu (tempo esgotado, 5xx do Google): o efeito pode ter sido aplicado. Uma
linha que ficou `iniciada` (o processo morreu no meio) é lida como incerta também.

Privacidade: `parametros` e `resultado` passam pela redação das páginas; o `desfazer` é a cópia
bruta (o evento inteiro, para recriá-lo) e nunca é mostrado nem vai ao Gemini. Código de
aprovação nunca entra aqui. Fica por `RETENCAO` (decisão do dono: 30 dias) no store de onde a
ação roda (D57): o `viking.db` no Mac (`registro_sqlite.py`, com a purga a cada abertura) ou o
Firestore na nuvem (`registro_firestore.py`, com a TTL; Sessão 10b). A regra fica toda aqui.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import contextvars
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config, registro_interface
from lifeos.browser import _redacao
from lifeos.registro_interface import FALHOU, FEITA, INCERTA, INICIADA, Acao

__all__ = ["FALHOU", "FEITA", "INCERTA", "INICIADA", "ORIGEM", "TURNO", "Acao", "Marca", "acao"]

RETENCAO = timedelta(days=30)
MAX_TEXTO = 300  # por campo de texto guardado (redigido)

# Quem pediu (`chat`, `mcp`, `cli`, `nuvem`) e em que turno do chat. Por `contextvars`, e não por
# argumento: não muda a assinatura de nenhuma tool do Gemini. O google-genai chama as tools no
# mesmo thread do `send_message`; o FastMCP copia o contexto para o thread da tool. Sem origem
# definida, grava `desconhecida` — e um teste proíbe que isso aconteça.
ORIGEM: contextvars.ContextVar[str] = contextvars.ContextVar("origem", default="desconhecida")
TURNO: contextvars.ContextVar[str] = contextvars.ContextVar("turno", default="")

# Onde mora o registro (`VIKING_STORE`, D57/D59): o `viking.db` no Mac, o Firestore quando a ação
# roda na nuvem. O `mypy` confere que os dois módulos satisfazem `registro_interface.Registro`.
_STORE: registro_interface.Registro
if config.STORE == "firestore":
    from lifeos import registro_firestore

    _STORE = registro_firestore
else:
    from lifeos import registro_sqlite

    _STORE = registro_sqlite


@dataclass
class Marca:
    """O que o bloco `with registro.acao(...)` recebe para anotar o que aconteceu."""

    id: int
    resultado: dict[str, Any] = field(default_factory=dict)
    desfazer: dict[str, Any] | None = None

    def feito(self, resultado: dict[str, Any] | None = None, *, desfazer=None) -> None:
        self.resultado = resultado or {}
        self.desfazer = desfazer


def _agora(agora: datetime | None = None) -> datetime:
    return (agora or datetime.now(UTC)).astimezone(UTC)


def _corte(agora: datetime | None = None) -> datetime:
    """O começo da retenção: o store apaga o que é mais velho (o SQLite na hora, o Firestore pela
    TTL, com atraso), e toda leitura corta aqui, para os dois responderem igual."""
    corte = _agora(agora) - RETENCAO
    _STORE.purgar(corte)
    return corte


def limpo(valor: Any) -> Any:
    """Redação das páginas em todo texto (CPF, cartão, chaves, controles), recursiva."""
    if isinstance(valor, str):
        return _redacao.redigir(_redacao.limpar_controles(valor))[:MAX_TEXTO]
    if isinstance(valor, dict):
        return {str(k): limpo(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [limpo(v) for v in valor]
    return valor


def _eh_incerta(exc: BaseException) -> bool:
    return bool(getattr(exc, "incerta", False))


@contextmanager
def acao(
    operacao: str, parametros: dict[str, Any], *, agora: datetime | None = None
) -> Iterator[Marca]:
    """Grava `iniciada` antes do efeito; ao sair, `feita`, `falhou` ou `incerta`. A exceção sobe."""
    momento = _agora(agora)
    _corte(momento)
    marca = Marca(
        _STORE.iniciar(
            turno=TURNO.get(),
            origem=ORIGEM.get(),
            operacao=operacao,
            parametros=json.dumps(limpo(parametros), ensure_ascii=False),
            criada_em=momento,
        )
    )
    try:
        yield marca
    except BaseException as exc:
        estado = INCERTA if _eh_incerta(exc) else FALHOU
        _terminar(marca, estado, erro=type(exc).__name__ + ": " + str(exc))
        raise
    _terminar(marca, FEITA)


def _terminar(marca: Marca, estado: str, *, erro: str = "") -> None:
    _STORE.terminar(
        marca.id,
        estado=estado,
        resultado=json.dumps(limpo(marca.resultado), ensure_ascii=False),
        erro=limpo(erro),
        desfazer=json.dumps(marca.desfazer) if marca.desfazer is not None else None,
        terminada_em=_agora(),
    )


def do_turno(turno: str) -> list[Acao]:
    """O que o turno fez (ou pode ter feito), na ordem."""
    if not turno:
        return []
    return _STORE.do_turno(turno, desde=_corte())


def recentes(*, dias: int = 1, limite: int = 50, agora: datetime | None = None) -> list[Acao]:
    """As mais novas primeiro, desde `dias` atrás."""
    desde = max(_agora(agora) - timedelta(days=max(1, dias)), _corte(agora))
    return _STORE.recentes(desde=desde, limite=limite)


def contaveis(operacao: str, *, desde: datetime) -> list[Acao]:
    """As ações desta operação desde `desde` que aconteceram ou PODEM ter acontecido (tudo menos
    `falhou`): é o que conta num limite (e-mails para o dono por dia, D46)."""
    return _STORE.contaveis(operacao, desde=max(_agora(desde), _corte()))


def obter(acao_id: int) -> Acao | None:
    return _STORE.obter(acao_id, desde=_corte())


def ultima_desfazivel(
    operacoes: tuple[str, ...], *, prefixo_turno: str, janela: timedelta, agora=None
) -> Acao | None:
    """A mais nova destas operações, feita nesta sessão (turnos com `prefixo_turno`), dentro da
    `janela` e ainda não desfeita."""
    if not prefixo_turno or not operacoes:
        return None
    desde = max(_agora(agora) - janela, _corte(agora))
    return _STORE.ultima_desfazivel(operacoes, prefixo_turno=prefixo_turno, desde=desde)


def reivindicar_desfazer(acao_id: int) -> dict[str, Any] | None:
    """Marca como desfeita e devolve a cópia bruta — uma vez só. `None` se já desfeita, sem cópia
    ou não feita."""
    copia = _STORE.reivindicar_desfazer(acao_id, agora=_agora())
    return json.loads(copia) if copia is not None else None


def devolver_desfazer(acao_id: int) -> None:
    """O desfazer falhou: a ação volta a ser desfazível."""
    _STORE.devolver_desfazer(acao_id)
