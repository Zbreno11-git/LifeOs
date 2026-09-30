"""Pedidos pelo MCP e a aprovação no terminal (Sessão 5, D36).

O ataque: um app ligado no servidor MCP (ou um modelo dentro dele, induzido por um texto) apaga
um evento do dono. Agora o MCP só registra o PEDIDO; nada muda até o dono rodar `viking aprovar`
num terminal de verdade e digitar o código. As perguntas: o código vaza para o app? O pedido
apaga sozinho? Um código errado, velho ou de um evento que mudou aprova?
"""

import ast
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.sentinela import aparece

from lifeos import aprovacoes, cli, confirmacao, registro
from lifeos.calendar import service as calendario_service

SENTINELA = "4821"


@pytest.fixture()
def pedidos(calendario, monkeypatch):
    sorteios = iter([int(SENTINELA), *range(1000, 1100)])
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(sorteios))
    return calendario


def _chamar(nome: str, args: dict):
    from fastmcp import Client

    from lifeos.mcp_server.server import mcp

    async def _rodar():
        async with Client(mcp) as client:
            return await client.call_tool(nome, args, raise_on_error=False)

    return asyncio.run(_rodar())


def _pedir_apagar():
    return _chamar("viking_apagar_evento", {"event_id": "abc", "titulo_esperado": "Dentista"})


def _abertos():
    return confirmacao.abertas(aprovacoes.CALENDARIO_APAGAR) + confirmacao.abertas(
        aprovacoes.CALENDARIO_REAGENDAR
    )


# --- o MCP só pede ----------------------------------------------------------------------------


def test_apagar_pelo_mcp_so_pede_e_o_codigo_nao_sai(pedidos):
    resultado = _pedir_apagar()
    assert resultado.is_error is False
    dados = resultado.structured_content
    assert (dados["estado"], dados["aprovar_com"], dados["evento"]["title"]) == (
        "aguardando_aprovacao",
        "viking aprovar",
        "Dentista",
    )
    assert pedidos["apagados"] == []
    texto = resultado.content[0].text
    assert "NADA mudou ainda" in texto
    assert not aparece(SENTINELA, texto) and not aparece(SENTINELA, dados)
    (aberto,) = _abertos()
    assert aberto.codigo == SENTINELA  # o código existe — só não saiu pelo MCP


def test_reagendar_pelo_mcp_so_pede(pedidos):
    resultado = _chamar(
        "viking_reagendar_evento",
        {
            "event_id": "abc",
            "titulo_esperado": "Dentista",
            "novo_inicio": "2026-10-02T10:00",
            "novo_fim": "2026-10-02T11:00",
        },
    )
    assert resultado.is_error is False and pedidos["patches"] == []
    assert not aparece(SENTINELA, resultado.content[0].text)


def test_dois_pedidos_convivem(pedidos):
    _pedir_apagar()
    _pedir_apagar()
    assert len(_abertos()) == 2  # um não some em silêncio por causa do outro


def test_limite_de_pedidos_abertos(pedidos):
    for _ in range(calendario_service.MAX_PEDIDOS_ABERTOS):
        assert _pedir_apagar().is_error is False
    sexto = _pedir_apagar()
    assert sexto.is_error is True
    assert sexto.structured_content["erro"] == "limite_de_pedidos"


def test_limite_de_pedidos_por_hora(pedidos):
    for _ in range(calendario_service.MAX_PEDIDOS_POR_HORA):
        assert _pedir_apagar().is_error is False
        confirmacao.cancelar(aprovacoes.CALENDARIO_APAGAR)  # abertos em zero: só a hora conta
    assert _pedir_apagar().structured_content["erro"] == "limite_de_pedidos"


def test_origem_mcp_no_registro(pedidos):
    _chamar(
        "viking_criar_evento",
        {"summary": "Reunião", "start_time": "2026-10-01T10:00", "end_time": "2026-10-01T11:00"},
    )
    assert [a.origem for a in registro.recentes()] == ["mcp"]


# --- `viking aprovar` ---------------------------------------------------------------------


def _aprovar(monkeypatch, digitado, *, tty=True):
    monkeypatch.setattr("sys.stdin.isatty", lambda: tty)
    monkeypatch.setattr("sys.stdout.isatty", lambda: tty)
    fila = iter(digitado)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(fila))
    monkeypatch.setattr("sys.argv", ["viking", "aprovar"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


def test_aprovar_sem_terminal_interativo_recusa(pedidos, monkeypatch, capsys):
    _pedir_apagar()
    assert _aprovar(monkeypatch, [], tty=False) == 2
    assert pedidos["apagados"] == [] and len(_abertos()) == 1
    assert not aparece(SENTINELA, capsys.readouterr().out)  # nem o código aparece


def test_aprovar_com_o_codigo_apaga_uma_vez(pedidos, monkeypatch, capsys):
    _pedir_apagar()
    assert _aprovar(monkeypatch, [SENTINELA]) == 0
    assert pedidos["apagados"] == ["abc"]
    assert "✅ Evento 'Dentista' apagado" in capsys.readouterr().out
    (acao,) = [a for a in registro.recentes() if a.operacao == "calendario.apagar"]
    assert acao.origem == "mcp"
    assert _aprovar(monkeypatch, []) == 0
    assert "Nenhum pedido esperando" in capsys.readouterr().out


def test_aprovar_com_codigo_errado_nao_apaga(pedidos, monkeypatch):
    _pedir_apagar()
    assert _aprovar(monkeypatch, ["0000"]) == 2
    assert pedidos["apagados"] == [] and len(_abertos()) == 1


def test_enter_pula_sem_mexer(pedidos, monkeypatch, capsys):
    _pedir_apagar()
    assert _aprovar(monkeypatch, [""]) == 0
    assert pedidos["apagados"] == [] and len(_abertos()) == 1
    assert "Pulado" in capsys.readouterr().out


def test_pedido_de_mais_de_uma_hora_nao_aparece(pedidos, monkeypatch, capsys):
    agora = datetime.now(UTC) - aprovacoes.VALIDADE_MCP - timedelta(minutes=1)
    calendario_service.pedir_mudanca(calendario_service.APAGAR, "abc", "Dentista", agora=agora)
    assert _aprovar(monkeypatch, []) == 0
    assert "Nenhum pedido esperando" in capsys.readouterr().out
    with pytest.raises(confirmacao.Expirado):
        calendario_service.executar_aprovado(calendario_service.APAGAR, SENTINELA)
    assert pedidos["apagados"] == []


@pytest.mark.parametrize(
    "mudanca",
    [
        {"summary": "Outro"},
        {"etag": "v2"},
        {"updated": "2026-09-27T12:00:00Z"},
        {"start": {"date": "2026-10-05"}},
        {"status": "cancelled"},
    ],
)
def test_evento_que_mudou_desde_o_pedido_nao_e_mexido(pedidos, monkeypatch, capsys, mudanca):
    pedidos["evento"].update({"etag": "v1", "updated": "2026-09-27T10:00:00Z"})
    _pedir_apagar()
    pedidos["evento"].update(mudanca)
    assert _aprovar(monkeypatch, [SENTINELA]) == 2
    assert pedidos["apagados"] == []
    assert "mudou (ou foi apagado) desde o pedido" in capsys.readouterr().err


def _evento_com_hora(pedidos, inicio):
    pedidos["evento"].update(
        {
            "start": {"dateTime": inicio},
            "end": {"dateTime": "2026-10-01T14:00:00-03:00"},
            "etag": "v1",
            "updated": "2026-09-27T10:00:00Z",
        }
    )


def test_fuso_do_dono_diferente_na_aprovacao_nao_e_mudanca(pedidos, monkeypatch, capsys):
    """O servidor MCP e o `viking aprovar` são processos diferentes, e o fuso do dono de cada um
    pode não ser o mesmo (sem `VIKING_TIMEZONE`, o do relógio de quem subiu o processo). O mesmo
    instante, escrito noutro fuso, não é um evento que mudou (antes: recusava, 2026-09-28)."""
    from zoneinfo import ZoneInfo

    _evento_com_hora(pedidos, "2026-10-01T13:00:00-03:00")
    _pedir_apagar()
    monkeypatch.setattr(calendario_service, "TIMEZONE", ZoneInfo("Asia/Tokyo"))
    assert _aprovar(monkeypatch, [SENTINELA]) == 0
    assert pedidos["apagados"] == ["abc"]


def test_evento_que_andou_uma_hora_com_a_mesma_versao_nao_e_mexido(pedidos, monkeypatch, capsys):
    """A regra do início sozinha: `etag` e `updated` iguais aos do pedido, e o início uma hora
    depois. Quem recusa aqui é a comparação do instante, não a da versão."""
    _evento_com_hora(pedidos, "2026-10-01T13:00:00-03:00")
    _pedir_apagar()
    pedidos["evento"]["start"] = {"dateTime": "2026-10-01T14:00:00-03:00"}
    assert _aprovar(monkeypatch, [SENTINELA]) == 2
    assert pedidos["apagados"] == []
    assert "mudou (ou foi apagado) desde o pedido" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("a", "b", "igual"),
    [
        ("2026-10-01T13:00:00-03:00", "2026-10-01T09:00:00-07:00", True),
        ("2026-10-01T13:00:00-03:00", "2026-10-01T13:00:00-07:00", False),
        ("2026-10-01", "2026-10-01", True),
        ("2026-10-01", "2026-10-02", False),
        # dia inteiro nunca é o mesmo que um horário, mesmo à meia-noite (com e sem fuso)
        ("2026-10-01", "2026-10-01T00:00:00-03:00", False),
        ("2026-10-01", "2026-10-01T00:00:00", False),
        # com fuso contra sem fuso: não dá para saber se é o mesmo instante
        ("2026-10-01T13:00:00", "2026-10-01T13:00:00-03:00", False),
        # vazio ou texto que não é horário nunca é "o mesmo", nem igual ao outro
        ("sem data", "sem data", False),
        (None, None, False),
    ],
)
def test_mesmo_instante(a, b, igual):
    assert calendario_service._mesmo_instante(a, b) is igual


def test_reagendar_aprovado_muda_o_horario(pedidos, monkeypatch):
    _chamar(
        "viking_reagendar_evento",
        {
            "event_id": "abc",
            "titulo_esperado": "Dentista",
            "novo_inicio": "2026-10-02T10:00",
            "novo_fim": "2026-10-02T11:00",
        },
    )
    assert _aprovar(monkeypatch, [SENTINELA]) == 0
    (_id, corpo) = pedidos["patches"][-1]
    assert corpo["start"]["dateTime"].startswith("2026-10-02T10:00")


# --- quem pode executar um pedido ---------------------------------------------------------


def _quem_chama(nome: str) -> set[str]:
    raiz = Path(registro.__file__).parent
    return {
        str(arquivo.relative_to(raiz))
        for arquivo in raiz.rglob("*.py")
        for no in ast.walk(ast.parse(arquivo.read_text()))
        if isinstance(no, ast.Call)
        and getattr(no.func, "attr", getattr(no.func, "id", None)) == nome
    }


def test_so_a_cli_executa_um_pedido_aprovado():
    assert _quem_chama("executar_aprovado") == {"cli.py"}


def test_o_mcp_nunca_consome_codigo():
    fonte = (Path(registro.__file__).parent / "mcp_server" / "server.py").read_text()
    assert "consumir" not in fonte and "executar_aprovado" not in fonte
    assert "print(" not in fonte  # o stdout do MCP é o canal do protocolo
