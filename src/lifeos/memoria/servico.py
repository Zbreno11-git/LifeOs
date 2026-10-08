"""O que o `viking memoria` do Mac pede ao motor (Sessão 13, D66): listar, esquecer, desfazer,
corrigir e reindexar. Cada função recebe o JSON do pedido e devolve o da resposta; um pedido torto
é `ValueError` (o motor responde 400), com a mensagem sem o texto de fato nenhum.

O id que o dono digita é o curto (os 8 primeiros caracteres que o terminal mostra): `por_prefixo`
o resolve, e um prefixo ambíguo nunca escolhe.

Corrigir é um fato novo que substitui o antigo (`origem="viking memoria"`), pelo mesmo filtro e com
o vetor novo; reindexar refaz o vetor de quem não tem (o restaurado do backup) ou tem outro
modelo. Os dois chamam o Gemini: pelo cliente instrumentado, com o teto do chat e um prazo.

Desde a 13b (D67), as receitas moram ao lado (`receitas.py`): a lista leva as duas, e esquecer e
desfazer acham o id em qualquer uma (um prefixo que casa nas duas é ambíguo e nunca escolhe).
Receita não se corrige: ensinar de novo com o mesmo nome substitui.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from typing import Any

from lifeos import config, custos, prazo
from lifeos.memoria import receitas, regras, store, vetores

PRAZO_S = 200  # abaixo dos 300 s do Cloud Run, como o turno do chat
LOTE = 20  # textos por pedido de embedding: 20 fatos de até 200 caracteres cabem nos 8.192 tokens


FATO, RECEITA = "fato", "receita"


def _qual(dados: Any) -> tuple[str, str]:
    """(o tipo, o id completo) do que o dono digitou: um fato ou uma receita."""
    prefixo = dados.get("id") if isinstance(dados, dict) else None
    if not isinstance(prefixo, str):
        raise ValueError("o pedido precisa do id do fato")  # noqa: TRY004 - o motor: 400
    achados = [
        (tipo, achado)
        for tipo, achado in (
            (FATO, store.por_prefixo(prefixo)),
            (RECEITA, receitas.por_prefixo(prefixo, store.PREFIXO_MINIMO)),
        )
        if achado is not None
    ]
    if len(achados) != 1:
        raise ValueError(
            f"nenhum fato ou receita com esse id, ou mais de um (use ao menos "
            f"{store.PREFIXO_MINIMO} caracteres, como o `viking memoria --todos` mostra)"
        )
    return achados[0]


def _id(dados: Any) -> str:
    """O id de um fato (corrigir): uma receita não se corrige."""
    tipo, achado = _qual(dados)
    if tipo == RECEITA:
        raise ValueError("receita não se corrige: ensine de novo com o mesmo nome no chat")
    return achado


def _cliente() -> Any:
    from lifeos.assistant import na_nuvem

    teto = custos.Teto(mes=config.TETO_GEMINI_MES, dia=config.TETO_GEMINI_DIA, fuso=config.TIMEZONE)
    cliente = na_nuvem._cliente()
    custos.instrumentar(
        cliente,
        sessao=custos.Sessao(),
        antes=lambda _modelo: teto.conferir(),
        depois=lambda c: teto.somar(c.custo),
    )
    return cliente


def listar(_dados: Any = None) -> dict[str, Any]:
    """Todos os fatos e as receitas guardados (os esquecidos até a TTL os apagar, e as propostas
    ainda vivas), do mais novo ao mais velho."""
    return {
        "fatos": [store.copia(f) for f in store.todos()],
        "receitas": [receitas.copia(r) for r in receitas.todas()],
    }


def esquecer(dados: Any) -> dict[str, Any]:
    tipo, achado = _qual(dados)
    if tipo == RECEITA:
        receita = receitas.esquecer(achado)
        if receita is None:
            raise ValueError("a receita não existe mais")
        return {"receita": receitas.copia(receita)}
    fato = store.esquecer(achado)
    if fato is None:
        raise ValueError("o fato não existe mais")
    return {"fato": store.copia(fato)}


def devolver(dados: Any) -> dict[str, Any]:
    """O `viking memoria --desfazer`. Chama-se `devolver` aqui de propósito: `desfazer` é o nome
    que `tests/test_gmail_aprovacao.py` vigia (só o laço do chat e a CLI desfazem uma limpeza)."""
    tipo, achado = _qual(dados)
    if tipo == RECEITA:
        receita = receitas.devolver(achado)
        if receita is None:
            raise ValueError(
                "nada a desfazer: a receita está ativa, é só uma proposta, ou o esquecimento "
                "passou dos 30 dias"
            )
        return {"receita": receitas.copia(receita)}
    fato = store.devolver(achado)
    if fato is None:
        raise ValueError("nada a desfazer: o fato está ativo, ou o esquecimento passou dos 30 dias")
    return {"fato": store.copia(fato)}


def corrigir(dados: Any) -> dict[str, Any]:
    antigo = _id(dados)
    texto = dados.get("texto")
    if not isinstance(texto, str):
        raise ValueError("o pedido precisa do texto novo")  # noqa: TRY004 - o motor: 400
    motivo = regras.recusa(texto)
    if motivo is not None:
        raise ValueError(f"esse texto não pode virar fato: {motivo}")
    with prazo.ate(PRAZO_S):
        (vetor,) = vetores.embutir(_cliente(), [regras.limpo(texto)], pergunta=False)
    fato = store.gravar(texto, origem="viking memoria", vetor=vetor, substitui=antigo)
    return {"fato": store.copia(fato)}


def reindexar(_dados: Any = None) -> dict[str, Any]:
    """Refaz o vetor de cada fato sem vetor ou com outro modelo/dimensão, em lotes."""
    faltam = store.sem_vetor()
    if not faltam:
        return {"refeitos": 0}
    refeitos = 0
    with prazo.ate(PRAZO_S):
        cliente = _cliente()
        for i in range(0, len(faltam), LOTE):
            lote = faltam[i : i + LOTE]
            prazo.conferir(30, "o próximo lote de vetores")
            for fato, vetor in zip(
                lote, vetores.embutir(cliente, [f.texto for f in lote], pergunta=False), strict=True
            ):
                store.trocar_vetor(fato.id, vetor)
                refeitos += 1
    return {"refeitos": refeitos}
