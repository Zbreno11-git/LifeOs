"""`viking chat --nuvem`: o terminal do Mac conversando com o chat que roda no motor (Sessão 10b,
D59).

A conversa mora aqui, na memória do terminal: a cada turno ela vai inteira ao motor e volta com o
turno novo (a nuvem não guarda a conversa, decisão do dono em 2026-09-30). Fechar o terminal
encerra a conversa, como no `viking chat` do Mac. A nota do Viking (o aviso do que já foi feito
antes de um erro) também fica aqui até o turno seguinte.

O texto que chega da rede passa por `limpar_controles` antes de ir ao terminal: um evento da agenda
com um código de controle de terminal no título não mexe na tela do dono.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import secrets
import sys
from typing import Any

from lifeos.browser._redacao import limpar_controles
from lifeos.custos import dinheiro
from lifeos.nuvem import cliente

SAIR = ("sair", "exit", "quit")


def _gasto(gasto: Any) -> str:
    if not isinstance(gasto, dict):
        return "Gasto da nuvem: ainda não sei (nenhum turno respondeu)."
    try:
        return (
            f"Gasto do Gemini na nuvem (estimativa): hoje ~{dinheiro(float(gasto['dia']))} de "
            f"{dinheiro(float(gasto['teto_dia']))} · no mês ~{dinheiro(float(gasto['mes']))} de "
            f"{dinheiro(float(gasto['teto_mes']))}"
        )
    except (KeyError, TypeError, ValueError):
        return "Gasto da nuvem: a resposta veio num formato inesperado."


def _texto(valor: Any) -> str:
    return limpar_controles(valor) if isinstance(valor, str) else ""


def iniciar(entrada: Any = input) -> int:
    """O REPL do chat da nuvem. 0 ao sair; 1 se nem o primeiro contato deu certo."""
    try:
        sessao_http = cliente.sessao_de_chat()
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    print("☁️  Viking na nuvem (agenda e lembretes). Navegador, e-mail e finanças: `viking chat`.")
    print("Digite 'sair' para encerrar.\n")

    sessao, numero = secrets.token_hex(4), 0
    historico: list[Any] = []
    nota, gasto = "", None
    while True:
        try:
            linha = entrada("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not linha:
            continue
        if linha.lower() in SAIR:
            print("🤖 Viking: Até logo!")
            print(_gasto(gasto))
            return 0
        if linha.lower() in ("/custos", "custos"):
            print(_gasto(gasto))
            continue
        numero += 1
        print("⏳ Pensando (na nuvem)...")
        pedido = {
            "mensagem": linha,
            "historico": historico,
            "nota": nota,
            "sessao": sessao,
            "numero": numero,
        }
        try:
            resposta = cliente.turno_de_chat(sessao_http, pedido)
        except cliente.ErroDaNuvem as exc:
            print(f"❌ Nuvem: {exc}.\n")
            continue  # a conversa e a nota ficam como estavam: o turno não entrou
        historico_novo = resposta.get("historico")
        if isinstance(historico_novo, list):
            historico = historico_novo
        nota = _texto(resposta.get("nota"))
        gasto = resposta.get("gasto", gasto)
        if resposta.get("resposta") is not None:
            print(f"🤖 Viking: {_texto(resposta.get('resposta'))}\n")
        else:
            print(f"❌ {_texto(resposta.get('erro')) or 'a nuvem não respondeu o turno'}\n")
        if _texto(resposta.get("aviso")):
            print(f"{_texto(resposta.get('aviso'))}\n")
        if _texto(resposta.get("consumo")):
            print(f"   💸 gemini (nuvem): {_texto(resposta.get('consumo'))}", file=sys.stderr)
