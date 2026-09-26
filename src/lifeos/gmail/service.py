"""Serviço do Gmail: leitura pela API oficial, sem texto para o modelo (isso é `gmail/tools.py`).

Mesmo desenho de `calendar/service.py`: devolve dados (`Email`, `EmailCompleto`, `RaioX`) ou
levanta um erro de domínio com `codigo`. Só leitura: o escopo é `gmail.readonly`.

Falha nunca vira vazio: uma busca em que parte dos e-mails não pôde ser lida devolve quantos
faltaram (`falharam`), e um raio-x que bateu no teto diz que é piso, não total (`no_teto`).

Pode ter `from __future__ import annotations`: nada daqui é registrado como tool do Gemini.
"""

from __future__ import annotations

import base64
import binascii
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parseaddr
from html import unescape
from html.parser import HTMLParser

from googleapiclient.errors import HttpError

# `_redacao` é stdlib pura e a única cópia da regra de caracteres de controle (ver D13).
from lifeos.browser._redacao import limpar_controles
from lifeos.config import TIMEZONE
from lifeos.gmail.oauth import get_gmail_service

MAX_RESULTADOS = 20  # por busca; a tool não pede mais que isto
MAX_CORPO = 4000  # caracteres do corpo devolvidos
MAX_RAIO_X = 200  # e-mails lidos por raio-x; acima disso o resultado é piso
LOTE = 25  # pedidos por lote; o Gmail recusa (429) lotes grandes demais em rajada
PAUSA_S = 1.0  # antes da única nova tentativa de quem falhou no lote

_CABECALHOS = ["From", "Subject", "Date", "List-Unsubscribe", "List-Id"]
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_CATEGORIAS = {
    "CATEGORY_PROMOTIONS": "promoções",
    "CATEGORY_UPDATES": "atualizações",
    "CATEGORY_SOCIAL": "social",
    "CATEGORY_FORUMS": "fóruns",
}


class ErroGmail(Exception):
    """Base dos erros de domínio. `codigo` identifica a falha; `dados` são campos extras."""

    codigo = "falha_api"

    def __init__(self, mensagem: str, **dados: object) -> None:
        super().__init__(mensagem)
        self.dados = dados


class SemLogin(ErroGmail):
    """Não deu para obter o token (sem client secret, permissão desmarcada, login revogado)."""

    codigo = "sem_login"


class EntradaInvalida(ErroGmail):
    codigo = "entrada_invalida"


class NaoEncontrado(ErroGmail):
    codigo = "nao_encontrado"


class FalhaDaApi(ErroGmail):
    codigo = "falha_api"


@dataclass(frozen=True)
class Email:
    id: str
    remetente: str
    endereco: str
    assunto: str
    data: str
    trecho: str
    nao_lido: bool
    categorias: tuple[str, ...] = ()
    lista: bool = False  # tem List-Unsubscribe/List-Id: newsletter, anúncio, lista de envio


@dataclass(frozen=True)
class Busca:
    emails: tuple[Email, ...]
    falharam: int  # e-mails achados que não puderam ser lidos
    mais: bool = False  # havia mais e-mails além do limite pedido


@dataclass(frozen=True)
class EmailCompleto:
    email: Email
    corpo: str
    truncado: bool
    anexos: int


@dataclass(frozen=True)
class Remetente:
    nome: str
    endereco: str
    total: int
    nao_lidos: int
    lista: bool
    promocoes: int


@dataclass(frozen=True)
class RaioX:
    dias: int
    lidos: int
    falharam: int
    no_teto: bool  # parou em MAX_RAIO_X com mais e-mails na janela: os números são piso
    remetentes: tuple[Remetente, ...]


# --- acesso à API ----------------------------------------------------------------------------


def _servico():
    try:
        return get_gmail_service()
    except Exception as exc:  # sem token utilizável, nada do Gmail funciona: erro de domínio
        raise SemLogin(str(exc)) from exc


def _executar(montar):
    """Toda chamada ao Google passa por aqui (a falha pode vir já ao montar o pedido)."""
    try:
        return montar().execute()
    except HttpError as exc:
        if getattr(exc.resp, "status", None) == 404:
            raise NaoEncontrado(str(exc)) from exc
        raise FalhaDaApi(str(exc)) from exc
    except Exception as exc:  # qualquer outra falha da API vira erro de domínio
        raise FalhaDaApi(str(exc)) from exc


def _ids(service, consulta: str, limite: int) -> tuple[list[str], bool]:
    """Ids da busca, paginando até `limite`. O bool diz se sobrou e-mail além do limite."""
    ids: list[str] = []
    pagina = None
    while True:
        pedido = {"userId": "me", "q": consulta, "maxResults": min(limite - len(ids), 500)}
        if pagina:
            pedido["pageToken"] = pagina
        resposta = _executar(lambda p=pedido: service.users().messages().list(**p))
        ids += [m["id"] for m in resposta.get("messages") or [] if m.get("id")]
        pagina = resposta.get("nextPageToken")
        if not pagina or len(ids) >= limite:
            return ids[:limite], bool(pagina) or len(ids) > limite


def _metadados(service, ids: list[str]) -> tuple[list[Email], int]:
    """Metadados em lotes. Quem falhar ganha uma nova tentativa depois de uma pausa; quem falhar
    de novo é contado e devolvido, nunca descartado em silêncio."""
    lidos: dict[str, dict] = {}
    falhas: list[str] = []

    def guardar(request_id, resposta, excecao):
        if excecao is None and isinstance(resposta, dict):
            lidos[request_id] = resposta
        else:
            falhas.append(request_id)

    pendentes = list(dict.fromkeys(ids))
    for tentativa in range(2):
        falhas.clear()
        for inicio in range(0, len(pendentes), LOTE):
            lote_ids = pendentes[inicio : inicio + LOTE]
            lote = service.new_batch_http_request(callback=guardar)
            for email_id in lote_ids:
                pedido = (
                    service.users()
                    .messages()
                    .get(userId="me", id=email_id, format="metadata", metadataHeaders=_CABECALHOS)
                )
                lote.add(pedido, request_id=email_id)
            try:
                lote.execute()
            except Exception:  # noqa: BLE001 - lote inteiro caiu: todos dele contam como falha
                falhas.extend(i for i in lote_ids if i not in lidos)
        pendentes = [i for i in dict.fromkeys(falhas) if i not in lidos]
        if not pendentes:
            break
        if tentativa == 0:
            time.sleep(PAUSA_S)
    return [_email_de(lidos[i]) for i in ids if i in lidos], len(pendentes)


# --- tradução do formato do Gmail --------------------------------------------------------------


def _cabecalho(cabecalhos: list[dict], nome: str) -> str:
    for item in cabecalhos or []:
        if str(item.get("name", "")).lower() == nome.lower():
            valor = str(item.get("value") or "")
            if "=?" in valor:  # RFC 2047 ("=?UTF-8?B?...?="), caso venha sem decodificar
                try:
                    valor = str(make_header(decode_header(valor)))
                except (ValueError, LookupError):
                    pass
            return valor
    return ""


def _data(interna) -> str:
    try:
        instante = datetime.fromtimestamp(int(interna) / 1000, TIMEZONE)
    except (TypeError, ValueError, OverflowError, OSError):
        return "sem data"
    return instante.strftime("%Y-%m-%d %H:%M")


def _email_de(mensagem: dict) -> Email:
    cabecalhos = (mensagem.get("payload") or {}).get("headers") or []
    rotulos = set(mensagem.get("labelIds") or [])
    nome, endereco = parseaddr(_cabecalho(cabecalhos, "From"))
    return Email(
        id=str(mensagem.get("id") or ""),
        remetente=limpar_controles(nome or endereco or "remetente desconhecido"),
        endereco=limpar_controles(endereco.lower()),
        assunto=limpar_controles(_cabecalho(cabecalhos, "Subject") or "(sem assunto)"),
        data=_data(mensagem.get("internalDate")),
        trecho=limpar_controles(unescape(mensagem.get("snippet") or "")),
        nao_lido="UNREAD" in rotulos,
        categorias=tuple(nome for chave, nome in _CATEGORIAS.items() if chave in rotulos),
        lista=bool(_cabecalho(cabecalhos, "List-Unsubscribe") or _cabecalho(cabecalhos, "List-Id")),
    )


def _charset(parte: dict) -> str:
    tipo = _cabecalho(parte.get("headers") or [], "Content-Type")
    achado = re.search(r'charset="?([\w.:-]+)"?', tipo, re.IGNORECASE)
    return achado.group(1) if achado else "utf-8"


def _decodificar(parte: dict) -> str:
    """`body.data` é base64url SEM padding, com os bytes no charset da parte."""
    dados = (parte.get("body") or {}).get("data") or ""
    try:
        bruto = base64.urlsafe_b64decode(dados + "=" * (-len(dados) % 4))
    except (binascii.Error, ValueError):
        return ""
    try:
        return bruto.decode(_charset(parte), errors="replace")
    except LookupError:  # charset que o Python não conhece
        return bruto.decode("utf-8", errors="replace")


class _SoTexto(HTMLParser):
    """HTML → texto: descarta script/style, quebra linha nos blocos. `convert_charrefs` (padrão)
    já resolve `&amp;` e afins."""

    _BLOCOS = frozenset({"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table"})
    _IGNORAR = frozenset({"script", "style", "head", "title"})

    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORAR:
            self._ignorando += 1
        elif tag in self._BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self._IGNORAR and self._ignorando:
            self._ignorando -= 1
        elif tag in self._BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._ignorando:
            self.partes.append(data)


def _html_para_texto(html: str) -> str:
    leitor = _SoTexto()
    leitor.feed(html)
    leitor.close()
    return "".join(leitor.partes)


def _partes(parte: dict):
    yield parte
    for filha in parte.get("parts") or []:
        yield from _partes(filha)


def _corpo(payload: dict) -> tuple[str, int]:
    """(texto, anexos). Prefere as partes text/plain; sem elas, converte as text/html."""
    planos, htmls, anexos = [], [], 0
    for parte in _partes(payload or {}):
        if parte.get("filename"):
            anexos += 1
            continue
        tipo = str(parte.get("mimeType") or "").lower()
        if tipo == "text/plain":
            planos.append(_decodificar(parte))
        elif tipo == "text/html":
            htmls.append(_decodificar(parte))
    texto = "\n".join(planos) if any(p.strip() for p in planos) else ""
    if not texto:
        texto = "\n".join(_html_para_texto(h) for h in htmls)
    linhas = (" ".join(linha.split()) for linha in texto.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip(), anexos


# --- operações ------------------------------------------------------------------------------


def perfil() -> tuple[str, int]:
    """(endereço da conta, total de mensagens) — a prova de que o login serve para o Gmail."""
    service = _servico()
    resposta = _executar(lambda: service.users().getProfile(userId="me"))
    return str(resposta.get("emailAddress") or ""), int(resposta.get("messagesTotal") or 0)


def buscar(consulta: str, max_resultados: int = 10) -> Busca:
    """Busca com a sintaxe do Gmail ("from:x newer_than:7d", "is:unread")."""
    limite = max(1, min(int(max_resultados), MAX_RESULTADOS))
    service = _servico()
    ids, mais = _ids(service, str(consulta or "").strip(), limite)
    emails, falharam = _metadados(service, ids)
    return Busca(tuple(emails), falharam, mais)


def consulta_de_hoje(agora: datetime | None = None) -> str:
    """Não lidos na caixa de entrada desde a meia-noite no fuso do Viking. `after:` com segundos
    desde a época, porque a data escrita (`after:2026/09/26`) o Gmail lê num fuso que não é o
    nosso."""
    agora = agora or datetime.now(TIMEZONE)
    meia_noite = agora.astimezone(TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    return f"is:unread in:inbox after:{int(meia_noite.timestamp())}"


def nao_lidos_de_hoje() -> Busca:
    return buscar(consulta_de_hoje(), MAX_RESULTADOS)


def ler(email_id: str) -> EmailCompleto:
    email_id = str(email_id or "").strip()
    if not _ID.fullmatch(email_id):
        raise EntradaInvalida("o ID do e-mail veio vazio ou com caracteres inesperados")
    service = _servico()
    mensagem = _executar(
        lambda: service.users().messages().get(userId="me", id=email_id, format="full")
    )
    corpo, anexos = _corpo(mensagem.get("payload") or {})
    corpo = limpar_controles(corpo)
    return EmailCompleto(
        email=_email_de(mensagem),
        corpo=corpo[:MAX_CORPO],
        truncado=len(corpo) > MAX_CORPO,
        anexos=anexos,
    )


def raio_x(dias: int = 30) -> RaioX:
    """Quem manda o quê na caixa de entrada, e quanto disso fica sem abrir. Só lê."""
    dias = max(1, min(int(dias), 365))
    service = _servico()
    ids, sobrou = _ids(service, f"in:inbox newer_than:{dias}d", MAX_RAIO_X)
    emails, falharam = _metadados(service, ids)
    grupos: dict[str, list[Email]] = {}
    for email in emails:
        grupos.setdefault(email.endereco or email.remetente, []).append(email)
    remetentes = sorted(
        (
            Remetente(
                nome=lista[0].remetente,
                endereco=lista[0].endereco,
                total=len(lista),
                nao_lidos=sum(e.nao_lido for e in lista),
                lista=any(e.lista for e in lista),
                promocoes=sum("promoções" in e.categorias for e in lista),
            )
            for lista in grupos.values()
        ),
        key=lambda r: (-r.nao_lidos, -r.total, r.endereco),
    )
    return RaioX(dias, len(emails), falharam, sobrou, tuple(remetentes))
