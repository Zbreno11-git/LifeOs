"""`viking memoria` (Sessão 13, D66): o visor da memória no Mac, como o `viking registro`.

Sem opção, os fatos ativos; `--todos`, também os trocados e os esquecidos (até sumirem); `--semana`,
o que entrou nos últimos 7 dias (o mesmo do e-mail de segunda); `--esquecer ID`, `--desfazer ID` e
`--corrigir ID --texto T` mudam um fato; `--reindexar` refaz os vetores (depois de restaurar um
backup). Tudo pelo motor: a memória mora na nuvem, e o Mac não a guarda.

O id é o curto que a lista mostra (8 caracteres). O texto que vem da rede passa por
`limpar_controles` antes do terminal. Sai com 1 quando algo falhou.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from lifeos import config
from lifeos.browser._redacao import limpar_controles

SEMANA = timedelta(days=7)


def _quando(texto: Any) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    return momento if momento.tzinfo is not None else None


def _dia(momento: datetime | None) -> str:
    return f"{momento.astimezone(config.TIMEZONE):%d/%m/%Y}" if momento else "?"


def _estado(fato: dict[str, Any]) -> str:
    if fato.get("esquecido_em"):
        return f" (esquecido; some em {_dia(_quando(fato.get('apagar_em')))})"
    if fato.get("invalida_em"):
        por = str(fato.get("substituido_por") or "")[:8]
        return f" (trocado em {_dia(_quando(fato.get('invalida_em')))} por {por})"
    return ""


def linha(fato: dict[str, Any]) -> str:
    texto = limpar_controles(str(fato.get("texto", "")))
    curto = limpar_controles(str(fato.get("id", "")))[:8]
    return f"{curto}  {_dia(_quando(fato.get('criado_em')))}  {texto}{_estado(fato)}"


def lista(
    fatos: list[dict[str, Any]], *, todos: bool = False, semana: bool = False, agora=None
) -> str:
    """O texto da lista (puro: os testes leem sem rede)."""
    agora = agora or datetime.now(UTC)
    if semana:
        corte = agora - SEMANA
        escolhidos = [f for f in fatos if (_quando(f.get("criado_em")) or agora) >= corte]
        vazio = "Nada anotado nos últimos 7 dias."
    elif todos:
        escolhidos, vazio = list(fatos), "A memória está vazia."
    else:
        escolhidos = [f for f in fatos if f.get("ativo") is True]
        vazio = "Nenhum fato anotado (os esquecidos e os trocados: viking memoria --todos)."
    if not escolhidos:
        return vazio
    return "\n".join(linha(f) for f in escolhidos)


def executar(args: Any) -> int:
    from lifeos.nuvem import cliente

    try:
        if args.esquecer:
            fato = cliente.acao_da_memoria("esquecer", {"id": args.esquecer})["fato"]
            print(f"🗑️ esquecido (some de vez em 30 dias; desfaça com --desfazer): {linha(fato)}")
        elif args.desfazer:
            fato = cliente.acao_da_memoria("desfazer", {"id": args.desfazer})["fato"]
            print(f"↩️ de volta: {linha(fato)}")
        elif args.corrigir:
            if not args.texto:
                print("❌ --corrigir precisa de --texto com o fato certo.", file=sys.stderr)
                return 1
            fato = cliente.acao_da_memoria("corrigir", {"id": args.corrigir, "texto": args.texto})[
                "fato"
            ]
            print(f"📝 anotado no lugar: {linha(fato)}")
        elif args.reindexar:
            refeitos = cliente.acao_da_memoria("reindexar", {})["refeitos"]
            print(f"✅ vetores refeitos: {int(refeitos)}")
        else:
            if args.texto:
                print("❌ --texto só vale com --corrigir.", file=sys.stderr)
                return 1
            print(lista(cliente.fatos_da_memoria(), todos=args.todos, semana=args.semana))
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    except (KeyError, TypeError, ValueError):
        print("❌ Nuvem: a resposta veio num formato inesperado.", file=sys.stderr)
        return 1
    return 0
