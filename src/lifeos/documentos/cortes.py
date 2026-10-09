"""O arquivo que o dono manda, conferido e cortado em trechos (Sessão 14, D68). Puro, sem rede: o
Mac confere antes de mandar, e o motor confere de novo (`conferir`) antes de cortar.

O que entra (o dono, 2026-10-09): `.md` ou `.txt`, UTF-8, até 1 MB, com um tema. PDF não: o Docs
exporta as notas do NotebookLM como Markdown ou texto puro, e o leitor de PDF medido (`pypdf`) tem
um histórico de PDF malformado que trava ou estoura a memória.

O corte: por parágrafo (linha em branco), juntando os curtos até `MAX_TRECHO` caracteres, e um
parágrafo maior é partido na frase (e, sem frase, na palavra). Um título Markdown (`# …` a `###### …`)
começa um trecho novo e vira a `secao` dos que vêm abaixo (o caminho dos títulos, "Perna › Agachamento"),
que vai junto no vetor como o título do texto. Cada trecho guarda as linhas de/até do arquivo: a
citação "linhas X–Y" se confere no arquivo do dono. O `.txt` exportado do Docs não tem título: o
trecho fica sem `secao`, e o corte é o mesmo.

O texto que se guarda sai sem caracteres de controle de terminal e sem os invisíveis de formatação
(bidi, largura zero, o BOM): o trecho volta ao terminal do dono e ao modelo.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from lifeos.browser._redacao import limpar_controles
from lifeos.memoria import regras

MAX_BYTES = 1_000_000  # o dono, 2026-10-09: "1 MB"
MAX_TRECHO = 600  # caracteres: medido no C1 (2026-10-09), mais perto da pergunta certa que 1.500
MAX_NOME = 120  # caracteres do nome do arquivo
MAX_TEMA = 40  # caracteres do tema, como o nome de uma receita
EXTENSOES = (".md", ".txt")

_TITULO = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
_FIM_DE_FRASE = re.compile(r"(?<=[.!?…:;])\s+")
_INVISIVEIS = {c: None for c in range(0x110000) if unicodedata.category(chr(c)) == "Cf"}


class Recusado(ValueError):
    """O arquivo não entra (o motivo, nunca o conteúdo)."""


@dataclass(frozen=True)
class Trecho:
    ordem: int  # 0, 1, 2… na ordem do arquivo
    linha_de: int  # 1-based, inclusiva
    linha_ate: int
    secao: str  # o caminho dos títulos acima ("" sem título)
    texto: str


def _linha(texto: str) -> str:
    """Uma linha como se guarda: sem controle de terminal nem invisível, sem espaço no fim."""
    return limpar_controles(unicodedata.normalize("NFC", texto)).translate(_INVISIVEIS).rstrip()


def nome_valido(nome: object) -> str:
    """O nome do arquivo, sem a pasta (o Mac nunca manda o caminho da máquina)."""
    if not isinstance(nome, str):
        raise Recusado("o nome do arquivo tem de ser um texto")
    limpo = _linha(nome).strip()
    if "/" in limpo or "\\" in limpo:
        raise Recusado("o nome vai sem a pasta")
    if not limpo.lower().endswith(EXTENSOES):
        raise Recusado("só arquivos .md ou .txt")
    if len(limpo) > MAX_NOME:
        raise Recusado(f"nome com mais de {MAX_NOME} caracteres")
    if not regras.nome_lido(limpo.rsplit(".", 1)[0]):
        raise Recusado("nome sem letras nem números")
    return limpo


def tema_valido(tema: object) -> str:
    if not isinstance(tema, str):
        raise Recusado("o tema tem de ser um texto")
    limpo = " ".join(_linha(tema).split())
    if len(limpo) > MAX_TEMA:
        raise Recusado(f"tema com mais de {MAX_TEMA} caracteres")
    if not regras.nome_lido(limpo):
        raise Recusado("tema sem letras nem números")
    return limpo


def texto_do_arquivo(dados: bytes) -> str:
    """Os bytes do arquivo como texto (no Mac, antes de mandar): UTF-8 estrito, sem NUL, até 1 MB."""
    if len(dados) > MAX_BYTES:
        raise Recusado(f"arquivo com mais de {MAX_BYTES:,} bytes".replace(",", "."))
    if b"\x00" in dados:
        raise Recusado("arquivo binário (tem byte nulo): só texto .md ou .txt")
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        raise Recusado("o arquivo não é UTF-8 (salve como texto UTF-8)") from None
    return conferir(texto)


def conferir(texto: object) -> str:
    """O texto que chegou ao motor (pela rede): o mesmo limite, contado em bytes UTF-8."""
    if not isinstance(texto, str):
        raise Recusado("o texto tem de ser um texto")
    if len(texto.encode("utf-8", "surrogatepass")) > MAX_BYTES:
        raise Recusado(f"arquivo com mais de {MAX_BYTES:,} bytes".replace(",", "."))
    if "\x00" in texto:
        raise Recusado("arquivo binário (tem byte nulo): só texto .md ou .txt")
    if not "".join(_linha(texto).split()):
        raise Recusado("arquivo vazio")
    return texto


def _partir(paragrafo: str) -> list[str]:
    """Um parágrafo maior que o teto, em pedaços: na frase; uma frase gigante, na palavra; uma
    palavra gigante, no caractere."""
    pedacos: list[str] = []
    atual = ""
    for frase in _FIM_DE_FRASE.split(paragrafo):
        for parte in _ate_o_teto(frase):
            if atual and len(atual) + 1 + len(parte) > MAX_TRECHO:
                pedacos.append(atual)
                atual = parte
            else:
                atual = f"{atual} {parte}" if atual else parte
    if atual:
        pedacos.append(atual)
    return pedacos


def _ate_o_teto(frase: str) -> list[str]:
    if len(frase) <= MAX_TRECHO:
        return [frase]
    partes: list[str] = []
    atual = ""
    for palavra in frase.split():
        if len(palavra) > MAX_TRECHO:  # uma palavra sem espaço maior que o teto: no caractere
            if atual:
                partes.append(atual)
                atual = ""
            corte = len(palavra) - len(palavra) % MAX_TRECHO or len(palavra) - MAX_TRECHO
            partes += [palavra[i : i + MAX_TRECHO] for i in range(0, corte, MAX_TRECHO)]
            palavra = palavra[corte:]
        if atual and len(atual) + 1 + len(palavra) > MAX_TRECHO:
            partes.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}" if atual else palavra
    if atual:
        partes.append(atual)
    return partes


def cortar(texto: str) -> list[Trecho]:
    """Os trechos do arquivo, na ordem. Um arquivo só de títulos e espaços dá a lista vazia."""
    linhas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    titulos: list[tuple[int, str]] = []  # (nível, título): o caminho até aqui
    trechos: list[Trecho] = []
    # o trecho em montagem: (linha_de, linha_ate, partes)
    de, ate = 0, 0
    partes: list[str] = []
    paragrafo: list[str] = []
    paragrafo_de = 0

    def secao() -> str:
        return " › ".join(t for _n, t in titulos)

    def fechar() -> None:
        nonlocal de, ate, partes
        if partes:
            trechos.append(Trecho(len(trechos), de, ate, secao(), "\n\n".join(partes)))
        de, ate, partes = 0, 0, []

    def juntar(texto_do_paragrafo: str, inicio: int, fim: int) -> None:
        nonlocal de, ate, partes
        for pedaco in (
            _partir(texto_do_paragrafo)
            if len(texto_do_paragrafo) > MAX_TRECHO
            else [texto_do_paragrafo]
        ):
            tamanho = sum(len(p) for p in partes) + 2 * len(partes)
            if partes and tamanho + len(pedaco) > MAX_TRECHO:
                fechar()
            if not partes:
                de = inicio
            partes.append(pedaco)
            ate = fim

    def fechar_paragrafo(fim: int) -> None:
        nonlocal paragrafo
        if paragrafo:
            juntar("\n".join(paragrafo), paragrafo_de, fim)
        paragrafo = []

    for numero, crua in enumerate(linhas, 1):
        linha = _linha(crua)
        titulo = _TITULO.match(linha.strip())
        if titulo:
            fechar_paragrafo(numero - 1)
            fechar()
            nivel, nome = len(titulo.group(1)), " ".join(titulo.group(2).split())
            titulos = [t for t in titulos if t[0] < nivel] + [(nivel, nome)]
            continue
        if not linha.strip():
            fechar_paragrafo(numero - 1)
            continue
        if not paragrafo:
            paragrafo_de = numero
        paragrafo.append(" ".join(linha.split()))
    fechar_paragrafo(len(linhas))
    fechar()
    return trechos
