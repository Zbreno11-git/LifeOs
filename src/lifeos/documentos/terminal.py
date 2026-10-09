"""`viking documentos` (Sessão 14, D68): mandar um arquivo ao Viking e ver o que ele guarda.

`--aprender ARQUIVO --tema T` lê um `.md` ou `.txt` (UTF-8, até 1 MB) **neste Mac**, confere e manda
só o nome (sem a pasta), o tema e o texto ao motor, que corta, embute e guarda; o mesmo arquivo no
mesmo tema substitui o anterior. Sem opção, os documentos ativos; `--todos`, também os trocados, os
esquecidos e os que não terminaram de aprender (até sumirem); `--esquecer ID` e `--desfazer ID`.
Tudo pelo motor: os documentos moram na nuvem, como a memória.

Nada do texto do arquivo vai à tela nem a uma mensagem de erro: a régua (`cortes`) diz o motivo,
e o que vem da rede passa por `limpar_controles` antes do terminal. Sai com 1 quando algo falhou.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from lifeos import config
from lifeos.browser._redacao import limpar_controles
from lifeos.documentos import cortes


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


def _texto(valor: Any) -> str:
    return limpar_controles(str(valor)) if valor is not None else ""


def _estado(documento: dict[str, Any]) -> str:
    if documento.get("esquecido_em"):
        return f" (esquecido; some em {_dia(_quando(documento.get('apagar_em')))})"
    if documento.get("invalida_em"):
        por = _texto(documento.get("substituido_por"))[:8]
        return f" (trocado em {_dia(_quando(documento.get('invalida_em')))} por {por})"
    if documento.get("estado") == "aprendendo":
        return f" (não terminou de aprender; some em {_dia(_quando(documento.get('apagar_em')))})"
    return ""


def linha(documento: dict[str, Any]) -> str:
    curto = _texto(documento.get("id"))[:8]
    quando = _quando(documento.get("aprendido_em")) or _quando(documento.get("criado_em"))
    nome, tema = _texto(documento.get("nome")), _texto(documento.get("tema"))
    trechos = documento.get("n_trechos")
    n = trechos if isinstance(trechos, int) and not isinstance(trechos, bool) else "?"
    return f"{curto}  {_dia(quando)}  📄 {nome} (tema {tema}, {n} trecho(s)){_estado(documento)}"


def lista(documentos: list[dict[str, Any]], *, todos: bool = False) -> str:
    escolhidos = documentos if todos else [d for d in documentos if d.get("ativo") is True]
    if not escolhidos:
        return (
            "Nenhum documento."
            if todos
            else "Nenhum documento ativo (os esquecidos e os trocados: viking documentos --todos)."
        )
    return "\n".join(linha(d) for d in escolhidos)


def ler_arquivo(caminho: Path) -> tuple[str, str]:
    """(o nome sem a pasta, o texto) de um arquivo do Mac, conferido; `cortes.Recusado` com o
    motivo. O tamanho é conferido antes de ler: um arquivo de 2 GB não entra na memória."""
    nome = cortes.nome_valido(caminho.name)
    if caminho.stat().st_size > cortes.MAX_BYTES:
        raise cortes.Recusado(f"arquivo com mais de {cortes.MAX_BYTES:,} bytes".replace(",", "."))
    return nome, cortes.texto_do_arquivo(caminho.read_bytes())


def executar(args: Any) -> int:
    from lifeos.nuvem import cliente

    if args.tema is not None and not args.aprender:
        print("❌ --tema só vale com --aprender.", file=sys.stderr)
        return 1
    try:
        if args.aprender:
            if not args.tema:
                print(
                    "❌ diga o tema: viking documentos --aprender ARQUIVO --tema T", file=sys.stderr
                )
                return 1
            nome, texto = ler_arquivo(Path(args.aprender).expanduser())
            tema = cortes.tema_valido(args.tema)
            resposta = cliente.acao_dos_documentos(
                "aprender", {"nome": nome, "tema": tema, "texto": texto}
            )
            print(f"📄 aprendi: {linha(resposta['documento'])}")
            antigo = resposta.get("substituido")
            if isinstance(antigo, dict):
                curto = _texto(antigo.get("id"))[:8]
                print(
                    f"   no lugar da versão de {_dia(_quando(antigo.get('aprendido_em')))} "
                    f"(desfaça com: viking documentos --desfazer {curto})"
                )
        elif args.esquecer:
            documento = cliente.acao_dos_documentos("esquecer", {"id": args.esquecer})["documento"]
            print(
                f"🗑️ esquecido (some de vez em 30 dias; desfaça com --desfazer): {linha(documento)}"
            )
        elif args.desfazer:
            documento = cliente.acao_dos_documentos("desfazer", {"id": args.desfazer})["documento"]
            print(f"↩️ de volta: {linha(documento)}")
        else:
            print(lista(cliente.dos_documentos(), todos=args.todos))
    except cortes.Recusado as exc:
        print(f"❌ {exc}.", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"❌ não consegui ler o arquivo ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    except (KeyError, TypeError, ValueError):
        print("❌ Nuvem: a resposta veio num formato inesperado.", file=sys.stderr)
        return 1
    return 0
