"""O que o Jev (e o daemon do Browser Harness, que ele sobe) recebe do ambiente do Viking.

Sessão 6, auditoria §11.1, D41: uma lista do que pode passar. As chaves do Viking não chegam lá, e
as do Jev vêm só do `.env` dele — o ambiente do pai vence o `--env-file` do `uv` (medido).
Os roteiros falsos devolvem só os NOMES das variáveis que receberam, nunca os valores.
"""

import json
import os
import sys

import pytest

from lifeos import cli
from lifeos.browser import jev_runner
from lifeos.browser.jev_runner import ambiente_do_jev, run_jev

FORA = {
    "GEMINI_API_KEY": "g",
    "PLUGGY_CLIENT_SECRET": "p",
    "PLUGGY_ITEM_IDS": "i",
    "GOOGLE_APPLICATION_CREDENTIALS": "c",
    "OPENROUTER_API_KEY": "o",
    "TEXT_MODEL_API_KEY": "t",
    "TYPESAFE_MODEL": "m",
    "BROWSER_USE_API_KEY": "b",
    "VIRTUAL_ENV": "/venv/viking",
    "PYTHONPATH": "/src",
    "PYTHONHOME": "/py",
    "CONDA_PREFIX": "/conda",
    "VIKING_DB_PATH": "/data/viking.db",
    "VIKING_JEV_DIR": "/jev",
    # Escolheriam (ou desligariam) o `.env` que o Jev lê: é o Viking quem escolhe.
    "UV_ENV_FILE": "/repo/.env",
    "UV_NO_ENV_FILE": "1",
}

DENTRO = {
    "PATH": "/usr/bin",
    "HOME": "/home/dono",
    "TMPDIR": "/var/folders/x",
    "LANG": "pt_BR.UTF-8",
    "LC_ALL": "pt_BR.UTF-8",
    "HTTPS_PROXY": "http://proxy:3128",
    "https_proxy": "http://proxy:3128",
    "NO_PROXY": "localhost",
    "SSL_CERT_FILE": "/etc/cert.pem",
    "BU_NAME": "default",
    "BH_HOME": "/bh",
    "BROWSER_HARNESS_HOME": "/bh",
    "UV_CACHE_DIR": "/cache/uv",
    "XDG_CONFIG_HOME": "/home/dono/.config",
    "DISPLAY": ":0",
    "CHROME_PATH": "/opt/chrome",
}

# Parecem da lista e não são: o prefixo casa inteiro e no começo, e maiúsculas contam.
DISFARCES = {
    "BUDGET_SECRET": "x",
    "UVICORN_KEY": "x",
    "BHX_TOKEN": "x",
    "MEU_BH_TOKEN": "x",
    "XDGTOKEN": "x",
    "bh_home": "x",
    "Path": "x",
}

_NOMES = (
    "import json, os\n"
    "print(json.dumps({'schema': 1, 'nonce': os.environ.get('VIKING_JEV_NONCE', ''),\n"
    "    'type': 'result', 'status': 'done', 'history': [{'nomes': sorted(os.environ)}]}))\n"
)


def test_so_a_lista_passa_e_com_o_valor_igual():
    env = ambiente_do_jev("n", {**FORA, **DENTRO, **DISFARCES})
    assert env == {**DENTRO, "VIKING_JEV_NONCE": "n"}


@pytest.mark.parametrize("nome", sorted(DISFARCES))
def test_disfarce_de_prefixo_nao_passa(nome):
    assert ambiente_do_jev("", {nome: "x"}) == {}


def test_nonce_herdado_do_pai_nao_passa():
    """Só o desta execução: um `viking` rodando dentro de outro não repassa o nonce de fora."""
    assert ambiente_do_jev("", {"VIKING_JEV_NONCE": "velho"}) == {}
    assert ambiente_do_jev("novo", {"VIKING_JEV_NONCE": "velho"}) == {"VIKING_JEV_NONCE": "novo"}


def test_sem_origem_le_o_ambiente_do_processo(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("BU_NAME", "default")
    env = ambiente_do_jev()
    assert "GEMINI_API_KEY" not in env
    assert env["BU_NAME"] == "default"


@pytest.fixture()
def ambiente_do_dono(monkeypatch):
    for nome, valor in {**FORA, **DISFARCES}.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("BU_NAME", "default")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")


def test_o_jev_recebe_so_a_lista_de_ponta_a_ponta(ambiente_do_dono, monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='jev-ultrafast'\n")
    monkeypatch.setattr(jev_runner, "JEV_DIR", tmp_path)
    monkeypatch.setattr(jev_runner.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(jev_runner, "build_command", lambda *a, **k: [sys.executable, "-c", _NOMES])
    resultado = run_jev("https://x.com", ["g"], timeout_s=30)
    assert resultado.status == "done"
    nomes = set(resultado.history[0]["nomes"])
    assert nomes.isdisjoint(FORA)
    assert nomes.isdisjoint(DISFARCES)
    assert {"PATH", "BU_NAME", "HTTPS_PROXY", "VIKING_JEV_NONCE"} <= nomes


def test_o_doctor_recebe_so_a_lista_de_ponta_a_ponta(ambiente_do_dono, monkeypatch, capfd):
    monkeypatch.setattr(jev_runner, "comando_doctor", lambda: [sys.executable, "-c", _NOMES])
    monkeypatch.setattr(sys, "argv", ["viking", "browser", "--doctor"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 0
    (linha,) = [x for x in capfd.readouterr().out.splitlines() if x.startswith("{")]
    nomes = set(json.loads(linha)["history"][0]["nomes"])
    assert nomes.isdisjoint(FORA)
    assert nomes.isdisjoint(DISFARCES)
    assert {"PATH", "BU_NAME", "HTTPS_PROXY"} <= nomes
    assert "VIKING_JEV_NONCE" not in nomes


@pytest.mark.parametrize("com_env_file", [True, False])
def test_o_doctor_usa_o_env_do_jev_como_a_tarefa(monkeypatch, tmp_path, com_env_file):
    """As chaves do Jev saem do `.env` dele (D7) — no doctor também, pelo mesmo `_uv_run`."""
    env_file = tmp_path / ".env"
    if com_env_file:
        env_file.write_text("BH_CLIENT=viking\n")
    monkeypatch.setattr(jev_runner, "JEV_DIR", tmp_path)
    monkeypatch.setattr(jev_runner, "JEV_ENV_FILE", env_file)
    doctor = jev_runner.comando_doctor()
    tarefa = jev_runner.build_command("https://x.com", ["g"], timeout_s=5)
    assert doctor[-2:] == ["browser-harness", "doctor"]
    assert doctor[:-2] == tarefa[: len(doctor) - 2]
    assert ("--env-file" in doctor) is com_env_file


def test_a_chamada_do_doctor_leva_env(monkeypatch):
    recebidos = []
    monkeypatch.setattr(cli.subprocess, "call", lambda cmd, **k: recebidos.append(k))
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(sys, "argv", ["viking", "browser", "--doctor"])
    with pytest.raises(SystemExit):
        cli.main()
    (kwargs,) = recebidos
    assert "GEMINI_API_KEY" not in kwargs["env"]
    assert kwargs["env"]["PATH"] == os.environ["PATH"]
