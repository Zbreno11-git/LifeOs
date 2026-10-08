"""Configuração central do Viking: variáveis de ambiente e caminhos padrão.

Ponto único de `load_dotenv()` — nenhum outro módulo deve chamar isso diretamente.
"""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = REPO_ROOT / "secrets"
DATA_DIR = REPO_ROOT / "data"

load_dotenv(REPO_ROOT / ".env")


def _path_env(name: str, default: Path) -> Path:
    """Resolve `name` como caminho. Um valor relativo é ancorado em REPO_ROOT, não no diretório de
    onde o comando foi chamado — sem isso, `viking` funcionava "por acidente" conforme o cwd (o
    `.env.example` recomenda justamente caminhos relativos: `./secrets/...`, `./jev-ultrafast`).
    """
    value = os.getenv(name)
    if not value:
        return default
    # expanduser() ANTES do join: "~/pasta" precisa virar a pasta pessoal real antes de ancorar em
    # REPO_ROOT, senão "~" some dentro do caminho como um caractere literal.
    caminho = Path(value).expanduser()
    return (REPO_ROOT / caminho).resolve()


def _timezone():
    """Fuso civil usado para resolver "amanhã" e montar janelas de dia no calendário.

    Sem `VIKING_TIMEZONE` usamos o offset local da máquina. Repare que isso é um offset **fixo**,
    não uma zona IANA: basta para o Brasil de hoje (sem horário de verão), mas não acompanha
    transições de DST. Quem precisar disso deve setar `VIKING_TIMEZONE=America/Sao_Paulo`.
    """
    nome = os.getenv("VIKING_TIMEZONE")
    if not nome:
        return datetime.now().astimezone().tzinfo
    try:
        return ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            f"VIKING_TIMEZONE={nome!r} não é uma zona IANA válida (ex.: America/Sao_Paulo)."
        ) from exc


TIMEZONE = _timezone()
# False: o Viking adivinhou o fuso pelo relógio da máquina (sem VIKING_TIMEZONE).
TIMEZONE_ESCOLHIDO = bool(os.getenv("VIKING_TIMEZONE"))


def _float_env(name: str, default: str, *, minimo: float = 0.0, inclusive: bool = False) -> float:
    """Lê `name` como float, com mensagem de erro que nomeia a variável (em vez do ValueError cru
    do Python) e rejeita NaN/infinito — `float("nan")` e `float("inf")` NÃO levantam ValueError
    normalmente, e um timeout/preço não-finito quebra comparações a jusante em silêncio (uma
    comparação com NaN nunca é verdadeira, então um deadline com NaN nunca dispara).
    """
    bruto = os.getenv(name, default)
    try:
        valor = float(bruto)
    except ValueError as exc:
        raise ValueError(f"{name}={bruto!r} não é um número válido.") from exc
    if not math.isfinite(valor):
        raise ValueError(f"{name}={bruto!r} precisa ser finito (nem NaN, nem infinito).")
    ok = valor >= minimo if inclusive else valor > minimo
    if not ok:
        op = ">=" if inclusive else ">"
        raise ValueError(f"{name}={bruto!r} precisa ser {op} {minimo}.")
    return valor


def _int_env(name: str, default: str, *, minimo: int = 0) -> int:
    """Como `_float_env`, mas para inteiros (sem noção de NaN/infinito nesse tipo)."""
    bruto = os.getenv(name, default)
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ValueError(f"{name}={bruto!r} não é um número inteiro válido.") from exc
    if valor <= minimo:
        raise ValueError(f"{name}={bruto!r} precisa ser > {minimo}.")
    return valor


def _lista_env(name: str) -> tuple[str, ...]:
    """Lista separada por vírgula, normalizada como domínio: minúsculas, sem espaço nem ponto final."""
    bruto = os.getenv(name) or ""
    return tuple(d for d in (p.strip().lower().rstrip(".") for p in bruto.split(",")) if d)


# Sites que o navegador do Viking recusa por padrão (decisão do dono, 2026-09-26): o Jev manda o
# texto da página ao OpenRouter a cada passo, e numa Chrome logada isso seria o e-mail ou o
# extrato inteiro. Casa o domínio e qualquer subdomínio dele.
_BLOQUEADOS_PADRAO = (
    # e-mail
    "mail.google.com",
    "gmail.com",
    "outlook.live.com",
    "outlook.office.com",
    "outlook.office365.com",
    "mail.yahoo.com",
    "mail.proton.me",
    "icloud.com",
    # bancos e pagamentos — Brasil
    "itau.com.br",
    "bb.com.br",
    "bradesco.com.br",
    "santander.com.br",
    "caixa.gov.br",
    "nubank.com.br",
    "inter.co",
    "bancointer.com.br",
    "c6bank.com.br",
    "btgpactual.com",
    "xpi.com.br",
    "sicoob.com.br",
    "sicredi.com.br",
    "mercadopago.com.br",
    "picpay.com",
    # bancos e pagamentos — EUA
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "citi.com",
    "capitalone.com",
    "americanexpress.com",
    "paypal.com",
    "venmo.com",
)


def _dominios_bloqueados(extras: tuple[str, ...], liberados: tuple[str, ...]) -> tuple[str, ...]:
    """Padrão + extras − liberados. A liberação remove a ENTRADA exata: liberar `www.itau.com.br`
    não libera `itau.com.br` (que continua casando o `www`)."""
    vistos = dict.fromkeys((*_BLOQUEADOS_PADRAO, *extras))
    return tuple(d for d in vistos if d not in liberados)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_PATH = _path_env(
    "VIKING_GOOGLE_CREDENTIALS_PATH", SECRETS_DIR / "google_credentials.json"
)
GOOGLE_TOKEN_PATH = _path_env("VIKING_GOOGLE_TOKEN_PATH", SECRETS_DIR / "google_token.json")
# Token próprio do Gmail: um login do Gmail que falhe ou seja revogado não derruba o calendário.
GMAIL_TOKEN_PATH = _path_env("VIKING_GMAIL_TOKEN_PATH", SECRETS_DIR / "google_token_gmail.json")
# O token do Drive do backup (Sessão 11c, D63): `drive.file`, outro login, outro arquivo.
DRIVE_TOKEN_PATH = _path_env("VIKING_DRIVE_TOKEN_PATH", SECRETS_DIR / "google_token_drive.json")
REMINDERS_DB_PATH = _path_env("VIKING_DB_PATH", DATA_DIR / "viking.db")

# Pluggy (finanças pelo Meu Pluggy, uso pessoal). Os IDs são os das conexões "espelho" criadas
# pelo conector MeuPluggy na aplicação do dono (`viking financas --conectar`), não os do site do
# Meu Pluggy. Ver docs/fontes/pluggy-open-finance.md.
PLUGGY_CLIENT_ID = os.getenv("PLUGGY_CLIENT_ID") or ""
PLUGGY_CLIENT_SECRET = os.getenv("PLUGGY_CLIENT_SECRET") or ""
PLUGGY_ITEM_IDS = _lista_env("PLUGGY_ITEM_IDS")

# Automação de navegador: o Viking chama o Jev por subprocesso, no ambiente do próprio Jev.
# As chaves do Jev (OPENROUTER_API_KEY, TEXT_MODEL_*) ficam no .env DELE — aqui só o ponteiro.
JEV_DIR = _path_env("VIKING_JEV_DIR", REPO_ROOT / "jev-ultrafast")
JEV_ENV_FILE = _path_env("VIKING_JEV_ENV_FILE", JEV_DIR / ".env")
UV_BIN = os.getenv("VIKING_UV_BIN", "uv")
BROWSER_TIMEOUT_S = _float_env("VIKING_BROWSER_TIMEOUT_S", "180")
# Teto de ações por tarefa. Abaixo do teto de 60 do próprio Jev: limita o custo do pior caso
# (uma tarefa em loop) sem cortar tarefas legítimas, que raramente passam de 15 passos.
BROWSER_MAX_ACOES = _int_env("VIKING_BROWSER_MAX_ACOES", "30")
BROWSER_BLOQUEADOS = _dominios_bloqueados(
    _lista_env("VIKING_BROWSER_BLOQUEADOS"), _lista_env("VIKING_BROWSER_LIBERADOS")
)

# Contabilidade de custo do Gemini: US$ por 1 milhão de tokens. Moram aqui, e não em `custos.py`,
# porque este é o único módulo que roda `load_dotenv()` — lidos lá, os overrides do .env chegavam
# tarde demais e eram silenciosamente ignorados.
PRECO_GEMINI_ENTRADA = _float_env("VIKING_PRECO_GEMINI_ENTRADA", "0.30", inclusive=True)
PRECO_GEMINI_SAIDA = _float_env("VIKING_PRECO_GEMINI_SAIDA", "2.50", inclusive=True)
# Teto de gasto do Gemini no chat da nuvem (D59, decisão do dono em 2026-09-30): US$ por mês e por
# dia, no fuso do dono, conferido antes de cada chamada ao modelo (`custos.Teto`). O alerta do GCP
# só avisa; este para. É estimativa pelas tarifas acima.
TETO_GEMINI_MES = _float_env("VIKING_TETO_GEMINI_MES", "10")
TETO_GEMINI_DIA = _float_env("VIKING_TETO_GEMINI_DIA", "1")
# As cotas do dia do chat da nuvem (D65, decisão do dono em 2026-10-07), além do teto: o gasto do
# modelo forte (US$) e as consultas de busca na web (`custos.Cotas`). 30 buscas por dia ficam
# abaixo das 5.000 grátis por mês dos modelos 3 (lido em 2026-10-07).
TETO_FORTE_DIA = _float_env("VIKING_TETO_FORTE_DIA", "0.30")
BUSCAS_DIA = _int_env("VIKING_BUSCAS_DIA", "30")


def _ligado(nome: str, padrao: str) -> bool:
    valor = (os.getenv(nome) or padrao).strip()
    if valor not in ("0", "1"):
        raise ValueError(f"{nome} tem de ser 0 ou 1")
    return valor == "1"


# A memória de fatos do chat da nuvem (Sessão 13, D66): ligada por padrão. Só os testes de antes da
# 13 a desligam (`tests/conftest.py`), porque o cliente falso deles não tem o embedding.
MEMORIA = _ligado("VIKING_MEMORIA", "1")

# Nuvem (Sessão 10, D58). O ID do projeto, a URL do motor e a conta de faturamento moram só no
# `.env`, nunca no repo. A região é decisão do dono (a casa dele, 2026-09-29).
NUVEM_PROJETO = os.getenv("VIKING_NUVEM_PROJETO") or ""
NUVEM_REGIAO = os.getenv("VIKING_NUVEM_REGIAO") or "southamerica-east1"
NUVEM_URL = (os.getenv("VIKING_NUVEM_URL") or "").rstrip("/")


def _store() -> str:
    """Onde moram os lembretes: `sqlite` (o `viking.db`, padrão) ou `firestore` (a nuvem)."""
    valor = os.getenv("VIKING_STORE") or "sqlite"
    if valor not in ("sqlite", "firestore"):
        raise ValueError(f"VIKING_STORE={valor!r}: use 'sqlite' ou 'firestore'.")
    return valor


STORE = _store()

# Segredos da nuvem (Sessão 10b, D59): o Secret Manager os entrega ao motor como arquivos de um
# volume, nunca como variável de ambiente. Este módulo é o único leitor. No Mac os caminhos ficam
# vazios e valem o `GEMINI_API_KEY` do `.env` e o token de `secrets/`.
GEMINI_CHAVE_ARQUIVO = os.getenv("VIKING_GEMINI_CHAVE_ARQUIVO") or ""
AGENDA_TOKEN_ARQUIVO = os.getenv("VIKING_AGENDA_TOKEN_ARQUIVO") or ""
GMAIL_TOKEN_ARQUIVO = os.getenv("VIKING_GMAIL_TOKEN_ARQUIVO") or ""  # Sessão 10c, D60
DRIVE_TOKEN_ARQUIVO = os.getenv("VIKING_DRIVE_TOKEN_ARQUIVO") or ""  # Sessão 11c, D63
# Só no serviço de finanças (Sessão 11d, D64): o motor nunca recebe este volume.
PLUGGY_ARQUIVO = os.getenv("VIKING_PLUGGY_ARQUIVO") or ""
# Só no motor: a URL do serviço de finanças, a quem ele pergunta (e a audience do token que manda).
FINANCAS_URL = (os.getenv("VIKING_FINANCAS_URL") or "").rstrip("/")
_SEGREDOS: dict[str, str] = {}


def _segredo(caminho: str) -> str:
    """O conteúdo de um arquivo de segredo, lido uma vez por processo (cada leitura do volume é um
    acesso cobrado no Secret Manager). Arquivo vazio ou ausente erra alto, sem mostrar valor."""
    if caminho not in _SEGREDOS:
        try:
            valor = Path(caminho).read_text().strip()
        except OSError as exc:
            raise RuntimeError(f"o segredo em {caminho} não abriu ({type(exc).__name__})") from None
        if not valor:
            raise RuntimeError(f"o segredo em {caminho} está vazio")
        _SEGREDOS[caminho] = valor
    return _SEGREDOS[caminho]


def gemini_chave() -> str:
    """A chave do Gemini: a do volume na nuvem, a do `.env` no Mac. Vazia = sem chave."""
    if GEMINI_CHAVE_ARQUIVO:
        return _segredo(GEMINI_CHAVE_ARQUIVO)
    return GEMINI_API_KEY or ""


def agenda_token() -> str:
    """O token da agenda (JSON) do volume da nuvem. Só existe na nuvem."""
    if not AGENDA_TOKEN_ARQUIVO:
        raise RuntimeError("VIKING_AGENDA_TOKEN_ARQUIVO vazio: o token da agenda não está aqui")
    return _segredo(AGENDA_TOKEN_ARQUIVO)


def gmail_no_motor() -> bool:
    """O motor tem o token do Gmail? O deploy só põe a variável quando o segredo tem versão
    (`scripts/nuvem.py`; Sessão 11, D61): sem ela, o chat da nuvem não tem as tools do Gmail."""
    return bool(GMAIL_TOKEN_ARQUIVO)


def gmail_token() -> str:
    """O token do Gmail (JSON) do volume da nuvem, subido do Mac (D57, D60). Só existe na nuvem."""
    if not GMAIL_TOKEN_ARQUIVO:
        raise RuntimeError("VIKING_GMAIL_TOKEN_ARQUIVO vazio: o token do Gmail não está aqui")
    return _segredo(GMAIL_TOKEN_ARQUIVO)


def drive_no_motor() -> bool:
    """O motor tem o token do Drive (o backup, Sessão 11c, D63)? Como o do Gmail: o deploy só põe a
    variável quando o segredo `viking-drive` tem versão."""
    return bool(DRIVE_TOKEN_ARQUIVO)


def drive_token() -> str:
    """O token do Drive (JSON) do volume da nuvem, subido do Mac (D63). Só existe na nuvem."""
    if not DRIVE_TOKEN_ARQUIVO:
        raise RuntimeError("VIKING_DRIVE_TOKEN_ARQUIVO vazio: o token do Drive não está aqui")
    return _segredo(DRIVE_TOKEN_ARQUIVO)


def financas_no_motor() -> bool:
    """O motor tem o serviço de finanças (Sessão 11d, D64)? O deploy só põe a URL dele quando o
    segredo `viking-pluggy` tem versão: sem ela, o chat da nuvem não tem as tools de finanças. O
    motor nunca tem a chave: pergunta ao serviço (`financas/remoto.py`)."""
    return bool(FINANCAS_URL)


def pluggy_segredo() -> str:
    """O JSON das credenciais da Pluggy (a chave, o segredo e os IDs das conexões) do volume do
    serviço de finanças, subido do Mac (D64). Só existe nesse serviço; quem o lê é
    `financas/pluggy.credenciais`."""
    if not PLUGGY_ARQUIVO:
        raise RuntimeError("VIKING_PLUGGY_ARQUIVO vazio: as credenciais da Pluggy não estão aqui")
    return _segredo(PLUGGY_ARQUIVO)
