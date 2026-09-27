"""Cliente da API da Pluggy, só com o que o Viking usa.

A mesma chave que lê o extrato também cria pagamento PIX (`POST /payments/requests`), muda
transação e apaga conexão (`DELETE /items/{id}`) — medido na OpenAPI em 2026-09-26. Por isso
toda chamada passa por `_pedir`, que recusa qualquer método que não seja `GET`, fora de
`/auth` e `/connect_token`, **antes** de abrir conexão. Uma chamada nova de escrita exige mudar
`_ESCRITAS_PERMITIDAS` e o teste que a trava.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.pluggy.ai"
MEUPLUGGY = 200  # o conector "espelho" das conexões do Meu Pluggy
VALIDADE_CHAVE_S = 110 * 60  # a chave de `/auth` vale 2 h (documentação); renova antes
TEMPO_LIMITE_S = 30
# Falha de conexão numa LEITURA é tentada de novo (o Mac do dono teve `URLError` em dois de
# quatro comandos seguidos, 2026-09-27, e o mesmo pedido passou no VPS). Escrita nunca repete.
ESPERAS_S = (1.0, 3.0)
_ESCRITAS_PERMITIDAS = frozenset({("POST", "/auth"), ("POST", "/connect_token")})
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class ErroPluggy(Exception):
    codigo = "falha_pluggy"


class SemCredenciais(ErroPluggy):
    codigo = "sem_credenciais"


class EntradaInvalida(ErroPluggy):
    codigo = "entrada_invalida"


class FalhaDaPluggy(ErroPluggy):
    codigo = "falha_pluggy"

    def __init__(self, mensagem: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.status = status


def id_valido(item_id: str) -> str:
    """ID de conexão no formato da Pluggy (UUID); o resto é recusado antes de virar caminho."""
    limpo = str(item_id or "").strip().lower()
    if not _UUID.fullmatch(limpo):
        raise EntradaInvalida("o ID da conexão não tem o formato da Pluggy")
    return limpo


def _abrir(pedido: urllib.request.Request):
    """Único ponto que fala com a rede; a trava de `tests/conftest.py` o substitui."""
    return urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE_S)


def _esperar(segundos: float) -> None:
    time.sleep(segundos)


def _motivo(exc: Exception) -> str:
    """O porquê de uma falha de conexão (`timed out`, erro de DNS ou de SSL), curto e imprimível.
    Vem da biblioteca de rede, não do corpo do pedido: não carrega a chave nem o segredo."""
    texto = " ".join(str(getattr(exc, "reason", None) or exc).split())
    texto = "".join(c for c in texto if c.isprintable())[:120]
    return f"{type(exc).__name__}: {texto}" if texto else type(exc).__name__


def _pedir(metodo: str, caminho: str, *, corpo: dict | None = None, chave: str = "") -> dict:
    if metodo != "GET" and (metodo, caminho) not in _ESCRITAS_PERMITIDAS:
        raise PermissionError(f"o Viking não escreve na Pluggy: {metodo} {caminho}")
    cabecalhos = {"Accept": "application/json", "Content-Type": "application/json"}
    if chave:
        cabecalhos["X-API-KEY"] = chave
    dados = json.dumps(corpo).encode() if corpo is not None else None
    esperas = ESPERAS_S if metodo == "GET" else ()
    for tentativa in range(len(esperas) + 1):
        pedido = urllib.request.Request(
            API + caminho, data=dados, headers=cabecalhos, method=metodo
        )
        try:
            with _abrir(pedido) as resposta:
                return json.loads(resposta.read() or b"{}")
        except urllib.error.HTTPError as exc:
            # Só o código e a descrição curta da Pluggy: o corpo pode ecoar o que foi enviado.
            try:
                detalhe = json.loads(exc.read() or b"{}").get("codeDescription") or ""
            except (ValueError, AttributeError):
                detalhe = ""
            raise FalhaDaPluggy(
                f"a Pluggy respondeu {exc.code}" + (f" ({detalhe})" if detalhe else ""), exc.code
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if tentativa < len(esperas):
                _esperar(esperas[tentativa])
                continue
            vezes = f", {tentativa + 1} tentativas" if tentativa else ""
            raise FalhaDaPluggy(f"sem resposta da Pluggy ({_motivo(exc)}{vezes})") from None
        except ValueError:
            raise FalhaDaPluggy("a Pluggy respondeu algo que não é JSON") from None
    raise AssertionError("inalcançável")  # o laço sempre devolve ou levanta


class Cliente:
    """Guarda a chave de `/auth` enquanto vale; o segredo nunca aparece em erro nem em `repr`."""

    def __init__(self, client_id: str, client_secret: str, *, relogio=time.monotonic) -> None:
        if not client_id or not client_secret:
            raise SemCredenciais(
                "faltam PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET no .env da raiz "
                "(ver docs/fontes/pluggy-open-finance.md)"
            )
        self._id, self._segredo, self._relogio = client_id, client_secret, relogio
        self._chave, self._vence = "", 0.0

    def __repr__(self) -> str:
        return "Cliente(pluggy)"

    def _chave_valida(self) -> str:
        if not self._chave or self._relogio() >= self._vence:
            resposta = _pedir(
                "POST", "/auth", corpo={"clientId": self._id, "clientSecret": self._segredo}
            )
            chave = resposta.get("apiKey")
            if not isinstance(chave, str) or not chave:
                raise FalhaDaPluggy("a Pluggy não devolveu a chave de acesso")
            self._chave, self._vence = chave, self._relogio() + VALIDADE_CHAVE_S
        return self._chave

    def get(self, caminho: str, **parametros) -> dict:
        consulta = urllib.parse.urlencode({k: v for k, v in parametros.items() if v is not None})
        return _pedir(
            "GET", caminho + (f"?{consulta}" if consulta else ""), chave=self._chave_valida()
        )

    def token_de_conexao(self) -> str:
        """Token curto (30 min, documentação) para a janela oficial de conexão da Pluggy."""
        resposta = _pedir("POST", "/connect_token", corpo={}, chave=self._chave_valida())
        token = resposta.get("accessToken")
        if not isinstance(token, str) or not token:
            raise FalhaDaPluggy("a Pluggy não devolveu o token de conexão")
        return token

    def conexao(self, item_id: str) -> dict:
        return self.get(f"/items/{id_valido(item_id)}")


def cliente() -> Cliente:
    from lifeos.config import PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET

    return Cliente(PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET)
