"""Login OAuth do Google, compartilhado pelo calendário e pelo Gmail.

Cada serviço tem o próprio arquivo de token (o do Gmail em `google_token_gmail.json`): um login do
Gmail que falhe ou seja revogado não derruba o calendário. O `client_secret` é um só
(`GOOGLE_CREDENTIALS_PATH`), do mesmo app OAuth. Ver docs/fontes/google-calendar-api.md.

Duas conferências que a biblioteca não faz sozinha (medido em 2026-09-26):
- `Credentials.from_authorized_user_file(caminho, scopes)` guarda os escopos **pedidos**, e
  `has_scopes()` compara com eles — daria sempre verdadeiro. Quem diz para o que o token serve é o
  campo `scopes` gravado no próprio arquivo.
- Na tela do Google dá para desmarcar uma permissão e concluir o login mesmo assim; o que foi
  concedido de fato vem em `granted_scopes`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from lifeos.config import GOOGLE_CREDENTIALS_PATH


class PermissaoNaoConcedida(PermissionError):
    """O login terminou sem uma permissão que o Viking pediu (desmarcada na tela do Google)."""


def _escopos_do_arquivo(token_path: Path) -> set[str]:
    try:
        info = json.loads(token_path.read_text())
    except (OSError, ValueError):
        return set()
    escopos = info.get("scopes") if isinstance(info, dict) else None
    if isinstance(escopos, str):
        escopos = escopos.split()
    return set(escopos or [])


def _gravar_token(token_path: Path, conteudo: str) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    # 600: o refresh token dá acesso à conta; só o dono lê. `os.open` só aplica o modo a arquivo
    # novo, então o `chmod` cobre o token que já existia com 644.
    descritor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w") as arquivo:
        arquivo.write(conteudo)
    os.chmod(token_path, 0o600)


def credenciais(scopes: list[str], token_path: Path) -> Credentials:
    """Token válido para `scopes`: reaproveita o salvo, renova, ou abre o login no navegador."""
    creds = None
    if token_path.exists() and set(scopes) <= _escopos_do_arquivo(token_path):
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Revogado ou vencido de vez (senha trocada, acesso removido na conta Google). Sem
            # isto o token morto ficava no disco e toda tentativa, inclusive `--login`, falhava
            # igual: o único conserto era apagar o arquivo à mão.
            creds = None
    if not (creds and creds.valid):
        if not GOOGLE_CREDENTIALS_PATH.exists():
            raise FileNotFoundError(
                f"Credenciais OAuth não encontradas em {GOOGLE_CREDENTIALS_PATH}. "
                "Ver docs/fontes/google-calendar-api.md."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_PATH), scopes)
        creds = flow.run_local_server(port=0)
        concedidos = getattr(creds, "granted_scopes", None)
        faltando = set(scopes) - set(concedidos) if concedidos is not None else set()
        if faltando:
            raise PermissaoNaoConcedida(
                "O login terminou sem a permissão pedida (" + ", ".join(sorted(faltando)) + "). "
                "Refaça e deixe a caixa dessa permissão marcada na tela do Google."
            )

    _gravar_token(token_path, creds.to_json())
    return creds


def servico(api: str, versao: str, scopes: list[str], token_path: Path):
    return build(api, versao, credentials=credenciais(scopes, token_path))
