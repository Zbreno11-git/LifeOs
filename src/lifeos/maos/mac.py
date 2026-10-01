"""`viking maos` (Sessão 11, D61): o navegador deste Mac atendendo o chat da nuvem.

Um terminal em primeiro plano, que o dono liga quando quer: nada roda em segundo plano (ele
recusou), e nenhuma porta se abre. A cada `INTERVALO_S` o Mac **pergunta** ao motor se há tarefa
(`POST /maos/pegar`, com o token do `viking-maos@`, que só fala com `/maos/*`). Se há:

1. confere o formato (`maos/fila.validar_tarefa`): um campo a mais, inclusive um `liberar`, e
   nada roda;
2. roda pelo mesmo caminho do `viking chat` do Mac (`browser.executar_e_contar`): os domínios
   bloqueados, o freio de cliques, a trava entre processos e a redação valem aqui, no Mac;
3. devolve só o texto, já redigido (`POST /maos/entregar`): o mesmo que o Gemini do Mac leria;
4. se o freio recusou um clique de sair ou de mexer na conta, a proposta e o código aparecem
   **neste terminal**, e é aqui que o dono digita o código (D38, D57). A nuvem fica sabendo só que
   houve uma recusa (`liberacao.AVISO_AO_GEMINI`), nunca o código.

Ctrl-C desliga: a tarefa em curso é interrompida (o `run_jev` mata o Jev) e entregue assim.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import re
import secrets
import sys
import time
from typing import Any

from lifeos import confirmacao
from lifeos.browser import executar_e_contar, imprimir_progresso, liberacao
from lifeos.browser._redacao import limpar_controles, redigir_url
from lifeos.maos import fila
from lifeos.nuvem import cliente

INTERVALO_S = 5.0  # de quanto em quanto pergunta (D61: a latência aceita)
ESPERA_MAX_S = 60.0  # rede caída: a espera dobra até isto, sem desistir
ESPERA_DO_CODIGO_S = 120.0  # quanto o terminal espera o código de uma liberação
TENTATIVAS_DE_ENTREGA = 3
_CODIGO = re.compile(
    rf"\s*(?:confirm[ao]\s*)?(\d{{{confirmacao.DIGITOS}}})\s*[.!]?\s*", re.IGNORECASE
)

SEM_TERMINAL = (
    "❌ O `viking maos` só roda num terminal: é nele que aparece o que o navegador faz e o código "
    "para liberar um clique. Abra um terminal do Mac e rode de novo."
)


def _dormir(segundos: float) -> None:
    time.sleep(segundos)


def _terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ler_linha(prazo_s: float) -> str | None:
    """Uma linha do terminal, ou `None` se ninguém digitou a tempo."""
    import select

    prontos, _, _ = select.select([sys.stdin], [], [], prazo_s)
    return sys.stdin.readline() if prontos else None


def _entregar(sessao: Any, tarefa_id: str, por: str, texto: str) -> bool:
    for tentativa in range(TENTATIVAS_DE_ENTREGA):
        try:
            return cliente.entregar_tarefa(sessao, tarefa_id, por, texto)
        except cliente.ErroDaNuvem as exc:
            if tentativa == TENTATIVAS_DE_ENTREGA - 1:
                print(f"⚠️  Não consegui devolver o resultado à nuvem: {exc}.", file=sys.stderr)
                return False
            _dormir(2.0)
    return False


def _liberar(proposta: Any) -> None:
    """O código da proposta, digitado aqui. Três errados cancelam (`confirmacao.TENTATIVAS`)."""
    while confirmacao.aberta(liberacao.ACAO):
        print(
            f"🔐 Digite o código aqui para liberar (só Enter pula; espero {ESPERA_DO_CODIGO_S:.0f} "
            "s):",
            flush=True,
        )
        linha = _ler_linha(ESPERA_DO_CODIGO_S)
        achado = _CODIGO.fullmatch(linha or "")
        if not (linha or "").strip():
            print("   Não liberei: o clique continua recusado.")
            return
        if achado is None:
            print(f"   Isso não é um código de {confirmacao.DIGITOS} números.")
            continue
        try:
            texto, _resultado = liberacao.clicar_aprovado(
                achado.group(1), on_progress=imprimir_progresso
            )
        except confirmacao.ErroConfirmacao as exc:
            print(f"   {exc}")
            continue
        print(texto)
        return


def atender(sessao: Any, por: str, bruta: Any) -> bool:
    """Uma tarefa da nuvem. `False` se o dono interrompeu (Ctrl-C) e o `viking maos` deve parar."""
    try:
        tarefa = fila.validar_tarefa(bruta)
    except fila.TarefaInvalida as exc:
        print(f"⛔ Recusei uma tarefa da nuvem: {exc}. Nada rodou.")
        tarefa_id = bruta.get("id") if isinstance(bruta, dict) else None
        if isinstance(tarefa_id, str) and fila.id_valido(tarefa_id):
            texto = f"O Mac recusou a tarefa ({exc}): nada rodou no navegador."
            _entregar(sessao, tarefa_id, por, texto)
        return True
    objetivo = limpar_controles(tarefa.objetivo)[:80]
    endereco = limpar_controles(redigir_url(tarefa.url))[:100]
    print(f"🧭 Tarefa da nuvem: «{objetivo}» em {endereco}")
    texto, resultado, proposta = executar_e_contar(
        tarefa.url,
        tarefa.objetivo,
        timeout_s=tarefa.limite_s,
        manter_aberta=tarefa.manter_aberta,
    )
    if _entregar(sessao, tarefa.id, por, texto):
        print("   ✅ Resultado devolvido à nuvem.")
    else:
        print("   ⚠️ A nuvem não aceitou o resultado (o turno já tinha desistido).")
    if resultado.error_code == "timeout_terminated":  # Ctrl-C no meio da tarefa
        return False
    if proposta is not None:
        _liberar(proposta)
    return True


def iniciar(*, voltas: int | None = None) -> int:
    """O laço do `viking maos`. 0 ao desligar; 1 se nem começou. `voltas` limita as perguntas
    (para os testes)."""
    if not _terminal():
        print(SEM_TERMINAL, file=sys.stderr)
        return 1
    try:
        sessao = cliente.sessao_das_maos()
    except cliente.ErroDaNuvem as exc:
        print(f"❌ Nuvem: {exc}.", file=sys.stderr)
        return 1
    por = secrets.token_hex(8)
    print("🖐️  Viking maos: o navegador deste Mac atende o `viking chat --nuvem`.")
    print(f"   Pergunto à nuvem a cada {INTERVALO_S:.0f} s. Ctrl-C desliga.\n")
    espera = INTERVALO_S
    feitas = 0
    try:
        while voltas is None or feitas < voltas:
            feitas += 1
            try:
                bruta = cliente.pegar_tarefa(sessao, por)
            except cliente.ErroDaNuvem as exc:
                print(f"⚠️  Nuvem: {exc}. Tento de novo em {espera:.0f} s.", file=sys.stderr)
                _dormir(espera)
                espera = min(espera * 2, ESPERA_MAX_S)
                continue
            espera = INTERVALO_S
            if bruta is None:
                _dormir(INTERVALO_S)
                continue
            if not atender(sessao, por, bruta):
                print("\n🖐️  Viking maos desligado (a tarefa em curso foi interrompida).")
                return 0
    except KeyboardInterrupt:
        print("\n🖐️  Viking maos desligado.")
    return 0
