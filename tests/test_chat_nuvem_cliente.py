"""`viking chat --nuvem` no Mac (Sessão 10b, D59): o terminal guarda a conversa e a nota, e a
manda inteira a cada turno.

Sem rede: o transporte (`cliente.turno_de_chat`) é um roteiro que anota cada pedido. As perguntas:
o turno seguinte leva a conversa que o motor devolveu? Um erro de rede perde a conversa ou a nota?
Um texto com controle de terminal chega cru à tela? O `/custos` inventa número antes do primeiro
turno?
"""

import copy
import sys

import pytest

from lifeos.nuvem import chat_cliente, cliente

GASTO = {"dia": 0.01, "mes": 0.2, "teto_dia": 1.0, "teto_mes": 10.0, "estimado": True}


class _Motor:
    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def __call__(self, _sessao, pedido):
        self.pedidos.append(copy.deepcopy(pedido))
        passo = self.respostas.pop(0)
        if isinstance(passo, BaseException):
            raise passo
        return passo


def _rodar(monkeypatch, linhas, *respostas):
    motor = _Motor(*respostas)
    monkeypatch.setattr(cliente, "sessao_de_chat", lambda: object())
    monkeypatch.setattr(cliente, "capacidades", lambda _s: {"commit": "x", "gmail": True})
    monkeypatch.setattr(cliente, "turno_de_chat", motor)
    fila = iter(linhas)
    codigo = chat_cliente.iniciar(entrada=lambda _p="": next(fila))
    return codigo, motor


def _turno(texto, historico, nota="", **extra):
    return {"resposta": texto, "historico": historico, "nota": nota, "gasto": GASTO} | extra


def test_o_turno_seguinte_leva_a_conversa_e_a_nota_devolvidas(monkeypatch, capsys):
    h1 = [
        {"role": "user", "parts": [{"text": "oi"}]},
        {"role": "model", "parts": [{"text": "olá"}]},
    ]
    codigo, motor = _rodar(
        monkeypatch,
        ["oi", "e amanhã?", "sair"],
        _turno("olá", h1, nota="[Nota do Viking] x"),
        _turno("nada amanhã", [*h1, {"role": "user"}, {"role": "model"}]),
    )
    assert codigo == 0
    primeiro, segundo = motor.pedidos
    assert primeiro["historico"] == [] and primeiro["numero"] == 1
    assert segundo["historico"] == h1 and segundo["nota"] == "[Nota do Viking] x"
    assert segundo["numero"] == 2 and segundo["sessao"] == primeiro["sessao"]
    assert "🤖 Viking: nada amanhã" in capsys.readouterr().out


def test_erro_de_rede_nao_perde_a_conversa_nem_a_nota(monkeypatch, capsys):
    h1 = [{"role": "user", "parts": [{"text": "oi"}]}]
    codigo, motor = _rodar(
        monkeypatch,
        ["oi", "de novo", "de novo", "sair"],
        _turno("olá", h1, nota="nota"),
        cliente.ErroDaNuvem("a nuvem não respondeu em 320 s"),
        _turno("voltei", h1),
    )
    assert codigo == 0
    assert motor.pedidos[2]["historico"] == h1 and motor.pedidos[2]["nota"] == "nota"
    assert "❌ Nuvem: a nuvem não respondeu em 320 s." in capsys.readouterr().out


def test_erro_do_turno_mostra_o_erro_e_o_aviso(monkeypatch, capsys):
    _rodar(
        monkeypatch,
        ["marca dentista", "sair"],
        {
            "resposta": None,
            "erro": "Erro ao processar a resposta: 503",
            "aviso": "⚠️ Antes do erro, o Viking já fez (ou pode ter feito):\n- criou «Dentista»",
            "historico": [],
            "nota": "n",
            "gasto": GASTO,
        },
    )
    saida = capsys.readouterr().out
    assert "❌ Erro ao processar a resposta: 503" in saida and "criou «Dentista»" in saida


def test_texto_da_rede_sai_sem_controle_de_terminal(monkeypatch, capsys):
    malicioso = "evento" + chr(0x1B) + "]0;hack" + chr(7) + chr(0x9B) + "2J"
    _rodar(monkeypatch, ["oi", "sair"], _turno(malicioso, []))
    saida = capsys.readouterr().out
    assert chr(0x1B) not in saida and chr(0x9B) not in saida and chr(7) not in saida


def test_custos_antes_do_primeiro_turno_nao_inventa_numero(monkeypatch, capsys):
    _rodar(monkeypatch, ["/custos", "oi", "/custos", "sair"], _turno("olá", []))
    saida = capsys.readouterr().out
    assert "ainda não sei" in saida
    assert "hoje ~US$ 0,01 de US$ 1,00 · no mês ~US$ 0,20 de US$ 10,00" in saida


def test_sem_login_do_google_cloud_sai_1(monkeypatch, capsys):
    def sem_login():
        raise cliente.ErroDaNuvem("este computador não tem o login do Google Cloud")

    monkeypatch.setattr(cliente, "sessao_de_chat", sem_login)
    assert chat_cliente.iniciar(entrada=lambda _p="": "sair") == 1
    assert "login do Google Cloud" in capsys.readouterr().err


def test_viking_chat_nuvem_chega_aqui_e_nao_ao_chat_do_mac(monkeypatch):
    from lifeos import cli
    from lifeos.assistant import agent

    monkeypatch.setattr(chat_cliente, "iniciar", lambda: 7)
    monkeypatch.setattr(agent, "iniciar_assistente", lambda: pytest.fail("chat do Mac"))
    monkeypatch.setattr(sys, "argv", ["viking", "chat", "--nuvem"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 7


# --- o que só o dono vê (Sessão 10c, D60) --------------------------------------------------------


def _com_terminal(monkeypatch, interativo: bool):
    from lifeos import ao_dono

    monkeypatch.setattr(ao_dono, "interativo", lambda: interativo)


def test_o_pedido_diz_se_o_terminal_e_interativo(monkeypatch, capsys):
    _com_terminal(monkeypatch, True)
    _, motor = _rodar(monkeypatch, ["oi", "sair"], _turno("olá", []))
    assert motor.pedidos[0]["interativo"] is True
    _com_terminal(monkeypatch, False)
    _, motor = _rodar(monkeypatch, ["oi", "sair"], _turno("olá", []))
    assert motor.pedidos[0]["interativo"] is False


def test_ao_dono_aparece_so_num_terminal_interativo(monkeypatch, capsys):
    so_dele = "Para aprovar, digite:  confirma 6284"
    resposta = _turno(None, [], ao_dono=[so_dele + "\x1b[2J"])
    _com_terminal(monkeypatch, True)
    _rodar(monkeypatch, ["confirma 6284", "sair"], resposta)
    saida = capsys.readouterr().out
    assert so_dele in saida and "\x1b" not in saida
    assert "não respondeu" not in saida  # a resposta da barreira vem só em `ao_dono`

    _com_terminal(monkeypatch, False)
    _rodar(monkeypatch, ["confirma 6284", "sair"], resposta)
    saida = capsys.readouterr().out
    assert "6284" not in saida.replace("Você: ", "") and chat_cliente.SEM_TERMINAL in saida


# --- a abertura diz o que a nuvem tem (Sessão 11, D61) ---------------------------------------


def test_a_abertura_nao_promete_o_gmail_que_nao_esta_la():
    sem = chat_cliente.abertura({"commit": "x", "gmail": False})
    assert (
        sem
        == "☁️  Viking na nuvem (agenda e lembretes). Navegador, Gmail e finanças: `viking chat`."
    )
    com = chat_cliente.abertura({"commit": "x", "gmail": True})
    assert (
        com
        == "☁️  Viking na nuvem (agenda, lembretes e Gmail). Navegador e finanças: `viking chat`."
    )
    assert chat_cliente.abertura({}) == sem  # um motor velho, sem o campo: não promete
    maos = chat_cliente.abertura({"commit": "x", "gmail": False, "maos": True})
    assert maos == (
        "☁️  Viking na nuvem (agenda, lembretes e o navegador do Mac, com o `viking maos` ligado "
        "lá). Gmail e finanças: `viking chat`."
    )


def test_sem_o_primeiro_contato_nao_abre(monkeypatch, capsys):
    monkeypatch.setattr(cliente, "sessao_de_chat", lambda: object())

    def recusa(_s):
        raise cliente.ErroDaNuvem("a nuvem recusou a identidade (HTTP 403)")

    monkeypatch.setattr(cliente, "capacidades", recusa)
    assert chat_cliente.iniciar(entrada=lambda _p="": "sair") == 1
    assert "❌ Nuvem: a nuvem recusou a identidade (HTTP 403)." in capsys.readouterr().err


# --- o aviso do backup na abertura (Sessão 11c, D63) --------------------------------------------


def test_o_aviso_do_backup_vem_so_depois_de_48_horas():
    from datetime import UTC, datetime, timedelta

    agora = datetime(2026, 10, 9, 12, tzinfo=UTC)

    def com(horas):
        feito = (agora - timedelta(hours=horas)).isoformat()
        return chat_cliente.aviso_do_backup({"backup": True, "backup_em": feito}, agora)

    assert com(47) is None
    assert com(49) == (
        "⚠️  Backup no Drive: conferido pela última vez há 2.0 dias; a rodada diária pode estar "
        "falhando (`viking backup`)."
    )
    nenhum = chat_cliente.aviso_do_backup({"backup": True, "backup_em": None}, agora)
    assert nenhum is not None and "nenhum feito ainda" in nenhum


def test_sem_o_backup_ligado_a_abertura_nao_fala_dele():
    assert chat_cliente.aviso_do_backup({"backup": False, "backup_em": None}) is None
    assert chat_cliente.aviso_do_backup({}) is None  # um motor velho, sem o campo


def test_viking_backup_diz_a_ultima_conferencia_e_nao_promete_um_arquivo_por_dia(
    monkeypatch, capsys
):
    """Desde 2026-10-07 o `backup_em` é a última vez que o Drive confirmou o conteúdo de agora (um
    arquivo novo só quando algo muda): o texto não pode dizer que um arquivo nasceu naquela hora."""
    from argparse import Namespace

    from lifeos import cli
    from lifeos.nuvem import cliente

    monkeypatch.setattr(cliente, "sessao_de_chat", lambda: None)
    monkeypatch.setattr(
        cliente,
        "capacidades",
        lambda _s: {"backup": True, "backup_em": "2026-10-08T09:00:02+00:00"},
    )
    args = Namespace(conferir=False, restaurar=None, executar=False, login=False)
    assert cli._backup(args) == 0
    saida = capsys.readouterr().out
    assert "conferido em 2026-10-08T09:00:02+00:00 (UTC)" in saida
    assert "um arquivo novo só quando algo muda" in saida
