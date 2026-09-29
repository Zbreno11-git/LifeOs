"""O scanner de segredos (Sessão 10, D58): o gitleaks acha um segredo commitado, o hook recusa o
commit com um segredo no stage, e o que está no `.gitignore` (como `secrets/`) não é acusado.

O canário tem o formato real de um token do GitHub e é gerado aqui, a cada execução: escrito no
código, o próprio repo passaria a ter um "segredo". Roda com o binário no cache
(`scripts/gitleaks.sh` baixa e confere o sha256) ou com `VIKING_EXIGIR_GITLEAKS=1`, que o CI liga:
lá o passo do gitleaks já baixou o binário antes, e um pulado seria verde por outro motivo.
"""

import json
import os
import re
import secrets
import shutil
import string
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "gitleaks.sh"


def _versao() -> str:
    return re.search(r'^VERSAO="([\d.]+)"$', SCRIPT.read_text(), re.MULTILINE).group(1)


def _binario_no_cache() -> bool:
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return (cache / "viking" / f"gitleaks-{_versao()}" / "gitleaks").is_file()


pytestmark = pytest.mark.skipif(
    not (_binario_no_cache() or os.environ.get("VIKING_EXIGIR_GITLEAKS") == "1"),
    reason="gitleaks fora do cache (bash scripts/gitleaks.sh version baixa; o CI exige)",
)


def _canario() -> str:
    """Um token do GitHub com o formato real (`ghp_` + 36), aleatório a cada execução."""
    return "ghp_" + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(36))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    ambiente = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, env=ambiente, check=False
    )


def _scan(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args, "--redact", "--no-banner"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    (repo / ".gitignore").write_text("secrets/\n")
    (repo / "leia.md").write_text("nada aqui\n")
    _git(repo, "add", ".")
    assert _git(repo, "commit", "-q", "-m", "inicio").returncode == 0
    return repo


def test_segredo_commitado_e_acusado_com_a_regra(repo):
    (repo / "config.py").write_text(f'TOKEN = "{_canario()}"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "vaza")

    resultado = _scan("git", "--report-format", "json", "--report-path", "-", str(repo))

    assert resultado.returncode == 1, resultado.stderr
    (achado,) = json.loads(resultado.stdout)
    assert (achado["RuleID"], achado["File"]) == ("github-pat", "config.py")
    assert achado["Secret"] == "REDACTED"  # o relatório não repete o segredo


def test_historico_sem_segredo_passa(repo):
    resultado = _scan("git", str(repo))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_o_ignorado_nao_e_acusado_e_o_mesmo_no_stage_e(repo):
    """`secrets/` fica fora do git (os tokens do Google do VPS moram lá); o mesmo conteúdo posto no
    stage fora dele é pego antes de virar commit."""
    token = _canario()
    (repo / "secrets").mkdir()
    (repo / "secrets" / "token.json").write_text(f'{{"t": "{token}"}}\n')
    assert _scan("git", "--pre-commit", "--staged", str(repo)).returncode == 0

    (repo / "token.json").write_text(f'{{"t": "{token}"}}\n')
    _git(repo, "add", "token.json")
    assert _scan("git", "--pre-commit", "--staged", str(repo)).returncode == 1


def test_o_hook_instalado_recusa_o_commit(repo):
    (repo / "scripts").mkdir()
    shutil.copy(SCRIPT, repo / "scripts" / "gitleaks.sh")
    shutil.copy(RAIZ / "scripts" / "instalar_hooks.sh", repo / "scripts" / "instalar_hooks.sh")
    instalado = subprocess.run(
        ["bash", "scripts/instalar_hooks.sh"], cwd=repo, capture_output=True, text=True, check=False
    )
    assert instalado.returncode == 0, instalado.stderr

    (repo / "config.py").write_text(f'TOKEN = "{_canario()}"\n')
    _git(repo, "add", "config.py")
    commit = _git(repo, "commit", "-q", "-m", "vaza")

    assert commit.returncode != 0
    assert "vaza" not in _git(repo, "log", "--format=%s").stdout


def test_o_instalador_nao_sobrescreve_um_hook_alheio(repo):
    (repo / "scripts").mkdir()
    shutil.copy(RAIZ / "scripts" / "instalar_hooks.sh", repo / "scripts" / "instalar_hooks.sh")
    alheio = repo / ".git" / "hooks" / "pre-commit"
    alheio.write_text("#!/bin/sh\necho outro\n")
    resultado = subprocess.run(
        ["bash", "scripts/instalar_hooks.sh"], cwd=repo, capture_output=True, text=True, check=False
    )
    assert resultado.returncode == 1
    assert alheio.read_text() == "#!/bin/sh\necho outro\n"


def test_o_repo_inteiro_passa_no_scanner():
    """O histórico deste repo: 0 achados, com os dispensados do `.gitleaksignore`."""
    resultado = _scan("git", str(RAIZ))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_dispensa_e_sempre_um_achado_exato_nunca_um_arquivo():
    linhas = [
        linha
        for linha in (RAIZ / ".gitleaksignore").read_text().splitlines()
        if linha.strip() and not linha.startswith("#")
    ]
    assert linhas
    for linha in linhas:
        assert re.fullmatch(r"[0-9a-f]{40}:[^:*?]+:[a-z0-9-]+:\d+", linha), linha
