"""Serviço do Gmail: leitura pela API oficial, sem texto para o modelo (isso é `gmail/tools.py`).

Mesmo desenho de `calendar/service.py`: devolve dados (`Email`, `EmailCompleto`, `RaioX`,
`Selecao`) ou levanta um erro de domínio com `codigo`. A única escrita é tirar e devolver o
rótulo `INBOX` (arquivar/desarquivar, Sessão Gmail 2), e só `gmail/limpeza.py` a chama, depois
da aprovação do dono.

Falha nunca vira vazio: uma busca em que parte dos e-mails não pôde ser lida devolve quantos
faltaram (`falharam`), e um raio-x que bateu no teto diz que é piso, não total (`no_teto`).

Pode ter `from __future__ import annotations`: nada daqui é registrado como tool do Gemini.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
import time
import unicodedata
from collections import deque
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
PAUSA_S = 1.0  # antes da única nova tentativa de quem falhou no lote (falha que não é de cota)
TETO_LIMPEZA = 250  # e-mails por aprovação (D28, revista: ~1 min de conferência na cota abaixo)
LOTE_MODIFY = 1000  # máximo de IDs por batchModify

# Cota do Gmail, lida em developers.google.com/workspace/gmail/api/reference/quota (2026-09-26):
# 6.000 unidades por minuto por usuário; get = 20, list = 5, batchModify = 50. No Mac do dono, no
# mesmo dia, 207 e-mails lidos duas vezes em menos de um minuto voltaram 403 rateLimitExceeded.
COTA_POR_MINUTO = 6000
ORCAMENTO_POR_MINUTO = 4800  # 80%: outro processo do Viking pode estar gastando a mesma cota
CUSTO_GET, CUSTO_LIST, CUSTO_MODIFY = 20, 5, 50
ESPERAS_S = (2, 4, 8, 16, 32, 64)  # espera crescente no erro de cota (o Google recomenda ≤ 64 s)
_MOTIVOS_DE_LIMITE = frozenset({"rateLimitExceeded", "userRateLimitExceeded"})
MAX_REMETENTES_LIMPEZA = 10  # por proposta
MAX_LISTAGEM = 5000  # IDs listados por consulta da limpeza; acima disso a contagem é piso

_CABECALHOS = ["From", "Subject", "Date", "List-Unsubscribe", "List-Id"]
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
# Endereço exato, sem espaço nem operador: vira `from:<endereço>` numa consulta do Gmail, e
# `a@b.com OR in:anywhere` ampliaria a seleção para a conta inteira.
_ENDERECO = re.compile(r"[a-z0-9._%+-]{1,64}@[a-z0-9-]{1,63}(\.[a-z0-9-]{1,63}){1,8}")
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


class LimiteDoGmail(FalhaDaApi):
    """A cota por minuto acabou e continuou acabada depois de todas as esperas."""

    codigo = "limite_gmail"


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
    na_caixa: bool = False  # rótulo INBOX
    estrela: bool = False
    importante: bool = False


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


def _relogio() -> float:
    return time.monotonic()


def _dormir(segundos: float) -> None:
    time.sleep(segundos)


def _avisar(texto: str) -> None:
    """Espera longa aparece no terminal: sem isto, a limpeza parecia travada."""
    print(texto, file=sys.stderr, flush=True)


class _Cota:
    """Janela de 60 s com o que ESTE processo gastou; antes de passar do orçamento, espera. Não
    enxerga outro processo (um `--raio-x` rodado logo antes): para isso existe a espera no erro."""

    def __init__(self) -> None:
        self._gastos: deque[tuple[float, int]] = deque()

    def gastar(self, unidades: int) -> None:
        while True:
            agora = _relogio()
            while self._gastos and self._gastos[0][0] <= agora - 60:
                self._gastos.popleft()
            usado = sum(u for _, u in self._gastos)
            if not self._gastos or usado + unidades <= ORCAMENTO_POR_MINUTO:
                self._gastos.append((agora, unidades))
                return
            espera = self._gastos[0][0] + 60 - agora
            if espera >= 1:
                _avisar(f"⏳ Esperando {espera:.0f} s: o Gmail limita as consultas por minuto.")
            _dormir(max(espera, 0.01))


_COTA = _Cota()


def _motivos(exc: HttpError) -> set[str]:
    try:
        dados = json.loads(exc.content.decode("utf-8"))
        erros = dados["error"].get("errors") or []
    except (ValueError, KeyError, TypeError, AttributeError):
        return set()
    return {str(e.get("reason")) for e in erros if isinstance(e, dict)}


def _eh_limite(exc: BaseException | None) -> bool:
    if not isinstance(exc, HttpError):
        return False
    status = getattr(exc.resp, "status", None)
    return status == 429 or (status == 403 and bool(_motivos(exc) & _MOTIVOS_DE_LIMITE))


def _descrever(exc: BaseException) -> str:
    """O erro sem o corpo cru do Google, que traz o número do projeto OAuth e iria para o terminal
    e para o Gemini (visto no Mac do dono, 2026-09-26)."""
    if isinstance(exc, HttpError):
        motivos = ", ".join(sorted(_motivos(exc)))
        status = getattr(exc.resp, "status", "?")
        return f"HTTP {status}" + (f" ({motivos})" if motivos else "")
    return limpar_controles(str(exc))[:200]


_LIMITE = "o Gmail limitou as consultas por minuto; espere um minuto e tente de novo"


def _executar(montar, custo: int = CUSTO_LIST):
    """Toda chamada ao Google passa por aqui (a falha pode vir já ao montar o pedido). Gasta da
    cota antes; no erro de cota, espera cada vez mais (`ESPERAS_S`) e tenta de novo."""
    for espera in (*ESPERAS_S, None):
        _COTA.gastar(custo)
        try:
            return montar().execute()
        except HttpError as exc:
            if _eh_limite(exc) and espera is not None:
                _avisar(f"⏳ O Gmail pediu calma; tentando de novo em {espera} s.")
                _dormir(espera)
                continue
            if _eh_limite(exc):
                raise LimiteDoGmail(_LIMITE) from exc
            if getattr(exc.resp, "status", None) == 404:
                raise NaoEncontrado(_descrever(exc)) from exc
            raise FalhaDaApi(_descrever(exc)) from exc
        except Exception as exc:  # qualquer outra falha da API vira erro de domínio
            raise FalhaDaApi(_descrever(exc)) from exc
    raise AssertionError("inalcançável")  # pragma: no cover


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
    """Metadados em lotes, dentro da cota (cada e-mail custa `CUSTO_GET`). Quem falhar por cota
    espera cada vez mais e tenta de novo; por outro motivo, uma nova tentativa. Quem sobrar é
    contado e devolvido, nunca descartado em silêncio."""
    lidos: dict[str, dict] = {}
    falhas: dict[str, BaseException | None] = {}

    def guardar(request_id, resposta, excecao):
        if excecao is None and isinstance(resposta, dict):
            lidos[request_id] = resposta
        else:
            falhas[request_id] = excecao

    pendentes = list(dict.fromkeys(ids))
    esperas = iter(ESPERAS_S)
    outra_vez = True
    while pendentes:
        falhas.clear()
        for inicio in range(0, len(pendentes), LOTE):
            lote_ids = pendentes[inicio : inicio + LOTE]
            _COTA.gastar(CUSTO_GET * len(lote_ids))
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
            except Exception as exc:  # noqa: BLE001 - lote inteiro caiu: todos dele são falha
                falhas.update({i: exc for i in lote_ids if i not in lidos})
        pendentes = [i for i in falhas if i not in lidos]
        if not pendentes:
            break
        if any(_eh_limite(e) for e in falhas.values()):
            espera = next(esperas, None)
            if espera is None:
                break
            _avisar(f"⏳ O Gmail pediu calma; {len(pendentes)} e-mail(s) de novo em {espera} s.")
            _dormir(espera)
        elif outra_vez:
            outra_vez = False
            _dormir(PAUSA_S)
        else:
            break
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


# Enchimento invisível que newsletter põe na prévia (ZWNJ, ZWJ, BOM, soft hyphen, CGJ) para o
# cliente de e-mail não mostrar o resto do HTML: medido na caixa real do dono em 2026-09-26, o
# trecho de vários e-mails era só isso. Gasta token do Gemini e não diz nada.
def _sem_enchimento(texto: str) -> str:
    return "".join(c for c in texto if c != "\u034f" and unicodedata.category(c) != "Cf")


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
        trecho=" ".join(
            _sem_enchimento(limpar_controles(unescape(mensagem.get("snippet") or ""))).split()
        ),
        nao_lido="UNREAD" in rotulos,
        categorias=tuple(nome for chave, nome in _CATEGORIAS.items() if chave in rotulos),
        lista=bool(_cabecalho(cabecalhos, "List-Unsubscribe") or _cabecalho(cabecalhos, "List-Id")),
        na_caixa="INBOX" in rotulos,
        estrela="STARRED" in rotulos,
        importante="IMPORTANT" in rotulos,
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
    linhas = (" ".join(linha.split()) for linha in _sem_enchimento(texto).splitlines())
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
        lambda: service.users().messages().get(userId="me", id=email_id, format="full"),
        CUSTO_GET,
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


# --- limpeza: seleção, arquivar, desarquivar (Sessão Gmail 2) ---------------------------------

# O que nunca sai da caixa (D25). Cada motivo filtra a consulta E é conferido de novo no cliente,
# nos metadados de cada e-mail: uma camada falhar não arquiva o protegido.
_PROTECOES = (
    ("com estrela", "is:starred"),
    ("importantes", "is:important"),
    ("com anexo", "has:attachment"),
)


@dataclass(frozen=True)
class Grupo:
    """O que a limpeza faria com um remetente."""

    endereco: str
    nome: str
    sai: tuple[str, ...]  # IDs que seriam arquivados, dos mais antigos para os mais novos
    sobram: int  # arquivaveis que não couberam no teto desta aprovação
    protegidos: tuple[tuple[str, int], ...]  # (motivo, quantos); um e-mail pode ter dois motivos
    assuntos: tuple[str, ...]  # até 3, dos mais recentes que saem
    outro_remetente: int  # a busca trouxe, mas o remetente não é exatamente este endereço
    falharam: int  # não deu para conferir os metadados: ficam na caixa
    piso: bool  # alguma consulta bateu em MAX_LISTAGEM: as contagens são piso


@dataclass(frozen=True)
class Selecao:
    grupos: tuple[Grupo, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(i for g in self.grupos for i in g.sai)

    @property
    def sobram(self) -> int:
        return sum(g.sobram for g in self.grupos)


@dataclass(frozen=True)
class Modificacao:
    feitos: tuple[str, ...]
    falharam: tuple[str, ...]
    erro: str = ""


def enderecos_validos(remetentes) -> list[str]:
    """Endereços exatos, sem repetição, na ordem pedida. Qualquer um fora do formato recusa tudo:
    melhor não arquivar nada do que arquivar a lista errada."""
    itens = remetentes.split(",") if isinstance(remetentes, str) else list(remetentes or [])
    vistos: list[str] = []
    for item in itens:
        endereco = str(item).strip().strip("<>").lower()
        if not endereco:
            continue
        if not _ENDERECO.fullmatch(endereco):
            raise EntradaInvalida(
                "cada remetente tem de ser um endereço de e-mail exato, como aparece no raio-x",
                endereco=limpar_controles(endereco)[:80],
            )
        if endereco not in vistos:
            vistos.append(endereco)
    if not vistos:
        raise EntradaInvalida("nenhum remetente pedido")
    if len(vistos) > MAX_REMETENTES_LIMPEZA:
        raise EntradaInvalida(f"no máximo {MAX_REMETENTES_LIMPEZA} remetentes por vez")
    return vistos


def selecionar(remetentes, *, teto: int = TETO_LIMPEZA, somente=None) -> Selecao:
    """O que sairia da caixa de entrada: todos os e-mails de cada remetente, lidos ou não, menos
    os protegidos. Só lê. Passando do teto, vão os mais antigos de cada remetente, na ordem pedida.

    `somente`: na confirmação, restringe aos IDs aprovados — o que ganhou estrela depois fica, e o
    que chegou depois não entra. Nesse caminho **não relê e-mail por e-mail** (20 unidades de cota
    cada; ler duas vezes estourou a cota no Mac do dono): as duas camadas são buscas — a que exclui
    os protegidos e as que os listam, subtraídas. O remetente exato já foi conferido na proposta.
    """
    enderecos = enderecos_validos(remetentes)
    permitidos = set(somente) if somente is not None else None
    service = _servico()
    orcamento = max(0, min(int(teto), TETO_LIMPEZA))
    grupos = []
    for endereco in enderecos:
        base = f"from:{endereco} in:inbox"
        protegidos, com_anexo, todos_protegidos, piso = [], set(), set(), False
        for motivo, filtro in _PROTECOES:
            ids, cheio = _ids(service, f"{base} {filtro}", MAX_LISTAGEM)
            piso |= cheio
            protegidos.append((motivo, len(ids)))
            todos_protegidos |= set(ids)
            if filtro == "has:attachment":
                com_anexo = set(ids)
        filtros = " ".join(f"-{f}" for _, f in _PROTECOES)
        candidatos, cheio = _ids(service, f"{base} {filtros}", MAX_LISTAGEM)
        piso |= cheio
        # O Gmail lista do mais novo para o mais velho; os mais antigos saem primeiro.
        candidatos = [i for i in reversed(candidatos) if i not in com_anexo]
        if permitidos is not None:
            sai = [i for i in candidatos if i in permitidos and i not in todos_protegidos]
            sai = sai[:orcamento]
            orcamento -= len(sai)
            grupos.append(
                Grupo(
                    endereco=endereco,
                    nome=endereco,
                    sai=tuple(sai),
                    sobram=0,
                    protegidos=tuple((m, n) for m, n in protegidos if n),
                    assuntos=(),
                    outro_remetente=0,
                    falharam=0,
                    piso=piso,
                )
            )
            continue
        escolhidos = candidatos[:orcamento]
        emails, falharam = _metadados(service, escolhidos)
        sai, outro, nome = [], 0, ""
        for email in emails:
            if email.endereco != endereco:
                outro += 1
            elif email.na_caixa and not email.estrela and not email.importante:
                sai.append(email)
                nome = nome or email.remetente
        orcamento -= len(escolhidos)
        grupos.append(
            Grupo(
                endereco=endereco,
                nome=nome or endereco,
                sai=tuple(e.id for e in sai),
                sobram=len(candidatos) - len(escolhidos),
                protegidos=tuple((m, n) for m, n in protegidos if n),
                assuntos=tuple(e.assunto for e in reversed(sai[-3:])),
                outro_remetente=outro,
                falharam=falharam,
                piso=piso,
            )
        )
    return Selecao(tuple(grupos))


def _rotular(ids, corpo: dict) -> Modificacao:
    ids = [i for i in dict.fromkeys(ids) if _ID.fullmatch(str(i))]
    if not ids:
        return Modificacao((), ())
    service = _servico()
    feitos: list[str] = []
    for inicio in range(0, len(ids), LOTE_MODIFY):
        lote = ids[inicio : inicio + LOTE_MODIFY]
        try:
            _executar(
                lambda lote=lote: (
                    service.users().messages().batchModify(userId="me", body={"ids": lote, **corpo})
                ),
                CUSTO_MODIFY,
            )
        except ErroGmail as exc:
            return Modificacao(tuple(feitos), tuple(ids[len(feitos) :]), str(exc))
        feitos += lote
    return Modificacao(tuple(feitos), ())


def arquivar(ids) -> Modificacao:
    """Tira da caixa de entrada (continua em "Todos os e-mails"). Nada é apagado nem marcado."""
    return _rotular(ids, {"removeLabelIds": ["INBOX"]})


def desarquivar(ids) -> Modificacao:
    return _rotular(ids, {"addLabelIds": ["INBOX"]})
