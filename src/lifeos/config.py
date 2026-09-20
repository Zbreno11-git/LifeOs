"""Configuração central do Viking: variáveis de ambiente e caminhos padrão.

Ponto único de `load_dotenv()` — nenhum outro módulo deve chamar isso diretamente.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = REPO_ROOT / "secrets"
DATA_DIR = REPO_ROOT / "data"

load_dotenv(REPO_ROOT / ".env")


def _path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


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
BROWSER_TIMEOUT_S = float(os.getenv("VIKING_BROWSER_TIMEOUT_S", "180"))
# Teto de ações por tarefa. Abaixo do teto de 60 do próprio Jev: limita o custo do pior caso
# (uma tarefa em loop) sem cortar tarefas legítimas, que raramente passam de 15 passos.
BROWSER_MAX_ACOES = int(os.getenv("VIKING_BROWSER_MAX_ACOES", "30"))
