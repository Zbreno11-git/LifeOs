"""Limpeza da caixa de entrada (Sessão Gmail 2): propor → o dono digita o código → arquivar.

O fluxo, e onde cada trava mora:
1. `preparar(remetentes)` — o Gemini (ou `viking gmail --arquivar`) pede; a seleção só lê, e a
   proposta com os IDs exatos ganha um código (`lifeos/confirmacao.py`). Quem mostra o código é
   o Viking, só ao dono (`gmail/tools.py`, `lifeos/ao_dono.py`); ele nunca volta no texto do
   Gemini. Pela nuvem, só se o terminal do Mac é interativo (D60).
2. `confirmar(codigo)` — chamado só pelo laço do chat (`assistant/agent.py`, antes do Gemini) ou
   pela CLI. Refaz a seleção restrita aos IDs aprovados, só com buscas (barato na cota do Gmail),
   e arquiva o que ainda vale.
3. `desfazer(codigo)` — por 7 dias (D27), devolve à caixa exatamente os que foram arquivados.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from lifeos import ao_dono, aprovacoes, confirmacao
from lifeos.gmail import service

ACAO = aprovacoes.GMAIL_ARQUIVAR
DESFAZER_POR = aprovacoes.JANELA_GMAIL  # D27


@dataclass(frozen=True)
class Proposta:
    selecao: service.Selecao
    codigo: str | None  # None: nada a arquivar, e nenhum código foi criado
    expira: datetime | None


@dataclass(frozen=True)
class Execucao:
    codigo: str
    aprovados: int
    fora: int  # aprovados que deixaram de valer (ganharam estrela, saíram da caixa...)
    modificacao: service.Modificacao
    desfazer_ate: datetime


@dataclass(frozen=True)
class Desfeito:
    modificacao: service.Modificacao


def preparar(remetentes) -> Proposta:
    if ao_dono.pela_rede() and not ao_dono.interativo():
        # Pela nuvem, sem terminal do lado do dono, ninguém leria o código (dono, 2026-09-30, D60);
        # recusa antes de ler o Gmail, sem gastar cota. No Mac a limpeza continua como era.
        raise service.SemTerminal(
            "sem um terminal interativo, não há como mostrar o código ao dono"
        )
    selecao = service.selecionar(remetentes)
    if not selecao.ids:
        # Sem o que aprovar, nenhum código novo — e o da proposta anterior também deixa de valer:
        # o dono acabou de ver uma lista (vazia) diferente da que aquele código aprovaria.
        confirmacao.cancelar(ACAO)
        return Proposta(selecao, None, None)
    proposta = confirmacao.propor(
        ACAO,
        {"remetentes": [g.endereco for g in selecao.grupos], "ids": list(selecao.ids)},
    )
    return Proposta(selecao, proposta.codigo, proposta.expira)


def confirmar(codigo: str) -> Execucao:
    registro = confirmacao.consumir(ACAO, codigo)
    aprovados = list(registro.dados.get("ids") or [])
    try:
        atual = service.selecionar(registro.dados.get("remetentes") or [], somente=aprovados)
    except service.ErroGmail as exc:
        confirmacao.registrar(registro.id, {"arquivados": [], "erro": str(exc)})
        raise
    ainda = set(atual.ids)
    ids = [i for i in aprovados if i in ainda]
    fora = len(aprovados) - len(ids)
    modificacao = service.arquivar(ids)
    confirmacao.registrar(
        registro.id,
        {
            "arquivados": list(modificacao.feitos),
            "falharam": list(modificacao.falharam),
            "fora": fora,
        },
    )
    quando = registro.consumida_em or datetime.now(UTC)
    return Execucao(
        codigo=registro.codigo,
        aprovados=len(aprovados),
        fora=fora,
        modificacao=modificacao,
        desfazer_ate=quando + DESFAZER_POR,
    )


def desfazer(codigo: str) -> Desfeito:
    registro = confirmacao.consumida(ACAO, codigo, janela=DESFAZER_POR)
    resultado = dict(registro.resultado)
    if resultado.get("desfeito_em"):
        raise confirmacao.JaUsado("essa limpeza já foi desfeita")
    modificacao = service.desarquivar(resultado.get("arquivados") or [])
    # Quem falhou ao voltar continua em "arquivados": um novo `desfaz` com o mesmo código tenta
    # de novo só esses, até o prazo.
    resultado["arquivados"] = list(modificacao.falharam)
    resultado["devolvidos"] = list(resultado.get("devolvidos") or []) + list(modificacao.feitos)
    if not modificacao.falharam:
        resultado["desfeito_em"] = datetime.now(UTC).isoformat()
    confirmacao.registrar(registro.id, resultado)
    return Desfeito(modificacao)
