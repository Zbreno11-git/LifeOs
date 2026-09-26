"""Delimitar conteúdo de terceiros (página do navegador, e-mail) para o modelo ler como DADO.

Uma cópia só da regra, usada por `browser/mensagens.py` e `gmail/tools.py`. O cabeçalho avisa o
modelo; o delimitador `«…»` marca onde o dado começa e termina; `neutralizar` impede que o próprio
dado feche o bloco com um `»` e faça o resto parecer instrução do sistema (§6.3 da auditoria).
"""

from __future__ import annotations


def neutralizar(texto: str) -> str:
    return texto.replace("«", "‹").replace("»", "›")


def bloco(cabecalho: str, conteudo: str) -> str:
    """`cabecalho` é nosso; `conteudo` é do terceiro e sai neutralizado. Vazio → vazio."""
    if not conteudo:
        return ""
    return f"{cabecalho}\n«{neutralizar(conteudo)}»"
