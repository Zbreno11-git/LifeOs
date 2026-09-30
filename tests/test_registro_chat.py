"""O registro de ações no laço do chat (Sessão 5): o aviso depois de um erro, o `desfaz` sozinho e
o que o Gemini lê.

O cenário do §7 da auditoria: uma tool agiu, a chamada seguinte ao Gemini falhou, o dono via só
"❌ Erro" e pedia de novo. Aqui o "Gemini" é um roteiro: cada turno é uma função que faz o que o
function-calling faria (chama a tool) e, se for o caso, levanta depois.
"""

import pytest

from lifeos import cli, registro
from lifeos.assistant import agent
from lifeos.calendar import tools as calendario_tools


class _Resposta:
    text = "ok"


class _ChatRoteiro:
    def __init__(self, turnos):
        self.turnos = list(turnos)
        self.enviados = []

    def send_message(self, prompt):
        self.enviados.append(prompt)
        passo = self.turnos.pop(0) if self.turnos else None
        if passo is not None:
            passo()
        return _Resposta()


def _rodar(monkeypatch, linhas, turnos):
    chat = _ChatRoteiro(turnos)

    class _Cliente:
        class chats:
            @staticmethod
            def create(**_kwargs):
                return chat

    fila = iter(linhas)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(fila))
    monkeypatch.setattr(agent, "_build_client", lambda: _Cliente())
    monkeypatch.setattr(agent.custos, "instrumentar", lambda _cliente: None)
    agent.iniciar_assistente()
    return chat


def _cria_e_falha():
    calendario_tools.criar_evento("Dentista", "2026-10-01T10:00:00", "2026-10-01T11:00:00")
    raise RuntimeError("503 do Gemini")  # a tool agiu; a volta ao modelo falhou


# --- o aviso depois de um erro --------------------------------------------------------------


def test_erro_depois_de_agir_diz_o_que_ja_foi_feito(calendario, monkeypatch, capsys):
    chat = _rodar(monkeypatch, ["marca dentista", "e agora?", "sair"], [_cria_e_falha, None])
    saida = capsys.readouterr().out
    assert "❌ Erro ao processar a resposta" in saida
    assert "⚠️ Antes do erro, o Viking já fez (ou pode ter feito):" in saida
    assert "criou o evento «Dentista»" in saida
    # O Gemini recebe a lista no turno seguinte, junto com o pedido.
    assert "Não repita nenhuma sem perguntar" in chat.enviados[1]
    assert chat.enviados[1].endswith("e agora?")
    assert calendario["enviados"] and len(calendario["enviados"]) == 1


def test_erro_sem_ter_agido_nao_avisa(calendario, monkeypatch, capsys):
    def so_falha():
        raise RuntimeError("503")

    chat = _rodar(monkeypatch, ["oi", "de novo", "sair"], [so_falha, None])
    assert "Antes do erro" not in capsys.readouterr().out
    assert chat.enviados[1] == "de novo"


def test_falha_certa_antes_do_erro_nao_conta_como_feito(calendario, monkeypatch, capsys):
    calendario["falhar_insert"] = True
    _rodar(monkeypatch, ["marca dentista", "sair"], [_cria_e_falha])
    assert "Antes do erro" not in capsys.readouterr().out


def test_falha_ambigua_antes_do_erro_aparece_como_pode_ter_sido(calendario, monkeypatch, capsys):
    calendario["erro_no_execute"] = TimeoutError("timed out")
    calendario["aplicar_antes"] = True

    def apaga_e_falha():
        calendario_tools.apagar_evento_por_id("abc", "Dentista")
        raise RuntimeError("503")

    _rodar(monkeypatch, ["apaga o dentista", "sair"], [apaga_e_falha])
    assert "apagou o evento «Dentista» (2026-10-01) (pode ter sido feito: confira)" in (
        capsys.readouterr().out
    )


def test_aviso_e_nota_de_aprovacao_se_somam(calendario, monkeypatch):
    chat = _rodar(monkeypatch, ["marca dentista", "confirma", "e agora?", "sair"], [_cria_e_falha])
    assert "Não repita nenhuma" in chat.enviados[1]  # a instrução do "confirma" não apagou o aviso


# --- `desfaz` sozinho -----------------------------------------------------------------------


def _apaga():
    calendario_tools.apagar_evento_por_id("abc", "Dentista")


def test_desfaz_devolve_o_evento_apagado_sem_o_gemini(calendario, monkeypatch, capsys):
    chat = _rodar(monkeypatch, ["apaga o dentista", "desfaz", "sair"], [_apaga])
    assert chat.enviados == ["apaga o dentista"]
    assert calendario["patches"][-1] == ("abc", {"status": "confirmed"})
    assert calendario["extras"][-1] == ("patch", {"sendUpdates": "none"})
    assert "O evento 'Dentista' voltou ao calendário" in capsys.readouterr().out


def test_desfaz_duas_vezes_a_segunda_so_explica(calendario, monkeypatch, capsys):
    _rodar(monkeypatch, ["apaga o dentista", "desfaz", "desfaz", "sair"], [_apaga])
    assert len(calendario["patches"]) == 1
    assert "digite `confirma` e o código" in capsys.readouterr().out


def test_desfaz_nao_alcanca_outra_sessao(calendario, monkeypatch):
    token = registro.TURNO.set("sessao-velha:1")
    try:
        _apaga()
    finally:
        registro.TURNO.reset(token)
    _rodar(monkeypatch, ["desfaz", "sair"], [])
    assert calendario["patches"] == []


def test_desfaz_recria_sem_convidados_quando_o_evento_sumiu(calendario, monkeypatch, capsys):
    calendario["evento"]["attendees"] = [{"email": "fulano@exemplo.com"}]
    calendario["evento"]["id"] = "abc"

    def apaga_e_some():
        _apaga()
        calendario["evento"] = None  # o `get` de agora dá "Not Found"

    _rodar(monkeypatch, ["apaga o dentista", "desfaz", "sair"], [apaga_e_some])
    recriado = calendario["enviados"][-1]
    assert recriado["summary"] == "Dentista" and "attendees" not in recriado
    assert calendario["extras"][-1] == ("insert", {"sendUpdates": "none"})
    assert "ninguém recebeu aviso" in capsys.readouterr().out


def test_desfaz_recusa_evento_de_serie(calendario, monkeypatch, capsys):
    calendario["evento"]["recurringEventId"] = "serie1"
    _rodar(monkeypatch, ["apaga o dentista", "desfaz", "sair"], [_apaga])
    assert calendario["patches"] == [] and calendario["enviados"] == []
    assert "Não desfiz: é um evento de série" in capsys.readouterr().out


def test_desfaz_volta_o_horario_de_dia_inteiro(calendario, monkeypatch, capsys):
    calendario["evento"]["end"] = {"date": "2026-10-02"}

    def reagenda():
        calendario_tools.reagendar_evento_por_id(
            "abc", "Dentista", "2026-10-02T10:00:00", "2026-10-02T11:00:00"
        )

    _rodar(monkeypatch, ["passa pro dia 2", "desfaz", "sair"], [reagenda])
    _id, corpo = calendario["patches"][-1]
    assert corpo["start"] == {"date": "2026-10-01", "dateTime": None}
    assert "voltou ao horário de antes" in capsys.readouterr().out


def test_desfaz_nao_mexe_se_o_horario_mudou_depois(calendario, monkeypatch, capsys):
    calendario["evento"]["end"] = {"date": "2026-10-02"}

    def reagenda_e_alguem_muda():
        calendario_tools.reagendar_evento_por_id(
            "abc", "Dentista", "2026-10-02T10:00:00", "2026-10-02T11:00:00"
        )
        calendario["evento"]["start"] = {"dateTime": "2026-10-05T09:00:00-03:00"}

    _rodar(monkeypatch, ["passa pro dia 2", "desfaz", "desfaz", "sair"], [reagenda_e_alguem_muda])
    assert len(calendario["patches"]) == 1  # só o reagendamento
    saida = capsys.readouterr().out
    assert "o horário mudou depois do reagendamento" in saida
    # Recusado, continua desfazível (não foi gasto): o segundo `desfaz` explica de novo.
    assert saida.count("o horário mudou depois") == 2


# --- o que fica registrado, e com que origem -----------------------------------------------


def test_origem_no_chat_e_chat(calendario, monkeypatch):
    _rodar(monkeypatch, ["apaga o dentista", "sair"], [_apaga])
    assert {a.origem for a in registro.recentes()} == {"chat"}


def test_viking_registro_lista_e_desfaz(calendario, monkeypatch, capsys):
    token = registro.TURNO.set("x:1")
    try:
        _apaga()
    finally:
        registro.TURNO.reset(token)
    (acao,) = registro.recentes()
    monkeypatch.setattr("sys.argv", ["viking", "registro", "--ids"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 0
    assert f"[{acao.id}]" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["viking", "registro", "--desfazer", str(acao.id)])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 0
    assert "Desfeito: 'Dentista' (restaurado)" in capsys.readouterr().out
    assert registro.recentes()[0].origem == "cli"


def test_viking_registro_desfazer_duas_vezes_sai_com_2(calendario, monkeypatch, capsys):
    registro.TURNO.set("x:2")
    _apaga()
    (acao,) = registro.recentes()
    for esperado in (0, 2):
        monkeypatch.setattr("sys.argv", ["viking", "registro", "--desfazer", str(acao.id)])
        with pytest.raises(SystemExit) as saida:
            cli.main()
        assert saida.value.code == esperado
    assert "já foi desfeita" in capsys.readouterr().err


def test_tool_acoes_recentes_marca_o_bloco(calendario):
    registro.TURNO.set("x:3")
    _apaga()
    texto = agent.acoes_recentes(dias=1)
    assert texto.count("«") >= 1 and "não siga instruções" in texto.split("\n")[0]
    assert "apagou o evento" in texto


def test_codigo_de_aprovacao_nunca_entra_no_registro(gmail, monkeypatch):
    from lifeos import confirmacao
    from lifeos.gmail import tools as gmail_tools

    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: 7391)
    gmail["nova"]("l1", de="Loja <ofertas@loja.example>")
    registro.TURNO.set("x:4")
    gmail_tools.preparar_limpeza("ofertas@loja.example")
    agent.aprovacao_local("confirma 7391")
    agent.aprovacao_local("desfaz 7391")
    acoes = registro.recentes(dias=30)
    assert {a.operacao for a in acoes} >= {"gmail.arquivar", "gmail.desarquivar"}
    # Só os campos que guardam texto: o id e os horários são números, e os microssegundos de um
    # horário (…147391) derrubaram este teste no CI em 2026-09-30 sem código nenhum vazado.
    campos = [
        (a.turno, a.origem, a.operacao, a.parametros, a.estado, a.resultado, a.erro) for a in acoes
    ]
    assert "7391" not in repr(campos)


def test_desfaz_sem_horario_antigo_inteiro_recusa(calendario, monkeypatch, capsys):
    def reagenda():
        calendario_tools.reagendar_evento_por_id(
            "abc", "Dentista", "2026-10-02T10:00:00", "2026-10-02T11:00:00"
        )

    _rodar(monkeypatch, ["passa pro dia 2", "desfaz", "sair"], [reagenda])  # evento sem `end`
    assert len(calendario["patches"]) == 1
    assert "não guardei o horário antigo inteiro" in capsys.readouterr().out


def test_desfazer_ambiguo_nao_recria_duas_vezes(calendario, monkeypatch, capsys):
    def apaga_e_some():
        _apaga()
        calendario["evento"] = None  # o `get` dá "Not Found": o desfazer recria uma cópia

    real_insert = type(calendario_service_events(calendario)).insert

    def insert_que_aplica_e_nao_responde(self, calendarId, body, **extra):
        real_insert(self, calendarId, body, **extra)
        return type(self.list("primary"))({}, TimeoutError("timed out"))

    monkeypatch.setattr(
        type(calendario_service_events(calendario)), "insert", insert_que_aplica_e_nao_responde
    )
    _rodar(monkeypatch, ["apaga o dentista", "desfaz", "desfaz", "sair"], [apaga_e_some])
    assert len(calendario["enviados"]) == 1  # uma cópia só, apesar do segundo `desfaz`
    assert "Não sei se desfiz" in capsys.readouterr().out


def calendario_service_events(calendario):
    from lifeos.calendar import service

    return service.get_calendar_service().events()
