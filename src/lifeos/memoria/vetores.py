"""A busca por significado da memória (Sessão 13, D66): o `gemini-embedding-2`.

Lido em 2026-10-08 (https://ai.google.dev/gemini-api/docs/embeddings): sem `task_type` neste
modelo, a tarefa vai no próprio texto (`PREFIXO_PERGUNTA` na pergunta, `PREFIXO_FATO` no fato); as
dimensões menores já vêm normalizadas (medido: norma 1,0000 a 768). E **uma lista de strings vira
um vetor só**, a soma de todas ("Adding multiple inputs directly to the `contents` parameter
produces one aggregated embedding"; erro meu no C1, erros classe 3): cada texto vai num
`types.Content` próprio, e a quantidade que volta é conferida.

O vetor é descartável (D48): o texto é a fonte, e o `viking memoria --reindexar` refaz todo vetor de
outro modelo ou dimensão. Trocar de modelo é reembutir tudo: os espaços não se misturam.

A chamada passa pelo cliente instrumentado do turno (`custos.instrumentar`): o teto e o prazo valem,
e o custo entra no 💸 pelos bytes do texto (a resposta não traz contagem de tokens).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from typing import Any

MODELO = "gemini-embedding-2"
DIMENSAO = 768  # recomendada pela página; o Firestore aceita até 2048
PREFIXO_FATO = "title: none | text: "
PREFIXO_PERGUNTA = "task: search result | query: "


class VetorInvalido(RuntimeError):
    """O embedding voltou numa forma inesperada (quantidade ou dimensão): nada se grava."""


def embutir(cliente: Any, textos: list[str], *, pergunta: bool) -> list[list[float]]:
    """Um vetor por texto, na ordem. `pergunta=True` para o que se busca, `False` para o fato."""
    prefixo = PREFIXO_PERGUNTA if pergunta else PREFIXO_FATO
    return embutir_prontos(cliente, [prefixo + t for t in textos])


def embutir_prontos(cliente: Any, textos: list[str]) -> list[list[float]]:
    """Um vetor por texto que já vem com a tarefa escrita (o trecho de um documento leva o título
    dele, "title: arquivo — seção | text: …", Sessão 14). O resto é o `embutir`."""
    if not textos:
        return []
    from google.genai import types

    resposta = cliente.models.embed_content(
        model=MODELO,
        contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in textos],
        config=types.EmbedContentConfig(output_dimensionality=DIMENSAO),
    )
    vetores = [list(e.values or []) for e in (resposta.embeddings or [])]
    if len(vetores) != len(textos):
        raise VetorInvalido(f"pedi {len(textos)} vetores e voltaram {len(vetores)}")
    if any(len(v) != DIMENSAO for v in vetores):
        raise VetorInvalido(f"um vetor voltou fora das {DIMENSAO} dimensões")
    return vetores
