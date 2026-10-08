"""O que pode virar fato da memória (Sessão 13, D66): um filtro determinístico, puro, sem rede.

O extrator (`extrator.py`) já recebe a regra no texto dele, mas **o modelo não é a única
barreira**: tudo o que ele propõe passa por aqui antes de gravar, e o `viking memoria --corrigir`
também. O dono decidiu em 2026-10-08 o que nunca se anota: valores das finanças, dados de outras
pessoas e planos com data, além de senha e código, sempre. E a D48 manda recusar a forma de ordem
("sempre que…, envie…"): é o resto de risco de um e-mail que o dono cola na mensagem.

Cada regra foi escrita com a lista dos vizinhos legítimos e dos disfarces ao lado
(`tests/test_memoria_regras.py`, erros classe 7): "toda segunda" é rotina e passa, "segunda que
vem" é plano e não passa; "faz aniversário em março" passa, "dia 20 de março" não.

O texto é lido normalizado (NFKC, sem os caracteres invisíveis de formatação): letras de largura
dupla e um hífen invisível no meio de "envie" não escapam da regra.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
import unicodedata

from lifeos.browser._redacao import limpar_controles

MAX_TEXTO = 200  # caracteres por fato: uma frase, não um e-mail
MAX_NOVOS = 3  # fatos novos por mensagem do dono
POR_TURNO = 8  # os fatos que entram numa resposta (o dono, 2026-10-08)

_DIAS = r"(?:segunda|ter[cç]a|quarta|quinta|sexta)(?:-feira)?|s[aá]bado|domingo"
_MESES = (
    r"janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
)

# (motivo, padrão): o motivo vai ao log de quem chama só como contagem, nunca com o texto.
_RECUSAS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "senha ou código",
        re.compile(r"\b(?:senha|password|pin|token|c[oó]digo|chave de acesso|2fa)\b"),
    ),
    (
        "valor em dinheiro",
        re.compile(
            r"(?:r\$|us\$|u\$s|€|£|\$)\s*\d"
            r"|\d[\d.,]*\s*(?:reais|real|d[oó]lares|d[oó]lar|euros?)\b"
            # "8 mil", "300 pila" sozinhos são ambíguos ("10 mil passos"): só com a palavra de
            # dinheiro na mesma frase
            r"|\b(?:sal[aá]rio|saldo|fatura|d[ií]vida|empr[eé]stimo|investimento|renda|"
            r"aluguel|gast[aeo]\w*|poupan[cç]a|conta\s+banc[aá]ria)\b[^.]*\d"
            r"|\d[^.]*\b(?:sal[aá]rio|saldo|fatura|d[ií]vida|empr[eé]stimo|investimento|renda|"
            r"aluguel|poupan[cç]a)\b"
        ),
    ),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("telefone ou documento", re.compile(r"(?:\d[\s().-]*){8,}")),
    (
        "endereço",
        re.compile(
            r"\b(?:rua|avenida|av\.|alameda|travessa|rodovia|estrada|apto|apartamento|cep)"
            r"[^\n]{0,40}?\d"
        ),
    ),
    (
        "data marcada",
        re.compile(
            r"\bdia\s+\d{1,2}\b"
            r"|\b\d{1,2}\s*/\s*\d{1,2}\b"
            rf"|\b\d{{1,2}}\s+de\s+(?:{_MESES})\b"
            r"|\b(?:amanh[aã]|ontem|hoje|depois de amanh[aã]|anteontem)\b"
            r"|\b(?:semana|m[eê]s|ano)\s+que\s+vem\b"
            r"|\bpr[oó]xim[oa]\s+(?:semana|m[eê]s|ano|" + _DIAS + r")\b"
            rf"|\b(?:{_DIAS})\s+que\s+vem\b"
            rf"|\b(?:nest[ea]|ness[ea]|est[ea]|ess[ea])\s+(?:{_DIAS}|semana|m[eê]s)\b"
            r"|\bfim\s+d[oe]\s+(?:m[eê]s|semana|ano)\b"
            r"|\bdaqui\s+a\s+\w+\s+(?:dias?|semanas?|meses|m[eê]s|horas?)\b"
        ),
    ),
    (
        "forma de ordem",
        re.compile(
            # uma condição seguida de uma ação que o Viking poderia fazer
            # ("se" só como condição: "se o usuário…", "se pedir"; não o reflexivo "se chama")
            r"\b(?:quando|sempre\s+que|toda\s+vez\s+que|caso|se\s+(?:o|a|os|as|eu|ele|ela|"
            r"voc[eê]|algu[eé]m|algum|alguma|um|uma|\w+(?:r|rem))\b)[^.]*\b(?:envi|mand|encaminh|"
            r"apag|exclu|delet|remov|transfer|pag|pix|arquiv|confirm|compartilh|cancel|compr|"
            r"clic|execut|respond|ignor|aprov|copi)\w*"
            # ou uma ordem dirigida ao assistente
            r"|\b(?:voc[eê]|o\s+assistente|o\s+viking|a\s+ia)\s+(?:deve|precisa|tem\s+que|"
            r"n[aã]o\s+deve)\b"
            r"|\bignor[ea]\w*\s+(?:as|todas|tudo|qualquer|o\s+que)\b"
            r"|\b(?:sempre|nunca)\s+(?:envie|mande|encaminhe|apague|pague|transfira|confirme|"
            r"pergunte|aprove|responda|copie|clique)\b"
        ),
    ),
)

_INVISIVEIS = {c: None for c in range(0x110000) if unicodedata.category(chr(c)) == "Cf"}


def normalizar(texto: str) -> str:
    """O texto como a regra o lê: NFKC, sem os invisíveis de formatação, minúsculo, espaços
    simples."""
    texto = unicodedata.normalize("NFKC", texto).translate(_INVISIVEIS)
    return " ".join(texto.lower().split())


def limpo(texto: str) -> str:
    """O texto como se grava: sem controle de terminal nem invisíveis, espaços simples."""
    texto = limpar_controles(unicodedata.normalize("NFC", texto or "")).translate(_INVISIVEIS)
    return " ".join(texto.split())


def recusa(texto: str) -> str | None:
    """Por que este texto não pode virar fato (o motivo, sem o texto), ou `None` se pode."""
    gravado = limpo(texto)
    if not gravado:
        return "vazio"
    if len(gravado) > MAX_TEXTO:
        return f"mais de {MAX_TEXTO} caracteres"
    lido = normalizar(gravado)
    for motivo, padrao in _RECUSAS:
        if padrao.search(lido):
            return motivo
    return None
