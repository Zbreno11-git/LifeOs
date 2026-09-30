"""Enviar e-mail (Sessão 8, D46): para a própria conta, livre; para qualquer outro, com o código.

O fluxo, e onde cada trava mora:
1. `novo(para, assunto, corpo)` e `resposta(email_id, corpo)`: chamados pelas tools do Gemini
   (`gmail/tools.py`) e pela CLI. O texto é validado (sem controle, bidi nem caractere invisível:
   o dono tem de ler exatamente o que sai) e vira um `Rascunho`.
   - Todos os destinatários são a conta do Gmail (`service.perfil`, decisão do dono): envia na
     hora, até `LIMITE_LIVRE` em 24 h.
   - Qualquer outro endereço: `confirmacao.propor` com o rascunho inteiro. O código vai só ao
     dono (`gmail/tools.py`, `lifeos/ao_dono.py`), e só com terminal interativo (pela nuvem, o
     do Mac, D60); nunca ao retorno da tool, ao registro nem por e-mail (D26, D52).
2. `confirmar(codigo)`: só o laço do chat e a CLI chamam (`tests/test_gmail_aprovacao.py`). Monta
   a mensagem **só** dos dados aprovados e envia por `service.enviar` (a única chamada de envio).

Na resposta, o destinatário sai do cabeçalho da original (`service.para_responder`): a tool nem
tem parâmetro de endereço, então um e-mail com injeção não escolhe para quem vai. Todo e-mail sai
com a marca `X-Viking` e a linha visível `ASSINATURA` (D53; dono, 2026-09-28).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage

from lifeos import ao_dono, aprovacoes, confirmacao, registro
from lifeos.gmail import formato, service

ACAO = aprovacoes.GMAIL_ENVIAR
LIMITE_LIVRE = 20  # e-mails para a própria conta em 24 h (dono, 2026-09-28)
JANELA_LIVRE = timedelta(hours=24)  # janela móvel: não depende do fuso de ninguém
MAX_PARA = 5
MAX_ASSUNTO = 200
MAX_CORPO = 5000  # o terminal mostra o corpo inteiro: sem limite, o dono não leria tudo
ASSINATURA = "Escrito pelo Viking (Assistente AI)"


class LimiteDiario(service.ErroGmail):
    codigo = "limite_diario"


SemTerminal = service.SemTerminal


@dataclass(frozen=True)
class Rascunho:
    para: tuple[str, ...]
    assunto: str
    corpo: str  # o texto pedido, sem a assinatura
    conversa: str = ""  # threadId, na resposta
    em_resposta_a: str = ""  # Message-ID da original
    referencias: str = ""
    original: str = ""  # de que conversa é a resposta, para o dono ver

    @property
    def texto_final(self) -> str:
        """O texto fonte com a assinatura: o que o dono vê no terminal e aprova."""
        return f"{self.corpo}\n\n— {ASSINATURA}\n"

    @property
    def texto_puro(self) -> str:
        """A parte `text/plain`: o mesmo texto, sem os marcadores de negrito e itálico."""
        return f"{formato.texto_puro(self.corpo)}\n\n— {ASSINATURA}\n"


@dataclass(frozen=True)
class Pedido:
    rascunho: Rascunho
    enviado: service.Enviado | None = None  # caminho livre: já foi
    codigo: str | None = None  # com código: só para o terminal do dono
    expira: datetime | None = None


@dataclass(frozen=True)
class Confirmado:
    rascunho: Rascunho
    enviado: service.Enviado


# --- o que o texto pode ter ------------------------------------------------------------------

# Aceitos além do texto comum: o ZWJ e os seletores de variação que as sequências de emoji usam.
_EMOJI = frozenset({chr(0x200D), chr(0xFE0E), chr(0xFE0F)})
_INVISIVEIS = frozenset({"Cc", "Cf", "Co", "Cn", "Cs", "Zl", "Zp"})


def _invisivel(c: str) -> bool:
    """Controle, bidi, formatação invisível (inclusive os caracteres de "tag" que escondem texto),
    uso privado, não atribuído, seletores de variação fora dos de emoji."""
    if c in _EMOJI:
        return False
    ponto = ord(c)
    return (
        unicodedata.category(c) in _INVISIVEIS
        or 0xFE00 <= ponto <= 0xFE0F
        or 0xE0100 <= ponto <= 0xE01EF
    )


def _texto(bruto, campo: str, maximo: int, *, multilinha: bool) -> str:
    """Recusa, não limpa: o que o dono lê no terminal tem de ser o que sai."""
    texto = str(bruto or "")
    if multilinha:
        texto = texto.replace("\r\n", "\n")
    texto = texto.strip()
    if not texto:
        raise service.EntradaInvalida(f"{campo} veio vazio")
    if len(texto) > maximo:
        raise service.EntradaInvalida(f"{campo} passa de {maximo} caracteres")
    permitidos = {"\n", "\t"} if multilinha else set()
    ruim = next((c for c in texto if c not in permitidos and _invisivel(c)), None)
    if ruim is not None:
        raise service.EntradaInvalida(
            f"{campo} tem um caractere invisível ou de controle (U+{ord(ruim):04X})"
        )
    return texto


def _sem_invisiveis(texto: str) -> str:
    """Para o que vem da mensagem original (o assunto de terceiro): limpo, e o dono vê o limpo."""
    return " ".join("".join(c for c in texto if not _invisivel(c)).split())


# "eu" (ou "mim") no `para` é a própria conta: o Gemini não sabe o endereço do dono e, no Mac
# (2026-09-28), perguntou duas vezes antes de um "manda pra mim". A conta vem do `getProfile`, e o
# endereço do dono não precisa ir ao modelo.
_EU = frozenset({"eu", "mim"})


def destinatarios(para, *, dono: str) -> tuple[str, ...]:
    brutos = (
        para if isinstance(para, list | tuple) else str(para or "").replace(";", ",").split(",")
    )
    enderecos = []
    for bruto in brutos:
        if not str(bruto).strip():
            continue
        endereco = dono if str(bruto).strip().lower() in _EU else service.endereco_valido(bruto)
        if endereco is None:
            raise service.EntradaInvalida(
                "endereço de e-mail inválido", endereco=_sem_invisiveis(str(bruto))[:80]
            )
        enderecos.append(endereco)
    enderecos = list(dict.fromkeys(enderecos))
    if not enderecos:
        raise service.EntradaInvalida("sem destinatário")
    if len(enderecos) > MAX_PARA:
        raise service.EntradaInvalida(f"no máximo {MAX_PARA} destinatários por e-mail")
    return tuple(enderecos)


# --- montar e enviar -------------------------------------------------------------------------


def montar(rascunho: Rascunho, *, de: str) -> bytes:
    """A mensagem inteira, com a marca: `multipart/alternative` com a parte texto e a HTML,
    as duas saídas do corpo aprovado por `formato` (Sessão 8b; nenhuma parte de anexo existe
    aqui). O `EmailMessage` recusa CR/LF num cabeçalho (medido no Python 3.12.3, 2026-09-28)."""
    mensagem = EmailMessage(policy=policy.SMTP)
    mensagem["From"] = de
    mensagem["To"] = ", ".join(rascunho.para)
    mensagem["Subject"] = rascunho.assunto
    if rascunho.em_resposta_a:
        mensagem["In-Reply-To"] = rascunho.em_resposta_a
        mensagem["References"] = " ".join(
            r for r in (rascunho.referencias, rascunho.em_resposta_a) if r
        )
    mensagem[service.MARCA] = service.MARCA_VALOR
    mensagem.set_content(rascunho.texto_puro)
    mensagem.add_alternative(
        formato.documento(rascunho.corpo, assinatura=ASSINATURA), subtype="html"
    )
    return mensagem.as_bytes()


def conta() -> str:
    """O endereço da própria conta do Gmail: o único que recebe sem código."""
    endereco = service.endereco_valido(service.perfil()[0])
    if endereco is None:
        raise service.FalhaDaApi("não consegui ler o endereço da conta do Gmail")
    return endereco


def _terminal() -> bool:
    """O código só se mostra a uma pessoa: no Mac, o terminal deste processo; na nuvem, o que o
    terminal do Mac declarou no pedido (`lifeos/ao_dono.py`)."""
    return ao_dono.interativo()


def usados_hoje(agora: datetime | None = None) -> int:
    """E-mails livres (para a conta) nas últimas 24 h, contando os que podem ter saído."""
    desde = (agora or datetime.now(UTC)) - JANELA_LIVRE
    return sum(
        1
        for acao in registro.contaveis("gmail.enviar", desde=desde)
        if acao.parametros.get("livre") is True
    )


def _enviar(rascunho: Rascunho, *, de: str, livre: bool) -> service.Enviado:
    return service.enviar(
        montar(rascunho, de=de),
        para=rascunho.para,
        assunto=rascunho.assunto,
        conversa=rascunho.conversa,
        livre=livre,
    )


def _decidir(rascunho: Rascunho, dono: str) -> Pedido:
    if set(rascunho.para) == {dono}:
        usados = usados_hoje()
        if usados >= LIMITE_LIVRE:
            raise LimiteDiario(
                f"já saíram {usados} e-mails para você nas últimas 24 h (o limite é {LIMITE_LIVRE})"
            )
        return Pedido(rascunho, enviado=_enviar(rascunho, de=dono, livre=True))
    if not _terminal():
        raise SemTerminal("sem um terminal interativo, não há como mostrar o código ao dono")
    proposta = confirmacao.propor(ACAO, asdict(rascunho))
    return Pedido(rascunho, codigo=proposta.codigo, expira=proposta.expira)


def novo(para, assunto, corpo) -> Pedido:
    dono = conta()
    rascunho = Rascunho(
        para=destinatarios(para, dono=dono),
        assunto=_texto(assunto, "o assunto", MAX_ASSUNTO, multilinha=False),
        corpo=_texto(corpo, "o texto", MAX_CORPO, multilinha=True),
    )
    return _decidir(rascunho, dono)


def resposta(email_id, corpo) -> Pedido:
    corpo = _texto(corpo, "o texto", MAX_CORPO, multilinha=True)
    original = service.para_responder(email_id)
    dono = conta()
    para = original.destino
    if para == (dono,):
        # Responder a uma mensagem que o próprio dono mandou vai a quem ele escreveu (o `To` dela,
        # sem ele), como no Gmail; sem ninguém além dele, fica com ele (uma nota para si).
        para = tuple(e for e in original.para_original if e != dono) or para
    assunto = _sem_invisiveis(original.assunto) or "(sem assunto)"
    if not assunto.lower().startswith("re:"):
        assunto = f"Re: {assunto}"
    rascunho = Rascunho(
        para=para,
        assunto=assunto[:MAX_ASSUNTO],
        corpo=corpo,
        conversa=original.conversa,
        em_resposta_a=original.message_id,
        referencias=original.referencias,
        original=f"“{_sem_invisiveis(original.assunto)[:80]}” de {original.remetente}",
    )
    return _decidir(rascunho, dono)


def confirmar(codigo: str) -> Confirmado:
    """Gasta o código e envia exatamente o que foi aprovado. O endereço da conta vem antes, para
    uma falha de login não gastar o código."""
    dono = conta()
    aprovado = confirmacao.consumir(ACAO, codigo)
    dados = aprovado.dados
    rascunho = Rascunho(**{**dados, "para": tuple(dados.get("para") or ())})
    try:
        enviado = _enviar(rascunho, de=dono, livre=False)
    except service.ErroGmail as exc:
        confirmacao.registrar(aprovado.id, {"erro": str(exc), "incerta": exc.incerta})
        raise
    confirmacao.registrar(aprovado.id, {"id": enviado.id, "conversa": enviado.conversa})
    return Confirmado(rascunho, enviado)
