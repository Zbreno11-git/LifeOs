"""As perguntas de finanças que atravessam a rede (Sessão 11d, D64): um formato fechado.

Na nuvem, quem tem a chave da Pluggy é só o serviço de finanças (`nuvem/financas.py`). O motor,
que roda o Gemini e lê e-mails de terceiros, pergunta a ele por aqui e recebe o **texto pronto**
que o chat do Mac já recebe (`financas/tools.responder_*`): nunca um caminho da Pluggy, nunca o
JSON cru. Cinco perguntas, cada uma com os seus campos (texto curto); o resto é recusado, nas duas
pontas, sem ecoar o que veio.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from typing import Any

from lifeos.financas import pluggy

MAX_CAMPO = 200  # caracteres: datas, um valor, um pedaço de descrição
CAMPOS: dict[str, tuple[str, ...]] = {
    "saldo": (),
    "gastos": ("desde", "ate"),
    "buscar": ("texto", "desde", "ate", "valor"),
    "fatura": (),
    "conexoes": (),
}


class PerguntaInvalida(pluggy.EntradaInvalida, ValueError):
    """O pedido não está no formato fechado: o serviço responde 400, e a tool, a frase "Não
    entendi o pedido" (`tools.mensagem_de_erro`), como qualquer entrada inválida."""


def conferir(dados: Any) -> dict[str, str]:
    """A pergunta com todos os campos dela (vazio quando não veio), ou `PerguntaInvalida`."""
    if not isinstance(dados, dict):
        raise PerguntaInvalida("a pergunta de finanças tem de ser um objeto")
    nome = dados.get("pergunta")
    if not isinstance(nome, str) or nome not in CAMPOS:
        raise PerguntaInvalida("pergunta de finanças desconhecida")
    if set(dados) - {"pergunta", *CAMPOS[nome]}:
        raise PerguntaInvalida("a pergunta de finanças tem campo a mais")
    saida = {"pergunta": nome}
    for campo in CAMPOS[nome]:
        valor = dados.get(campo, "")
        if not isinstance(valor, str) or len(valor) > MAX_CAMPO:
            raise PerguntaInvalida(f"o campo {campo} tem de ser um texto de até {MAX_CAMPO}")
        saida[campo] = valor
    return saida


def responder_aqui(dados: dict[str, str], *, levantar: bool = False) -> str:
    """A resposta com a Pluggy deste processo (o serviço de finanças, ou o Mac)."""
    from lifeos.financas import tools

    pedido = conferir(dados)
    nome = pedido["pergunta"]
    if nome == "saldo":
        return tools.responder_saldo(levantar=levantar)
    if nome == "gastos":
        return tools.responder_gastos(pedido["desde"], pedido["ate"], levantar=levantar)
    if nome == "buscar":
        return tools.responder_buscar(
            pedido["texto"], pedido["desde"], pedido["ate"], pedido["valor"], levantar=levantar
        )
    if nome == "fatura":
        return tools.responder_fatura(levantar=levantar)
    return tools.responder_conexoes(levantar=levantar)
