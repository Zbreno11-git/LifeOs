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


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_CREDENTIALS_PATH = _path_env(
    "VIKING_GOOGLE_CREDENTIALS_PATH", SECRETS_DIR / "google_credentials.json"
)
GOOGLE_TOKEN_PATH = _path_env("VIKING_GOOGLE_TOKEN_PATH", SECRETS_DIR / "google_token.json")
REMINDERS_DB_PATH = _path_env("VIKING_DB_PATH", DATA_DIR / "viking.db")

# Automação de navegador: o Viking chama o Jev por subprocesso, no ambiente do próprio Jev.
# As chaves do Jev (OPENROUTER_API_KEY, TEXT_MODEL_*) ficam no .env DELE — aqui só o ponteiro.
JEV_DIR = _path_env("VIKING_JEV_DIR", REPO_ROOT / "jev-ultrafast")
JEV_ENV_FILE = _path_env("VIKING_JEV_ENV_FILE", JEV_DIR / ".env")
UV_BIN = os.getenv("VIKING_UV_BIN", "uv")
BROWSER_TIMEOUT_S = _float_env("VIKING_BROWSER_TIMEOUT_S", "180")
# Teto de ações por tarefa. Abaixo do teto de 60 do próprio Jev: limita o custo do pior caso
# (uma tarefa em loop) sem cortar tarefas legítimas, que raramente passam de 15 passos.
BROWSER_MAX_ACOES = _int_env("VIKING_BROWSER_MAX_ACOES", "30")

# Contabilidade de custo do Gemini: US$ por 1 milhão de tokens. Moram aqui, e não em `custos.py`,
# porque este é o único módulo que roda `load_dotenv()` — lidos lá, os overrides do .env chegavam
# tarde demais e eram silenciosamente ignorados.
PRECO_GEMINI_ENTRADA = _float_env("VIKING_PRECO_GEMINI_ENTRADA", "0.30", inclusive=True)
PRECO_GEMINI_SAIDA = _float_env("VIKING_PRECO_GEMINI_SAIDA", "2.50", inclusive=True)
