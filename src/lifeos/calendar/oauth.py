"""Autenticação OAuth do Google Calendar.

Portado de `calendar-bot/oauth.py`: a lógica é a mesma, mas os caminhos de `credentials.json` e
`token.json` (antes relativos ao diretório de trabalho, só funcionavam por acidente) agora vêm de
`lifeos.config`, que resolve para `secrets/` por padrão. Ver docs/fontes/google-calendar-api.md.
"""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from lifeos.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    creds = None
    if GOOGLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not GOOGLE_CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Credenciais OAuth não encontradas em {GOOGLE_CREDENTIALS_PATH}. "
                    "Ver docs/fontes/google-calendar-api.md."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        GOOGLE_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOOGLE_TOKEN_PATH.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


if __name__ == "__main__":
    print("Testando autenticação no Google Calendar...")
    get_calendar_service()
    print("✅ Autenticação realizada com sucesso!")
