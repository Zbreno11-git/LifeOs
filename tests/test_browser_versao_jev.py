"""Qual Jev o Viking vai rodar (Sessão 6, auditoria §11.2, D41): avisar, não bloquear.

Os casos de git usam um repositório **de verdade** em `tmp_path`; só o que não dá para produzir
(git fora do PATH, git travado, dono diferente) usa dublê.
"""

import json
import subprocess
import sys

import pytest

import lifeos.browser as navegador
from lifeos import cli
from lifeos.browser import jev_runner, versao_jev
from lifeos.browser.jev_runner import BrowserResult
from lifeos.browser.versao_jev import Versao, aviso, conferir, texto

COM_PATCH = 'URL = "https://openrouter.ai/api/alpha/decisions"\n'
SEM_PATCH = 'URL = "https://api.typesafe.dev/decisions"\n'


def _git(pasta, *args):
    return subprocess.run(
        ["git", "-C", str(pasta), "-c", "user.name=t", "-c", "user.email=t@t.invalid",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()  # fmt: skip


def _clone(pasta, conteudo=COM_PATCH):
    (pasta / "jev_ultrafast").mkdir(parents=True)
    (pasta / "jev_ultrafast" / "model.py").write_text(conteudo)
    _git(pasta, "init", "-q", "-b", "viking-openrouter")
    _git(pasta, "add", ".")
    _git(pasta, "commit", "-q", "-m", "patch")
    return pasta


@pytest.fixture()
def clone(tmp_path):
    return _clone(tmp_path / "jev")


def test_clone_como_esperado_nao_avisa(clone):
    v = conferir(clone)
    assert v == Versao("viking-openrouter", _git(clone, "rev-parse", "--short", "HEAD"), 0, True)
    assert aviso(v) == ""
    assert texto(v, clone).splitlines()[1:] == [
        f"   ramo: viking-openrouter · commit: {v.commit}",
        "   mudanças não salvas: nenhuma",
        "   patch OpenRouter: presente",
    ]


def test_sem_o_patch_avisa(tmp_path):
    v = conferir(_clone(tmp_path / "jev", SEM_PATCH))
    assert v.patch is False
    assert aviso(v) == "⚠️  Jev: patch OpenRouter AUSENTE. Detalhes: viking browser --doctor"
    assert "   patch OpenRouter: AUSENTE" in texto(v).splitlines()


def test_o_que_decide_e_o_conteudo_nao_o_hash(clone):
    """Um rebase do fork muda o hash e o patch continua lá: nada a avisar."""
    antes = conferir(clone).commit
    _git(clone, "commit", "-q", "--amend", "-m", "rebase do fork")
    depois = conferir(clone)
    assert depois.commit != antes
    assert aviso(depois) == ""


def test_mudancas_nao_salvas_contam_as_novas_tambem(clone):
    (clone / "jev_ultrafast" / "model.py").write_text(COM_PATCH + "# mexido\n")
    (clone / "rascunho.py").write_text("")
    v = conferir(clone)
    assert v.nao_salvas == 2
    assert aviso(v) == (
        "⚠️  Jev: 2 mudança(s) não salva(s) no clone. Detalhes: viking browser --doctor"
    )


def test_clone_sem_git_dentro_de_outro_repo_nao_herda_o_ramo_de_fora(tmp_path):
    """O clone fica dentro do repo do Viking: sem o `.git` próprio, o git subiria de pasta e
    responderia com o ramo do Viking."""
    fora = _clone(tmp_path / "viking", SEM_PATCH)
    dentro = fora / "jev-ultrafast"
    (dentro / "jev_ultrafast").mkdir(parents=True)
    (dentro / "jev_ultrafast" / "model.py").write_text(COM_PATCH)
    v = conferir(dentro)
    assert v == Versao(patch=True, erro="a pasta do Jev não é a raiz de um repositório git")
    assert aviso(v) == (
        "⚠️  Jev: versão não conferida (a pasta do Jev não é a raiz de um repositório git). "
        "Detalhes: viking browser --doctor"
    )


def test_pasta_que_nao_existe(tmp_path):
    v = conferir(tmp_path / "nada")
    assert v.patch is None
    assert v.erro.startswith("o git recusou: ")
    assert aviso(v).startswith("⚠️  Jev: patch OpenRouter não conferido")


def test_commit_solto(clone):
    _git(clone, "checkout", "-q", "--detach")
    assert "   ramo: nenhum (commit solto)" in texto(conferir(clone))


def test_sem_git_no_path(clone, monkeypatch):
    monkeypatch.setattr(versao_jev.shutil, "which", lambda _: None)
    assert conferir(clone) == Versao(patch=True, erro="o git não está no PATH")


def test_git_travado(clone, monkeypatch):
    def travado(*a, **k):
        raise subprocess.TimeoutExpired(a[0], k["timeout"])

    monkeypatch.setattr(versao_jev.subprocess, "run", travado)
    assert conferir(clone).erro == "o git não respondeu em 5 s"


def test_git_que_recusa_o_dono_da_pasta(clone, monkeypatch):
    """`safe.directory`: o clone de outro usuário. Cai no "não consegui", com a frase do git."""
    recusa = "fatal: detected dubious ownership in repository at '/x'\nTo add an exception..."
    monkeypatch.setattr(
        versao_jev.subprocess,
        "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 128, "", recusa),
    )
    assert conferir(clone).erro == (
        "o git recusou: fatal: detected dubious ownership in repository at '/x'"
    )


def test_o_git_roda_com_o_ambiente_da_lista(clone, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    real = subprocess.run
    ambientes = []

    def espiao(cmd, **k):
        ambientes.append(k["env"])
        return real(cmd, **k)

    monkeypatch.setattr(versao_jev.subprocess, "run", espiao)
    conferir(clone)
    assert len(ambientes) == 4
    assert all("GEMINI_API_KEY" not in env for env in ambientes)


def test_avisar_nunca_derruba_a_tarefa(monkeypatch, capsys):
    def quebra(*a, **k):
        raise RuntimeError("inesperado")

    monkeypatch.setattr(versao_jev, "conferir", quebra)
    versao_jev.avisar()
    assert capsys.readouterr().err == (
        "⚠️  Jev: não consegui conferir a versão. Detalhes: viking browser --doctor\n"
    )


@pytest.fixture()
def tarefa_falsa(monkeypatch, tmp_path):
    """Um clone sem o patch e um `run_jev` que não abre nada."""
    monkeypatch.setattr(versao_jev, "JEV_DIR", _clone(tmp_path / "jev", SEM_PATCH))
    falso = lambda url, goals, **k: BrowserResult(status="done", goals=tuple(goals))
    monkeypatch.setattr(navegador, "run_jev", falso)


def test_o_aviso_vai_para_o_dono_e_nao_para_o_gemini(tarefa_falsa, capsys):
    devolvido = navegador.executar_no_navegador("https://x.com", "abrir")
    assert "patch OpenRouter" not in devolvido
    assert "⚠️  Jev: patch OpenRouter AUSENTE" in capsys.readouterr().err


def test_silencioso_nao_avisa(tarefa_falsa, capsys):
    navegador.executar_no_navegador("https://x.com", "abrir", silencioso=True)
    assert capsys.readouterr().err == ""


def test_viking_browser_json_avisa_so_no_stderr(tarefa_falsa, monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["viking", "browser", "--url", "https://x.com", "--goal", "g", "--json"]
    )
    with pytest.raises(SystemExit):
        cli.main()
    saida = capsys.readouterr()
    assert json.loads(saida.out)["status"] == "done"
    assert "⚠️  Jev: patch OpenRouter AUSENTE" in saida.err


def test_a_versao_sai_antes_do_harness_mesmo_num_pipe(clone, tmp_path):
    """Num pipe o stdout do Viking tem buffer, e o harness (outro processo) escreve direto: sem o
    flush, "Jev em …" saía depois da saída do harness (medido rodando o `--doctor` no VPS)."""
    roteiro = tmp_path / "doctor.py"
    roteiro.write_text(
        "import sys\n"
        "from lifeos import cli\n"
        "from lifeos.browser import jev_runner, versao_jev, trava\n"
        f"versao_jev.JEV_DIR = {str(clone)!r}\n"
        f"trava.TRAVA_PATH = __import__('pathlib').Path({str(tmp_path / 'lock')!r})\n"
        "jev_runner.comando_doctor = lambda: [sys.executable, '-c', 'print(\"HARNESS\")']\n"
        "sys.argv = ['viking', 'browser', '--doctor']\n"
        "cli.main()\n"
    )
    saida = subprocess.run(
        [sys.executable, str(roteiro)], check=True, capture_output=True, text=True, timeout=30
    ).stdout.splitlines()
    assert saida[0].startswith("Jev em ")
    assert saida[-1] == "HARNESS"


def test_o_doctor_mostra_a_versao(clone, monkeypatch, capfd):
    monkeypatch.setattr(versao_jev, "JEV_DIR", clone)
    monkeypatch.setattr(jev_runner, "comando_doctor", lambda: [sys.executable, "-c", "0"])
    monkeypatch.setattr(sys, "argv", ["viking", "browser", "--doctor"])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    assert saida.value.code == 0
    assert capfd.readouterr().out.splitlines()[:4] == texto(conferir(clone), clone).splitlines()
