"""O embedding da memória (Sessão 13, D66) e a conta dele no teto.

O cliente é o de verdade do google-genai, com só a chamada de rede (`_embed_content`) trocada por um
roteiro que anota o que recebeu: um falso que ignorasse a forma do pedido deixaria verde a lista de
strings que o modelo soma num vetor só (medido no C1; erros, classes 3 e 4).
"""

import pytest
from google import genai
from google.genai import types

from lifeos import custos
from lifeos.memoria import vetores


class _Roteiro:
    def __init__(self, quantos=None, dimensao=vetores.DIMENSAO):
        self.quantos, self.dimensao = quantos, dimensao
        self.pedidos: list[dict] = []

    def __call__(self, **kwargs):
        self.pedidos.append(kwargs)
        n = len(kwargs["contents"]) if self.quantos is None else self.quantos
        return types.EmbedContentResponse(
            embeddings=[types.ContentEmbedding(values=[0.1] * self.dimensao) for _ in range(n)]
        )


def _cliente(roteiro):
    cliente = genai.Client(api_key="teste")
    cliente.models._embed_content = roteiro
    return cliente


def test_cada_texto_vai_num_content_com_o_prefixo_e_a_dimensao():
    roteiro = _Roteiro()
    saida = vetores.embutir(_cliente(roteiro), ["treino às 7h", "café"], pergunta=False)
    assert len(saida) == 2 and all(len(v) == vetores.DIMENSAO for v in saida)
    (pedido,) = roteiro.pedidos
    assert pedido["model"] == vetores.MODELO
    conteudos = pedido["contents"]
    assert len(conteudos) == 2 and all(isinstance(c, types.Content) for c in conteudos)
    assert [c.parts[0].text for c in conteudos] == [
        "title: none | text: treino às 7h",
        "title: none | text: café",
    ]
    assert pedido["config"].output_dimensionality == vetores.DIMENSAO


def test_a_pergunta_leva_o_prefixo_de_busca():
    roteiro = _Roteiro()
    vetores.embutir(_cliente(roteiro), ["que horas eu malho?"], pergunta=True)
    assert roteiro.pedidos[0]["contents"][0].parts[0].text == (
        "task: search result | query: que horas eu malho?"
    )


def test_um_vetor_agregado_erra_alto():
    """O que o C1 viu: 24 textos, 1 vetor. Nada se grava com a quantidade errada."""
    with pytest.raises(vetores.VetorInvalido, match="pedi 3 vetores e voltaram 1"):
        vetores.embutir(_cliente(_Roteiro(quantos=1)), ["a", "b", "c"], pergunta=False)


def test_dimensao_errada_erra_alto():
    with pytest.raises(vetores.VetorInvalido, match="768"):
        vetores.embutir(_cliente(_Roteiro(dimensao=3072)), ["a"], pergunta=False)


def test_lista_vazia_nao_chama():
    roteiro = _Roteiro()
    assert vetores.embutir(_cliente(roteiro), [], pergunta=True) == []
    assert roteiro.pedidos == []


def test_o_embedding_entra_na_conta_pelos_bytes_e_o_teto_confere_antes():
    roteiro = _Roteiro()
    cliente = _cliente(roteiro)
    sessao, vistos, depois = custos.Sessao(), [], []
    custos.instrumentar(cliente, sessao=sessao, antes=vistos.append, depois=depois.append)
    vetores.embutir(cliente, ["café"], pergunta=False)
    assert vistos == [vetores.MODELO]
    bytes_ = len("title: none | text: café".encode())
    (consumo,) = depois
    assert consumo.modelo == vetores.MODELO
    assert consumo.entrada == bytes_ and consumo.saida == 0
    assert consumo.custo == pytest.approx(bytes_ * 0.20 / 1_000_000)
    assert sessao.turno().custo == consumo.custo
    assert sessao.resumo_do_turno().startswith(f"{vetores.MODELO}: ≤{bytes_} tokens (bytes")


def test_o_teto_estourado_para_o_embedding_antes_da_rede():
    roteiro = _Roteiro()
    cliente = _cliente(roteiro)

    def recusa(_modelo):
        raise RuntimeError("teto")

    custos.instrumentar(cliente, antes=recusa)
    with pytest.raises(RuntimeError, match="teto"):
        vetores.embutir(cliente, ["café"], pergunta=False)
    assert roteiro.pedidos == []


def test_uma_forma_que_nao_sei_contar_erra_alto():
    with pytest.raises(TypeError, match="forma"):
        custos.do_embedding(
            [types.Part(inline_data=types.Blob(data=b"x", mime_type="image/png"))], vetores.MODELO
        )


def test_o_modelo_do_embedding_esta_na_tabela():
    assert custos.tarifa(vetores.MODELO) == (0.20, 0.0)
    assert vetores.MODELO in custos.POR_BYTES
