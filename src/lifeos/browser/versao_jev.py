"""Qual Jev o Viking vai rodar (Sessão 6, auditoria §11.2, D41).

O clone do Jev é um fork com o patch do endpoint OpenRouter; nada conferia se ele estava ali. O dono
decidiu **avisar, não bloquear**: `viking browser --doctor` mostra tudo, e cada tarefa avisa numa
linha do stderr quando algo destoa. O que decide é o **conteúdo** de `jev_ultrafast/model.py`, não o
hash do commit (um rebase do fork mudaria o hash e o patch continuaria lá); ramo, commit e mudanças
não salvas são informativos. Conferir nunca levanta: sem `git`, fora de repositório ou com o `git`
recusando, a resposta é "não consegui conferir".
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from lifeos.browser import _redacao
from lifeos.browser.jev_runner import ambiente_do_jev
from lifeos.config import JEV_DIR

MARCA_DO_PATCH = "openrouter.ai/api/alpha/decisions"
ARQUIVO_DO_PATCH = Path("jev_ultrafast") / "model.py"
GIT_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class Versao:
    ramo: str = ""
    commit: str = ""
    nao_salvas: int = 0
    # None: o arquivo do patch não existe ou não abriu.
    patch: bool | None = None
    erro: str = ""


class _SemResposta(Exception):
    pass


def _git(pasta: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise _SemResposta("o git não está no PATH")
    try:
        feito = subprocess.run(
            [git, "-C", str(pasta), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_S,
            env=ambiente_do_jev(),
        )
    except subprocess.TimeoutExpired:
        raise _SemResposta(f"o git não respondeu em {GIT_TIMEOUT_S:.0f} s") from None
    except OSError as exc:
        raise _SemResposta(f"não consegui rodar o git ({exc})") from None
    if feito.returncode != 0:
        linhas = feito.stderr.strip().splitlines()
        raise _SemResposta(f"o git recusou: {linhas[0] if linhas else feito.returncode}")
    return feito.stdout.strip()


def _tem_patch(pasta: Path) -> bool | None:
    try:
        return MARCA_DO_PATCH in (pasta / ARQUIVO_DO_PATCH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def conferir(jev_dir: Path | None = None) -> Versao:
    pasta = Path(jev_dir or JEV_DIR)
    patch = _tem_patch(pasta)
    try:
        # Sem isto, um clone sem `.git` dentro do repo do Viking responderia com o ramo do Viking.
        raiz = Path(_git(pasta, "rev-parse", "--show-toplevel"))
        if raiz.resolve() != pasta.resolve():
            raise _SemResposta("a pasta do Jev não é a raiz de um repositório git")
        ramo = _git(pasta, "rev-parse", "--abbrev-ref", "HEAD")
        commit = _git(pasta, "rev-parse", "--short", "HEAD")
        status = _git(pasta, "status", "--porcelain")
    except _SemResposta as exc:
        return Versao(patch=patch, erro=_redacao.limpar_controles(str(exc)) or "")
    return Versao(ramo, commit, len(status.splitlines()), patch)


def _patch_em_texto(patch: bool | None) -> str:
    if patch is None:
        return f"não conferido (não li {ARQUIVO_DO_PATCH})"
    return "presente" if patch else "AUSENTE"


def texto(v: Versao, jev_dir: Path | None = None) -> str:
    """O bloco do `viking browser --doctor`."""
    linhas = [f"Jev em {Path(jev_dir or JEV_DIR)}"]
    if v.erro:
        linhas.append(f"   versão: não consegui conferir — {v.erro}")
    else:
        ramo = "nenhum (commit solto)" if v.ramo == "HEAD" else v.ramo
        linhas.append(f"   ramo: {ramo} · commit: {v.commit}")
        linhas.append(f"   mudanças não salvas: {v.nao_salvas or 'nenhuma'}")
    linhas.append(f"   patch OpenRouter: {_patch_em_texto(v.patch)}")
    return "\n".join(linhas)


def aviso(v: Versao) -> str:
    """Uma linha para o stderr de cada tarefa, ou vazio se está tudo como esperado."""
    problemas = []
    if v.patch is not True:
        problemas.append(f"patch OpenRouter {_patch_em_texto(v.patch)}")
    if v.erro:
        problemas.append(f"versão não conferida ({v.erro})")
    elif v.nao_salvas:
        problemas.append(f"{v.nao_salvas} mudança(s) não salva(s) no clone")
    if not problemas:
        return ""
    return f"⚠️  Jev: {'; '.join(problemas)}. Detalhes: viking browser --doctor"


def avisar() -> None:
    """O aviso de cada tarefa, no stderr (o dono vê, o Gemini não). Nunca derruba a tarefa."""
    try:
        linha = aviso(conferir())
    except Exception:  # noqa: BLE001 - conferir a versão é cosmético perto da tarefa
        linha = "⚠️  Jev: não consegui conferir a versão. Detalhes: viking browser --doctor"
    if linha:
        print(linha, file=sys.stderr)
