"""Autenticação OAuth do Google Calendar.

Portado de `calendar-bot/oauth.py`. O fluxo em si mora em `lifeos/google_auth.py` desde a Sessão
Gmail (2026-09-26), compartilhado com o Gmail; aqui ficam só o escopo e o arquivo do token do
calendário. O nome `get_calendar_service` é o ponto que `calendar/service.py` chama e que a trava
de `tests/conftest.py` substitui — não renomear. Ver docs/fontes/google-calendar-api.md.
"""

from __future__ import annotations

from lifeos import google_auth
from lifeos.config import GOOGLE_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    return google_auth.servico("calendar", "v3", SCOPES, GOOGLE_TOKEN_PATH)


def get_calendar_service_sem_login():
    """O serviço só se o token salvo já vale agora; `None` em vez de renovar ou abrir o login."""
    creds = google_auth.credenciais_sem_login(SCOPES, GOOGLE_TOKEN_PATH)
    return google_auth.build("calendar", "v3", credentials=creds) if creds else None


if __name__ == "__main__":
    print("Testando autenticação no Google Calendar...")
    get_calendar_service()
    print("✅ Autenticação realizada com sucesso!")
