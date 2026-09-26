"""Redação e limpeza do texto de páginas (§6 da auditoria). Unitário + adversarial: cada caso
aqui é uma forma de vazar dado ou de enganar o terminal/o modelo, testada sem rede nem navegador.
"""

import re
import sys
import time
from pathlib import Path

import pytest

from lifeos.browser import _redacao as r

# --- caracteres de controle ----------------------------------------------------------------


@pytest.mark.parametrize(
    "malicioso",
    [
        "\x1b[2J\x1b[31mlimpa a tela e pinta de vermelho",
        "\x9b31mCSI em C1",
        "fatura\u202egpj.exe",
        "nul\x00no meio",
        "\x07sino\x7f",
        "isolado\u2066bidi\u2069",
    ],
)
def test_controles_somem(malicioso):
    limpo = r.limpar_controles(malicioso)
    assert not any(ord(c) < 0x20 and c not in "\t\n" for c in limpo)
    assert not any(0x7F <= ord(c) <= 0x9F for c in limpo)
    assert "\u202e" not in limpo and "\u2066" not in limpo


def test_tab_e_quebra_de_linha_ficam():
    assert r.limpar_controles("a\tb\nc") == "a\tb\nc"


def test_limpar_controles_e_idempotente():
    texto = "\x1b[2Jx\u202ey"
    assert r.limpar_controles(r.limpar_controles(texto)) == r.limpar_controles(texto)


def test_vazio_e_none_passam_direto():
    assert r.limpar_controles("") == ""
    assert r.limpar_controles(None) is None
    assert r.redigir(None) is None
    assert r.redigir_url(None) is None


# --- documentos e cartão ---------------------------------------------------------------------


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725"])
def test_cpf_valido_e_redigido(cpf):
    assert r.redigir(f"meu cpf é {cpf}.") == "meu cpf é [CPF]."


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-81", "11222333000181"])
def test_cnpj_valido_e_redigido(cnpj):
    assert r.redigir(f"CNPJ {cnpj}") == "CNPJ [CNPJ]"


@pytest.mark.parametrize(
    "inofensivo",
    [
        "529.982.247-24",  # dígito verificador errado
        "111.111.111-11",  # todos iguais passam na conta, mas não são CPF
        "11987654321",  # celular com DDD: 11 dígitos, não é CPF
        "11.222.333/0001-82",
        "1234 5678 1234 5678",  # 16 dígitos que não passam no Luhn
    ],
)
def test_numero_sem_digito_verificador_valido_fica(inofensivo):
    assert r.redigir(inofensivo) == inofensivo


@pytest.mark.parametrize(
    "cartao", ["4111 1111 1111 1111", "4111-1111-1111-1111", "4111111111111111"]
)
def test_cartao_luhn_valido_e_redigido(cartao):
    assert r.redigir(f"cartão {cartao} ok") == "cartão [cartão] ok"


def test_cnpj_que_passa_no_luhn_vira_cnpj_e_nao_cartao():
    """Este CNPJ também é Luhn-válido: se o cartão fosse aplicado antes, viraria `[cartão]`."""
    assert r._luhn("11222333003520")
    assert r.redigir("11222333003520") == "[CNPJ]"


def test_ssn():
    assert r.redigir("SSN 123-45-6789") == "SSN [SSN]"


# --- tokens e chaves -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "segredo",
    [
        "sk-or-v1-" + "a" * 40,
        "sk-" + "B" * 30,
        "ghp_" + "c" * 36,
        "github_pat_" + "d" * 50,
        "AIza" + "e" * 35,
        "xoxb-1234567890-abc",
        "AKIA" + "F" * 16,
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
    ],
)
def test_tokens_conhecidos_sao_redigidos(segredo):
    assert r.redigir(f"chave: {segredo} fim") == "chave: [token] fim"


def test_bloco_de_chave_privada():
    bloco = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nabc\n-----END RSA PRIVATE KEY-----"
    assert r.redigir(f"x {bloco} y") == "x [chave] y"


def test_email_fica_visivel():
    """Decisão do dono (2026-09-26): e-mail numa página costuma ser contato e é útil."""
    assert r.redigir("fale com contato@empresa.com") == "fale com contato@empresa.com"


def test_redigir_e_idempotente():
    texto = "cpf 529.982.247-25 cartão 4111111111111111 sk-" + "x" * 30
    uma = r.redigir(texto)
    assert r.redigir(uma) == uma


# --- URL ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://x.com/r?token=abc", "https://x.com/r?token=[redigido]"),
        ("https://x.com/r?access_token=abc&a=1", "https://x.com/r?access_token=[redigido]&a=1"),
        (
            "https://x.com/cb#access_token=abc&t=bearer",
            "https://x.com/cb#access_token=[redigido]&t=bearer",
        ),
        ("https://x.com/r?api_key=abc", "https://x.com/r?api_key=[redigido]"),
        ("https://x.com/cb?code=abc&state=s", "https://x.com/cb?code=[redigido]&state=s"),
    ],
)
def test_parametros_sensiveis_da_url(url, esperado):
    assert r.redigir_url(url) == esperado


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/s?q=a%20b&keyword=sapatos",
        "https://x.com/doc#secao-2",
        "https://www.youtube.com/results?search_query=spider+man",
    ],
)
def test_url_sem_parametro_sensivel_volta_identica(url):
    assert r.redigir_url(url) == url


# --- texto digitado --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rotulo", ["Senha", "API key", "Código de verificação", "Card number", "PIN", "Token"]
)
def test_digitado_em_campo_sensivel_some(rotulo):
    assert r.mascarar_digitado(rotulo, "valor-secreto-123") == r.OCULTO


def test_digitado_em_campo_comum_so_e_redigido():
    assert r.mascarar_digitado("Buscar", "viagem pra sp") == "viagem pra sp"
    assert r.mascarar_digitado("Buscar", "cpf 529.982.247-25") == "cpf [CPF]"


# --- página ---------------------------------------------------------------------------------


def test_pagina_nao_muta_o_original():
    original = {
        "url": "https://x.com/?token=abc",
        "title": "CPF 529.982.247-25",
        "text": "cartão 4111111111111111",
        "fingerprint": "fp",
    }
    copia = dict(original)
    redigida = r.pagina(original)
    assert original == copia
    assert redigida["text"] == "cartão [cartão]"
    assert redigida["title"] == "CPF [CPF]"
    assert redigida["url"] == "https://x.com/?token=[redigido]"
    assert redigida["fingerprint"] == "fp"


def test_pagina_preserva_titulo_none():
    assert r.pagina({"url": "https://x.com", "title": None, "text": ""})["title"] is None


# --- domínios bloqueados (adversarial) ------------------------------------------------------

_BLOQ = ("itau.com.br", "mail.google.com")


@pytest.mark.parametrize(
    "url",
    [
        "https://itau.com.br",
        "https://www.itau.com.br/login",
        "https://ITAU.COM.BR./",
        "https://itau.com.br:443/x",
        "https://evil.com@itau.com.br/",
        "itau.com.br/conta",
        "//www.itau.com.br",
        "https://mail.google.com/mail/u/0",
    ],
)
def test_dominio_bloqueado(url):
    assert r.dominio_bloqueado(url, _BLOQ) is not None


@pytest.mark.parametrize(
    "url",
    [
        "https://notitau.com.br",
        "https://itau.com.br.evil.com",
        "https://itau.com.br@evil.com/",
        "https://google.com",
        "https://example.com/?next=https://itau.com.br",
        "",
        "http://[::1",
    ],
)
def test_dominio_nao_bloqueado(url):
    assert r.dominio_bloqueado(url, _BLOQ) is None


# --- robustez -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gigante",
    [
        "1-" * 100_000,
        "-----BEGIN PRIVATE KEY-----\n" * 10_000,
        "9" * 200_000,
    ],
)
def test_texto_gigante_nao_explode(gigante):
    """Detector de custo quadrático (ReDoS), não benchmark — o limite é generoso de propósito."""
    inicio = time.perf_counter()
    r.redigir(gigante)
    r.limpar_controles(gigante)
    assert time.perf_counter() - inicio < 2


def test_redacao_so_usa_stdlib():
    """Roda dentro do ambiente do Jev, onde `lifeos` não existe."""
    fonte = Path(r.__file__).read_text()
    assert re.findall(r"^\s*(?:from|import)\s+lifeos", fonte, re.MULTILINE) == []
    modulos = re.findall(r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", fonte, re.MULTILINE)
    assert set(modulos) <= set(sys.stdlib_module_names)
