"""`viking memoria` no Mac (Sessão 13, D66): a lista e as ações, sem rede (o cliente é trocado).

As perguntas: sem opção, só os ativos; `--todos` diz o estado de cada um; `--semana` corta em 7
dias; o texto que vem da rede sai sem controle de terminal; erro da nuvem ou resposta torta saem
com 1 e uma frase, nunca um traceback.
"""

from argparse import Namespace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from lifeos import config
from lifeos.memoria import terminal
from lifeos.nuvem import cliente

AGORA = datetime(2026, 10, 8, 18, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fuso(monkeypatch):
    monkeypatch.setattr(config, "TIMEZONE", ZoneInfo("America/Los_Angeles"))


def _fato(texto, *, dias=0, **marcas):
    criado = AGORA - timedelta(days=dias)
    fato = {
        "id": f"{abs(hash(texto)) % 10**8:08d}-0000-4000-8000-000000000000",
        "texto": texto,
        "origem": "chat",
        "sessao": "",
        "turno": "",
        "criado_em": criado.isoformat(),
        "ativo": True,
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    fato.update(marcas)
    return fato


ATIVO = _fato("O usuário corre aos sábados.", dias=1)
TROCADO = _fato(
    "O usuário treina às 7h.",
    dias=10,
    ativo=False,
    invalida_em=(AGORA - timedelta(days=2)).isoformat(),
    substituido_por="abcdef01-0000-4000-8000-000000000000",
)
ESQUECIDO = _fato(
    "O usuário toca violão.",
    dias=3,
    ativo=False,
    esquecido_em=(AGORA - timedelta(days=1)).isoformat(),
    apagar_em=(AGORA + timedelta(days=29)).isoformat(),
)
FATOS = [ATIVO, ESQUECIDO, TROCADO]


def test_sem_opcao_so_os_ativos():
    texto = terminal.lista(FATOS, agora=AGORA)
    assert texto.splitlines() == [f"{ATIVO['id'][:8]}  07/10/2026  O usuário corre aos sábados."]


def test_todos_diz_o_estado_de_cada_um():
    linhas = terminal.lista(FATOS, todos=True, agora=AGORA).splitlines()
    assert len(linhas) == 3
    assert linhas[1].endswith("O usuário toca violão. (esquecido; some em 06/11/2026)")
    assert linhas[2].endswith("O usuário treina às 7h. (trocado em 06/10/2026 por abcdef01)")


def test_semana_corta_em_7_dias():
    linhas = terminal.lista(FATOS, semana=True, agora=AGORA).splitlines()
    assert [linha.split("  ")[-1] for linha in linhas] == [
        "O usuário corre aos sábados.",
        "O usuário toca violão. (esquecido; some em 06/11/2026)",
    ]


def test_listas_vazias_dizem_o_que_fazer():
    assert "viking memoria --todos" in terminal.lista([ESQUECIDO], agora=AGORA)
    assert terminal.lista([], todos=True) == "A memória está vazia."
    assert terminal.lista([TROCADO], semana=True, agora=AGORA) == "Nada anotado nos últimos 7 dias."


def test_o_texto_da_rede_sai_sem_controle_de_terminal():
    linha = terminal.linha(_fato("O usuário\x1b[2J corre."))
    assert "\x1b" not in linha and linha.endswith("O usuário[2J corre.")


def _args(**kw):
    base = {
        "todos": False,
        "semana": False,
        "esquecer": None,
        "desfazer": None,
        "corrigir": None,
        "reindexar": False,
        "receitas": False,
        "texto": None,
    }
    base.update(kw)
    return Namespace(**base)


def test_corrigir_sem_texto_e_texto_sem_corrigir_saem_com_1(capsys, monkeypatch):
    monkeypatch.setattr(cliente, "acao_da_memoria", lambda *_a: pytest.fail("não devia chamar"))
    monkeypatch.setattr(cliente, "da_memoria", lambda: pytest.fail("não devia chamar"))
    assert terminal.executar(_args(corrigir="abcdef01")) == 1
    assert terminal.executar(_args(texto="x")) == 1
    assert "--texto" in capsys.readouterr().err


def test_cada_acao_chama_a_rota_certa(capsys, monkeypatch):
    pedidos = []

    def acao(nome, corpo):
        pedidos.append((nome, corpo))
        return {"refeitos": 2} if nome == "reindexar" else {"fato": ATIVO}

    monkeypatch.setattr(cliente, "acao_da_memoria", acao)
    assert terminal.executar(_args(esquecer="abcdef01")) == 0
    assert terminal.executar(_args(desfazer="abcdef01")) == 0
    assert terminal.executar(_args(corrigir="abcdef01", texto="O usuário corre aos domingos.")) == 0
    assert terminal.executar(_args(reindexar=True)) == 0
    assert pedidos == [
        ("esquecer", {"id": "abcdef01"}),
        ("desfazer", {"id": "abcdef01"}),
        ("corrigir", {"id": "abcdef01", "texto": "O usuário corre aos domingos."}),
        ("reindexar", {}),
    ]
    saida = capsys.readouterr().out
    assert "🗑️ esquecido" in saida and "↩️ de volta" in saida and "vetores refeitos: 2" in saida


def test_erro_da_nuvem_e_resposta_torta_saem_com_1(capsys, monkeypatch):
    def falha():
        raise cliente.ErroDaNuvem("a nuvem não respondeu")

    monkeypatch.setattr(cliente, "da_memoria", falha)
    assert terminal.executar(_args()) == 1
    monkeypatch.setattr(cliente, "acao_da_memoria", lambda *_a: {"outra": 1})
    assert terminal.executar(_args(esquecer="abcdef01")) == 1
    erro = capsys.readouterr().err
    assert "a nuvem não respondeu" in erro and "formato inesperado" in erro


def test_o_cliente_so_aceita_as_acoes_conhecidas():
    with pytest.raises(ValueError, match="desconhecida"):
        cliente.acao_da_memoria("apagar", {})


# --- as receitas (Sessão 13b, D67) ---------------------------------------------------------------


def _receita(nome, *, dias=0, **marcas):
    criado = AGORA - timedelta(days=dias)
    receita = {
        "id": f"{abs(hash(nome)) % 10**8:08d}-1111-4000-8000-000000000000",
        "nome": nome,
        "passos": ["veja a agenda", "mande por e-mail"],
        "estado": "guardada",
        "ativo": True,
        "origem": "chat",
        "sessao": "",
        "turno": "",
        "criado_em": criado.isoformat(),
        "guardada_em": criado.isoformat(),
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    receita.update(marcas)
    return receita


GUARDADA = _receita("fechamento", dias=1)
PROPOSTA = _receita(
    "ignorada",
    estado="proposta",
    ativo=False,
    guardada_em=None,
    apagar_em=(AGORA + timedelta(days=1)).isoformat(),
)
ESQUECIDA = _receita(
    "velha",
    dias=2,
    ativo=False,
    esquecido_em=(AGORA - timedelta(days=1)).isoformat(),
    apagar_em=(AGORA + timedelta(days=29)).isoformat(),
)
RECEITAS = [GUARDADA, PROPOSTA, ESQUECIDA]


def test_a_lista_mostra_as_receitas_guardadas_marcadas():
    linhas = terminal.lista([ATIVO], RECEITAS, agora=AGORA).splitlines()
    assert linhas[1] == f"{GUARDADA['id'][:8]}  07/10/2026  📋 fechamento (2 passo(s))"
    assert len(linhas) == 2


def test_todos_mostra_a_proposta_e_a_esquecida():
    linhas = terminal.lista([], RECEITAS, todos=True, agora=AGORA).splitlines()
    assert linhas[1].endswith(
        "📋 ignorada (2 passo(s)) (proposta, não guardada; some em 09/10/2026)"
    )
    assert linhas[2].endswith("📋 velha (2 passo(s)) (esquecido; some em 06/11/2026)")


def test_so_com_receita_a_lista_nao_diz_vazia():
    assert "📋 fechamento" in terminal.lista([], [GUARDADA], agora=AGORA)


def test_receitas_mostra_os_passos_inteiros_e_limpos():
    suja = _receita("bom\x1b[2J dia", passos=["mostre\x07 a agenda"])
    texto = terminal.so_receitas([suja, PROPOSTA])
    assert texto.splitlines()[1:] == ["   1. mostre a agenda"]
    assert "\x1b" not in texto and "ignorada" not in texto
    assert "Nenhuma receita guardada" in terminal.so_receitas([PROPOSTA])


def test_receitas_e_esquecer_uma_receita_pelo_terminal(capsys, monkeypatch):
    monkeypatch.setattr(cliente, "da_memoria", lambda: ([ATIVO], [GUARDADA]))
    monkeypatch.setattr(cliente, "acao_da_memoria", lambda *_a: {"receita": ESQUECIDA})
    assert terminal.executar(_args(receitas=True)) == 0
    assert terminal.executar(_args(esquecer="abcdef01")) == 0
    saida = capsys.readouterr().out
    assert "   1. veja a agenda" in saida and "O usuário corre" not in saida
    assert "🗑️ esquecido" in saida and "📋 velha" in saida


@pytest.mark.parametrize(
    ("resposta", "esperado"),
    [
        ({"fatos": [ATIVO]}, ([ATIVO], [])),  # um motor de antes da 13b
        ({"fatos": [ATIVO], "receitas": [GUARDADA]}, ([ATIVO], [GUARDADA])),
        ({"fatos": [ATIVO], "receitas": "x"}, None),
        ({"fatos": [ATIVO], "receitas": [3]}, None),
        ({"receitas": []}, None),
    ],
)
def test_o_cliente_confere_a_lista_da_memoria(monkeypatch, resposta, esperado):
    monkeypatch.setattr(cliente, "_sessao", lambda: None)
    monkeypatch.setattr(cliente, "_chamar", lambda *_a, **_k: resposta)
    if esperado is None:
        with pytest.raises(cliente.ErroDaNuvem, match="formato inesperado"):
            cliente.da_memoria()
    else:
        assert cliente.da_memoria() == esperado
