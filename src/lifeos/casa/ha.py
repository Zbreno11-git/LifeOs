"""O Home Assistant deste laptop, pela API REST local (D70): o interruptor e o agente local.

- **O interruptor** (`input_boolean.viking_voz`, que o dono vira pelo iPhone): conferido antes de
  cada pedido. Desligado, o HA fora, ou uma resposta estranha: **fechado** (nada sai para a nuvem).
- **O agente local** (`conversation.home_assistant`): a frase transcrita vai primeiro a ele, como o
  "Prefer handling commands locally" do próprio HA (desde 2024.12). Se ele reconheceu (fez ou
  respondeu), a fala é a dele; se não reconheceu (`no_intent_match`), a frase vai ao Viking. O HA
  só alcança as entidades que o dono expôs à voz (opt-in do HA).

O token do HA é um "long-lived access token" do perfil do dono, guardado só na pasta da ponte.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRAZO_S = 10
AGENTE_LOCAL = "conversation.home_assistant"
IDIOMA = "pt-BR"
# O HA reconheceu o pedido: fez (`action_done`) ou respondeu (`query_answer`).
RECONHECEU = ("action_done", "query_answer")
# O HA não entendeu a frase: é do Viking. Qualquer outro erro (ex.: `no_valid_targets`, "não achei
# a luz da varanda") foi um pedido para o HA, e a fala é a dele.
NAO_E_DO_HA = "no_intent_match"


@dataclass(frozen=True)
class Interruptor:
    ligado: bool
    motivo: str = ""


@dataclass(frozen=True)
class RespostaDoHA:
    fala: str
    fez: bool


class HA:
    def __init__(self, url: str, token: str, interruptor: str, http: Any):
        self.url = url.rstrip("/")
        self.token = token
        self.interruptor = interruptor
        self.http = http

    def _cabecalhos(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def ligado(self) -> Interruptor:
        try:
            resposta = self.http.get(
                f"{self.url}/api/states/{self.interruptor}",
                headers=self._cabecalhos(),
                timeout=PRAZO_S,
            )
        except Exception as exc:  # noqa: BLE001 - o HA fora: fechado
            return Interruptor(False, f"o Home Assistant não respondeu ({type(exc).__name__})")
        if resposta.status_code == 404:
            return Interruptor(False, f"o interruptor {self.interruptor} não existe no HA")
        if resposta.status_code != 200:
            return Interruptor(False, f"o Home Assistant respondeu HTTP {resposta.status_code}")
        try:
            estado = resposta.json().get("state")
        except (ValueError, AttributeError):
            return Interruptor(False, "o Home Assistant respondeu algo que não é o estado")
        if estado != "on":
            return Interruptor(False, "o interruptor Viking voz está desligado")
        return Interruptor(True)

    def conversar(self, texto: str) -> RespostaDoHA | None:
        """A fala do HA se ele reconheceu o pedido; `None` se a frase é do Viking (ou se o HA não
        respondeu: aí o Viking ainda pode atender, e o interruptor já foi conferido antes)."""
        try:
            resposta = self.http.post(
                f"{self.url}/api/conversation/process",
                headers=self._cabecalhos(),
                json={"text": texto, "language": IDIOMA, "agent_id": AGENTE_LOCAL},
                timeout=PRAZO_S,
            )
            dados = resposta.json() if resposta.status_code == 200 else None
        except Exception:  # noqa: BLE001 - o HA não entendeu: segue para o Viking
            return None
        corpo = (dados or {}).get("response") if isinstance(dados, dict) else None
        if not isinstance(corpo, dict):
            return None
        tipo = corpo.get("response_type")
        codigo = (
            (corpo.get("data") or {}).get("code") if isinstance(corpo.get("data"), dict) else None
        )
        fala = ((corpo.get("speech") or {}).get("plain") or {}).get("speech") or ""
        if tipo in RECONHECEU:
            return RespostaDoHA(fala=str(fala) or "Feito.", fez=tipo == "action_done")
        if tipo == "error" and codigo != NAO_E_DO_HA and fala:
            return RespostaDoHA(fala=str(fala), fez=False)
        return None
