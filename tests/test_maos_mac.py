"""`viking maos` no Mac (Sessão 11, D61): o navegador deste Mac atendendo o chat da nuvem.

Sem rede nem Chrome: o motor é um roteiro (`cliente.pegar_tarefa`/`entregar_tarefa` trocados), e
o `run_jev` é falso nos dois lugares que o chamam (a tarefa e a reexecução liberada), como em
`tests/test_browser_liberacao.py`. As perguntas: uma tarefa com um campo a mais (um `liberar`
vindo da nuvem) roda? Sem terminal, começa? O código de uma liberação sai deste terminal (na
entrega à nuvem, no registro)? O texto que volta é o mesmo que o chat do Mac leria? Rede caída
derruba o `viking maos`?
"""

import itertools
import json
import uuid

import pytest
from tests.sentinela import aparece
from tests.test_browser_liberacao import _CLICOU, CODIGO, DIGITAL, OBJETIVO, SENTINELA, URL, _recusa

import lifeos.browser
from lifeos import aprovacoes, confirmacao, registro
from lifeos.browser import liberacao
from lifeos.browser.jev_runner import BrowserResult
from lifeos.browser.mensagens import formatar
from lifeos.maos import fila, mac
from lifeos.nuvem import cliente

POR = "não importa: sorteado"


def _tarefa(**mudancas):
    dados = {
        "id": str(uuid.uuid4()),
        "url": URL,
        "objetivo": OBJETIVO,
        "manter_aberta": False,
        "limite_s": 125.0,
    }
    dados.update(mudancas)
    return dados


@pytest.fixture
def maos(monkeypatch):
    """O motor de mentira, o Jev de mentira, um terminal, e o relógio que não dorme."""
    sorteios = itertools.chain([SENTINELA], itertools.count(1000))
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(sorteios))
    estado = {
        "fila": [],  # o que `pegar_tarefa` devolve, em ordem (uma exceção é levantada)
        "entregas": [],
        "jev": [],
        "resposta": BrowserResult(status="done", goals=(OBJETIVO,), url=URL, title="Example"),
        "linhas": [],  # o que o dono digita no terminal
        "dormiu": [],
    }

    def pegar(_sessao, _por):
        passo = estado["fila"].pop(0) if estado["fila"] else None
        if isinstance(passo, BaseException):
            raise passo
        return passo

    def entregar(_sessao, tarefa_id, _por, texto):
        estado["entregas"].append((tarefa_id, texto))
        return True

    def run_jev(url, goals, **kwargs):
        estado["jev"].append({"url": url, "goals": list(goals), **kwargs})
        return _CLICOU if kwargs.get("liberar") else estado["resposta"]

    monkeypatch.setattr(cliente, "sessao_das_maos", lambda: object())
    monkeypatch.setattr(cliente, "pegar_tarefa", pegar)
    monkeypatch.setattr(cliente, "entregar_tarefa", entregar)
    monkeypatch.setattr(lifeos.browser, "run_jev", run_jev)
    monkeypatch.setattr(liberacao, "run_jev", run_jev)
    monkeypatch.setattr(liberacao, "terminal_interativo", lambda: True)
    monkeypatch.setattr(lifeos.browser.versao_jev, "avisar", lambda: None)
    monkeypatch.setattr(mac, "_terminal", lambda: True)
    monkeypatch.setattr(mac, "_dormir", estado["dormiu"].append)
    monkeypatch.setattr(
        mac, "_ler_linha", lambda _p: estado["linhas"].pop(0) if estado["linhas"] else None
    )
    return estado


def test_a_tarefa_roda_no_mac_e_o_texto_volta_a_nuvem(maos):
    tarefa = _tarefa()
    maos["fila"] = [tarefa]
    assert mac.iniciar(voltas=1) == 0
    ((jev),) = maos["jev"]
    assert jev["url"] == URL and jev["goals"] == [OBJETIVO]
    assert jev["timeout_s"] == 125.0 and jev["fechar"] is True  # manter_aberta=False
    assert "liberar" not in jev
    assert maos["entregas"] == [(tarefa["id"], formatar(maos["resposta"]))]


def test_tarefa_com_liberar_nao_roda(maos, capsys):
    tarefa = _tarefa(liberar=DIGITAL)
    maos["fila"] = [tarefa]
    assert mac.iniciar(voltas=1) == 0
    assert maos["jev"] == []
    ((tarefa_id, texto),) = maos["entregas"]
    assert tarefa_id == tarefa["id"] and "recusou" in texto and "nada rodou" in texto
    assert "Recusei uma tarefa da nuvem" in capsys.readouterr().out


def test_tarefa_sem_id_valido_nao_roda_nem_se_entrega(maos):
    maos["fila"] = [{"id": "a/b", "url": URL}]
    assert mac.iniciar(voltas=1) == 0
    assert maos["jev"] == [] and maos["entregas"] == []


def test_sem_terminal_nao_comeca(maos, monkeypatch, capsys):
    monkeypatch.setattr(mac, "_terminal", lambda: False)
    maos["fila"] = [_tarefa()]
    assert mac.iniciar(voltas=1) == 1
    assert maos["jev"] == [] and len(maos["fila"]) == 1  # nem perguntou à nuvem
    assert "só roda num terminal" in capsys.readouterr().err


def test_o_codigo_da_liberacao_fica_neste_terminal(maos, capsys):
    """O freio recusa "Sair": a proposta e o código aparecem aqui, a nuvem recebe só o aviso, e o
    dono libera digitando o código neste terminal."""
    maos["resposta"] = _recusa()
    maos["linhas"] = [f"{CODIGO}\n"]
    tarefa = _tarefa()
    maos["fila"] = [tarefa]
    assert mac.iniciar(voltas=1) == 0
    terminal = capsys.readouterr().out
    assert f"confirma {CODIGO}" in terminal and "✅ Cliquei em «Sair», uma vez." in terminal
    ((tarefa_id, texto),) = maos["entregas"]
    assert tarefa_id == tarefa["id"] and texto.endswith(liberacao.AVISO_AO_GEMINI)
    assert not aparece(CODIGO, texto)  # a nuvem (e o Gemini dela) nunca vê o código
    original, liberada = maos["jev"]
    assert "liberar" not in original and liberada["liberar"] == DIGITAL
    acoes = json.dumps([a.parametros for a in registro.recentes(dias=1, limite=50)], default=str)
    assert not aparece(CODIGO, acoes)


def test_tres_codigos_errados_cancelam_a_liberacao(maos, capsys):
    maos["resposta"] = _recusa()
    maos["linhas"] = ["0001\n", "0002\n", "0003\n", f"{CODIGO}\n"]
    maos["fila"] = [_tarefa()]
    assert mac.iniciar(voltas=1) == 0
    assert len(maos["jev"]) == 1  # o clique liberado nunca rodou
    assert not confirmacao.aberta(aprovacoes.NAVEGADOR_CLIQUE)
    assert maos["linhas"] == [f"{CODIGO}\n"]  # parou de perguntar depois do cancelamento


def test_so_enter_pula_a_liberacao(maos, capsys):
    maos["resposta"] = _recusa()
    maos["linhas"] = ["\n"]
    maos["fila"] = [_tarefa()]
    assert mac.iniciar(voltas=1) == 0
    assert len(maos["jev"]) == 1
    assert "Não liberei" in capsys.readouterr().out


def test_ocupado_vira_o_texto_de_ocupado_na_nuvem(maos):
    """Outro `viking` usando o Chrome (a trava entre processos, Sessão 6): nada roda, e a nuvem
    recebe o texto que o chat do Mac leria."""
    maos["resposta"] = BrowserResult(
        status="error", goals=(OBJETIVO,), error_code="busy", error_detail="ocupado pelo chat"
    )
    maos["fila"] = [_tarefa()]
    mac.iniciar(voltas=1)
    ((_id, texto),) = maos["entregas"]
    assert texto == formatar(maos["resposta"]) and "Outra tarefa de navegador" in texto


def test_rede_caida_espera_mais_a_cada_volta_e_nao_desiste(maos, capsys):
    erro = cliente.ErroDaNuvem("a nuvem não respondeu (rede, ou o motor fora do ar)")
    maos["fila"] = [erro, erro, erro, erro, erro, None]
    assert mac.iniciar(voltas=6) == 0
    assert maos["dormiu"] == [5.0, 10.0, 20.0, 40.0, 60.0, mac.INTERVALO_S]
    assert capsys.readouterr().err.count("Tento de novo") == 5


def test_ctrl_c_desliga(maos, capsys):
    maos["fila"] = [KeyboardInterrupt()]
    assert mac.iniciar(voltas=3) == 0
    assert "desligado" in capsys.readouterr().out


def test_ctrl_c_no_meio_da_tarefa_entrega_e_desliga(maos):
    maos["resposta"] = BrowserResult(
        status="error", goals=(OBJETIVO,), error_code="timeout_terminated", error_detail="x"
    )
    maos["fila"] = [_tarefa(), _tarefa()]
    assert mac.iniciar(voltas=5) == 0
    assert len(maos["entregas"]) == 1 and len(maos["fila"]) == 1  # não pegou a segunda


def test_o_formato_que_o_mac_aceita_e_o_da_fila():
    assert set(_tarefa()) == set(fila.CAMPOS)
