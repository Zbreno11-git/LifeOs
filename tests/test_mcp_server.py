"""Primeiro teste que chama o servidor MCP do Viking pelo protocolo de verdade (fastmcp.Client
em memória, sem stdio nem subprocesso) — antes só conferíamos os schemas descobertos, nunca uma
chamada de tool de ponta a ponta (auditoria §14). Cobre só as tools de lembrete: são as únicas
tocadas nesta sessão e não dependem de OAuth do Google Calendar, que não existe neste ambiente.
"""

import asyncio

import pytest


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test-viking.db"
    monkeypatch.setattr("lifeos.reminders.store.REMINDERS_DB_PATH", db_path)
    return db_path


def _chamar(nome: str, args: dict):
    from fastmcp import Client

    from lifeos.mcp_server.server import mcp

    async def _rodar():
        async with Client(mcp) as client:
            return await client.call_tool(nome, args, raise_on_error=False)

    return asyncio.run(_rodar())


def _listar_tools():
    from fastmcp import Client

    from lifeos.mcp_server.server import mcp

    async def _rodar():
        async with Client(mcp) as client:
            return await client.list_tools()

    return asyncio.run(_rodar())


def test_lista_as_dez_tools(temp_db):
    nomes = {t.name for t in _listar_tools()}
    esperadas = {
        "viking_listar_proximos_eventos",
        "viking_listar_eventos_por_data",
        "viking_criar_evento",
        "viking_criar_evento_dia_inteiro",
        "viking_buscar_eventos",
        "viking_apagar_evento",
        "viking_reagendar_evento",
        "viking_criar_lembrete",
        "viking_listar_lembretes",
        "viking_concluir_lembrete",
    }
    assert nomes == esperadas


def test_criar_lembrete_com_quando_valido_pelo_mcp(temp_db):
    resultado = _chamar("viking_criar_lembrete", {"titulo": "Revisar PR", "quando": "2026-09-25"})

    assert resultado.is_error is False
    assert resultado.structured_content["title"] == "Revisar PR"
    assert resultado.structured_content["due_at"].startswith("2026-09-25")


def test_criar_lembrete_sem_quando_continua_funcionando(temp_db):
    resultado = _chamar("viking_criar_lembrete", {"titulo": "Sem prazo"})

    assert resultado.is_error is False
    assert resultado.structured_content["due_at"] is None


def test_criar_lembrete_com_quando_invalido_e_erro_estruturado(temp_db):
    resultado = _chamar("viking_criar_lembrete", {"titulo": "X", "quando": "não-é-data"})

    assert resultado.is_error is True
    assert resultado.structured_content == {"erro": "quando_invalido", "quando": "não-é-data"}
    assert "ISO 8601" in resultado.content[0].text


def test_listar_lembretes_traz_lista_estruturada(temp_db):
    _chamar("viking_criar_lembrete", {"titulo": "Um"})
    _chamar("viking_criar_lembrete", {"titulo": "Dois"})

    resultado = _chamar("viking_listar_lembretes", {})

    assert resultado.is_error is False
    titulos = {item["title"] for item in resultado.structured_content["lembretes"]}
    assert titulos == {"Um", "Dois"}


def test_concluir_lembrete_existente_pelo_mcp(temp_db):
    criado = _chamar("viking_criar_lembrete", {"titulo": "Concluir"})
    reminder_id = criado.structured_content["id"]

    resultado = _chamar("viking_concluir_lembrete", {"reminder_id": reminder_id})

    assert resultado.is_error is False
    assert resultado.structured_content["completed_at"] is not None


def test_concluir_lembrete_inexistente_e_erro_estruturado(temp_db):
    resultado = _chamar("viking_concluir_lembrete", {"reminder_id": 99999})

    assert resultado.is_error is True
    assert resultado.structured_content == {"erro": "nao_encontrado", "reminder_id": 99999}


def test_paridade_com_cli_o_mesmo_quando_e_aceito(temp_db):
    """Motivo desta sessão existir (§12.5): o `quando` que `assistant/agent.py::criar_lembrete`
    já aceitava não existia como parâmetro em `viking_criar_lembrete` do MCP."""
    from lifeos.assistant.agent import criar_lembrete

    resposta_cli = criar_lembrete("Prova de paridade", quando="2026-09-25")
    resultado_mcp = _chamar(
        "viking_criar_lembrete", {"titulo": "Prova de paridade", "quando": "2026-09-25"}
    )

    assert "criado" in resposta_cli
    assert resultado_mcp.structured_content["due_at"].startswith("2026-09-25")


# --- calendário pelo protocolo MCP (Sessão 3b) — com o fake do Google do conftest ----------

_ITEM = {
    "id": "e1",
    "summary": "Dentista",
    "start": {"dateTime": "2026-10-02T10:00:00-03:00"},
    "end": {"dateTime": "2026-10-02T11:00:00-03:00"},
    "htmlLink": "http://cal/e1",
}


def test_listar_proximos_traz_eventos_estruturados(calendario):
    calendario["itens"] = [_ITEM]
    resultado = _chamar("viking_listar_proximos_eventos", {})
    assert resultado.is_error is False
    assert resultado.structured_content == {
        "eventos": [
            {
                "id": "e1",
                "title": "Dentista",
                "start": "2026-10-02T10:00:00-03:00",
                "end": "2026-10-02T11:00:00-03:00",
                "all_day": False,
                "link": "http://cal/e1",
            }
        ]
    }


def test_lista_vazia_nao_e_erro(calendario):
    resultado = _chamar("viking_buscar_eventos", {"termo_busca": "nada"})
    assert resultado.is_error is False
    assert resultado.structured_content == {"eventos": []}


def test_texto_do_mcp_e_o_mesmo_do_gemini(calendario):
    """Uma frase, um lugar: o MCP devolve exatamente o texto que o Gemini recebe."""
    from lifeos.calendar import tools

    calendario["itens"] = [_ITEM]
    resultado = _chamar("viking_listar_eventos_por_data", {"data_inicio": "2026-10-02"})
    assert resultado.content[0].text == tools.listar_eventos_por_data("2026-10-02")


def test_data_invalida_e_erro_estruturado(calendario):
    resultado = _chamar(
        "viking_listar_eventos_por_data", {"data_inicio": "2026-09-20", "data_fim": "2026-09-10"}
    )
    assert resultado.is_error is True
    assert resultado.structured_content == {"erro": "entrada_invalida", "campo": "data"}
    assert calendario["consultas"] == []


def test_criar_dia_inteiro_pelo_mcp_tem_fim_exclusivo(calendario):
    resultado = _chamar(
        "viking_criar_evento_dia_inteiro", {"summary": "Feriado", "data": "2026-12-31"}
    )
    assert resultado.structured_content["all_day"] is True
    assert resultado.structured_content["end"] == "2027-01-01"


def test_apagar_titulo_divergente_pelo_mcp_nao_apaga(calendario):
    resultado = _chamar("viking_apagar_evento", {"event_id": "abc", "titulo_esperado": "Outro"})
    assert resultado.is_error is True
    assert resultado.structured_content["erro"] == "titulo_divergente"
    assert resultado.structured_content["titulo_real"] == "Dentista"
    assert calendario["apagados"] == []


@pytest.mark.parametrize(
    ("event_id", "titulo"), [("abc", ""), ("abc", "   "), ("", "Dentista"), ("abc", "dent")]
)
def test_travas_da_sessao_1_valem_pelo_mcp(calendario, event_id, titulo):
    """Segurança: um cliente MCP chama a tool destrutiva direto, sem o Gemini no meio — a trava
    precisa estar no domínio, não no prompt (§5.3). Vazio, só espaços, ID vazio e substring."""
    resultado = _chamar("viking_apagar_evento", {"event_id": event_id, "titulo_esperado": titulo})
    assert resultado.is_error is True
    assert calendario["apagados"] == []


def test_apagar_ok_pelo_mcp(calendario):
    resultado = _chamar("viking_apagar_evento", {"event_id": "abc", "titulo_esperado": "dentista"})
    assert resultado.is_error is False
    assert resultado.structured_content["title"] == "Dentista"
    assert calendario["apagados"] == ["abc"]


def test_falha_da_api_ao_reagendar_e_erro_estruturado(calendario):
    calendario["falhar_patch"] = True
    resultado = _chamar(
        "viking_reagendar_evento",
        {
            "event_id": "abc",
            "titulo_esperado": "Dentista",
            "novo_inicio": "2026-10-02T10:00",
            "novo_fim": "2026-10-02T11:00",
        },
    )
    assert resultado.is_error is True
    assert resultado.structured_content["erro"] == "falha_api"
    assert "Dentista" in resultado.content[0].text
