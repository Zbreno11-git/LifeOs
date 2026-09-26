"""Freio de cliques que agem sobre a conta do dono (Sessão 4b, auditoria §5.2).

O Jev dirige a Chrome **logada** do dono: um clique em "Sair" desloga em todos os aparelhos, e
"Excluir conta" ou "Finalizar compra" não têm volta. `_jev_subprocess.instalar_protecao()` chama
`motivo()` com a ação que o modelo escolheu, **antes** de o Jev executá-la, e recusa a tarefa
inteira se houver motivo — a aba fica aberta e o dono clica, se era isso mesmo.

Categorias decididas pelo dono em 2026-09-26: sair, mexer na conta, dinheiro. "Publicar em seu
nome" ficou de fora de propósito ("Enviar" é o botão de muita busca). Não há liberação: a
confirmação em duas etapas da Sessão 5 é o caminho para isso.

Só stdlib e nunca `lifeos`: roda dentro do ambiente do Jev, como módulo irmão de
`_jev_subprocess.py` (mesma regra de `_redacao.py`).

Três sinais, porque cada um pega o que os outros deixam passar:
- o **rótulo** da ação ("Sair", "Excluir minha conta", "Comprar agora");
- o **href** do link, para "sair" — um link só com ícone chega ao Jev com o rótulo genérico "link";
- o **texto do contêiner** (form/dialog/linha) para botões genéricos: em "Tem certeza que deseja
  excluir sua conta? [Excluir]" o botão final diz só "Excluir".

Erra para o lado de parar: um falso positivo custa uma tarefa interrompida com o botão nomeado na
mensagem; um falso negativo custa a conta. Ex.: "Sair do modo tela cheia" é recusado.
"""

import re
import unicodedata
from urllib.parse import parse_qsl, urlsplit

# Rótulos mais longos que isto são texto corrido (card de artigo, "Como excluir sua conta do
# Google: ajuda"), não um comando. Botões e links de ação têm poucas palavras.
MAX_PALAVRAS = 8
# Botões genéricos ("Excluir", "Confirmar", "Sim") só são julgados pelo contêiner se forem curtos.
MAX_PALAVRAS_GENERICO = 3
# O Jev corta o texto do contêiner em 6000 caracteres; o teto aqui só limita o trabalho.
MAX_ESCOPO = 6000

# Layout de `page["guards"][node]` no `snapshot.js` do Jev (`cache.guard`). O teste de contrato
# em `tests/test_jev_subprocess_main.py` confere estes índices no clone real.
GUARD_TAMANHO = 14
GUARD_HREF = 12
GUARD_ESCOPO = 13

# `fill`, `scroll` e `wait` não enviam nada (ver `motivo`).
JULGADAS = frozenset({"click", "select"})

_NAO_PALAVRA = re.compile(r"[\W_]+")
# Removidos sem virar espaço: senão um controle no meio de "Sair" partiria a palavra.
_INVISIVEIS = {"Cc", "Cf"}


def normalizar(texto) -> str:
    """Minúsculas, sem acento, sem caractere invisível (Unicode Cf: zero-width, bidi; Cc: controle),
    forma de compatibilidade (letra de largura total vira a comum) e pontuação virando espaço.
    `Sa` + zero-width + `ir`, `SAIR` e `Log-Out` viram `sair` e `log out`."""
    decomposto = unicodedata.normalize("NFKD", str(texto or ""))
    limpo = "".join(
        " " if c.isspace() else c
        for c in decomposto
        if c.isspace() or not (unicodedata.combining(c) or unicodedata.category(c) in _INVISIVEIS)
    )
    return " ".join(_NAO_PALAVRA.sub(" ", limpo.casefold()).split())


def _alternativas(palavras: list[str]) -> str:
    return "(?:" + "|".join(palavras) + ")"


def _perto(a: str, b: str) -> re.Pattern:
    """`a` e `b` como palavras inteiras, em qualquer ordem, com até 3 palavras entre eles.
    Repetição limitada de propósito: o contêiner tem até 6000 caracteres."""
    gap = r"(?: \S+){0,3} "
    return re.compile(rf"\b{a}{gap}{b}\b|\b{b}{gap}{a}\b")


_REMOVER = _alternativas(
    [
        "excluir",
        "exclua",
        "exclusao",
        "apagar",
        "apague",
        "deletar",
        "delete",
        "deletion",
        "remover",
        "remova",
        "remove",
        "encerrar",
        "encerre",
        "encerramento",
        "close",
        "closure",
        "fechar",
        "desativar",
        "desative",
        "deactivate",
        "cancelar",
        "cancele",
        "cancelamento",
        "cancel",
        "cancellation",
    ]
)
_CONTA = _alternativas(
    [
        "conta",
        "account",
        "perfil",
        "profile",
        "assinatura",
        "subscription",
        "plano",
        "plan",
        "membership",
        "inscricao",
    ]
)
_TROCAR = _alternativas(
    [
        "trocar",
        "troque",
        "alterar",
        "altere",
        "mudar",
        "mude",
        "redefinir",
        "redefina",
        "change",
        "reset",
        "update",
        "atualizar",
        "desativar",
        "desligar",
        "disable",
        "remover",
        "remove",
    ]
)
_SEGURANCA = _alternativas(
    [
        "senha",
        "password",
        "e mail",
        "email",
        "2fa",
        "telefone",
        "phone",
        "autenticacao (?:em|de) dois fatores",
        "two factor",
        "verificacao em duas etapas",
        "(?:2|two) step",
    ]
)

_SAIR_ROTULO = [
    re.compile(r"\b(?:log ?out|log ?off|sign ?out|desconectar|desconecte se)\b"),
    re.compile(r"\b(?:encerrar|terminar|finalizar) sessao\b"),
    re.compile(r"^sair\b"),
    re.compile(r"\bsair (?:da|de) (?:sua |minha )?(?:conta|sessao)\b|\bsair de todos\b"),
]
# Trecho INTEIRO do caminho (ou um parâmetro), nunca substring: "/blog/como-sair-da-divida" é um
# artigo, "/logout" e "/conta/sair.php" não.
_SAIR_HREF = re.compile(r"(?:log[-_]?out|log[-_]?off|sign[-_]?out|signoff|sair|desconectar)")

_CONTA_REGRAS = [_perto(_REMOVER, _CONTA), _perto(_TROCAR, _SEGURANCA)]

_DINHEIRO_ROTULO = [
    re.compile(
        r"\b(?:comprar|compre|buy|purchase|pagar|pague|pay|checkout|transferir|transfira|transfer"
        r"|pix|doar|doe|donate|assine|subscribe)\b"
    ),
    re.compile(
        r"\b(?:finalizar|concluir|fechar|confirmar|place|confirm|complete|submit)"
        r" (?:(?:a|o|seu|sua|meu|minha|your|my) )?(?:compra|pedido|order|purchase|pagamento|payment)\b"
    ),
    re.compile(r"\benviar dinheiro\b|\bsend money\b|\bassinar (?:agora|ja|plano|premium)\b"),
]
_DINHEIRO_ESCOPO = re.compile(
    r"\b(?:comprar|compra|pagar|pagamento|payment|checkout|pedido|order|cartao de credito"
    r"|credit card|pix|boleto|transferencia|transfer)\b"
)

# Botões genéricos, julgados pelo contêiner. Remover só consulta o contexto de conta ("Excluir" a
# tarefa "comprar pão" não é gastar dinheiro); confirmar consulta os dois.
_GENERICOS_REMOVER = frozenset(
    [
        "excluir",
        "exclua",
        "delete",
        "remover",
        "remove",
        "apagar",
        "encerrar",
        "desativar",
        "deactivate",
        "cancelar",
        "cancel",
    ]
)
_GENERICOS_CONFIRMAR = frozenset(
    [
        "confirmar",
        "confirm",
        "concluir",
        "finalizar",
        "complete",
        "sim",
        "yes",
        "ok",
        "continuar",
        "continue",
        "prosseguir",
        "proceed",
        "enviar",
        "submit",
    ]
)


def _palavras(texto: str) -> int:
    return texto.count(" ") + 1 if texto else 0


def _generico(rotulo: str) -> str | None:
    """ "remover", "confirmar" ou None, pela primeira palavra de um rótulo curto."""
    palavras = rotulo.split()
    if not 0 < len(palavras) <= MAX_PALAVRAS_GENERICO:
        return None
    if palavras[0] in _GENERICOS_REMOVER:
        return "remover"
    return "confirmar" if palavras[0] in _GENERICOS_CONFIRMAR else None


def contexto(guard) -> tuple[str, str]:
    """(href, texto do contêiner) de um item de `page["guards"]`. `None` é legítimo (o Jev devolve
    `null` para elemento que sumiu da tela). Qualquer outra forma é o layout do Jev que mudou:
    `ValueError`, e quem chama recusa navegar em vez de frear às cegas."""
    if guard is None:
        return "", ""
    if not isinstance(guard, list) or len(guard) != GUARD_TAMANHO:
        raise ValueError(f"layout de guard inesperado: {type(guard).__name__}")
    href, escopo = guard[GUARD_HREF], guard[GUARD_ESCOPO]
    return (href if isinstance(href, str) else ""), (escopo if isinstance(escopo, str) else "")


def _href_de_sair(href: str) -> bool:
    if not href:
        return False
    try:
        partes = urlsplit(href.casefold())
    except ValueError:
        return False
    trechos = [t.rsplit(".", 1)[0] for t in partes.path.split("/")]
    for chave, valor in parse_qsl(partes.query, keep_blank_values=True):
        trechos += [chave, valor]
    return any(_SAIR_HREF.fullmatch(t) for t in trechos)


def _categoria_do_rotulo(rotulo: str) -> str | None:
    if _palavras(rotulo) > MAX_PALAVRAS:
        return None
    if any(r.search(rotulo) for r in _SAIR_ROTULO):
        return "sair"
    if any(r.search(rotulo) for r in _CONTA_REGRAS):
        return "conta"
    if any(r.search(rotulo) for r in _DINHEIRO_ROTULO):
        return "dinheiro"
    return None


def motivo(acao: dict, guard=None) -> str | None:
    """`"<categoria>: <rótulo>"` se a ação age sobre a conta; `None` se pode seguir.

    Julga `click` e `select`. O `select` porque o Jev dispara `change` ao escolher a opção, e o site
    pode enviar nesse evento (menu "Ações → Excluir conta"); o rótulo dele é "Campo → Opção". O
    `fill` não: o Jev não aperta Enter depois de digitar, então o envio seria o clique seguinte.
    """
    if (acao or {}).get("kind") not in JULGADAS:
        return None
    original = str(acao.get("label") or "")
    rotulo = normalizar(original)
    href, escopo_bruto = contexto(guard)
    # O rótulo vai na mensagem de erro: sem os invisíveis, que serviam justamente para disfarçar.
    visivel = (c for c in original if c.isspace() or unicodedata.category(c) not in _INVISIVEIS)
    exibido = " ".join("".join(visivel).split())[:80]

    # No `select` o Jev monta "Campo → Opção": a opção é julgada também sozinha ("Conta → Sair").
    candidatos = [rotulo]
    if acao.get("kind") == "select" and " → " in original:
        candidatos.append(normalizar(original.rsplit(" → ", 1)[1]))
    categoria = next(filter(None, map(_categoria_do_rotulo, candidatos)), None)
    if categoria is None and _href_de_sair(href):
        categoria = "sair"
    if categoria:
        return f"{categoria}: {exibido}"

    generico = _generico(rotulo)
    if generico and escopo_bruto:
        escopo = normalizar(escopo_bruto[:MAX_ESCOPO])
        if any(r.search(escopo) for r in _CONTA_REGRAS):
            return f"conta: {exibido}"
        if generico == "confirmar" and _DINHEIRO_ESCOPO.search(escopo):
            return f"dinheiro: {exibido}"
    return None
