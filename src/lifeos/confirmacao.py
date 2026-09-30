"""Confirmação mecânica: o dono aprova uma ação exata digitando um código curto.

Primeiro uso: a limpeza do Gmail (Sessão Gmail 2). A Sessão 5 reaproveita para o freio de
cliques e a exclusão no calendário. O código **nunca passa pelo Gemini**: quem o mostra é o
Viking, direto no terminal, e quem o lê é o laço do chat, antes de mandar a linha ao modelo
(`assistant/agent.py`). Por isso um conteúdo com prompt injection pode, no máximo, fazer o Gemini
*propor* uma ação — aprovar, só quem está no teclado.

Guarda a ação, os dados exatos aprovados, a validade e o resultado onde a ação roda (D57): no
`viking.db` do Mac (`confirmacao_sqlite.py`) ou no Firestore da nuvem (`confirmacao_firestore.py`,
Sessão 10c), atrás de `confirmacao_interface.Confirmacoes`, escolhido por `VIKING_STORE`. As
regras ficam aqui:
- o código vale uma vez e por `VALIDADE` (ou a `validade` da proposta: 1 h para o MCP);
- uma proposta nova da mesma ação substitui as abertas (um código velho não aprova outra lista),
  a menos que `substituir=False` (MCP: cada pedido de outro app espera o seu `viking aprovar`);
- um código não se repete, **em nenhuma ação**, enquanto outro com o mesmo número não venceu
  (em qualquer estado, inclusive substituída) ou foi usado há menos de `JANELA_UNICA`: "confirma
  1234" tem um dono só. Vencida e não usada deixa de reservar (reservar 8 dias de tudo deixaria
  outro app, com muitas propostas, travar a limpeza);
- **`TENTATIVAS` códigos errados cancelam** as propostas abertas daquela ação (decisão do dono,
  2026-09-30, D60): pela rede, o terminal deixou de ser a única barreira contra adivinhar. Vale
  nos dois chats e no `viking aprovar`. Código vencido ou já usado não conta (não é palpite).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config
from lifeos.confirmacao_interface import (
    ABERTA,
    CONSUMIDA,
    SUBSTITUIDA,
    CodigoInvalido,
    Confirmacoes,
    ErroConfirmacao,
    Expirado,
    JaUsado,
    Linha,
    Proposta,
    Registro,
    TentativasEsgotadas,
)

__all__ = [
    "CodigoInvalido",
    "ErroConfirmacao",
    "Expirado",
    "JaUsado",
    "Proposta",
    "Registro",
    "TentativasEsgotadas",
]

VALIDADE = timedelta(minutes=10)
JANELA_UNICA = timedelta(days=8)  # > os 7 dias do desfazer da limpeza (D27)
DIGITOS = 4
TENTATIVAS = 3  # códigos errados até cancelar a proposta aberta (dono, 2026-09-30, D60)
# `[0-9]`, não `\d`: no Python `\d` casa também dígitos de outros alfabetos ("１２３４").
_CODIGO = re.compile(rf"[0-9]{{{DIGITOS}}}")

# Onde moram as confirmações (`VIKING_STORE`, D57/D60): o `viking.db` no Mac, o Firestore na nuvem.
_STORE: Confirmacoes
if config.STORE == "firestore":
    from lifeos import confirmacao_firestore

    _STORE = confirmacao_firestore
else:
    from lifeos import confirmacao_sqlite

    _STORE = confirmacao_sqlite


def _agora(agora: datetime | None) -> datetime:
    return (agora or datetime.now(UTC)).astimezone(UTC)


def normalizar(codigo: str) -> str:
    """O código como o dono digitou, sem espaço; formato errado vira `CodigoInvalido`."""
    limpo = "".join(str(codigo or "").split())
    if not _CODIGO.fullmatch(limpo):
        raise CodigoInvalido(f"o código tem {DIGITOS} dígitos")
    return limpo


def _sortear() -> str:
    return f"{secrets.randbelow(10**DIGITOS):0{DIGITOS}d}"


def propor(
    acao: str,
    dados: dict[str, Any],
    *,
    validade: timedelta = VALIDADE,
    substituir: bool = True,
    agora: datetime | None = None,
) -> Proposta:
    agora = _agora(agora)
    return _STORE.propor(
        acao,
        dados,
        criada_em=agora,
        expira_em=agora + validade,
        substituir=substituir,
        janela_unica=JANELA_UNICA,
        sortear=_sortear,
        maximo=10**DIGITOS // 2,
    )


def aberta(acao: str, *, agora: datetime | None = None) -> bool:
    """Há proposta desta ação esperando código, dentro da validade?"""
    return bool(_STORE.abertas(acao, agora=_agora(agora)))


def vivo(acao: str, codigo: str, *, janela: timedelta, agora: datetime | None = None) -> bool:
    """O código ainda serve para algo: aprovar (proposta aberta e na validade) ou desfazer (ação
    feita dentro da `janela`). É o que decide que uma linha não pode ir ao Gemini."""
    if not _CODIGO.fullmatch(codigo or ""):
        return False
    agora = _agora(agora)
    linha = _STORE.mais_recente(acao, codigo)
    if linha is None:
        return False
    if linha.estado == ABERTA:
        return linha.expira_em >= agora
    if linha.estado == CONSUMIDA and linha.consumida_em:
        return linha.consumida_em + janela >= agora
    return False


def abertas(acao: str, *, agora: datetime | None = None) -> list[Proposta]:
    """As propostas desta ação esperando código, dentro da validade, da mais antiga à mais nova."""
    return _STORE.abertas(acao, agora=_agora(agora))


def criadas_desde(acao: str, desde: datetime) -> int:
    """Quantas propostas desta ação nasceram desde `desde` (limite de pedidos do MCP)."""
    return _STORE.criadas_desde(acao, _agora(desde))


def acao_do_codigo(codigo: str) -> str | None:
    """De que ação é este código (a proposta mais recente com ele, em qualquer estado); `None`
    se nunca existiu. Com o número reservado entre ações, um código vivo tem um dono só."""
    try:
        codigo = normalizar(codigo)
    except CodigoInvalido:
        return None
    linha = _STORE.mais_recente_do_codigo(codigo)
    return linha.acao if linha else None


def cancelar(acao: str) -> None:
    """Invalida as propostas abertas da ação (ex.: uma proposta nova que não tem o que aprovar)."""
    _STORE.cancelar(acao)


def _registro(linha: Linha) -> Registro:
    return Registro(
        id=linha.id,
        acao=linha.acao,
        codigo=linha.codigo,
        dados=linha.dados,
        consumida_em=linha.consumida_em,
        resultado=linha.resultado,
    )


def _errado(acao: str, agora: datetime) -> CodigoInvalido:
    """Um código que não aprova nada: conta nas propostas abertas da ação e diz quanto resta."""
    restam = _STORE.errar(acao, agora=agora, limite=TENTATIVAS)
    if restam == 0:
        return TentativasEsgotadas(
            f"{TENTATIVAS} códigos errados: cancelei a proposta, nada foi feito; peça de novo"
        )
    if restam is not None:
        vez = "tentativa" if restam == 1 else "tentativas"
        return CodigoInvalido(
            f"esse código não corresponde à proposta aberta (mais {restam} {vez} antes de ela "
            "ser cancelada)"
        )
    return CodigoInvalido("esse código não corresponde à proposta aberta")


def consumir(acao: str, codigo: str, *, agora: datetime | None = None) -> Registro:
    """Gasta o código: devolve os dados exatos que foram aprovados, uma vez só."""
    codigo = normalizar(codigo)
    agora = _agora(agora)
    linha = _STORE.mais_recente(acao, codigo)
    if linha is None or linha.estado == SUBSTITUIDA:
        raise _errado(acao, agora)
    if linha.estado == CONSUMIDA:
        raise JaUsado("esse código já foi usado")
    if linha.expira_em < agora:
        raise Expirado("o código venceu; peça a lista de novo")
    gasta = _STORE.consumir(linha.id, agora=agora, reservar_ate=agora + JANELA_UNICA)
    if gasta is None:  # outro processo gastou entre a leitura e agora
        raise JaUsado("esse código já foi usado")
    return _registro(gasta)


def registrar(registro_id: int, resultado: dict[str, Any]) -> None:
    _STORE.registrar(registro_id, resultado)


def consumida(
    acao: str, codigo: str, *, janela: timedelta, agora: datetime | None = None
) -> Registro:
    """Uma ação já aprovada e executada, para desfazer dentro da `janela`."""
    codigo = normalizar(codigo)
    agora = _agora(agora)
    linha = _STORE.mais_recente(acao, codigo)
    if linha is None or linha.estado != CONSUMIDA:
        raise CodigoInvalido("não há ação feita com esse código")
    registro = _registro(linha)
    if registro.consumida_em is None or registro.consumida_em + janela < agora:
        raise Expirado("passou o prazo para desfazer")
    return registro
