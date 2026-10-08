"""Trava de segurança da suíte inteira: nenhum teste fala com o Google de verdade.

No Mac do dono os tokens OAuth existem — um teste que escapasse do fake criaria ou apagaria evento
na agenda real, ou leria a caixa de e-mail dele. Os testes trocam `get_calendar_service` /
`get_gmail_service` por fakes depois desta trava (fixtures `autouse` são montadas antes das que o
teste pede). A trava cobre também o fundo do poço (`google_auth.build` e o fluxo de login), para
um caminho novo que esqueça os dois nomes acima.
"""

import base64
import email
import email.policy
import json
import os
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

# Antes de qualquer `import lifeos`: a config lê `VIKING_DB_PATH` uma vez, ao ser importada. Com
# isto, até um módulo que escapasse do `banco.CAMINHO` trocado abaixo cairia num banco temporário,
# nunca no `data/viking.db` (defesa em profundidade; `tests/test_banco.py`).
os.environ["VIKING_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="viking-testes-")) / "viking.db")
# A nuvem (Sessão 10): o VPS tem o login do dono no gcloud e o ADC dele vivos. Nenhuma biblioteca
# do Google os acha durante os testes (uma pasta de configuração vazia), e o projeto e a URL do
# `.env` ficam vazios (o `load_dotenv` não sobrescreve o que já existe). O Firestore só abre no
# emulador (`store_firestore._cliente`).
os.environ["CLOUDSDK_CONFIG"] = tempfile.mkdtemp(prefix="viking-gcloud-vazio-")
for _nome in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "FIRESTORE_EMULATOR_HOST"):
    os.environ.pop(_nome, None)
for _nome in ("VIKING_NUVEM_PROJETO", "VIKING_NUVEM_URL"):
    os.environ[_nome] = ""
os.environ["VIKING_STORE"] = "sqlite"
# A memória do chat da nuvem (Sessão 13): o cliente falso dos testes de antes não tem o embedding.
# `tests/test_na_nuvem_memoria.py` liga `config.MEMORIA` nos dela.
os.environ["VIKING_MEMORIA"] = "0"

import httplib2
import pytest
from googleapiclient.errors import HttpError


def _proibido(*_args, **_kwargs):
    raise AssertionError("um teste tentou abrir o Google de verdade — use o fake")


@pytest.fixture(autouse=True)
def _sem_google_de_verdade(monkeypatch):
    monkeypatch.setattr("lifeos.calendar.oauth.get_calendar_service", _proibido)
    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service", _proibido)
    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service_sem_login", _proibido)
    monkeypatch.setattr("lifeos.gmail.oauth.get_gmail_service", _proibido)
    monkeypatch.setattr("lifeos.gmail.service.get_gmail_service", _proibido)
    monkeypatch.setattr("lifeos.google_auth.build", _proibido)
    monkeypatch.setattr(
        "lifeos.google_auth.InstalledAppFlow.from_client_secrets_file", staticmethod(_proibido)
    )
    # A chave da Pluggy alcança PIX: nenhum teste fala com a Pluggy de verdade.
    monkeypatch.setattr("lifeos.financas.pluggy._abrir", _proibido)
    monkeypatch.setattr("lifeos.financas.pluggy._esperar", lambda _s: None)


@pytest.fixture(autouse=True)
def _banco_de_teste(monkeypatch, tmp_path):
    """Nenhum teste no `viking.db` real, e um banco novo por teste. Os três módulos (lembretes,
    registro de ações, confirmações) abrem por `banco.conectar()`, então este nome basta: antes da
    Sessão 9 ele trocava dois caminhos e esquecia o dos lembretes, e cada `pytest` gravava um
    lembrete no banco do dono (erros, classe 6)."""
    monkeypatch.setattr("lifeos.banco.CAMINHO", tmp_path / "viking.db")


# --- o emulador do Firestore (Sessão 10) --------------------------------------------------------

_RAIZ = Path(__file__).resolve().parents[1]


def _jar_no_cache() -> bool:
    script = (_RAIZ / "scripts" / "emulador_firestore.sh").read_text()
    versao = script.split('VERSAO="', 1)[1].split('"', 1)[0]
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return (cache / "viking" / f"cloud-firestore-emulator-v{versao}.jar").is_file()


def _porta_livre() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def emulador_firestore():
    """Sobe o emulador uma vez por sessão, só para quem pede. Sem o jar (o Mac, que não instala o
    Firestore) o teste é pulado; com `VIKING_EXIGIR_EMULADOR=1` (o CI) pular vira falha, porque um
    contrato pulado é verde por outro motivo (erros, classe 4)."""
    import shutil
    import subprocess
    import time
    import urllib.request

    exigido = os.environ.get("VIKING_EXIGIR_EMULADOR") == "1"
    faltam = []
    if not _jar_no_cache() and not exigido:
        faltam.append("o jar do emulador (bash scripts/emulador_firestore.sh baixa)")
    if not shutil.which(os.environ.get("VIKING_JAVA", "java")):
        faltam.append("Java 21")
    try:
        import google.cloud.firestore  # noqa: F401
    except ImportError:
        faltam.append("o extra nuvem (uv sync --locked --extra dev --extra nuvem)")
    if faltam:
        motivo = "Firestore sem " + " e ".join(faltam)
        if exigido:
            pytest.fail(motivo)
        pytest.skip(motivo)

    host = f"127.0.0.1:{_porta_livre()}"
    processo = subprocess.Popen(
        ["bash", str(_RAIZ / "scripts" / "emulador_firestore.sh"), *host.split(":")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    prazo = time.monotonic() + 120  # o primeiro uso baixa o jar (137 MB)
    while True:
        try:
            with urllib.request.urlopen(f"http://{host}/", timeout=1) as resposta:
                if resposta.status == 200:
                    break
        except OSError:
            pass
        if processo.poll() is not None or time.monotonic() > prazo:
            processo.kill()
            pytest.fail(f"o emulador do Firestore não subiu (saída {processo.poll()})")
        time.sleep(0.2)
    os.environ["FIRESTORE_EMULATOR_HOST"] = host
    try:
        yield host
    finally:
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
        import signal

        os.killpg(processo.pid, signal.SIGTERM)
        processo.wait(timeout=30)


@pytest.fixture
def firestore_limpo(emulador_firestore):
    """Um banco vazio por teste: o endpoint do emulador que apaga todos os documentos."""
    import urllib.request

    from lifeos.reminders import store_firestore

    projeto = store_firestore._cliente().project
    pedido = urllib.request.Request(
        f"http://{emulador_firestore}/emulator/v1/projects/{projeto}/databases/(default)/documents",
        method="DELETE",
    )
    with urllib.request.urlopen(pedido, timeout=10):
        pass
    return store_firestore


@pytest.fixture(autouse=True)
def _trava_do_navegador_de_teste(monkeypatch, tmp_path):
    """A trava do navegador (Sessão 6) nunca em `data/` do repo: um teste segurando a trava real
    faria o `viking` do dono dizer "ocupado"."""
    monkeypatch.setattr("lifeos.browser.trava.TRAVA_PATH", tmp_path / "navegador.lock")


@pytest.fixture(autouse=True)
def _versao_do_jev_de_teste(monkeypatch, tmp_path):
    """A conferência da versão do Jev (Sessão 6) nunca no clone de quem roda os testes: o resultado
    dependeria da máquina. Aqui cai no caminho de "não consegui conferir" (pasta que não existe)."""
    monkeypatch.setattr("lifeos.browser.versao_jev.JEV_DIR", tmp_path / "sem-jev")


# --- Google Calendar falso, compartilhado pelos testes de calendário e do MCP -------------


class _Exec:
    def __init__(self, valor, erro=None):
        self._valor = valor
        self._erro = erro

    def execute(self):
        if self._erro is not None:
            raise self._erro
        return self._valor


class _Events:
    def __init__(self, evento, estado):
        self._evento = evento
        self._estado = estado

    def get(self, calendarId, eventId):
        if self._evento is None:
            raise RuntimeError("Not Found")
        return _Exec(self._evento)

    def delete(self, calendarId, eventId):
        if self._estado.get("falhar_delete"):
            raise RuntimeError("API fora do ar")
        # `erro_no_execute`: a falha vem no envio (como no Google); com `aplicar_antes`, o
        # efeito acontece e SÓ DEPOIS a resposta falha — o caso "incerta" do registro.
        erro = self._estado.get("erro_no_execute")
        if erro is None or self._estado.get("aplicar_antes"):
            self._estado["apagados"].append(eventId)
            if self._evento is not None:
                self._evento["status"] = "cancelled"  # como o Google: fica, cancelado
        return _Exec({}, erro)

    def patch(self, calendarId, eventId, body, **extra):
        if self._estado.get("falhar_patch"):
            raise RuntimeError("API fora do ar")
        self._estado["patches"].append((eventId, body))
        self._estado.setdefault("extras", []).append(("patch", extra))
        if self._evento is not None:  # como o Google: o evento muda
            for campo in ("start", "end", "status"):
                if campo in body:
                    self._evento[campo] = body[campo]
        return _Exec({"summary": self._evento.get("summary") if self._evento else None})

    def insert(self, calendarId, body, **extra):
        if self._estado.get("falhar_insert"):
            raise RuntimeError("API fora do ar")
        self._estado["enviados"].append(body)
        self._estado.setdefault("extras", []).append(("insert", extra))
        if self._estado.get("insert_aparece"):  # como o Google: o criado passa a ser listado
            self._estado["itens"].append({**body, "id": "novo123"})
        return _Exec({"id": "novo123", "htmlLink": "http://exemplo"})

    def list(self, calendarId, **kwargs):
        if self._estado.get("falhar_list"):
            raise RuntimeError("API fora do ar")
        self._estado["consultas"].append(kwargs)
        # Como o Google: 250 por página se não pedir outro número, e `nextPageToken` enquanto
        # houver mais (https://developers.google.com/workspace/calendar/api/v3/reference/events/list).
        if self._estado.get("paginas_vazias"):  # o Google pode: página vazia com mais por vir
            return _Exec({"items": [], "nextPageToken": "mais"})
        itens = self._estado["itens"]
        inicio = int(kwargs.get("pageToken") or 0)
        fim = inicio + int(kwargs.get("maxResults") or 250)
        resposta = {"items": itens[inicio:fim]}
        if fim < len(itens):
            resposta["nextPageToken"] = str(fim)
        return _Exec(resposta)


class _Service:
    def __init__(self, evento, estado):
        self._events = _Events(evento, estado)

    def events(self):
        return self._events


@pytest.fixture()
def calendario(monkeypatch):
    """Fake do Google no lugar do `get_calendar_service` que o serviço usa. `estado` registra o
    que foi enviado e permite configurar o evento do `get`, os itens do `list` e falhas."""
    # O fuso do dono no dublê: Brasília, porque os horários dos testes vêm com -03:00 e o VPS está em
    # UTC (o dono real está noutro fuso; os testes de fuso cobrem esse caso). Sem
    # isto a régua do fuso (`service.fuso_diferente`) recusaria todos eles.
    monkeypatch.setattr("lifeos.calendar.service.TIMEZONE", ZoneInfo("America/Sao_Paulo"))
    estado = {
        "apagados": [],
        "patches": [],
        "enviados": [],
        "consultas": [],
        "itens": [],
        "falhar_delete": False,
        "evento": {"summary": "Dentista", "start": {"date": "2026-10-01"}},
    }

    def fake_service():
        return _Service(estado["evento"], estado)

    monkeypatch.setattr("lifeos.calendar.service.get_calendar_service", fake_service)
    return estado


# --- Gmail falso, no formato da API real (users.messages list/get + lotes) ------------------


def corpo_b64(texto: str, charset: str = "utf-8") -> str:
    """Como o Gmail entrega `body.data`: base64url, SEM o padding `=` no fim."""
    return base64.urlsafe_b64encode(texto.encode(charset)).decode().rstrip("=")


def _erro_http(status: int) -> HttpError:
    return HttpError(httplib2.Response({"status": str(status)}), b"erro falso")


# Cota do Gmail real (developers.google.com/workspace/gmail/api/reference/quota, 2026-09-26). O
# fake cobra do mesmo jeito, num relógio falso que só anda quando o serviço "dorme": o 403 que o
# dono viu no Mac (207 e-mails lidos duas vezes num minuto) vira reproduzível aqui.
COTA_POR_MINUTO = 6000
_CUSTOS = {"list": 5, "get": 20, "batchModify": 50, "getProfile": 1, "send": 100}


def erro_de_cota() -> HttpError:
    """Como o Gmail responde quando a cota por minuto acaba (formato do erro visto no Mac; o
    texto de verdade traz o número do projeto, que não entra aqui)."""
    corpo = {
        "error": {
            "code": 403,
            "message": "Quota exceeded for quota metric 'Total Query Cost' and limit 'Units per "
            "minute per user' of service 'gmail.googleapis.com' for consumer "
            "'project_number:0'.",
            "errors": [
                {
                    "message": "Quota exceeded",
                    "domain": "usageLimits",
                    "reason": "rateLimitExceeded",
                }
            ],
            "status": "PERMISSION_DENIED",
        }
    }
    return HttpError(httplib2.Response({"status": "403"}), json.dumps(corpo).encode())


def _cobrar(estado: dict, operacao: str) -> None:
    agora = estado["relogio"]
    janela = [(t, u) for t, u in estado["gastos"] if t > agora - 60]
    custo = _CUSTOS[operacao]
    if sum(u for _, u in janela) + custo > estado["cota_por_minuto"]:
        estado["recusas_por_cota"] += 1
        estado["gastos"] = janela
        raise erro_de_cota()
    estado["gastos"] = [*janela, (agora, custo)]


class _GmailPedido:
    def __init__(self, acao):
        self._acao = acao

    def execute(self):
        return self._acao()


class _GmailLote:
    def __init__(self, estado, callback):
        self._estado, self._callback, self._itens = estado, callback, []

    def add(self, pedido, request_id):
        self._itens.append((request_id, pedido))

    def execute(self):
        self._estado["lotes"].append(len(self._itens))
        if self._estado["falhar_lote"]:
            raise RuntimeError("lote fora do ar")
        for request_id, pedido in self._itens:
            try:
                self._callback(request_id, pedido.execute(), None)
            except Exception as exc:  # noqa: BLE001 - o lote real entrega a exceção por item
                self._callback(request_id, None, exc)


def _de(mensagem: dict) -> str:
    for cabecalho in mensagem["payload"]["headers"]:
        if cabecalho["name"] == "From":
            return cabecalho["value"].lower()
    return ""


def _casa(termo: str, mensagem: dict) -> bool:
    """Um termo da busca do Gmail, no mínimo que os testes usam. `from:` casa por **pedaço** do
    cabeçalho, como o Gmail real — é o que obriga o serviço a conferir o remetente exato."""
    rotulos = set(mensagem["labelIds"])
    chave, _, valor = termo.lower().partition(":")
    if chave == "from":
        return valor in _de(mensagem)
    if chave == "in" and valor == "inbox":
        return "INBOX" in rotulos
    if chave == "is":
        return {"starred": "STARRED", "important": "IMPORTANT", "unread": "UNREAD"}.get(
            valor, ""
        ) in rotulos
    if chave == "has" and valor == "attachment":
        return any(p.get("filename") for p in mensagem["payload"]["parts"])
    return True  # newer_than:, after:, texto livre: o fake não filtra


def _filtra(consulta: str, mensagem: dict) -> bool:
    for termo in (consulta or "").split():
        negado = termo.startswith("-")
        if _casa(termo.lstrip("-"), mensagem) == negado:
            return False
    return True


class _GmailMensagens:
    def __init__(self, estado):
        self._estado = estado

    def list(self, userId, q, maxResults, pageToken=None):
        estado = self._estado

        def acao():
            _cobrar(estado, "list")
            estado["consultas"].append(q)
            if estado["falhar_list"]:
                raise RuntimeError("API fora do ar")
            consulta = q
            if estado["consulta_frouxa"]:  # simula o Gmail ignorando as exclusões (`-is:...`)
                consulta = " ".join(termo for termo in q.split() if not termo.startswith("-"))
            ids = [i for i, m in estado["mensagens"].items() if _filtra(consulta, m)]
            inicio = int(pageToken or 0)
            fim = inicio + min(maxResults, estado["por_pagina"])
            resposta = {"messages": [{"id": i, "threadId": i} for i in ids[inicio:fim]]}
            if fim < len(ids):
                resposta["nextPageToken"] = str(fim)
            return resposta

        return _GmailPedido(acao)

    def get(self, userId, id, format, metadataHeaders=None):
        estado = self._estado

        def acao():
            _cobrar(estado, "get")
            estado["gets"].append((id, format))
            if id in estado["falhar_sempre"]:
                raise _erro_http(500)
            if id in estado["falhar_uma_vez"]:
                estado["falhar_uma_vez"].discard(id)
                raise _erro_http(429)
            if id not in estado["mensagens"]:
                raise _erro_http(404)
            return estado["mensagens"][id]

        return _GmailPedido(acao)

    def batchModify(self, userId, body):
        estado = self._estado

        def acao():
            _cobrar(estado, "batchModify")
            if estado["falhar_modify"]:
                estado["falhar_modify"] -= 1
                raise _erro_http(500)
            estado["modificacoes"].append(body)
            for email_id in body.get("ids", []):
                mensagem = estado["mensagens"].get(email_id)
                if mensagem is None:
                    continue
                rotulos = [
                    r for r in mensagem["labelIds"] if r not in body.get("removeLabelIds", [])
                ]
                rotulos += [r for r in body.get("addLabelIds", []) if r not in rotulos]
                mensagem["labelIds"] = rotulos
            return ""

        return _GmailPedido(acao)

    def send(self, userId, body):
        """Como o Gmail real: `raw` em base64url; guarda a mensagem decodificada, e o `threadId`
        que veio. `falhar_send` = lista de status HTTP das próximas chamadas (500 = pode ter
        saído; 400 = recusado; 429 = cota)."""
        estado = self._estado

        def acao():
            _cobrar(estado, "send")
            if estado["falhar_send"]:
                status = estado["falhar_send"].pop(0)
                if status == 429:
                    raise erro_de_cota()
                raise _erro_http(status)
            bruto = base64.urlsafe_b64decode(body["raw"])
            mensagem = email.message_from_bytes(bruto, policy=email.policy.default)
            numero = len(estado["enviados"]) + 1
            estado["enviados"].append(
                {"mensagem": mensagem, "bruto": bruto, "threadId": body.get("threadId")}
            )
            return {"id": f"enviado{numero}", "threadId": body.get("threadId") or f"t{numero}"}

        return _GmailPedido(acao)


class _GmailServico:
    def __init__(self, estado):
        self._estado = estado
        self._mensagens = _GmailMensagens(estado)

    def users(self):
        return self

    def getProfile(self, userId):
        return _GmailPedido(lambda: {"emailAddress": "dono@example.com", "messagesTotal": 1234})

    def messages(self):
        return self._mensagens

    def new_batch_http_request(self, callback):
        return _GmailLote(self._estado, callback)


def mensagem_gmail(
    email_id: str,
    *,
    de: str = "Loja <ofertas@loja.example>",
    assunto: str = "Oferta",
    trecho: str = "trecho",
    rotulos: tuple = ("INBOX", "UNREAD"),
    lista: bool = False,
    partes: list | None = None,
    quando_ms: int = 1_790_000_000_000,
    extras: dict | None = None,
    conversa: str | None = None,
) -> dict:
    cabecalhos = [{"name": "From", "value": de}, {"name": "Subject", "value": assunto}]
    cabecalhos += [{"name": nome, "value": valor} for nome, valor in (extras or {}).items()]
    if lista:
        cabecalhos.append({"name": "List-Unsubscribe", "value": "<mailto:sair@loja.example>"})
    payload = {"mimeType": "multipart/alternative", "headers": cabecalhos, "parts": partes or []}
    return {
        "id": email_id,
        "threadId": conversa or email_id,
        "labelIds": list(rotulos),
        "snippet": trecho,
        "internalDate": str(quando_ms),
        "payload": payload,
    }


@pytest.fixture()
def gmail(monkeypatch):
    """Gmail falso no lugar do `get_gmail_service` que o serviço usa. `estado["mensagens"]` é a
    caixa (id → mensagem no formato da API, na ordem da mais nova para a mais velha, como o
    Gmail lista); o resto registra o que foi pedido e liga falhas. `send` guarda em `enviados`;
    não tem `trash` nem `delete`: uma chamada dessas no serviço vira `AttributeError` no teste."""
    estado = {
        "mensagens": {},
        "consultas": [],
        "gets": [],
        "lotes": [],
        "por_pagina": 100,
        "falhar_list": False,
        "falhar_lote": False,
        "falhar_sempre": set(),
        "falhar_uma_vez": set(),
        "consulta_frouxa": False,
        "relogio": 0.0,
        "gastos": [],  # (instante, unidades) cobrados pelo fake, como o Google
        "cota_por_minuto": COTA_POR_MINUTO,
        "recusas_por_cota": 0,
        "esperas": [],  # cada "dormida" do serviço, em segundos
        "avisos": [],  # o que o serviço mostrou no terminal enquanto esperava
        "falhar_modify": 0,  # quantas chamadas de batchModify falham antes de funcionar
        "modificacoes": [],  # corpo de cada batchModify que deu certo
        "falhar_send": [],  # status HTTP das próximas chamadas de send
        "enviados": [],  # cada e-mail que o send aceitou, decodificado
    }

    def nova(email_id, **campos):
        estado["mensagens"][email_id] = mensagem_gmail(email_id, **campos)
        return estado["mensagens"][email_id]

    def parte(tipo, texto, charset="utf-8", nome=""):
        return {
            "mimeType": tipo,
            "filename": nome,
            "headers": [{"name": "Content-Type", "value": f'{tipo}; charset="{charset}"'}],
            "body": {"data": corpo_b64(texto, charset)},
        }

    estado["nova"], estado["parte"] = nova, parte
    monkeypatch.setattr("lifeos.gmail.service.get_gmail_service", lambda: _GmailServico(estado))
    monkeypatch.setattr("lifeos.gmail.service.PAUSA_S", 0)

    # Relógio falso compartilhado pelo serviço e pelo fake; "dormir" só anda o relógio.
    def dormir(segundos):
        estado["esperas"].append(segundos)
        estado["relogio"] += segundos

    from lifeos.gmail import service

    monkeypatch.setattr(service, "_relogio", lambda: estado["relogio"])
    monkeypatch.setattr(service, "_dormir", dormir)
    monkeypatch.setattr(service, "_avisar", estado["avisos"].append)
    monkeypatch.setattr(service, "_COTA", service._Cota())
    return estado
