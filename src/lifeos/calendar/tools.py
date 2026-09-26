"""Ferramentas de Google Calendar, expostas como funções (function-calling do Gemini e tools MCP).

A lógica e as travas moram em `calendar/service.py`. Aqui fica só o texto: cada `responder_*`
devolve uma `Resposta` (texto + dados + erro), usada pelas tools do Gemini abaixo (que devolvem só
o texto) e pelas tools do MCP (`mcp_server/server.py`, que devolvem texto + dados estruturados).
Uma frase, um lugar.
"""

# NÃO adicionar `from __future__ import annotations` aqui: o google-genai valida os argumentos
# das tools com isinstance(valor, anotação), e o future import transforma as anotações em strings,
# quebrando toda chamada que passe argumento (`isinstance() arg 2 must be a type...`).
from dataclasses import dataclass

from lifeos.calendar import service
from lifeos.calendar.service import (
    EntradaInvalida,
    ErroCalendario,
    Evento,
    EventoNaoEncontrado,
    FalhaDaApi,
    TituloDivergente,
)


@dataclass(frozen=True)
class Resposta:
    texto: str
    dados: Evento | list[Evento] | None = None
    erro: ErroCalendario | None = None


def _falha_da_api(exc: FalhaDaApi) -> Resposta:
    return Resposta(f"Não consegui falar com o Google Calendar: {exc}", erro=exc)


def _linhas(eventos: list[Evento]) -> list[str]:
    return [f"- [{e.inicio}]: {e.titulo} (ID: {e.id})" for e in eventos]


def responder_proximos(max_results: int = 10) -> Resposta:
    try:
        eventos = service.proximos(max_results)
    except FalhaDaApi as exc:
        return _falha_da_api(exc)
    if not eventos:
        return Resposta("Nenhum próximo evento encontrado.", dados=[])
    return Resposta("\n".join(_linhas(eventos)), dados=eventos)


def responder_por_data(data_inicio: str, data_fim: str | None = None) -> Resposta:
    try:
        eventos = service.por_data(data_inicio, data_fim)
    except EntradaInvalida as exc:
        return Resposta(f"Não entendi as datas: {exc}", erro=exc)
    except FalhaDaApi as exc:
        return _falha_da_api(exc)
    fim_exibido = data_fim or data_inicio
    if not eventos:
        return Resposta(f"Nenhum evento encontrado entre {data_inicio} e {fim_exibido}.", dados=[])
    cabecalho = f"Eventos encontrados de {data_inicio} até {fim_exibido}:"
    return Resposta("\n".join([cabecalho, *_linhas(eventos)]), dados=eventos)


def responder_buscar(termo_busca: str) -> Resposta:
    try:
        eventos = service.buscar(termo_busca)
    except FalhaDaApi as exc:
        return _falha_da_api(exc)
    if not eventos:
        return Resposta(f"Nenhum evento futuro encontrado com o termo '{termo_busca}'.", dados=[])
    linhas = [f"{len(eventos)} evento(s) com o termo '{termo_busca}':"]
    linhas += [f"- [{e.inicio}] {e.titulo} (ID: {e.id})" for e in eventos]
    return Resposta("\n".join(linhas), dados=eventos)


def responder_criar(
    summary: str, start_time: str, end_time: str, description: str = ""
) -> Resposta:
    try:
        evento = service.criar(summary, start_time, end_time, description)
    except EntradaInvalida as exc:
        if exc.dados.get("campo") == "intervalo":
            texto = f"O horário de fim ({end_time}) precisa ser depois do início ({start_time})."
        else:
            texto = f"Não entendi os horários '{start_time}' / '{end_time}'. Use ISO 8601."
        return Resposta(texto, erro=exc)
    except FalhaDaApi as exc:
        return _falha_da_api(exc)
    texto = f"✅ Evento '{summary}' criado com sucesso para {evento.inicio}! Link: {evento.link}"
    return Resposta(texto, dados=evento)


def responder_criar_dia_inteiro(summary: str, data: str, description: str = "") -> Resposta:
    try:
        evento = service.criar_dia_inteiro(summary, data, description)
    except EntradaInvalida as exc:
        return Resposta(f"Não entendi a data '{data}'. Use YYYY-MM-DD.", erro=exc)
    except FalhaDaApi as exc:
        return _falha_da_api(exc)
    return Resposta(
        f"✅ Evento de dia inteiro '{summary}' criado para a data {evento.inicio}!", dados=evento
    )


def _recusa_de_alvo(exc: ErroCalendario, verbo: str, event_id: str, titulo_esperado: str) -> str:
    """Frases das travas comuns a apagar e reagendar (`verbo`: "apaguei" / "reagendei")."""
    if isinstance(exc, EventoNaoEncontrado):
        return f"Não encontrei o evento de ID '{event_id}': {exc}"
    if isinstance(exc, TituloDivergente):
        return (
            f"NÃO {verbo} nada. O evento {event_id} se chama '{exc.dados['titulo_real']}', "
            f"não '{titulo_esperado}'. Confirme com o usuário qual é o evento certo."
        )
    return ""


def responder_apagar(event_id: str, titulo_esperado: str) -> Resposta:
    try:
        evento = service.apagar(event_id, titulo_esperado)
    except EntradaInvalida as exc:
        if exc.dados.get("campo") == "event_id":
            texto = "NÃO apaguei nada: o ID do evento veio vazio. Busque o evento antes de apagar."
        else:
            texto = (
                "NÃO apaguei nada: preciso do título exato do evento para conferir antes de "
                "apagar. Busque o evento e use o título que a busca devolveu."
            )
        return Resposta(texto, erro=exc)
    except (EventoNaoEncontrado, TituloDivergente) as exc:
        return Resposta(_recusa_de_alvo(exc, "apaguei", event_id, titulo_esperado), erro=exc)
    except FalhaDaApi as exc:
        titulo = exc.dados.get("titulo_real", event_id)
        return Resposta(f"NÃO consegui apagar o evento '{titulo}': {exc}", erro=exc)
    return Resposta(f"🗑️ Evento '{evento.titulo}' ([{evento.inicio}]) foi apagado.", dados=evento)


def responder_reagendar(
    event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str
) -> Resposta:
    try:
        evento = service.reagendar(event_id, titulo_esperado, novo_inicio, novo_fim)
    except EntradaInvalida as exc:
        campo = exc.dados.get("campo")
        if campo == "event_id":
            texto = "NÃO reagendei nada: o ID do evento veio vazio. Busque o evento antes."
        elif campo == "titulo_esperado":
            texto = (
                "NÃO reagendei nada: preciso do título exato do evento para conferir antes. "
                "Busque o evento e use o título que a busca devolveu."
            )
        elif campo == "intervalo":
            texto = (
                f"O novo horário de fim ({novo_fim}) precisa ser depois do início ({novo_inicio})."
            )
        else:
            texto = f"Não entendi os horários '{novo_inicio}' / '{novo_fim}'. Use ISO 8601."
        return Resposta(texto, erro=exc)
    except (EventoNaoEncontrado, TituloDivergente) as exc:
        return Resposta(_recusa_de_alvo(exc, "reagendei", event_id, titulo_esperado), erro=exc)
    except FalhaDaApi as exc:
        titulo = exc.dados.get("titulo_real", event_id)
        return Resposta(f"NÃO consegui reagendar o evento '{titulo}': {exc}", erro=exc)
    return Resposta(
        f"✅ O evento '{evento.titulo}' foi reagendado com sucesso para {evento.inicio}!",
        dados=evento,
    )


# --- tools do Gemini: docstring = o que o modelo lê; o corpo só devolve o texto ------------


def listar_proximos_eventos(max_results: int = 10) -> str:
    """Lista os próximos eventos do calendário a partir de agora.
    """
    return responder_proximos(max_results).texto


def listar_eventos_por_data(data_inicio: str, data_fim: str | None = None) -> str:
    """Lista eventos de um dia ou intervalo, no fuso civil configurado. Datas em YYYY-MM-DD.
    Sem `data_fim`, busca só o dia de `data_inicio`. Com `data_fim`, o intervalo é INCLUSIVO
    (o último dia também entra).
    """
    return responder_por_data(data_inicio, data_fim).texto


def criar_evento(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    """Cria um evento com horário marcado. `start_time` e `end_time` em ISO 8601, com ou sem fuso
    (ex.: '2026-09-23T10:00:00-03:00'); sem fuso, assume o fuso configurado do Viking.
    """
    return responder_criar(summary, start_time, end_time, description).texto


def criar_evento_dia_inteiro(summary: str, data: str, description: str = "") -> str:
    """Cria um evento de dia inteiro, sem horário. `data` em YYYY-MM-DD.
    """
    return responder_criar_dia_inteiro(summary, data, description).texto


def buscar_eventos_por_termo(termo_busca: str) -> str:
    """Busca eventos futuros por termo e devolve os candidatos com seus IDs. Use antes de apagar
    qualquer coisa: é daqui que sai o ID, e é isto que você mostra ao usuário para ele confirmar.
    """
    return responder_buscar(termo_busca).texto


def apagar_evento_por_id(event_id: str, titulo_esperado: str) -> str:
    """Apaga UM evento do calendário. Irreversível: só chame após buscar o evento e o usuário
    confirmar qual. `titulo_esperado` precisa bater EXATAMENTE com o título real (ignorando caixa
    e acentuação/forma Unicode) — a exclusão é recusada se divergir ou se vier vazio.
    `event_id` vem de uma busca ou listagem, nunca de chute.
    """
    return responder_apagar(event_id, titulo_esperado).texto


def reagendar_evento_por_id(
    event_id: str, titulo_esperado: str, novo_inicio: str, novo_fim: str
) -> str:
    """Muda o horário de UM evento já identificado. `titulo_esperado` precisa bater EXATAMENTE com
    o título real (ignorando caixa e acentuação/forma Unicode) — o reagendamento é recusado se
    divergir ou vier vazio. `event_id` vem de uma busca ou listagem, nunca de chute. Novos horários
    em ISO 8601, com ou sem fuso.
    """
    return responder_reagendar(event_id, titulo_esperado, novo_inicio, novo_fim).texto
