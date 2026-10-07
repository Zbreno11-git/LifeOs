"""`viking chat --nuvem`: o terminal do Mac conversando com o chat que roda no motor (Sessão 10b,
D59).

A conversa mora aqui, na memória do terminal: a cada turno ela vai inteira ao motor e volta com o
turno novo (a nuvem não guarda a conversa, decisão do dono em 2026-09-30). Fechar o terminal
encerra a conversa, como no `viking chat` do Mac. A nota do Viking (o aviso do que já foi feito
antes de um erro) também fica aqui até o turno seguinte.

O texto que chega da rede passa por `limpar_controles` antes de ir ao terminal: um evento da agenda
com um código de controle de terminal no título não mexe na tela do dono.

Desde a 10c (D60), o que só o dono vê (o código de aprovação, a lista de uma limpeza, o e-mail
antes de sair) chega no campo `ao_dono`, separado da resposta do modelo, e só é mostrado se este
terminal é interativo. O pedido diz ao motor se é (`interativo`): sem terminal, o motor nem cria a
proposta.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import secrets
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import ao_dono
from lifeos.browser._redacao import limpar_controles
from lifeos.custos import dinheiro
from lifeos.nuvem import cliente

SAIR = ("sair", "exit", "quit")
SEM_TERMINAL = (
    "(o Viking mandou uma mensagem só para você, com um código ou uma aprovação: ela só aparece "
    "num terminal interativo)"
)


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


def abertura(capacidades: dict[str, Any]) -> str:
    """A primeira linha: o que a nuvem tem agora e o que continua só no `viking chat` do Mac."""
    tem = ["agenda", "lembretes"]
    so_no_mac: list[str] = []
    (tem if capacidades.get("gmail") is True else so_no_mac).append("Gmail")
    if capacidades.get("maos") is True:  # Sessão 11: o navegador do Mac, pelas mãos
        tem.append("o navegador do Mac, com o `viking maos` ligado lá")
    else:
        so_no_mac.insert(0, "navegador")
    so_no_mac.append("finanças")
    lista = ", ".join(tem[:-1]) + f" e {tem[-1]}"
    fora = ", ".join(so_no_mac[:-1]) + f" e {so_no_mac[-1]}"
    return f"☁️  Viking na nuvem ({lista}). {fora[0].upper()}{fora[1:]}: `viking chat`."


# Sem backup há mais que isto, a abertura avisa (resposta do dono, 2026-10-06; D63).
BACKUP_VELHO = timedelta(hours=48)


def aviso_do_backup(capacidades: dict[str, Any], agora: datetime | None = None) -> str | None:
    """O aviso da abertura quando o backup no Drive está ligado e o último passou de 48 h (ou não
    houve nenhum). Sem o backup ligado, nada: a abertura não promete o que a nuvem não tem."""
    if capacidades.get("backup") is not True:
        return None
    agora = agora or datetime.now(UTC)
    texto = capacidades.get("backup_em")
    try:
        ultimo = datetime.fromisoformat(texto) if isinstance(texto, str) else None
    except ValueError:
        ultimo = None
    if ultimo is None:
        return "⚠️  Backup no Drive: nenhum feito ainda (`viking backup` mostra o estado)."
    if agora - ultimo > BACKUP_VELHO:
        dias = (agora - ultimo).total_seconds() / 86400
        return (
            f"⚠️  Backup no Drive: o último é de há {dias:.1f} dias; a rodada diária pode estar "
            "falhando (`viking backup`)."
        )
    return None


def _texto(valor: Any) -> str:
    return limpar_controles(valor) if isinstance(valor, str) else ""


def iniciar(entrada: Any = input) -> int:
    """O REPL do chat da nuvem. 0 ao sair; 1 se nem o primeiro contato deu certo."""
    try:
        sessao_http = cliente.sessao_de_chat()
        capacidades = cliente.capacidades(sessao_http)
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    print(abertura(capacidades))
    aviso = aviso_do_backup(capacidades)
    if aviso:
        print(aviso)
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
            "interativo": ao_dono.interativo(),
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
        so_seu = [_texto(t) for t in resposta.get("ao_dono") or [] if _texto(t)]
        if so_seu and ao_dono.interativo():
            for texto in so_seu:
                print(f"{texto}\n")
        elif so_seu:
            print(f"{SEM_TERMINAL}\n")
        if resposta.get("resposta") is not None:
            print(f"🤖 Viking: {_texto(resposta.get('resposta'))}\n")
        elif _texto(resposta.get("erro")) or not so_seu:
            print(f"❌ {_texto(resposta.get('erro')) or 'a nuvem não respondeu o turno'}\n")
        if _texto(resposta.get("aviso")):
            print(f"{_texto(resposta.get('aviso'))}\n")
        if _texto(resposta.get("consumo")):
            print(f"   💸 gemini (nuvem): {_texto(resposta.get('consumo'))}", file=sys.stderr)
