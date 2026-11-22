"""A ponte de casa falando com o motor (D70): as rotas `/voz/*`, com o token da `viking-casa@`.

O token de identidade sai da chave privada deste laptop (`service_account.IDTokenCredentials`,
com a audience = a URL do motor): o `google-auth` assina um JWT com ela e o troca no `token_uri`
do Google, sem o endpoint do IAM (medido em 2026-11-21 no `google-auth` 2.63: o IAM só entra fora
do domínio padrão). Por isso a conta não precisa de `TokenCreator`, só do `run.invoker`.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

PRAZO_S = 30  # ouvir, falar, a saúde
PRAZO_DO_TURNO_S = 320  # o turno do motor tem até 220 s, e o Cloud Run até 300
PEDACO = 4800  # bytes do áudio por leitura (100 ms a 24 kHz, 16 bits)


class ErroDoMotor(RuntimeError):
    """O motor não respondeu o que devia. `teto` diz se foi o teto de gasto (429)."""

    def __init__(self, mensagem: str, *, status: int = 0):
        super().__init__(mensagem)
        self.status = status

    @property
    def teto(self) -> bool:
        return self.status == 429


def sessao(info: dict[str, Any], audience: str) -> Any:
    """A sessão HTTP com o token de identidade da casa, renovado sozinho antes de vencer."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    credenciais = service_account.IDTokenCredentials.from_service_account_info(
        info, target_audience=audience
    )
    return AuthorizedSession(credenciais)


class Motor:
    def __init__(self, url: str, http: Any):
        self.url = url.rstrip("/")
        self.http = http

    def _erro(self, resposta: Any, oque: str) -> ErroDoMotor:
        try:
            motivo = resposta.json().get("erro", "")
        except ValueError:
            motivo = ""
        return ErroDoMotor(
            f"{oque}: HTTP {resposta.status_code}" + (f" ({motivo})" if motivo else ""),
            status=resposta.status_code,
        )

    def _pedir(self, metodo: str, rota: str, oque: str, **kwargs: Any) -> Any:
        try:
            resposta = self.http.request(metodo, self.url + rota, **kwargs)
        except Exception as exc:  # rede, DNS, o token que não renovou
            raise ErroDoMotor(f"{oque}: o motor não respondeu ({type(exc).__name__})") from exc
        if resposta.status_code != 200:
            raise self._erro(resposta, oque)
        return resposta

    def saude(self) -> dict[str, Any]:
        return self._pedir("GET", "/voz/saude", "a saúde", timeout=PRAZO_S).json()

    def ouvir(self, wav: bytes) -> str:
        resposta = self._pedir(
            "POST",
            "/voz/ouvir",
            "ouvir",
            data=wav,
            headers={"Content-Type": "audio/wav"},
            timeout=PRAZO_S,
        )
        texto = resposta.json().get("texto", "")
        return texto if isinstance(texto, str) else ""

    def responder(self, pedido: dict[str, Any]) -> dict[str, Any]:
        resposta = self._pedir(
            "POST", "/voz/responder", "o turno", json=pedido, timeout=PRAZO_DO_TURNO_S
        )
        dados = resposta.json()
        if not isinstance(dados, dict):
            raise ErroDoMotor("o turno: a resposta não é um objeto")
        return dados

    def falar(self, texto: str, *, inteiro: bool = False) -> Iterator[bytes]:
        """O áudio (PCM 24 kHz, mono, 16 bits) em pedaços, à medida que chega. Com `inteiro`, o
        motor recusa (413) o texto que não se fala sem corte. O áudio que para no meio (o motor
        derruba a conexão) é `ErroDoMotor`, nunca um fim normal."""
        resposta = self._pedir(
            "POST",
            "/voz/falar",
            "falar",
            json={"texto": texto, "inteiro": inteiro},
            timeout=PRAZO_S,
            stream=True,
        )
        try:
            for pedaco in resposta.iter_content(PEDACO):
                if pedaco:
                    yield pedaco
        except Exception as exc:  # a conexão caiu no meio (o motor ou a rede)
            raise ErroDoMotor(f"falar: o áudio parou no meio ({type(exc).__name__})") from exc
        finally:
            resposta.close()
