"""O texto do e-mail em duas versões (Sessão 8b, pedido do dono): `text/plain` sem os marcadores e
`text/html` com negrito, itálico e listas.

O Gemini escreve em markdown, e no Gmail do dono `**Gestão de Calendário:**` aparecia cru
(captura de 2026-09-28). A fonte continua uma só: o texto que o dono aprova no terminal (e que o
código de aprovação liga). As duas versões saem dele aqui, por funções puras, na hora de montar.

Como o HTML não deixa passar marcação de fora: o texto **cru** é dividido primeiro em blocos
(parágrafo, lista, título) e trechos (texto, negrito, itálico); depois **cada trecho passa por
`html.escape`**, e só as tags escritas aqui ficam sem escape. Nada vira link, imagem nem estilo:
um `<img>` ou `<a href>` que o Gemini escreva chega como texto. As duas versões saem da mesma
divisão, então dizem as mesmas palavras (`tests/test_gmail_formato.py`).

O subconjunto é pequeno de propósito: `**x**`, `*x*` (sem `*` colado a letra dos dois lados: `2*3*4`
fica como está), linhas `- `/`* `/`• ` e `1. `/`1) `, `# título`. Aninhado não existe: o que não
casa fica literal nas duas versões. Só stdlib (nenhuma lib de markdown: seriam dependência nova, e
deixam HTML cru passar sem configuração).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

_TITULO = re.compile(r"^[ \t]*#{1,6}[ \t]+(\S.*)$")
_ITEM = re.compile(r"^([ \t]*[-*•][ \t]+)(\S.*)$")
_NUMERO = re.compile(r"^([ \t]*(\d{1,9})[.)][ \t]+)(\S.*)$")
# Sem `*` e sem quebra dentro; começa e termina colado ao texto ("** x **" não é negrito).
_NEGRITO = re.compile(r"\*\*(?=[^\s*])([^*\n]*?[^\s*])\*\*")
_ITALICO = re.compile(r"(?<![\w*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![\w*])")
ESTILO_DA_ASSINATURA = "color:#888888;font-size:12px"


@dataclass(frozen=True)
class _Bloco:
    tipo: str  # "p", "ul", "ol", "titulo"
    linhas: tuple[str, ...]  # o conteúdo (sem o marcador, na lista e no título)
    inicio: int = 1  # o número do 1º item, na lista numerada


def _trechos(linha: str) -> list[tuple[str, str]]:
    """(estilo, texto), com estilo "" (texto), "b" ou "i"; a linha inteira, sem perder nada."""
    saida: list[tuple[str, str]] = []

    def italicos(inicio: int, fim: int) -> None:
        pos = inicio
        # `finditer` com `pos`/`endpos`: o lookbehind enxerga o que vem antes do trecho.
        for achado in _ITALICO.finditer(linha, inicio, fim):
            if achado.start() > pos:
                saida.append(("", linha[pos : achado.start()]))
            saida.append(("i", achado.group(1)))
            pos = achado.end()
        if fim > pos:
            saida.append(("", linha[pos:fim]))

    pos = 0
    for achado in _NEGRITO.finditer(linha):
        italicos(pos, achado.start())
        saida.append(("b", achado.group(1)))
        pos = achado.end()
    italicos(pos, len(linha))
    return saida


def _blocos(fonte: str) -> list[_Bloco]:
    blocos: list[_Bloco] = []
    for linha in fonte.split("\n"):
        anterior = blocos[-1] if blocos else None
        if not linha.strip():
            blocos.append(_Bloco("fim", ()))
            continue
        if titulo := _TITULO.match(linha):
            blocos.append(_Bloco("titulo", (titulo.group(1),)))
        elif item := _ITEM.match(linha):
            if anterior is not None and anterior.tipo == "ul":
                blocos[-1] = _Bloco("ul", (*anterior.linhas, item.group(2)))
            else:
                blocos.append(_Bloco("ul", (item.group(2),)))
        elif numero := _NUMERO.match(linha):
            if anterior is not None and anterior.tipo == "ol":
                blocos[-1] = _Bloco("ol", (*anterior.linhas, numero.group(3)), anterior.inicio)
            else:
                blocos.append(_Bloco("ol", (numero.group(3),), int(numero.group(2))))
        elif anterior is not None and anterior.tipo == "p":
            blocos[-1] = _Bloco("p", (*anterior.linhas, linha))
        else:
            blocos.append(_Bloco("p", (linha,)))
    return [b for b in blocos if b.tipo != "fim"]


def _html_do_trecho(linha: str) -> str:
    partes = []
    for estilo, texto in _trechos(linha):
        escapado = html.escape(texto)
        partes.append(f"<{estilo}>{escapado}</{estilo}>" if estilo else escapado)
    return "".join(partes)


def _html_do_bloco(bloco: _Bloco) -> str:
    if bloco.tipo == "titulo":
        return f"<p><b>{_html_do_trecho(bloco.linhas[0])}</b></p>"
    if bloco.tipo in {"ul", "ol"}:
        itens = "".join(f"<li>{_html_do_trecho(linha)}</li>" for linha in bloco.linhas)
        abre = f'<ol start="{bloco.inicio}">' if bloco.tipo == "ol" and bloco.inicio != 1 else ""
        return f"{abre or '<' + bloco.tipo + '>'}{itens}</{bloco.tipo}>"
    return "<p>" + "<br>".join(_html_do_trecho(linha) for linha in bloco.linhas) + "</p>"


def documento(fonte: str, *, assinatura: str) -> str:
    """A parte `text/html`: o texto formatado e a assinatura em cinza, menor (dono, 2026-09-29)."""
    corpo = "".join(_html_do_bloco(bloco) for bloco in _blocos(fonte))
    rodape = f'<p style="{ESTILO_DA_ASSINATURA}">— {html.escape(assinatura)}</p>'
    return f"<!DOCTYPE html><html><body>{corpo}{rodape}</body></html>"


def _puro_da_linha(linha: str) -> str:
    return "".join(texto for _estilo, texto in _trechos(linha))


def texto_puro(fonte: str) -> str:
    """A parte `text/plain`: as linhas como estão, sem `**`/`*` de ênfase nem o `#` de título. Os
    marcadores de lista ficam: legíveis como estão."""
    linhas = []
    for linha in fonte.split("\n"):
        if titulo := _TITULO.match(linha):
            linhas.append(_puro_da_linha(titulo.group(1)))
        elif marcado := _ITEM.match(linha) or _NUMERO.match(linha):
            linhas.append(marcado.group(1) + _puro_da_linha(marcado.groups()[-1]))
        else:
            linhas.append(_puro_da_linha(linha))
    return "\n".join(linhas)


def tem_formatacao(fonte: str) -> bool:
    """Se o HTML mostra algo diferente do texto corrido (para o aviso no terminal)."""
    return any(
        bloco.tipo != "p" or any(estilo for linha in bloco.linhas for estilo, _ in _trechos(linha))
        for bloco in _blocos(fonte)
    )
