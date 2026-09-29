"""O roteiro ao vivo da 3b (`scripts/calendario_mcp_ao_vivo.py`) roda, offline, contra o dublê do
Google: o MCP de verdade em memória, o evento de dia inteiro criado, listado, buscado e o apagar
só PEDIDO. E a saída nunca mostra o ID do evento (o dono cola a saída na conversa; repo público).
"""

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DATA = "2027-03-10"


def _script():
    if "calendario_mcp_ao_vivo" in sys.modules:
        return sys.modules["calendario_mcp_ao_vivo"]
    caminho = RAIZ / "scripts" / "calendario_mcp_ao_vivo.py"
    spec = importlib.util.spec_from_file_location("calendario_mcp_ao_vivo", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["calendario_mcp_ao_vivo"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def agenda(calendario):
    calendario["insert_aparece"] = True
    calendario["evento"] = {"id": "novo123", "summary": "Teste Viking 3b", "start": {"date": DATA}}
    return calendario


def _rodar(*args: str) -> int:
    return asyncio.run(_script().main(list(args)))


def test_cria_lista_busca_e_so_pede_para_apagar(agenda, capsys):
    assert _rodar(DATA) == 0
    saida = capsys.readouterr().out
    assert "1. criar: ok · dia inteiro: True" in saida
    assert f"2. listar por data: 1 achado(s) · dia inteiro em {DATA}: 1" in saida
    assert "3. buscar: 1 achado(s) · completa: True" in saida
    assert "4. pedido de apagar: aguardando_aprovacao" in saida
    assert agenda["enviados"] == [
        {
            "summary": "Teste Viking 3b",
            "description": "",
            "start": {"date": DATA},
            "end": {"date": "2027-03-11"},
        }
    ]
    assert agenda["apagados"] == []
    assert "novo123" not in saida


def test_se_ja_existe_nao_cria_outro(agenda, capsys):
    agenda["itens"] = [{"id": "velho", "summary": "Teste Viking 3b", "start": {"date": DATA}}]
    assert _rodar(DATA) == 1
    assert agenda["enviados"] == []
    assert "velho" not in capsys.readouterr().out


def test_conferir_conta_os_que_restam(agenda, capsys):
    assert _rodar(DATA, "--conferir") == 0
    assert f"ainda no calendário em {DATA}: 0" in capsys.readouterr().out
    agenda["itens"] = [{"id": "x", "summary": "Teste Viking 3b", "start": {"date": DATA}}]
    assert _rodar(DATA, "--conferir") == 1


def test_data_invalida_nao_chama_nada(agenda, capsys):
    assert _rodar("amanhã") == 1
    assert agenda["consultas"] == []
    assert agenda["enviados"] == []
