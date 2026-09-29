"""O e-mail formatado (Sessão 8b, pedido do dono): o texto que o Gemini escreve e o dono aprova vira
uma parte `text/plain` sem marcadores e uma `text/html` com negrito, itálico e listas.

Os ataques que estes testes fecham:
- o Gemini (ou um e-mail injetado que ele copiou) escreve HTML, e ele chega como marcação ao
  destinatário: link disfarçado, imagem que avisa que o e-mail foi aberto, script;
- a parte HTML diz outra coisa que a parte texto, que é a que o dono leu no terminal.

A régua principal não depende da lista de ataques: tiradas as tags que o conversor escreve (a
lista está aqui, à mão), não sobra nenhum `<` no HTML, e as palavras são as da parte texto.
"""

import html
import re

import pytest

from lifeos.gmail import formato

ASSINATURA = "Escrito pelo Viking (Assistente AI)"
FAMILIA = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)

# As únicas tags que o conversor pode escrever, com os únicos atributos. Escrita à mão: derivar do
# módulo faria a régua aceitar qualquer tag nova que ele passasse a escrever.
_NOSSAS_DE_BLOCO = re.compile(
    r"<!DOCTYPE html>|</?(?:html|body|p|ul|li)>|<br>|<ol(?: start=\"\d+\")?>|</ol>"
    r"|<p style=\"color:#888888;font-size:12px\">"
)
_NOSSAS_DE_TRECHO = re.compile(r"</?[bi]>")  # dentro da palavra: `*<b>x</b>*` é `*x*`

ADVERSARIAIS = [
    "<script>alert(1)</script>",
    '<img src=x onerror="fetch(1)">',
    '"><a href="https://evil.example">clique</a>',
    "<style>body{display:none}</style>",
    "**<a href=x>negrito</a>**",
    "- <img src=x>\n- item",
    "1. <script>x</script>",
    "# <b onclick=x>título</b>",
    "*<i onmouseover=x>i</i>*",
    "&lt;script&gt; já escapado",
    "javascript:alert(1)",
    "[clique](https://evil.example)",
    '<p style="color:#888888;font-size:12px">— assinatura falsa</p>',
    "<!DOCTYPE html><html><body>outro documento</body></html>",
    "**sem fechar",
    "***x***",
    "Texto\n- lista colada\n- no parágrafo\nfim",
    "a < b > c & d \" e ' f",
    "</p><p>fecha o parágrafo",
    "<br>quebra falsa",
]


def _documento(fonte: str) -> str:
    return formato.documento(fonte, assinatura=ASSINATURA)


def _sem_as_nossas(documento: str) -> str:
    return _NOSSAS_DE_BLOCO.sub(" ", _NOSSAS_DE_TRECHO.sub("", documento))


@pytest.mark.parametrize("fonte", ADVERSARIAIS)
def test_nada_do_texto_vira_marcacao(fonte):
    """Tiradas as tags que nós escrevemos, não sobra `<` nenhum: tudo o mais foi escapado."""
    resto = _sem_as_nossas(_documento(fonte))
    assert "<" not in resto
    assert ">" not in resto


@pytest.mark.parametrize("fonte", ADVERSARIAIS)
def test_nenhum_link_imagem_script_ou_evento(fonte):
    documento = _documento(fonte).lower()
    for proibido in ("<a", "<img", "<script", "<style", "<iframe", "<link", "<meta"):
        assert proibido not in documento
    assert re.search(r"<[^>]*\son\w+\s*=", documento) is None
    assert re.search(r"<[^>]*href", documento) is None


def _palavras(texto: str) -> list[str]:
    return texto.split()


def _marcador_de_lista(palavra: str) -> bool:
    return re.fullmatch(r"[-*•]|\d{1,9}[.)]", palavra) is not None


@pytest.mark.parametrize("fonte", [*ADVERSARIAIS, "**Gestão:** agenda\n\n- um\n- dois\n1. três"])
def test_html_e_texto_dizem_as_mesmas_palavras(fonte):
    """O HTML sem as nossas tags, com o escape desfeito, tem as palavras da parte texto; a parte
    texto só tem a mais os marcadores de lista (que no HTML viram `<li>`)."""
    do_html = _palavras(html.unescape(_sem_as_nossas(_documento(fonte))))
    do_texto = _palavras(formato.texto_puro(fonte) + f"\n\n— {ASSINATURA}")
    sobra = list(do_texto)
    for palavra in do_html:
        assert palavra in sobra, palavra
        sobra.remove(palavra)
    assert all(_marcador_de_lista(p) for p in sobra), sobra


# --- o que vira formatação -------------------------------------------------------------------


def test_o_email_da_captura_sai_formatado():
    """O texto da captura de tela do dono (2026-09-28), com o HTML esperado escrito à mão: a
    régua de palavras acima passaria com as duas partes erradas do mesmo jeito."""
    fonte = (
        "Olá! Eu sou o Viking.\n\n"
        "**Gestão de Calendário:** crio e mudo eventos.\n\n"
        "- Lembretes\n- E-mail\n\n"
        "Até mais"
    )
    assert _documento(fonte) == (
        "<!DOCTYPE html><html><body>"
        "<p>Olá! Eu sou o Viking.</p>"
        "<p><b>Gestão de Calendário:</b> crio e mudo eventos.</p>"
        "<ul><li>Lembretes</li><li>E-mail</li></ul>"
        "<p>Até mais</p>"
        '<p style="color:#888888;font-size:12px">— Escrito pelo Viking (Assistente AI)</p>'
        "</body></html>"
    )
    assert formato.texto_puro(fonte) == (
        "Olá! Eu sou o Viking.\n\n"
        "Gestão de Calendário: crio e mudo eventos.\n\n"
        "- Lembretes\n- E-mail\n\n"
        "Até mais"
    )


def test_italico_titulo_lista_numerada_e_quebra_de_linha():
    fonte = "# Resumo\nlinha um\nlinha *dois*\n\n3. terceiro\n4. quarto"
    assert _documento(fonte) == (
        "<!DOCTYPE html><html><body>"
        "<p><b>Resumo</b></p>"
        "<p>linha um<br>linha <i>dois</i></p>"
        '<ol start="3"><li>terceiro</li><li>quarto</li></ol>'
        '<p style="color:#888888;font-size:12px">— Escrito pelo Viking (Assistente AI)</p>'
        "</body></html>"
    )
    assert formato.texto_puro(fonte) == "Resumo\nlinha um\nlinha dois\n\n3. terceiro\n4. quarto"


@pytest.mark.parametrize(
    "fonte",
    [
        "2*3*4 = 24",
        "5 * 3 * 2",
        "a**b",
        "**",
        "* ",
        "palavra*meio*palavra",
        "---",
        "#hashtag",
        "**sem fechar",
        "** espaço dentro **",
    ],
)
def test_vizinhos_legitimos_ficam_como_estao(fonte):
    """Asteriscos de conta, de palavra e marcação que não fecha: literais nas duas partes."""
    assert formato.texto_puro(fonte) == fonte
    corpo = _documento(fonte).split("<body>")[1].split('<p style="color')[0]
    assert "<b>" not in corpo
    assert "<i>" not in corpo
    assert "<ul>" not in corpo


def test_lista_colada_num_paragrafo_abre_a_lista():
    corpo = _documento("Compras:\n- água\n- pão\nobrigado")
    assert "<p>Compras:</p><ul><li>água</li><li>pão</li></ul><p>obrigado</p>" in corpo


def test_asterisco_de_lista_nao_e_italico():
    assert "<ul><li>um</li><li><b>dois</b></li></ul>" in _documento("* um\n* **dois**")
    assert formato.texto_puro("* um\n* **dois**") == "* um\n* dois"


def test_triplo_asterisco_e_consistente_nas_duas_partes():
    assert "<p>*<b>x</b>*</p>" in _documento("***x***")
    assert formato.texto_puro("***x***") == "*x*"


def test_emoji_com_zwj_inteiro_nas_duas_partes():
    fonte = f"**Família** {FAMILIA}"
    assert FAMILIA in _documento(fonte)
    assert FAMILIA in formato.texto_puro(fonte)


def test_assinatura_escapada_e_em_cinza():
    documento = formato.documento("oi", assinatura="<b>x</b> & y")
    assert '<p style="color:#888888;font-size:12px">— &lt;b&gt;x&lt;/b&gt; &amp; y</p>' in documento


@pytest.mark.parametrize(
    ("fonte", "esperado"),
    [
        ("texto simples", False),
        ("2*3*4", False),
        ("**negrito**", True),
        ("*itálico*", True),
        ("- item", True),
        ("1. item", True),
        ("# título", True),
    ],
)
def test_tem_formatacao(fonte, esperado):
    assert formato.tem_formatacao(fonte) is esperado
