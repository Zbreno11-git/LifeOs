"""Login do Gmail: escopo de leitura, token próprio. O fluxo mora em `lifeos/google_auth.py`.

`get_gmail_service` é o ponto que `gmail/service.py` chama e que a trava de `tests/conftest.py`
substitui — não renomear. A limpeza da caixa (Sessão Gmail 2) troca o escopo por `gmail.modify`.
"""

from __future__ import annotations

from lifeos import google_auth
from lifeos.config import GMAIL_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    return google_auth.servico("gmail", "v1", SCOPES, GMAIL_TOKEN_PATH)
