"""O prazo do turno na nuvem (Sessão 10c, D60): nenhuma espera nem chamada começa se não cabe.

As perguntas: com o Gmail recusando por cota em toda chamada, o turno passa do prazo? Uma espera
do orçamento que não cabe começa? A chamada ao modelo que não cabe sai? Um turno que já agiu e
ficou sem tempo diz o que fez? No Mac (sem prazo), nada disso muda.
"""

import pytest
from tests import test_na_nuvem as base

from lifeos import config, prazo
from lifeos.assistant import agent, na_nuvem
from lifeos.gmail import service

_contexto_limpo = base._contexto_limpo
teto = base.teto
gemini = base.gemini


@pytest.fixture
def relogio(monkeypatch):
    """Um relógio só, o do Gmail falso quando há um: o prazo e as esperas andam juntos."""
    estado = {"t": 0.0}
    monkeypatch.setattr(prazo, "_relogio", lambda: estado["t"])
    return estado


def test_sem_prazo_tudo_cabe():
    assert prazo.restante() is None and prazo.cabe(10**9)


def test_o_prazo_so_vale_dentro_do_bloco(relogio):
    with prazo.ate(220):
        relogio["t"] = 100.0
        assert prazo.restante() == 120.0
        assert prazo.cabe(120) and not prazo.cabe(121)
        with pytest.raises(prazo.TempoEsgotado, match="faltam 120 s"):
            prazo.conferir(121, "isto")
    assert prazo.restante() is None


def test_gmail_recusando_sempre_nao_passa_do_prazo(gmail, monkeypatch):
    """Sem prazo, cada chamada espera 126 s (2+4+…+64) antes de desistir; com o prazo, a segunda
    para antes da espera que não caberia, e nada começa depois do limite menos um pedido."""
    monkeypatch.setattr(prazo, "_relogio", lambda: gmail["relogio"])
    gmail["cota_por_minuto"] = 0
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        with pytest.raises(service.LimiteDoGmail):
            service.buscar("from:a@b.example")
        assert gmail["relogio"] == sum(service.ESPERAS_S)
        with pytest.raises(service.LimiteDoGmail, match="não deu tempo"):
            service.buscar("from:a@b.example")
    assert gmail["relogio"] <= na_nuvem.PRAZO_DO_TURNO_S - service.REDE_S


def test_sem_prazo_o_mac_espera_como_sempre(gmail):
    gmail["cota_por_minuto"] = 0
    for _ in range(2):
        with pytest.raises(service.LimiteDoGmail) as erro:
            service.buscar("from:a@b.example")
        assert "não deu tempo" not in str(erro.value)
    assert gmail["relogio"] == 2 * sum(service.ESPERAS_S)


def test_espera_do_orcamento_que_nao_cabe_nem_comeca(gmail, monkeypatch):
    monkeypatch.setattr(prazo, "_relogio", lambda: gmail["relogio"])
    service._COTA.gastar(service.ORCAMENTO_POR_MINUTO)  # o minuto já está cheio
    with prazo.ate(90), pytest.raises(service.LimiteDoGmail, match="não deu tempo"):
        service.buscar("from:a@b.example")
    assert gmail["relogio"] == 0 and gmail["consultas"] == []


def test_a_chamada_ao_modelo_que_nao_cabe_nao_sai(teto, gemini, monkeypatch):
    monkeypatch.setattr(na_nuvem, "PRAZO_DO_TURNO_S", 50)
    roteiro = gemini(base._texto("não devia sair"))
    saida = na_nuvem.turno(base._pedido("o que tenho amanhã?"))
    assert roteiro.enviados == []
    assert saida["resposta"] is None and "não deu tempo" in saida["erro"]
    assert "50 s" in saida["erro"]


def test_turno_que_agiu_e_ficou_sem_tempo_diz_o_que_fez(teto, gemini, relogio, monkeypatch):
    original = agent.criar_lembrete

    def devagar(*args, **kwargs):
        relogio["t"] += na_nuvem.PRAZO_DO_TURNO_S - 20  # a tool levou quase o turno inteiro
        return original(*args, **kwargs)

    monkeypatch.setattr(agent, "criar_lembrete", devagar)
    roteiro = gemini(
        base._chama("criar_lembrete", titulo="Dentista"), base._texto("não devia sair")
    )
    saida = na_nuvem.turno(base._pedido("lembra do dentista"))
    assert len(roteiro.enviados) == 1  # a segunda chamada não coube
    assert "não deu tempo" in saida["erro"]
    assert "Dentista" in saida["aviso"] and saida["nota"]


def test_pedido_que_nao_cabe_no_prazo_nao_sai(gmail, monkeypatch):
    """Menos de um pedido inteiro (60 s de rede) de sobra: nem a busca sai."""
    monkeypatch.setattr(prazo, "_relogio", lambda: gmail["relogio"])
    with prazo.ate(service.REDE_S - 1), pytest.raises(service.LimiteDoGmail, match="não deu tempo"):
        service.buscar("from:a@b.example")
    assert gmail["consultas"] == []


def test_lote_de_leitura_que_nao_cabe_no_prazo_nao_sai(gmail, monkeypatch):
    """A busca coube; entre ela e a leitura dos e-mails o tempo passou, e o lote não sai."""
    monkeypatch.setattr(prazo, "_relogio", lambda: gmail["relogio"])
    gmail["nova"]("m1", de="Loja <a@b.example>")
    ids_de_verdade = service._ids

    def busca_que_demora(*args, **kwargs):
        achados = ids_de_verdade(*args, **kwargs)
        gmail["relogio"] += 2
        return achados

    monkeypatch.setattr(service, "_ids", busca_que_demora)
    with prazo.ate(service.REDE_S + 1), pytest.raises(service.LimiteDoGmail, match="não deu tempo"):
        service.buscar("from:a@b.example")
    assert gmail["gets"] == [] and gmail["lotes"] == []


def test_aviso_de_espera_so_no_terminal_do_mac(capsys, monkeypatch):
    """No motor o stderr é o log do Cloud Run, e o dono não o vê: o aviso de espera não sai lá."""
    service._avisar("⏳ Esperando 30 s: o Gmail limita as consultas por minuto.")
    assert "Esperando 30 s" in capsys.readouterr().err
    monkeypatch.setattr(config, "STORE", "firestore")
    service._avisar("⏳ Esperando 30 s: o Gmail limita as consultas por minuto.")
    assert capsys.readouterr() == ("", "")
