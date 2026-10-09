"""O que o `viking documentos` do Mac pede ao motor (Sessão 14, D68): listar, aprender, esquecer e
desfazer. Cada função recebe o JSON do pedido e devolve o da resposta; um pedido torto é
`ValueError` (o motor responde 400), com a mensagem sem o texto do documento.

Aprender chama o Gemini (o embedding de cada trecho): pelo cliente instrumentado da memória, com o
teto do chat e um prazo, e cada lote confere o prazo antes de pedir. O teto conta pelos bytes do
texto (um limite de cima: 1 MB conta até ~US$ 0,24 no teto do dia, de US$ 1).

O id que o dono digita é o curto (8 caracteres): `store.por_prefixo` o resolve, e um prefixo
ambíguo nunca escolhe. Desfazer se chama `devolver` aqui (a régua da D26).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from typing import Any

from lifeos import prazo
from lifeos.documentos import store
from lifeos.memoria import servico as memoria_servico
from lifeos.memoria import vetores

PRAZO_S = memoria_servico.PRAZO_S


def _id(dados: Any) -> str:
    prefixo = dados.get("id") if isinstance(dados, dict) else None
    if not isinstance(prefixo, str):
        raise ValueError("o pedido precisa do id do documento")  # noqa: TRY004 - o motor: 400
    achado = store.por_prefixo(prefixo)
    if achado is None:
        raise ValueError(
            f"nenhum documento com esse id, ou mais de um (use ao menos {store.PREFIXO_MINIMO} "
            "caracteres, como o `viking documentos --todos` mostra)"
        )
    return achado


def listar(_dados: Any = None) -> dict[str, Any]:
    """Todos os documentos ainda no banco (os esquecidos até a TTL os apagar), sem os trechos."""
    return {"documentos": [store.copia(d) for d in store.todos()]}


def aprender(dados: Any) -> dict[str, Any]:
    if not isinstance(dados, dict) or set(dados) != {"nome", "tema", "texto"}:
        raise ValueError("o pedido tem de ter nome, tema e texto")
    with prazo.ate(PRAZO_S):
        cliente = memoria_servico._cliente()
        novo, antigo = store.aprender(
            dados["nome"],
            dados["tema"],
            dados["texto"],
            embutir=lambda textos: vetores.embutir_prontos(cliente, textos),
            antes_do_lote=lambda: prazo.conferir(30, "o próximo lote de vetores"),
        )
    return {"documento": store.copia(novo), "substituido": store.copia(antigo) if antigo else None}


def esquecer(dados: Any) -> dict[str, Any]:
    documento = store.esquecer(_id(dados))
    if documento is None:
        raise ValueError("o documento não existe mais")
    return {"documento": store.copia(documento)}


def devolver(dados: Any) -> dict[str, Any]:
    """O `viking documentos --desfazer`. Chama-se `devolver` de propósito: `desfazer` é o nome que
    `tests/test_gmail_aprovacao.py` vigia."""
    documento = store.devolver(_id(dados))
    if documento is None:
        raise ValueError(
            "nada a desfazer: o documento está ativo, não terminou de aprender, ou o esquecimento "
            "passou dos 30 dias"
        )
    return {"documento": store.copia(documento)}


def reindexar_trechos(cliente: Any) -> int:
    """Refaz o vetor de cada trecho sem vetor ou com outro modelo (o restaurado do backup), em
    lotes, com o título do trecho (o `viking memoria --reindexar` chama, dentro do prazo dele)."""
    faltam = store.sem_vetor()
    refeitos = 0
    for i in range(0, len(faltam), store.LOTE_EMBUTIR):
        lote = faltam[i : i + store.LOTE_EMBUTIR]
        prazo.conferir(30, "o próximo lote de vetores")
        textos = [store.texto_do_vetor(t.arquivo, t.secao, t.texto) for t in lote]
        for trecho, vetor in zip(lote, vetores.embutir_prontos(cliente, textos), strict=True):
            store.trocar_vetor(trecho.id, vetor)
            refeitos += 1
    return refeitos
