"""Testa `_jev_subprocess.main()` de ponta a ponta, fingindo `jev_ultrafast` e `browser_harness`
via `sys.modules` — este venv não tem (nem deve ter) o ambiente real do Jev instalado; ver o
comentário no topo de `_jev_subprocess.py`. Cobre os achados P1 de runner da auditoria do Codex:
estado terminal perdendo para os guardas de limite/loop/prazo (§10.2), e `usage`/`kept_open`
ausentes nos erros de loop e timeout (§10.3/§10.4).
"""

import json
import sys
import types
from typing import ClassVar

import pytest

from lifeos.browser import _jev_subprocess as runner


class _FakeAgent:
    """Substitui `jev_ultrafast.Agent`. `proximos_estados` é preenchido pelo teste antes de
    chamar `main()` e devolvido, em ordem, por `run()`."""

    proximos_estados: ClassVar[list[dict]] = []

    def __init__(self, url, goals):
        self.url = url
        self.goals = goals
        self.browser = types.SimpleNamespace(target="tgt-falso")
        self.fechada = False

    def snapshot(self):
        return self.proximos_estados[-1] if self.proximos_estados else {}

    def run(self):
        yield from self.proximos_estados

    def close(self):
        self.fechada = True


@pytest.fixture()
def jev_falso(monkeypatch):
    """Injeta `jev_ultrafast` e `browser_harness.{admin,helpers}` falsos em `sys.modules` — os
    dois imports adiados que `main()`/`preparar_navegador()` fazem. `monkeypatch.setitem` desfaz
    isso sozinho no fim do teste."""
    fake_jev = types.ModuleType("jev_ultrafast")
    fake_jev.Agent = _FakeAgent

    fake_admin = types.ModuleType("browser_harness.admin")
    fake_admin.ensure_daemon = lambda: None
    fake_admin.daemon_browser_ready = lambda: True
    fake_admin.restart_daemon = lambda: None

    fake_helpers = types.ModuleType("browser_harness.helpers")
    fake_helpers.page_info = dict
    fake_helpers.cdp = lambda *a, **k: None

    monkeypatch.setitem(sys.modules, "jev_ultrafast", fake_jev)
    monkeypatch.setitem(sys.modules, "browser_harness.admin", fake_admin)
    monkeypatch.setitem(sys.modules, "browser_harness.helpers", fake_helpers)

    _FakeAgent.proximos_estados = []
    return _FakeAgent


def _estado(status: str, n: int, usage: dict | None = None) -> dict:
    historico = [{"action": f"passo{i}", "kind": "click"} for i in range(1, n + 1)]
    estado = {
        "status": status,
        "elapsed_ms": n * 100,
        "history": historico,
        "page": {"url": f"https://x.com/{n}", "title": "T", "text": ""},
    }
    if usage is not None:
        estado["decisions"] = [{"usage": usage}]
    return estado


def _rodar(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["jev-runner", "--url", "https://x.com", "--goal", "g", *args])
    return runner.main()


def _linhas(capsys) -> list[dict]:
    saida = capsys.readouterr().out
    return [json.loads(linha) for linha in saida.splitlines() if linha.strip()]


def test_estado_terminal_vence_o_limite_de_acoes(jev_falso, monkeypatch, capsys):
    """C1: concluir EXATAMENTE na ação-limite é sucesso, não step_budget — o achado §10.2."""
    jev_falso.proximos_estados = [_estado("running", 1), _estado("running", 2), _estado("done", 3)]
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "3")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "result"
    assert terminal["status"] == "done"
    assert codigo == runner.EXIT_DONE


def test_step_budget_ainda_funciona_sem_estado_terminal(jev_falso, monkeypatch, capsys):
    """Controle negativo: sem chegar a done/blocked, o teto de ações continua parando a tarefa."""
    jev_falso.proximos_estados = [
        _estado("running", 1),
        _estado("running", 2),
        _estado("running", 3),
    ]
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "3")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "step_budget"
    assert codigo == runner.EXIT_ERROR


@pytest.mark.parametrize("fechar", [False, True])
def test_step_budget_kept_open_reflete_a_flag_fechar(jev_falso, monkeypatch, capsys, fechar):
    """C3: kept_open tem que refletir o que o `finally` realmente faz com a aba."""
    jev_falso.proximos_estados = [
        _estado("running", 1),
        _estado("running", 2),
        _estado("running", 3),
    ]
    args = ["--timeout", "5", "--max-acoes", "3"]
    if fechar:
        args.append("--fechar")
    _rodar(monkeypatch, *args)
    terminal = _linhas(capsys)[-1]
    assert terminal["kept_open"] is (not fechar)


def test_loop_detected_carrega_usage(jev_falso, monkeypatch, capsys):
    """C2: usage sumia do evento de loop_detected — o custo aconteceu, mas não aparecia."""
    padroes = [
        {"url": "https://x.com/a", "action": "A"},
        {"url": "https://x.com/b", "action": "B"},
    ]
    estados = []
    historico = []
    for i in range(6):
        passo = padroes[i % 2]
        historico = [*historico, {"action": passo["action"], "kind": "click"}]
        estados.append(
            {
                "status": "running",
                "elapsed_ms": (i + 1) * 100,
                "history": list(historico),
                "page": {"url": passo["url"], "title": "T", "text": ""},
                "decisions": [{"usage": {"input_tokens": 5}}],
            }
        )
    jev_falso.proximos_estados = estados
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "50")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "loop_detected"
    assert terminal["usage"]["chamadas"] >= 1
    assert codigo == runner.EXIT_ERROR


def test_timeout_carrega_usage_e_kept_open(jev_falso, monkeypatch, capsys):
    """C2+C3: usage e kept_open sumiam do evento de timeout."""
    jev_falso.proximos_estados = [_estado("running", 1, usage={"input_tokens": 3})]
    codigo = _rodar(monkeypatch, "--timeout", "0", "--max-acoes", "50")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "timeout"
    assert terminal["usage"]["chamadas"] == 1
    assert terminal["kept_open"] is True
    assert codigo == runner.EXIT_INTERRUPTED
