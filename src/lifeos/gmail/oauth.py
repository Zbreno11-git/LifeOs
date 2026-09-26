"""Login do Gmail: token próprio; o fluxo mora em `lifeos/google_auth.py`.

`get_gmail_service` é o ponto que `gmail/service.py` chama e que a trava de `tests/conftest.py`
substitui — não renomear.

Escopo `gmail.modify` desde a Sessão Gmail 2 (arquivar). É o menor que tira e-mail da caixa, mas
autoriza também enviar e mover para a lixeira (medido em `gmail.v1.json`, 2026-09-26; D29). O
código só lê, arquiva e desarquiva: `tests/test_gmail_limpeza.py` falha se aparecer outra chamada.
Nunca o escopo de acesso total (o único que apaga de vez).
"""

from __future__ import annotations

from lifeos import google_auth
from lifeos.config import GMAIL_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service():
    return google_auth.servico("gmail", "v1", SCOPES, GMAIL_TOKEN_PATH)
