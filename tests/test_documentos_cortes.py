"""O arquivo conferido e cortado (Sessão 14, D68), sem rede, dos dois lados (erros, classe 7).

As perguntas: o que entra (`.md`/`.txt`, UTF-8, até 1 MB) e o que não entra? O corte respeita os
títulos e as linhas, e funciona no `.txt` que o Docs exporta (sem título nenhum)? Um parágrafo
gigante, uma frase sem ponto e uma palavra sem espaço viram trechos dentro do teto? O que se guarda
sai sem controle de terminal nem invisível?
"""

import pytest
from tests import crescimento

from lifeos.documentos import cortes

ZWSP = chr(0x200B)
RLO = chr(0x202E)
BOM = chr(0xFEFF)


# --- o que entra --------------------------------------------------------------------------------


@pytest.mark.parametrize("nome", ["treino.md", "Notas de Python.txt", "TREINO.MD", "ação 2026.md"])
def test_nome_legitimo_passa(nome):
    assert cortes.nome_valido(nome) == nome


@pytest.mark.parametrize(
    ("nome", "motivo"),
    [
        ("notas.pdf", "só arquivos .md ou .txt"),
        ("notas.docx", "só arquivos .md ou .txt"),
        ("notas", "só arquivos .md ou .txt"),
        ("/Users/usuario/notas.md", "sem a pasta"),
        ("pasta\\notas.md", "sem a pasta"),
        (".md", "sem letras"),
        ("!!!.txt", "sem letras"),
        ("n" * 118 + ".md", "mais de 120"),
        (3, "texto"),
    ],
)
def test_nome_recusado(nome, motivo):
    with pytest.raises(cortes.Recusado, match=motivo):
        cortes.nome_valido(nome)


def test_o_nome_perde_controle_e_invisivel():
    assert cortes.nome_valido(f"tre{ZWSP}ino{RLO}.md") == "treino.md"


@pytest.mark.parametrize("tema", ["treino", "Python 3", "coach de força"])
def test_tema_legitimo_passa(tema):
    assert cortes.tema_valido(tema) == tema


@pytest.mark.parametrize(
    ("tema", "motivo"), [("", "sem letras"), ("???", "sem letras"), ("t" * 41, "mais de 40")]
)
def test_tema_recusado(tema, motivo):
    with pytest.raises(cortes.Recusado, match=motivo):
        cortes.tema_valido(tema)


def test_o_arquivo_de_1_mb_entra_e_um_byte_a_mais_nao():
    linha = "abcdefghi\n"  # 10 bytes
    assert cortes.texto_do_arquivo((linha * 100_000).encode())
    with pytest.raises(cortes.Recusado, match="mais de 1.000.000 bytes"):
        cortes.texto_do_arquivo((linha * 100_000 + "x").encode())


def test_o_limite_conta_bytes_e_nao_caracteres():
    """ "ç" é 2 bytes em UTF-8: 600 mil "ç" são 1,2 MB, mesmo com 600 mil caracteres."""
    with pytest.raises(cortes.Recusado, match="bytes"):
        cortes.conferir("ç" * 600_000)


@pytest.mark.parametrize(
    ("dados", "motivo"),
    [
        (b"%PDF-1.7\n\x00\x01binario", "binário"),
        ("ação".encode("latin-1"), "UTF-8"),
        (b"\xff\xfeo\x00i\x00", "binário"),  # UTF-16 tem byte nulo
        (b"   \n\n\t  ", "vazio"),
        (b"", "vazio"),
        (f"{ZWSP}{BOM}\n".encode(), "vazio"),
    ],
)
def test_arquivo_recusado(dados, motivo):
    with pytest.raises(cortes.Recusado, match=motivo):
        cortes.texto_do_arquivo(dados)


def test_o_texto_que_chega_pela_rede_e_conferido_de_novo():
    with pytest.raises(cortes.Recusado):
        cortes.conferir(b"bytes")
    with pytest.raises(cortes.Recusado, match="binário"):
        cortes.conferir("a\x00b")


# --- o corte ------------------------------------------------------------------------------------

MARKDOWN = """# Perna

Agachamento: 4x8.
Descanso de 2 minutos.

## Joelho

Se doer, reduzir a amplitude.

# Costas

Barra fixa até a falha.
"""


def test_markdown_corta_nos_titulos_com_o_caminho_e_as_linhas():
    trechos = cortes.cortar(MARKDOWN)
    assert [(t.secao, t.linha_de, t.linha_ate) for t in trechos] == [
        ("Perna", 3, 4),
        ("Perna › Joelho", 8, 8),
        ("Costas", 12, 12),
    ]
    assert trechos[0].texto == "Agachamento: 4x8.\nDescanso de 2 minutos."
    assert [t.ordem for t in trechos] == [0, 1, 2]


def test_as_linhas_citadas_batem_com_o_arquivo():
    linhas = MARKDOWN.split("\n")
    for trecho in cortes.cortar(MARKDOWN):
        assert trecho.texto.split("\n")[0] == linhas[trecho.linha_de - 1]
        assert trecho.texto.split("\n")[-1] == linhas[trecho.linha_ate - 1]


def test_txt_do_docs_sem_titulo_junta_paragrafos_ate_o_teto():
    paragrafo = "Frase de um parágrafo do texto exportado. " * 4  # ~170 caracteres
    texto = "\n\n".join([paragrafo.strip()] * 10)
    trechos = cortes.cortar(texto)
    assert all(t.secao == "" for t in trechos)
    assert all(len(t.texto) <= cortes.MAX_TRECHO for t in trechos)
    assert 1 < len(trechos) < 10  # juntou, e não num trecho só
    assert "".join(t.texto for t in trechos).replace("\n", "").count("Frase") == 40


def test_titulo_de_nivel_menor_fecha_os_de_baixo():
    texto = "# A\n\n## B\n\nb\n\n### C\n\nc\n\n## D\n\nd\n"
    assert [t.secao for t in cortes.cortar(texto)] == ["A › B", "A › B › C", "A › D"]


def test_hashtag_sem_espaco_nao_e_titulo():
    trechos = cortes.cortar("#treino de hoje\n\ntexto\n")
    assert trechos[0].secao == "" and trechos[0].texto.startswith("#treino")


@pytest.mark.parametrize(
    "texto",
    [
        "Uma frase longa sem fim. " * 200,  # parágrafo gigante: parte na frase
        "palavra " * 1_000,  # frase gigante sem ponto: parte na palavra
        "x" * 5_000,  # uma palavra só: parte no caractere
    ],
)
def test_nada_passa_do_teto(texto):
    trechos = cortes.cortar(texto)
    assert trechos and all(0 < len(t.texto) <= cortes.MAX_TRECHO for t in trechos)
    assert "".join(t.texto.replace(" ", "") for t in trechos) == texto.replace(" ", "")


@pytest.mark.parametrize("quebra", ["\r\n", "\r"])
def test_crlf_e_cr_contam_linha_como_lf(quebra):
    texto = MARKDOWN.replace("\n", quebra)
    assert [(t.linha_de, t.linha_ate) for t in cortes.cortar(texto)] == [(3, 4), (8, 8), (12, 12)]


def test_o_que_se_guarda_sai_sem_controle_nem_invisivel():
    texto = f"{BOM}# Tí{ZWSP}tulo\n\nTexto com{RLO} bidi e \x1b[31mcor\x1b[0m e tab\taqui.\n"
    (trecho,) = cortes.cortar(texto)
    assert trecho.secao == "Título"
    assert RLO not in trecho.texto and ZWSP not in trecho.texto and "\x1b" not in trecho.texto
    assert "\t" not in trecho.texto  # o tab vira espaço como o resto


def test_so_titulos_da_lista_vazia():
    assert cortes.cortar("# A\n\n## B\n\n   \n") == []


@pytest.mark.parametrize(
    "unidade",
    ["palavra ", "x", "Frase curta. ", "linha\n\n"],
    ids=["palavras", "sem-espaco", "frases", "paragrafos"],
)
def test_o_corte_cresce_linear(unidade):
    """O pior caso de 1 MB é o texto sem quebra: nenhuma forma pode custar quadrático."""

    def executar(k):
        texto = unidade * (20_000 * k)
        return lambda: cortes.cortar(texto)

    crescimento.cresce_linear(executar)
