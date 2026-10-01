"""O lado da nuvem das mãos (Sessão 11, D61): o chat da nuvem pede uma tarefa de navegador ao Mac
e espera o resultado **no mesmo turno** (resposta do dono, 2026-10-01).

O prazo do turno manda (220 s, `prazo.py`, D60): a tarefa leva o tempo que sobra depois de
reservar a próxima chamada ao Gemini (60 s), a espera por quem pega (15 s) e uma folga (20 s). O
que não cabe nem começa. Sem o `viking maos` ligado, em 15 s a tarefa vence e não roda mais; se o
Mac pegou e não respondeu a tempo, o texto diz "não sei", nunca "não fiz".

Nada daqui manda liberar um clique: o formato da tarefa não tem esse campo (`maos/fila.py`).

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini (a tool é
`assistant/na_nuvem.navegar_e_executar`, que chama `pedir`).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from lifeos import config, prazo
from lifeos.maos import fila

PROXIMO_MODELO_S = 60.0  # a chamada ao Gemini que lê o resultado (`na_nuvem.PRAZO_DO_GEMINI_MS`)
FOLGA_S = 20.0  # o Jev fechando, a entrega pela rede
LEITURA_S = 1.0  # de quanto em quanto o turno relê a tarefa

NAO_CABE = (
    "Não mandei ao navegador: o que falta deste turno não dá para uma tarefa (faltam {falta:.0f} s). "
    "Nada foi feito; peça de novo numa mensagem nova."
)
DESLIGADO = (
    "O `viking maos` não está ligado no Mac: a tarefa não rodou, e nada foi feito no navegador. "
    "Diga ao usuário que, para usar o navegador por aqui, ele liga `viking maos` num terminal do "
    "Mac."
)
NAO_SEI = (
    "O Mac pegou a tarefa, mas não respondeu a tempo: não sei se ela terminou nem o que fez. Não "
    "repita sem perguntar ao usuário; ele vê o andamento no terminal do `viking maos`."
)


def _dormir(segundos: float) -> None:
    time.sleep(segundos)


def _agora() -> datetime:
    return datetime.now(UTC)


def limite_da_tarefa(restante: float | None) -> float:
    """Quanto a tarefa pode levar: o do navegador (`VIKING_BROWSER_TIMEOUT_S`), menos o que o
    turno precisa guardar para o resto."""
    teto = float(config.BROWSER_TIMEOUT_S)
    if restante is None:
        return teto
    return min(teto, restante - PROXIMO_MODELO_S - fila.PEGAR_EM.total_seconds() - FOLGA_S)


def pedir(url: str, objetivo: str, manter_aberta: bool) -> str:
    from lifeos.maos import fila_firestore

    restante = prazo.restante()
    limite = int(limite_da_tarefa(restante))
    if limite < fila.LIMITE_MIN_S:
        return NAO_CABE.format(falta=max(restante or 0.0, 0.0))
    try:
        tarefa_id = fila_firestore.criar(
            url, objetivo, manter_aberta=bool(manter_aberta), limite_s=limite, agora=_agora()
        )
    except fila.TarefaInvalida as exc:
        return f"Não mandei ao navegador: {exc}. Nada foi feito."

    # 1. Alguém pega em até `PEGAR_EM`? Senão a tarefa vence (se ninguém pegou no último instante).
    inicio = prazo._relogio()
    while True:
        atual = fila_firestore.situacao(tarefa_id)
        if atual is None:
            return NAO_SEI
        if atual.estado != fila.PENDENTE:
            break
        if prazo._relogio() - inicio >= fila.PEGAR_EM.total_seconds():
            if fila_firestore.vencer(tarefa_id):
                fila_firestore.apagar(tarefa_id)
                return DESLIGADO
            continue  # pegaram entre a leitura e a troca: segue esperando o resultado
        _dormir(LEITURA_S)

    # 2. O resultado, até o limite da tarefa mais a folga, e sem comer a chamada seguinte ao modelo.
    fim = prazo._relogio() + limite + FOLGA_S
    while True:
        atual = fila_firestore.situacao(tarefa_id)
        if atual is not None and atual.estado == fila.FEITA:
            fila_firestore.apagar(tarefa_id)
            return atual.resultado or "O Mac não devolveu texto nenhum da tarefa."
        if prazo._relogio() >= fim or not prazo.cabe(PROXIMO_MODELO_S + LEITURA_S):
            return NAO_SEI
        _dormir(LEITURA_S)
