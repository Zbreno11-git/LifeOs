"""Redação e limpeza de texto vindo de páginas — SÓ stdlib.

Importado dos dois lados da fronteira do subprocesso: por `_jev_subprocess.py` (dentro do
ambiente do Jev, como módulo irmão, antes de o texto da página ir ao OpenRouter) e pelo Viking
(`jev_runner`, antes de ir ao Gemini/terminal). Por isso não pode importar `lifeos` nem nada fora
da stdlib — é a única cópia da regra, e os dois lados precisam dela.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# C0 menos \t e \n, DEL, C1, e os controles bidi que reordenam o que o terminal mostra.
_CONTROLES = dict.fromkeys(
    [
        *range(0x09),
        *range(0x0B, 0x20),
        0x7F,
        *range(0x80, 0xA0),
        *range(0x202A, 0x202F),
        *range(0x2066, 0x206A),
    ]
)

# Tamanho do bloco de chave privada é limitado de propósito: `.*?` com DOTALL faria cada `BEGIN`
# sem `END` varrer o resto do texto — custo quadrático com uma página cheia deles.
_TOKENS = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.{0,5000}?-----END [A-Z ]*PRIVATE KEY-----"
    r"|\bsk-[A-Za-z0-9_-]{20,}"
    r"|\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{40,}"
    r"|\bAIza[0-9A-Za-z_-]{35}"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
    re.DOTALL,
)
_CNPJ = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)")
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_CARTAO = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_NAO_DIGITO = re.compile(r"\D")

_PARAM_SENSIVEL = re.compile(
    r"^(?:.*token|.*key|.*secret|code|api_?key|senha|password|passwd|pwd|sig|signature"
    r"|auth.*|.*session.*)$",
    re.IGNORECASE,
)
_CAMPO_SENSIVEL = re.compile(
    r"senha|password|passcode|passwd|token|otp|2fa|mfa|cvv|cvc|cart[aã]o|card|\bpin\b|secret"
    r"|segredo|c[oó]digo|code|verifica|api.?key|chave",
    re.IGNORECASE,
)
OCULTO = "[digitado — oculto]"


def limpar_controles(texto):
    """Remove caracteres de controle que um terminal interpretaria (cor, limpar tela, reordenar
    texto). `\\t` e `\\n` ficam: são estrutura legítima do texto da página."""
    return texto.translate(_CONTROLES) if texto else texto


def _luhn(digitos):
    total = 0
    for i, c in enumerate(reversed(digitos)):
        n = int(c)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _cpf_valido(d):
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if soma * 10 % 11 % 10 != int(d[n]):
            return False
    return True


def _cnpj_valido(d):
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
    for n in (12, 13):
        soma = sum(int(d[i]) * pesos[i + 13 - n] for i in range(n))
        resto = soma % 11
        if (0 if resto < 2 else 11 - resto) != int(d[n]):
            return False
    return True


def _cartao_valido(d):
    return 13 <= len(d) <= 19 and _luhn(d)


def _se_valido(valido, marca):
    """Troca o trecho por `marca` só se o dígito verificador bater — é isso que impede um
    telefone de 11 dígitos de virar "CPF"."""

    def trocar(m):
        return marca if valido(_NAO_DIGITO.sub("", m.group())) else m.group()

    return trocar


def redigir(texto):
    """Apaga tokens/chaves, CNPJ, CPF, cartão e SSN. A ordem importa: um CNPJ sem pontuação tem
    14 dígitos e poderia passar no Luhn como cartão se o cartão viesse antes. E-mails ficam
    visíveis (decisão do dono, 2026-09-26)."""
    if not texto:
        return texto
    texto = _TOKENS.sub(lambda m: "[chave]" if m.group().startswith("-----") else "[token]", texto)
    texto = _CNPJ.sub(_se_valido(_cnpj_valido, "[CNPJ]"), texto)
    texto = _CPF.sub(_se_valido(_cpf_valido, "[CPF]"), texto)
    texto = _CARTAO.sub(_se_valido(_cartao_valido, "[cartão]"), texto)
    return _SSN.sub("[SSN]", texto)


def _limpar_parametros(parte):
    pares = parse_qsl(parte, keep_blank_values=True)
    if not any(_PARAM_SENSIVEL.match(chave) for chave, _ in pares):
        return parte
    return urlencode(
        [(k, "[redigido]" if _PARAM_SENSIVEL.match(k) else v) for k, v in pares], safe="[]"
    )


def redigir_url(url):
    """Troca o valor de parâmetros sensíveis (token, key, code, senha...) na query e no
    fragmento — `#access_token=` é onde o OAuth implícito entrega o token. Sem parâmetro sensível,
    a URL volta intocada (re-serializar mudaria `%20` para `+` sem necessidade)."""
    if not url:
        return url
    try:
        partes = urlsplit(url)
    except ValueError:
        return redigir(url)
    query = _limpar_parametros(partes.query)
    fragmento = _limpar_parametros(partes.fragment)
    if query == partes.query and fragmento == partes.fragment:
        return url
    return urlunsplit(partes._replace(query=query, fragment=fragmento))


def mascarar_digitado(rotulo, texto):
    """O que o executor digitou num campo cujo rótulo parece sensível (senha, token, código 2FA,
    cartão...) some por inteiro; nos demais campos, só a redação normal."""
    if not texto:
        return texto
    if rotulo and _CAMPO_SENSIVEL.search(rotulo):
        return OCULTO
    return redigir(texto)


def pagina(page):
    """Cópia rasa da página com texto, título e URL redigidos. Nunca muta o original: o Jev usa
    esse dict (fingerprint) para conferir se a página ainda é a mesma antes de clicar."""
    return {
        **page,
        "text": redigir(page.get("text")),
        "title": redigir(page.get("title")),
        "url": redigir_url(page.get("url")),
    }


def _host(url):
    try:
        partes = urlsplit(url)
        if not partes.scheme and not url.startswith("//"):
            # "itau.com.br/x" sem esquema: sem isso o host sai vazio e o bloqueio é contornado.
            partes = urlsplit("//" + url)
        return (partes.hostname or "").rstrip(".")
    except ValueError:
        return ""


def dominio_bloqueado(url, bloqueados):
    """Devolve o domínio bloqueado que `url` atinge, ou None. Casa o domínio exato ou qualquer
    subdomínio dele — nunca um sufixo solto (`notitau.com.br` não é `itau.com.br`)."""
    host = _host(url or "")
    if not host:
        return None
    for dominio in bloqueados:
        if host == dominio or host.endswith("." + dominio):
            return dominio
    return None
