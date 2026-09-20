import subprocess
import sys
import time
from pathlib import Path

import pytest

from lifeos.browser import jev_runner
from lifeos.browser.jev_runner import build_command, parse_event, result_from, run_jev


@pytest.fixture()
def jev_falso(monkeypatch, tmp_path):
    """Uma pasta que parece um clone do Jev, com .env, sem tocar no clone real."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='jev-ultrafast'\n")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=x\n")
    monkeypatch.setattr(jev_runner, "JEV_DIR", tmp_path)
    monkeypatch.setattr(jev_runner, "JEV_ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(jev_runner, "UV_BIN", "uv")
    return tmp_path


def test_build_command_shape(jev_falso):
    cmd = build_command("https://x.com", ["a", "b"], timeout_s=30)
    assert cmd[:4] == ["uv", "run", "--directory", str(jev_falso)]
    assert "--env-file" in cmd and str(jev_falso / ".env") in cmd
    assert Path(cmd[cmd.index("python") + 1]).is_absolute()
    assert cmd[cmd.index("python") + 1].endswith("_jev_subprocess.py")
    assert [cmd[i + 1] for i, v in enumerate(cmd) if v == "--goal"] == ["a", "b"]
    assert cmd[cmd.index("--timeout") + 1] == "30"


def test_build_command_omite_env_file_inexistente(jev_falso):
    (jev_falso / ".env").unlink()
    assert "--env-file" not in build_command("https://x.com", ["a"], timeout_s=1)


def test_build_command_respeita_overrides(jev_falso, tmp_path):
    outro = tmp_path / "outro"
    outro.mkdir()
    cmd = build_command("u", ["g"], timeout_s=1, jev_dir=outro, uv_bin="/opt/uv")
    assert cmd[0] == "/opt/uv"
    assert str(outro) in cmd


def test_parse_event_ignora_lixo():
    assert parse_event("") is None
    assert parse_event("uv: resolvendo dependencias") is None
    assert parse_event("{quebrado") is None
    assert parse_event('{"sem_tipo": 1}') is None
    assert parse_event('{"type":"step","n":1}') == {"type": "step", "n": 1}


def test_result_from_done():
    eventos = [
        {"type": "start"},
        {"type": "step", "n": 1},
        {
            "type": "result",
            "status": "done",
            "url": "https://x.com/final",
            "title": "T",
            "steps": 3,
            "elapsed_ms": 4200,
            "history": [{"action": "Click"}],
            "page_text": "texto",
        },
    ]
    r = result_from(eventos, 0, None, ["g"])
    assert (r.status, r.steps, r.url, r.title) == ("done", 3, "https://x.com/final", "T")
    assert r.history == ({"action": "Click"},)
    assert r.error_code is None


def test_result_from_blocked():
    r = result_from([{"type": "result", "status": "blocked", "steps": 9}], 1, None, ["g"])
    assert r.status == "blocked" and r.error_code is None and r.steps == 9


def test_result_from_error_preserva_codigo():
    eventos = [{"type": "error", "code": "chrome_not_running", "message": "chrome-not-running: x"}]
    r = result_from(eventos, 2, None, ["g"])
    assert r.status == "error" and r.error_code == "chrome_not_running"
    assert "chrome-not-running" in r.error_detail


def test_result_from_stdout_lixo():
    r = result_from([], 0, "ruido no stderr", ["g"])
    assert r.status == "error" and r.error_code == "bad_output"
    assert r.stderr_tail == "ruido no stderr"


def test_result_from_sem_linha_terminal_com_rc_nao_zero():
    r = result_from([{"type": "step", "n": 1}], 3, None, ["g"])
    assert r.status == "error" and r.error_code == "runner_crash" and r.steps == 1


def test_uv_ausente_nao_spawna(monkeypatch, jev_falso):
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        jev_runner.subprocess, "Popen", lambda *a, **k: pytest.fail("nao deveria spawnar")
    )
    r = run_jev("https://x.com", ["g"])
    assert r.status == "error" and r.error_code == "uv_missing"


def test_jev_dir_ausente_nao_spawna(monkeypatch, tmp_path):
    monkeypatch.setattr(jev_runner, "JEV_DIR", tmp_path / "nao-existe")
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        jev_runner.subprocess, "Popen", lambda *a, **k: pytest.fail("nao deveria spawnar")
    )
    r = run_jev("https://x.com", ["g"])
    assert r.status == "error" and r.error_code == "jev_dir_missing"


def test_execucao_unica(monkeypatch, jev_falso):
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    jev_runner._EXECUCAO.acquire()
    try:
        r = run_jev("https://x.com", ["g"])
    finally:
        jev_runner._EXECUCAO.release()
    assert r.status == "error" and r.error_code == "busy"


def _fake_cmd(script: str) -> list[str]:
    return [sys.executable, "-c", script]


def test_progresso_e_resultado(monkeypatch, jev_falso):
    script = (
        "import json,sys\n"
        "for n in (1,2,3):\n"
        "    print(json.dumps({'schema':1,'type':'step','n':n,'elapsed_ms':n*100}));sys.stdout.flush()\n"
        "print(json.dumps({'schema':1,'type':'result','status':'done','steps':3,'url':'u'}))\n"
    )
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(jev_runner, "build_command", lambda *a, **k: _fake_cmd(script))

    vistos = []
    r = run_jev("https://x.com", ["g"], timeout_s=30, on_progress=vistos.append)
    assert [e["n"] for e in vistos] == [1, 2, 3]
    assert r.status == "done" and r.steps == 3 and r.url == "u"


def test_timeout_mata_o_filho(monkeypatch, jev_falso):
    capturado = {}

    real_popen = subprocess.Popen

    def espiao(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        capturado["proc"] = proc
        return proc

    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        jev_runner, "build_command", lambda *a, **k: _fake_cmd("import time;time.sleep(120)")
    )
    monkeypatch.setattr(jev_runner, "GRACE_S", 0.0)
    monkeypatch.setattr(jev_runner.subprocess, "Popen", espiao)

    inicio = time.monotonic()
    r = run_jev("https://x.com", ["g"], timeout_s=1)
    decorrido = time.monotonic() - inicio

    assert r.status == "error" and r.error_code == "timeout"
    assert decorrido < 20
    assert capturado["proc"].poll() is not None


def test_evento_de_saude_chega_no_callback_e_nao_atrapalha_o_resultado(monkeypatch, jev_falso):
    """O runner avisa quando precisou reatar/reiniciar o daemon antes de começar."""
    script = (
        "import json,sys\n"
        "print(json.dumps({'schema':1,'type':'health','state':'reiniciado'}));sys.stdout.flush()\n"
        "print(json.dumps({'schema':1,'type':'step','n':1,'elapsed_ms':50}))\n"
        "print(json.dumps({'schema':1,'type':'result','status':'done','steps':1}))\n"
    )
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(jev_runner, "build_command", lambda *a, **k: _fake_cmd(script))

    vistos = []
    r = run_jev("https://x.com", ["g"], timeout_s=30, on_progress=vistos.append)
    assert [e["type"] for e in vistos] == ["health", "step"]
    assert vistos[0]["state"] == "reiniciado"
    assert r.status == "done"


def test_falha_de_preflight_vira_codigo_proprio():
    eventos = [
        {"type": "error", "code": "browser_not_ready", "message": "browser-not-ready: probe falhou"}
    ]
    r = result_from(eventos, 2, None, ["g"])
    assert r.error_code == "browser_not_ready"


def test_build_command_so_manda_fechar_quando_pedido(jev_falso):
    assert "--fechar" not in build_command("u", ["g"], timeout_s=1)
    assert "--fechar" in build_command("u", ["g"], timeout_s=1, fechar=True)


def test_result_from_propaga_aba_aberta():
    eventos = [{"type": "result", "status": "done", "steps": 1, "kept_open": True}]
    assert result_from(eventos, 0, None, ["g"]).kept_open is True


def test_detector_de_pingpong():
    """A→B→A→B→A é ping-pong; A→A→A (mesma página) não é."""
    from lifeos.browser import _jev_subprocess as runner

    assert runner._oscilando(["a", "b", "a", "b", "a"]) is True
    assert runner._oscilando(["a", "a", "a", "a", "a"]) is False
    assert runner._oscilando(["a", "b", "c", "d", "e"]) is False
    assert runner._oscilando(["a", "b", "a"]) is False


def test_historico_registra_o_texto_digitado():
    """Sem o texto digitado não dá para diagnosticar 'buscou X mas abriu Y' (visto em 2026-09-21)."""
    eventos = [
        {
            "type": "result",
            "status": "done",
            "steps": 2,
            "history": [{"action": "Pesquisar", "kind": "type", "text": "spider man ambience"}],
        }
    ]
    r = result_from(eventos, 0, None, ["g"])
    assert r.history[0]["text"] == "spider man ambience"
