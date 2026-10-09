"""`viking memoria` (Sessão 13, D66): o visor da memória no Mac, como o `viking registro`.

Sem opção, os fatos ativos; `--todos`, também os trocados e os esquecidos (até sumirem); `--semana`,
o que entrou nos últimos 7 dias (o mesmo do e-mail de segunda); `--esquecer ID`, `--desfazer ID` e
`--corrigir ID --texto T` mudam um fato; `--reindexar` refaz os vetores (depois de restaurar um
backup). Tudo pelo motor: a memória mora na nuvem, e o Mac não a guarda.

Desde a 13b (D67), as receitas aparecem na mesma lista, marcadas com 📋 e o número de passos;
`--receitas` mostra as guardadas com os passos inteiros; `--esquecer`/`--desfazer` valem para elas.

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


def _passos(receita: dict[str, Any]) -> list[str]:
    passos = receita.get("passos")
    return [limpar_controles(str(p)) for p in passos] if isinstance(passos, list) else []


def linha_da_receita(receita: dict[str, Any]) -> str:
    nome = limpar_controles(str(receita.get("nome", "")))
    curto = limpar_controles(str(receita.get("id", "")))[:8]
    estado = _estado(receita)
    if receita.get("estado") == "proposta" and not estado:
        estado = f" (proposta, não guardada; some em {_dia(_quando(receita.get('apagar_em')))})"
    quando = _quando(receita.get("guardada_em")) or _quando(receita.get("criado_em"))
    return f"{curto}  {_dia(quando)}  📋 {nome} ({len(_passos(receita))} passo(s)){estado}"


def so_receitas(receitas: list[dict[str, Any]]) -> str:
    """O `--receitas`: as guardadas, cada uma com os passos inteiros."""
    ativas = [r for r in receitas if r.get("ativo") is True]
    if not ativas:
        return "Nenhuma receita guardada (ensine uma no viking chat --nuvem)."
    blocos = []
    for receita in ativas:
        passos = [f"   {n}. {p}" for n, p in enumerate(_passos(receita), 1)]
        blocos.append("\n".join([linha_da_receita(receita), *passos]))
    return "\n".join(blocos)


def lista(
    fatos: list[dict[str, Any]],
    receitas: list[dict[str, Any]] | None = None,
    *,
    todos: bool = False,
    semana: bool = False,
    agora=None,
) -> str:
    """O texto da lista (puro: os testes leem sem rede): os fatos, depois as receitas."""
    agora = agora or datetime.now(UTC)
    receitas = receitas or []
    if semana:
        corte = agora - SEMANA
        escolhidos = [f for f in fatos if (_quando(f.get("criado_em")) or agora) >= corte]
        das_receitas = [
            r
            for r in receitas
            if r.get("estado") == "guardada" and (_quando(r.get("guardada_em")) or agora) >= corte
        ]
        vazio = "Nada anotado nos últimos 7 dias."
    elif todos:
        escolhidos, das_receitas, vazio = list(fatos), list(receitas), "A memória está vazia."
    else:
        escolhidos = [f for f in fatos if f.get("ativo") is True]
        das_receitas = [r for r in receitas if r.get("ativo") is True]
        vazio = "Nenhum fato anotado (os esquecidos e os trocados: viking memoria --todos)."
    if not escolhidos and not das_receitas:
        return vazio
    return "\n".join(
        [*(linha(f) for f in escolhidos), *(linha_da_receita(r) for r in das_receitas)]
    )


def _linha_do_resultado(resposta: dict[str, Any]) -> str:
    """O fato ou a receita que uma ação devolveu."""
    if "receita" in resposta:
        return linha_da_receita(resposta["receita"])
    return linha(resposta["fato"])


def executar(args: Any) -> int:
    from lifeos.nuvem import cliente

    try:
        if args.esquecer:
            feito = _linha_do_resultado(cliente.acao_da_memoria("esquecer", {"id": args.esquecer}))
            print(f"🗑️ esquecido (some de vez em 30 dias; desfaça com --desfazer): {feito}")
        elif args.desfazer:
            feito = _linha_do_resultado(cliente.acao_da_memoria("desfazer", {"id": args.desfazer}))
            print(f"↩️ de volta: {feito}")
        elif args.corrigir:
            if not args.texto:
                print("❌ --corrigir precisa de --texto com o fato certo.", file=sys.stderr)
                return 1
            fato = cliente.acao_da_memoria("corrigir", {"id": args.corrigir, "texto": args.texto})[
                "fato"
            ]
            print(f"📝 anotado no lugar: {linha(fato)}")
        elif args.reindexar:
            refeitos = cliente.acao_da_memoria("reindexar", {})
            trechos = refeitos.get("trechos", 0)  # Sessão 14: um motor de antes não manda
            print(
                f"✅ vetores refeitos: {int(refeitos['refeitos'])}"
                + (f" (e {int(trechos)} trecho(s) de documento)" if trechos else "")
            )
        else:
            if args.texto:
                print("❌ --texto só vale com --corrigir.", file=sys.stderr)
                return 1
            fatos, receitas = cliente.da_memoria()
            if getattr(args, "receitas", False):
                print(so_receitas(receitas))
            else:
                print(lista(fatos, receitas, todos=args.todos, semana=args.semana))
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    except (KeyError, TypeError, ValueError):
        print("❌ Nuvem: a resposta veio num formato inesperado.", file=sys.stderr)
        return 1
    return 0
