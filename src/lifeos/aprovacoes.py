"""Os tipos de ação que o dono aprova com código (`confirmacao.py`), num lugar só.

Só dados: quem **executa** uma aprovação é o laço do chat (`assistant/agent.py`) ou a CLI
(`cli.py`), e nunca uma tool — `tests/test_gmail_aprovacao.py` confere isso lendo o código. Aqui
fica o que o laço precisa saber para reconhecer um código: de que ação ele é, por quanto tempo
depois de usado ele ainda "vive" (para desfazer) e onde ele se aprova.

- `no_chat=True`: o código aparece no terminal do chat e se aprova digitando `confirma NNNN` ali.
- `no_chat=False`: a proposta veio de fora (um app pelo MCP) e se aprova só em `viking aprovar`,
  num terminal interativo; digitado no chat, o código é reconhecido (nunca vai ao Gemini) e o
  Viking aponta o comando.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

GMAIL_ARQUIVAR = "gmail.arquivar"
CALENDARIO_APAGAR = "calendario.apagar"
CALENDARIO_REAGENDAR = "calendario.reagendar"
NAVEGADOR_CLIQUE = "navegador.clique"  # D38: um clique recusado pelo freio, uma vez
VALIDADE_MCP = timedelta(hours=1)  # decisão do dono, 2026-09-27
JANELA_GMAIL = timedelta(days=7)  # D27: desfazer uma limpeza por 7 dias


@dataclass(frozen=True)
class Tipo:
    acao: str
    janela: timedelta  # depois de usado, o código ainda serve para desfazer por este tempo
    no_chat: bool


TIPOS: tuple[Tipo, ...] = (
    Tipo(GMAIL_ARQUIVAR, janela=JANELA_GMAIL, no_chat=True),
    Tipo(CALENDARIO_APAGAR, janela=timedelta(0), no_chat=False),
    Tipo(CALENDARIO_REAGENDAR, janela=timedelta(0), no_chat=False),
    # Um clique não se desfaz: o código só vive enquanto a proposta está aberta.
    Tipo(NAVEGADOR_CLIQUE, janela=timedelta(0), no_chat=True),
)


def do_chat() -> tuple[Tipo, ...]:
    return tuple(t for t in TIPOS if t.no_chat)
