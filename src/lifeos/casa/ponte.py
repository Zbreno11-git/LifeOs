"""O caminho de uma fala do aparelho, do áudio à resposta no alto-falante (D70).

A ordem é a regra:
1. **o interruptor do HA**, antes de qualquer coisa: desligado (ou o HA fora), nada sai daqui;
2. **ouvir** no motor (o áudio → o texto);
3. **o HA primeiro**: o que o agente local dele reconhece, ele faz, e o Viking nem fica sabendo;
4. **o turno do Viking** pelo canal da voz, com a conversa desta sessão (o histórico e a nota
   ficam aqui, em memória, como no terminal do Mac; zeram depois de `INATIVA_S` sem falar);
5. **a fala**: o que só o dono vê (`ao_dono`, já sem o código: o motor tirou) e a resposta.

Um envio ou uma limpeza que pede aprovação volta no campo `aprovacao`: o código fica guardado
aqui por `JANELA_S`, nunca é falado nem mandado ao TTS, e **dois toques** no botão mandam
`confirma NNNN` como a próxima mensagem desta conversa (a barreira do motor o lê antes do modelo).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
import secrets
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from lifeos.casa.ha import HA
from lifeos.casa.remoto import ErroDoMotor, Motor
from lifeos.casa.som import ErroDoSom

INATIVA_S = 5 * 60  # uma conversa por voz que parou por 5 min recomeça do zero
JANELA_S = 60  # os dois toques valem por 1 min depois de o Viking pedir
MAX_FALA = 2_000  # o teto do `/voz/falar` (`assistant/voz.MAX_TEXTO_FALADO`)
_SO_ENFEITE = re.compile(r"^[\s\W_]*$")  # uma linha de "────" ou de "•" não se fala
_CODIGO = re.compile(r"\d{4}")  # a forma de um código de aprovação (`confirmacao.DIGITOS`)
NAO_LI_INTEIRO = (
    "Essa proposta é longa demais para eu ler inteira em voz alta, então não abri a aprovação: "
    "nada foi feito. Peça pelo chat."
)


class Ocupada(RuntimeError):
    """Outra fala ainda está em curso (o aparelho mostra "ocupado" e o dono repete)."""


@dataclass
class Conversa:
    sessao: str = field(default_factory=lambda: secrets.token_hex(4))
    numero: int = 0
    historico: list[Any] = field(default_factory=list)
    nota: str = ""
    ultima: float = 0.0
    codigo: str = ""
    codigo_ate: float = 0.0

    def pedido(self, mensagem: str) -> dict[str, Any]:
        self.numero += 1
        return {
            "mensagem": mensagem,
            "historico": self.historico,
            "nota": self.nota,
            "sessao": self.sessao,
            "numero": self.numero,
        }

    def absorver(self, resposta: dict[str, Any], agora: float) -> None:
        historico = resposta.get("historico")
        if isinstance(historico, list):
            self.historico = historico
        nota = resposta.get("nota")
        if isinstance(nota, str):
            self.nota = nota
        abertas = [a for a in resposta.get("aprovacao") or [] if isinstance(a, dict)]
        codigos = [a.get("codigo") for a in abertas]
        codigos = [c for c in codigos if isinstance(c, str) and _CODIGO.fullmatch(c)]
        if codigos:  # fechada até a fala inteira chegar ao alto-falante (`Ponte._turno`)
            self.codigo, self.codigo_ate = codigos[-1], 0.0


@dataclass(frozen=True)
class Resultado:
    """O que o aparelho mostra no LED: `ok`, `aguardando` (os dois toques), `desligado`,
    `vazio` (não ouviu fala), `nada` (dois toques sem aprovação aberta) ou `erro`."""

    estado: str
    origem: str = ""  # "ha" ou "viking"
    fala: str = ""


def texto_para_falar(resposta: dict[str, Any]) -> str:
    """O que vai ao alto-falante, inteiro: o que só o dono vê (sem as linhas de enfeite) e a
    resposta. O código já veio fora (o motor o tirou); a ponte ainda mascara o código aberto, se
    aparecer (`Ponte._dizer`). Quem corta é quem fala, e uma aprovação não se corta."""
    partes: list[str] = []
    for bloco in resposta.get("ao_dono") or []:
        if isinstance(bloco, str):
            partes += [
                linha.strip() for linha in bloco.splitlines() if not _SO_ENFEITE.match(linha)
            ]
    for campo in ("resposta", "aviso", "erro"):
        valor = resposta.get(campo)
        if isinstance(valor, str) and valor.strip():
            partes.append(valor.strip() if campo == "resposta" else f"Atenção: {valor.strip()}")
    return "\n".join(partes)


class Ponte:
    def __init__(
        self,
        motor: Motor,
        ha: HA,
        tocar: Callable[[Iterable[bytes]], int],
        relogio: Callable[[], float] = time.monotonic,
    ):
        self.motor = motor
        self.ha = ha
        self.tocar = tocar
        self.relogio = relogio
        self.conversa = Conversa()
        self._uma_por_vez = threading.Lock()

    def _conversa(self) -> Conversa:
        agora = self.relogio()
        if self.conversa.ultima and agora - self.conversa.ultima > INATIVA_S:
            self.conversa = Conversa()
        self.conversa.ultima = agora
        return self.conversa

    def _dizer(self, fala: str, ocultar: str = "", *, inteiro: bool = False) -> None:
        """Fala pelo motor e toca aqui. O código aberto (`ocultar`) nunca vai ao TTS, nem se o
        texto o trouxer por engano. Com `inteiro`, nada se corta: o motor recusa (413) o que não
        cabe, e a falha no meio do áudio ou do `aplay` sobe."""
        if ocultar:
            fala = re.sub(rf"(?<!\d){re.escape(ocultar)}(?!\d)", "····", fala)
        if fala.strip():
            self.tocar(self.motor.falar(fala if inteiro else fala[:MAX_FALA], inteiro=inteiro))

    def _turno(self, mensagem: str) -> Resultado:
        conversa = self._conversa()
        resposta = self.motor.responder(conversa.pedido(mensagem))
        conversa.absorver(resposta, self.relogio())
        fala = texto_para_falar(resposta)
        if not conversa.codigo:
            self._dizer(fala)
            return Resultado("ok", "viking", fala)
        # Uma aprovação: os dois toques só valem para o que o dono ouviu inteiro (D26, D70). O
        # texto que não cabe, o áudio que parou e o `aplay` que morreu fecham a proposta.
        codigo, conversa.codigo = conversa.codigo, ""
        if len(fala) > MAX_FALA:
            self._avisar(NAO_LI_INTEIRO)
            return Resultado("erro", "viking", NAO_LI_INTEIRO)
        try:
            self._dizer(fala, ocultar=codigo, inteiro=True)
        except ErroDoMotor as exc:
            if exc.status == 413:
                self._avisar(NAO_LI_INTEIRO)
                return Resultado("erro", "viking", NAO_LI_INTEIRO)
            raise
        conversa.codigo = codigo
        conversa.codigo_ate = self.relogio() + JANELA_S  # um minuto depois de ele terminar de falar
        return Resultado("aguardando", "viking", fala)

    def _avisar(self, fala: str) -> None:
        """Um aviso curto, sem aprovação: se nem ele sai, o LED de erro basta."""
        try:
            self._dizer(fala)
        except (ErroDoMotor, ErroDoSom):
            pass

    def _com_a_vez(self, trabalho: Callable[[], Resultado]) -> Resultado:
        if not self._uma_por_vez.acquire(blocking=False):
            raise Ocupada("outra fala ainda está em curso")
        try:
            interruptor = self.ha.ligado()
            if not interruptor.ligado:
                return Resultado("desligado", fala=interruptor.motivo)
            return trabalho()
        except (ErroDoMotor, ErroDoSom) as exc:
            return Resultado("erro", fala=str(exc))
        finally:
            self._uma_por_vez.release()

    def falou(self, wav: bytes) -> Resultado:
        """Uma fala do aparelho (o WAV do botão)."""

        def trabalho() -> Resultado:
            texto = self.motor.ouvir(wav).strip()
            if not texto:
                return Resultado("vazio")
            do_ha = self.ha.conversar(texto)
            if do_ha is not None:
                self._dizer(do_ha.fala)
                return Resultado("ok", "ha", do_ha.fala)
            self.conversa.codigo = ""  # uma fala nova fecha a aprovação aberta
            return self._turno(texto)

        return self._com_a_vez(trabalho)

    def tocou_duas_vezes(self) -> Resultado:
        """Os dois toques: aprova a proposta aberta desta conversa, se ainda estiver na janela."""

        def trabalho() -> Resultado:
            conversa = self.conversa
            codigo, ate = conversa.codigo, conversa.codigo_ate
            conversa.codigo = ""
            if not codigo or self.relogio() > ate:
                return Resultado("nada")
            return self._turno(f"confirma {codigo}")

        return self._com_a_vez(trabalho)
