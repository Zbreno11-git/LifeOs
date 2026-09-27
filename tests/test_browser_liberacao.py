"""Liberar um clique recusado pelo freio, uma vez (Sessão 5, D38) — o lado do Viking.

O subprocesso (a digital, `--liberar-uma`, "dinheiro nunca") é testado em
`test_jev_subprocess_main.py` e `test_acoes_sensiveis.py`. Aqui: a proposta só com terminal, o
código só no terminal (nunca no texto da tool nem no Gemini), a reexecução curta com o objetivo do
Viking, e quem pode aprovar.
"""

import ast
import itertools
import json
import sys
from pathlib import Path

import pytest

import lifeos.browser
from lifeos import aprovacoes, cli, confirmacao
from lifeos.assistant import agent
from lifeos.browser import liberacao
from lifeos.browser.jev_runner import BrowserResult

SENTINELA = 7391  # código preso: dá para procurar no texto sem ambiguidade
CODIGO = f"{SENTINELA:04d}"
LOJA = "https://loja.example"
URL = f"{LOJA}/conta"
OBJETIVO = "sair da minha conta da loja"
DIGITAL = {"esquema_host": LOJA, "categoria": "sair", "rotulo": "sair"}


def _recusa(**troca) -> BrowserResult:
    campos = {
        "status": "error",
        "goals": (OBJETIVO,),
        "url": URL,
        "error_code": "acao_sensivel",
        "error_detail": "acao-sensivel: sair: Sair",
        "kept_open": True,
        "acao_sensivel": {**DIGITAL, "url": URL},
        "liberavel": True,
    }
    return BrowserResult(**{**campos, **troca})


_CLICOU = BrowserResult(status="done", goals=("clicar",), steps=1, kept_open=True, liberado=True)


@pytest.fixture()
def navegador(monkeypatch):
    """`run_jev` falso nos dois lugares que o chamam: a tarefa original devolve a recusa, a
    reexecução aprovada devolve `resposta`. Guarda cada chamada."""
    sorteios = itertools.chain([SENTINELA], itertools.count(1000))
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(sorteios))
    estado = {"chamadas": [], "recusa": _recusa(), "resposta": _CLICOU}

    def run_jev_falso(url, goals, **kwargs):
        estado["chamadas"].append({"url": url, "goals": list(goals), **kwargs})
        return estado["resposta"] if kwargs.get("liberar") else estado["recusa"]

    monkeypatch.setattr(lifeos.browser, "run_jev", run_jev_falso)
    monkeypatch.setattr(liberacao, "run_jev", run_jev_falso)
    monkeypatch.setattr(liberacao, "terminal_interativo", lambda: True)
    return estado


def _abertas():
    return confirmacao.abertas(aprovacoes.NAVEGADOR_CLIQUE)


# --- a proposta --------------------------------------------------------------------------


def test_recusa_liberavel_vira_proposta_e_o_codigo_so_vai_ao_terminal(navegador, capsys):
    texto = agent.navegar_e_executar(URL, OBJETIVO)
    terminal = capsys.readouterr().out
    assert CODIGO not in texto
    assert texto.endswith(liberacao.AVISO_AO_GEMINI)
    assert f"confirma {CODIGO}" in terminal
    assert "«Sair» (sair da conta) em https://loja.example" in terminal
    (proposta,) = _abertas()
    assert proposta.dados == {"url": URL, "digital": DIGITAL, "exibido": "Sair"}


def test_sem_terminal_nao_ha_proposta(navegador, monkeypatch, capsys):
    """`--json`, pipe, MCP: o código não teria a quem ser mostrado."""
    monkeypatch.setattr(liberacao, "terminal_interativo", lambda: False)
    texto = agent.navegar_e_executar(URL, OBJETIVO)
    assert _abertas() == []
    assert liberacao.AVISO_AO_GEMINI not in texto
    assert CODIGO not in capsys.readouterr().out


@pytest.mark.parametrize(
    "recusa",
    [
        _recusa(liberavel=False),
        _recusa(acao_sensivel={**DIGITAL, "categoria": "dinheiro", "url": URL}),
        _recusa(acao_sensivel={**DIGITAL, "rotulo": "sair e pagar", "url": URL}),
        _recusa(acao_sensivel={**DIGITAL, "rotulo": "Sair", "url": URL}),
        _recusa(acao_sensivel={**DIGITAL, "url": "https://outra.example/conta"}),
        _recusa(acao_sensivel=None),
        _recusa(error_code="timeout"),
    ],
)
def test_o_que_nao_se_libera_nao_vira_proposta(navegador, recusa):
    """Mesmo que o subprocesso dissesse "liberável": dinheiro, digital fora da forma ou site
    diferente do da página não viram código."""
    navegador["recusa"] = recusa
    agent.navegar_e_executar(URL, OBJETIVO)
    assert _abertas() == []


def test_proposta_nova_substitui_a_aberta(navegador):
    agent.navegar_e_executar(URL, OBJETIVO)
    agent.navegar_e_executar(URL, OBJETIVO)
    (proposta,) = _abertas()
    assert proposta.codigo != CODIGO


# --- a reexecução aprovada ---------------------------------------------------------------


def test_aprovar_faz_so_aquele_clique_com_o_objetivo_do_viking(navegador):
    agent.navegar_e_executar(URL, OBJETIVO)
    texto, resultado = liberacao.clicar_aprovado(CODIGO)
    original, aprovada = navegador["chamadas"]
    assert "liberar" not in original
    assert aprovada == {
        "url": URL,
        "goals": ["clicar no botão «Sair»"],
        "timeout_s": liberacao.TIMEOUT_S,
        "max_acoes": liberacao.MAX_ACOES,
        "liberar": DIGITAL,
        "on_progress": None,
    }
    assert texto == "✅ Cliquei em «Sair», uma vez. A aba ficou aberta."
    assert resultado.liberado is True


def test_o_codigo_serve_uma_vez(navegador):
    agent.navegar_e_executar(URL, OBJETIVO)
    liberacao.clicar_aprovado(CODIGO)
    with pytest.raises(confirmacao.JaUsado):
        liberacao.clicar_aprovado(CODIGO)
    assert len(navegador["chamadas"]) == 2


def test_o_codigo_nunca_chega_ao_executor(navegador):
    """O registro de ações grava o que `run_jev` recebe: sem o código ali, sem código lá."""
    agent.navegar_e_executar(URL, OBJETIVO)
    liberacao.clicar_aprovado(CODIGO)
    assert CODIGO not in json.dumps(navegador["chamadas"], default=str)


@pytest.mark.parametrize(
    ("resposta", "comeca", "nota"),
    [
        (_CLICOU, "✅ Cliquei em «Sair», uma vez.", "o Viking o fez"),
        (
            BrowserResult(
                status="error", goals=(), error_code="acao_sensivel", liberado=True, steps=1
            ),
            "✅ Cliquei em «Sair», uma vez. Depois",
            "o Viking o fez",
        ),
        (
            BrowserResult(status="error", goals=(), error_code="timeout", liberado=True, steps=1),
            "⚠️ Liberei o clique em «Sair», e depois o executor falhou",
            "pode ter sido feito",
        ),
        (
            BrowserResult(status="blocked", goals=(), steps=2),
            "Não cliquei em «Sair»: o executor não chegou a esse botão.",
            "nada mudou",
        ),
    ],
)
def test_o_texto_diz_o_que_aconteceu_com_o_clique(navegador, resposta, comeca, nota):
    navegador["resposta"] = resposta
    agent.navegar_e_executar(URL, OBJETIVO)
    texto, resultado = liberacao.clicar_aprovado(CODIGO)
    assert texto.startswith(comeca)
    assert nota in liberacao.nota_do_clique(resultado)


# --- no chat -----------------------------------------------------------------------------


class _Resposta:
    text = "ok"


class _ChatFalso:
    """No primeiro turno, "decide" chamar a tool do navegador, como o function-calling faria."""

    def __init__(self):
        self.enviados = []

    def send_message(self, prompt):
        self.enviados.append(prompt)
        if len(self.enviados) == 1:
            self.retorno_da_tool = agent.navegar_e_executar(URL, OBJETIVO)
        return _Resposta()


def _rodar_chat(monkeypatch, linhas):
    chat = _ChatFalso()

    class _Cliente:
        class chats:  # imita `client.chats.create`
            @staticmethod
            def create(**_kwargs):
                return chat

    fila = iter(linhas)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(fila))
    monkeypatch.setattr(agent, "_build_client", lambda: _Cliente())
    monkeypatch.setattr(agent.custos, "instrumentar", lambda _cliente: None)
    agent.iniciar_assistente()
    return chat


def test_chat_confirma_libera_e_o_gemini_nunca_ve_o_codigo(navegador, monkeypatch, capsys):
    chat = _rodar_chat(monkeypatch, ["sai da loja", f"confirma {CODIGO}", "e agora?", "sair"])
    assert len(chat.enviados) == 2
    assert all(CODIGO not in enviado for enviado in chat.enviados)
    assert CODIGO not in chat.retorno_da_tool
    assert chat.enviados[1].startswith("[Nota do Viking, não do usuário")
    assert "o Viking o fez" in chat.enviados[1]
    assert navegador["chamadas"][-1]["liberar"] == DIGITAL
    assert "✅ Cliquei em «Sair», uma vez." in capsys.readouterr().out


def test_so_o_numero_com_proposta_aberta_aprova(navegador, monkeypatch):
    """Como o dono digitou na Gmail 2: só o código, e "sair" logo depois."""
    chat = _rodar_chat(monkeypatch, ["sai da loja", CODIGO, "sair"])
    assert chat.enviados == ["sai da loja"]
    assert navegador["chamadas"][-1]["liberar"] == DIGITAL


def test_desfaz_com_o_codigo_do_clique_nao_faz_nada(navegador, monkeypatch, capsys):
    chat = _rodar_chat(monkeypatch, ["sai da loja", f"desfaz {CODIGO}", "sair"])
    assert chat.enviados == ["sai da loja"]
    assert len(navegador["chamadas"]) == 1
    assert len(_abertas()) == 1
    assert "não se desfaz" in capsys.readouterr().out


def test_codigo_vencido_no_chat_nao_clica(navegador, monkeypatch, capsys):
    agent.navegar_e_executar(URL, OBJETIVO)
    monkeypatch.setattr(liberacao.confirmacao, "consumir", _levanta(confirmacao.Expirado("venceu")))
    assert agent.aprovacao_local(f"confirma {CODIGO}")[0] == "Não cliquei: venceu. Nada mudou."
    assert len(navegador["chamadas"]) == 1


def _levanta(exc):
    def _f(*_a, **_k):
        raise exc

    return _f


# --- em `viking browser` -----------------------------------------------------------------


def _rodar_cli(monkeypatch, *args, digitado=""):
    monkeypatch.setattr(sys, "argv", ["viking", "browser", "--url", URL, "--goal", OBJETIVO, *args])
    monkeypatch.setattr("builtins.input", lambda _prompt="": digitado)
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


def test_cli_pede_o_codigo_e_clica(navegador, monkeypatch, capsys):
    assert _rodar_cli(monkeypatch, "--quiet", digitado=CODIGO) == 0
    saida = capsys.readouterr().out
    assert f"digite o código {CODIGO}" in saida
    assert "✅ Cliquei em «Sair», uma vez." in saida
    assert navegador["chamadas"][-1]["liberar"] == DIGITAL


def test_cli_enter_cancela(navegador, monkeypatch, capsys):
    assert _rodar_cli(monkeypatch, "--quiet") == 2
    assert "nada foi clicado" in capsys.readouterr().out
    assert len(navegador["chamadas"]) == 1


def test_cli_json_nao_propoe(navegador, monkeypatch, capsys):
    """`--json` é para outro programa ler: nada de código na saída."""
    assert _rodar_cli(monkeypatch, "--json") == 2
    assert _abertas() == []
    assert CODIGO not in capsys.readouterr().out


# --- quem pode aprovar -------------------------------------------------------------------


def _chamadas(predicado) -> set[str]:
    raiz = Path(agent.__file__).parents[1]
    return {
        str(arquivo.relative_to(raiz))
        for arquivo in raiz.rglob("*.py")
        for no in ast.walk(ast.parse(arquivo.read_text()))
        if isinstance(no, ast.Call) and predicado(no)
    }


def test_so_o_laco_do_chat_e_a_cli_executam_aprovacoes():
    """Uma tool do Gemini que chamasse `clicar_aprovado` desfaria a D26/D38 em silêncio."""
    assert _chamadas(lambda no: getattr(no.func, "attr", None) == "clicar_aprovado") == {
        "assistant/agent.py",
        "cli.py",
    }


def test_so_o_caminho_de_aprovacao_passa_liberar():
    """`liberar=` sai de `liberacao.clicar_aprovado` e desce pelo `run_jev` ao `build_command`;
    em nenhum outro lugar."""
    assert _chamadas(lambda no: any(k.arg == "liberar" for k in no.keywords)) == {
        "browser/liberacao.py",
        "browser/jev_runner.py",
    }
