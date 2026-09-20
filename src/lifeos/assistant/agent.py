"""Assistente de chat unificado do Viking — calendário + navegador + lembretes.

Generalizado a partir do protótipo `calendar-bot/agent.py` (Gemini function-calling), que só
registrava ferramentas de calendário.
"""

from __future__ import annotations

import asyncio
import sys

from google import genai
from google.genai import types

from lifeos.browser import browser_goal
from lifeos.calendar import (
    criar_evento,
    criar_evento_dia_inteiro,
    deletar_evento_por_termo,
    listar_eventos_por_data,
    listar_proximos_eventos,
    reagendar_evento,
)
from lifeos.config import GEMINI_API_KEY
from lifeos.reminders import store


def navegar_e_executar(url: str, objetivo: str) -> str:
    """
    Abre uma URL num navegador controlado pelo Viking (via Browser Harness) e tenta avançar em
    direção a um objetivo em linguagem natural.

    Args:
        url: Endereço a abrir.
        objetivo: O que fazer/encontrar nessa página, em linguagem natural.
    """
    return asyncio.run(browser_goal(url, objetivo))


def criar_lembrete(titulo: str, corpo: str = "", tags: str = "") -> str:
    """
    Cria um lembrete ou nota geral (não é um evento de calendário).

    Args:
        titulo: Título curto do lembrete.
        corpo: Detalhes opcionais.
        tags: Tags separadas por vírgula, opcional.
    """
    reminder = store.add(
        title=titulo,
        body=corpo,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        source="viking-cli",
    )
    return f"✅ Lembrete #{reminder.id} criado: '{titulo}'."


def listar_lembretes() -> str:
    """Lista os lembretes/notas ainda não concluídos."""
    reminders = store.list_open()
    if not reminders:
        return "Nenhum lembrete pendente."
    return "\n".join(f"- #{r.id} {r.title}" for r in reminders)


def concluir_lembrete(reminder_id: int) -> str:
    """
    Marca um lembrete como concluído.

    Args:
        reminder_id: ID do lembrete (retornado ao criar ou listar).
    """
    reminder = store.complete(reminder_id)
    if not reminder:
        return f"Não encontrei o lembrete #{reminder_id}."
    return f"✅ Lembrete #{reminder_id} concluído."


def _build_client() -> genai.Client:
    if not GEMINI_API_KEY:
        print("❌ ERRO: GEMINI_API_KEY não encontrada no .env!")
        sys.exit(1)
    return genai.Client(api_key=GEMINI_API_KEY)


def iniciar_assistente() -> None:
    client = _build_client()
    ferramentas = [
        listar_proximos_eventos,
        listar_eventos_por_data,
        criar_evento,
        criar_evento_dia_inteiro,
        deletar_evento_por_termo,
        reagendar_evento,
        navegar_e_executar,
        criar_lembrete,
        listar_lembretes,
        concluir_lembrete,
    ]

    config = types.GenerateContentConfig(
        tools=ferramentas,
        system_instruction="""Você é o Viking, um assistente pessoal que administra Google Calendar,
navegação web (via Browser Harness) e lembretes/notas gerais.
- Para perguntas sobre uma data específica, use a ferramenta de busca por data.
- Para criar eventos sem horário exato, use a ferramenta de dia inteiro.
- Para tarefas que exigem abrir/usar um site, use a ferramenta de navegador.
- Para lembretes que não são eventos de calendário (ex.: 'lembre-me de revisar isso depois'), use as
  ferramentas de lembrete.
- Seja sempre prestativo, direto e confirme as ações realizadas com clareza.""",
        temperature=0.3,
    )

    chat = client.chats.create(model="gemini-2.5-flash", config=config)

    print("🤖 Viking iniciado! (calendário + navegador + lembretes)")
    print("Digite 'sair' para encerrar.\n")

    while True:
        prompt = input("Você: ")
        if prompt.lower() in ["sair", "exit", "quit"]:
            print("🤖 Viking: Até logo!")
            break

        print("⏳ Pensando...")
        try:
            resposta = chat.send_message(prompt)
            print(f"🤖 Viking: {resposta.text}\n")
        except Exception as e:  # noqa: BLE001 - loop de REPL não deve cair por erro de API/tool
            print(f"❌ Erro ao processar a resposta: {e}\n")


if __name__ == "__main__":
    iniciar_assistente()
