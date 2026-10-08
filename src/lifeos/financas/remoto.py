"""O motor pergunta ao serviço de finanças (Sessão 11d, D64): o motor nunca vê a chave da Pluggy.

O serviço (`nuvem/financas.py`, outro Cloud Run, outra conta) é o único que lê o segredo
`viking-pluggy`. O motor manda uma das perguntas fechadas de `financas/pergunta.py` e recebe o
texto pronto que o chat do Mac recebe. O token de identidade vem do servidor de metadados do
Cloud Run (a conta `viking-motor@`, com a audience = a URL do serviço), e o serviço confere o
e-mail na primeira instrução de toda rota.

Toda falha vira `pluggy.FalhaDaPluggy` com uma frase curta (sem corpo, sem token), que
`tools.mensagem_de_erro` já traduz: "Não consegui falar com a Pluggy agora: … Nada foi alterado."
O pedido respeita o prazo do turno (`prazo`): leva no máximo o que sobra depois da chamada ao
Gemini que lê a resposta.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import time
from typing import Any

from lifeos import config, prazo
from lifeos.financas import pergunta, pluggy

PRAZO_MAX_S = 60.0  # um `gastos` de um ano: alguns segundos no Mac (a Pluggy, 2026-09-27)
PROXIMO_MODELO_S = 60.0  # a chamada ao Gemini que lê a resposta (`na_nuvem.PRAZO_DO_GEMINI_MS`)
PRAZO_MIN_S = 5.0  # menos que isso não vale começar
MAX_RESPOSTA = 64 * 1024  # bytes: a maior resposta (20 transações de uma busca) tem poucos KB
# O 429 é do Cloud Run, nunca do serviço (que só responde 200, 400, 500 e a recusa de identidade):
# "The request was aborted because there was no available instance" (medido em 2026-10-08, com a
# instância única acordando), e o pedido não chegou ao serviço. A página de troubleshooting manda
# repetir com espera crescente; aqui no máximo duas vezes, e só se couber no prazo do turno (as
# perguntas são só de leitura).
ESPERAS_DO_429_S = (2.0, 4.0)


def _token() -> str:
    """O token de identidade do `viking-motor@` para o serviço, pelo servidor de metadados."""
    import google.auth.transport.requests
    from google.oauth2 import id_token

    return id_token.fetch_id_token(google.auth.transport.requests.Request(), config.FINANCAS_URL)


def _post(url: str, corpo: dict[str, Any], token: str, segundos: float) -> tuple[int, bytes]:
    """O único ponto que fala com a rede (os testes o trocam pelo serviço em processo)."""
    import requests

    resposta = requests.post(
        url, json=corpo, headers={"Authorization": f"Bearer {token}"}, timeout=segundos
    )
    return resposta.status_code, resposta.content


def _esperar(segundos: float) -> None:
    """A espera antes de repetir um 429 (os testes a trocam)."""
    time.sleep(segundos)


def segundos_do_pedido() -> float:
    """Quanto o pedido pode levar: o teto, menos o que o turno guarda para o Gemini."""
    falta = prazo.restante()
    if falta is None:
        return PRAZO_MAX_S
    return min(PRAZO_MAX_S, falta - PROXIMO_MODELO_S)


def _chamar(rota: str, corpo: dict[str, Any]) -> dict[str, Any]:
    if not config.FINANCAS_URL:
        raise pluggy.FalhaDaPluggy("o serviço de finanças não está ligado nesta nuvem")
    segundos = segundos_do_pedido()
    if segundos < PRAZO_MIN_S:
        raise pluggy.FalhaDaPluggy("não deu tempo de perguntar ao serviço de finanças neste turno")
    try:
        token = _token()
    except Exception as exc:  # noqa: BLE001 - o servidor de metadados: só o tipo
        raise pluggy.FalhaDaPluggy(
            f"sem o token para o serviço de finanças ({type(exc).__name__})"
        ) from None
    esperas = list(ESPERAS_DO_429_S)
    while True:
        try:
            status, bruto = _post(config.FINANCAS_URL + rota, corpo, token, segundos)
        except Exception as exc:  # noqa: BLE001 - tempo esgotado, conexão: só o tipo
            raise pluggy.FalhaDaPluggy(
                f"o serviço de finanças não respondeu ({type(exc).__name__})"
            ) from None
        if status != 429 or not esperas:
            break
        if segundos_do_pedido() - esperas[0] < PRAZO_MIN_S:
            break
        _esperar(esperas.pop(0))
        segundos = segundos_do_pedido()
    if status != 200:
        raise pluggy.FalhaDaPluggy(f"o serviço de finanças respondeu {status}", status)
    if len(bruto) > MAX_RESPOSTA:
        raise pluggy.FalhaDaPluggy("a resposta do serviço de finanças passou do tamanho")
    try:
        dados = json.loads(bruto)
    except ValueError:
        raise pluggy.FalhaDaPluggy("o serviço de finanças respondeu algo que não é JSON") from None
    if not isinstance(dados, dict):
        raise pluggy.FalhaDaPluggy("o serviço de finanças respondeu fora do formato")
    return dados


def perguntar(dados: dict[str, str]) -> str:
    """O texto da resposta (o mesmo do chat do Mac). `PerguntaInvalida` antes da rede."""
    resposta = _chamar("/responder", pergunta.conferir(dados))
    texto = resposta.get("texto")
    if not isinstance(texto, str) or set(resposta) != {"texto"}:
        raise pluggy.FalhaDaPluggy("o serviço de finanças respondeu fora do formato")
    return texto


def saude() -> dict[str, Any]:
    """O serviço lê as credenciais e conta as conexões, sem chamar a Pluggy (a fumaça do motor)."""
    resposta = _chamar("/saude", {})
    certo = (
        set(resposta) == {"commit", "credenciais", "conexoes"}
        and isinstance(resposta["commit"], str)
        and isinstance(resposta["credenciais"], bool)
        and isinstance(resposta["conexoes"], int)
        and not isinstance(resposta["conexoes"], bool)
    )
    if not certo:
        raise pluggy.FalhaDaPluggy("o serviço de finanças respondeu fora do formato")
    return resposta
