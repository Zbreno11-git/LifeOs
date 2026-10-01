"""A tarefa de navegador que a nuvem pede e o Mac roda (Sessão 11, D61): o formato e as regras.

O caminho inteiro:
1. o chat da nuvem (`assistant/na_nuvem.navegar_e_executar`) põe a tarefa na fila
   (`maos/fila_firestore.py`) e espera no mesmo turno;
2. o `viking maos` do Mac (`maos/mac.py`) pergunta ao motor a cada poucos segundos
   (`POST /maos/pegar`), roda a tarefa com todas as travas do Mac (domínios bloqueados, freio,
   trava entre processos, redação) e devolve só o texto já redigido (`POST /maos/entregar`);
3. o turno lê o resultado e o apaga.

**O formato é fechado** (`CAMPOS`): um campo a mais, inclusive um `liberar`, faz o Mac recusar
sem rodar nada. A nuvem nunca libera um clique: a liberação nasce, aparece e se aprova no
terminal do `viking maos` (D38, D57). Este módulo é só regra (nada de rede nem de Firestore): o
Mac, que não instala o extra `nuvem`, valida com ele também.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from lifeos.reminders.interface import id_valido

CAMPOS = ("id", "url", "objetivo", "manter_aberta", "limite_s")
PEGAR_EM = timedelta(seconds=15)  # sem o `viking maos` ligado, a tarefa vence sem rodar
VIDA = timedelta(days=1)  # a TTL de `tarefas.apagar_em`: o turno apaga antes; isto é o lixo
LIMITE_MIN_S = 30  # menos que isso não abre nem uma página
LIMITE_MAX_S = 600
MAX_URL = 2_000
MAX_OBJETIVO = 1_000
MAX_RESULTADO = 20_000  # caracteres; o texto que volta ao Gemini da nuvem
_POR = re.compile(r"[0-9a-f]{8,32}")

PENDENTE, PEGA, FEITA, VENCIDA = "pendente", "pega", "feita", "vencida"


class TarefaInvalida(ValueError):
    """O formato não é o combinado: nada roda."""


@dataclass(frozen=True)
class Tarefa:
    id: str
    url: str
    objetivo: str
    manter_aberta: bool
    limite_s: float

    def como_dict(self) -> dict[str, Any]:
        return {c: getattr(self, c) for c in CAMPOS}


def validar_tarefa(dados: Any) -> Tarefa:
    """A tarefa, conferida campo a campo; `TarefaInvalida` sem ecoar o conteúdo."""
    if not isinstance(dados, dict):
        raise TarefaInvalida("a tarefa tem de ser um objeto")
    if set(dados) != set(CAMPOS):
        raise TarefaInvalida(f"a tarefa tem de ter exatamente os campos {list(CAMPOS)}")
    if not id_valido(dados["id"]):
        raise TarefaInvalida("o id da tarefa tem de ser um UUID")
    url, objetivo = dados["url"], dados["objetivo"]
    if not isinstance(url, str) or not url.strip() or len(url) > MAX_URL:
        raise TarefaInvalida(f"a URL tem de ser um texto de 1 a {MAX_URL} caracteres")
    if not isinstance(objetivo, str) or not objetivo.strip() or len(objetivo) > MAX_OBJETIVO:
        raise TarefaInvalida(f"o objetivo tem de ser um texto de 1 a {MAX_OBJETIVO} caracteres")
    if not isinstance(dados["manter_aberta"], bool):
        raise TarefaInvalida("manter_aberta tem de ser verdadeiro ou falso")
    limite = dados["limite_s"]
    if isinstance(limite, bool) or not isinstance(limite, int | float):
        raise TarefaInvalida("limite_s tem de ser um número")
    if not LIMITE_MIN_S <= limite <= LIMITE_MAX_S:
        raise TarefaInvalida(f"limite_s tem de estar entre {LIMITE_MIN_S} e {LIMITE_MAX_S}")
    return Tarefa(dados["id"], url, objetivo, dados["manter_aberta"], float(limite))


def validar_por(por: Any) -> str:
    """Quem pegou: um identificador do processo do `viking maos` (dois terminais não se
    confundem)."""
    if not isinstance(por, str) or not _POR.fullmatch(por):
        raise TarefaInvalida("por tem de ser um identificador hexadecimal curto")
    return por


def resultado_curto(texto: str) -> str:
    if len(texto) <= MAX_RESULTADO:
        return texto
    return texto[:MAX_RESULTADO] + "\n[… cortado: o resultado passou do tamanho que a nuvem aceita]"
