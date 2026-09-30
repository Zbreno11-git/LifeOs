"""A imagem do motor (Sessão 10, D58; skill `nuvem-e-deploy` §3): o que entra nela, e de onde.

Lê o `Dockerfile` e o `.dockerignore` como texto. As perguntas: a base está fixada por digest (uma
tag muda de conteúdo sem o commit mudar)? Só entra o que o motor precisa (nenhum `.env`,
`secrets/`, `data/`, `.git`)? A instalação é a do lock? O processo roda sem root, e sem log de
acesso (a URL fica no log do Cloud Run; o nosso não repete)?
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DOCKERFILE = (RAIZ / "Dockerfile").read_text()
IGNORE = (RAIZ / ".dockerignore").read_text()


def _instrucoes(nome: str) -> list[str]:
    return [
        linha.split(" ", 1)[1] for linha in DOCKERFILE.splitlines() if linha.startswith(f"{nome} ")
    ]


def test_base_fixada_por_digest_e_a_mesma_nos_dois_estagios():
    bases = [b.split(" AS ")[0] for b in _instrucoes("FROM")]
    assert len(bases) == 2
    for base in bases:
        assert re.fullmatch(r"python:3\.12-slim@sha256:[0-9a-f]{64}", base), base
    assert bases[0] == bases[1]


def test_so_entra_o_que_o_motor_precisa():
    linhas = [
        linha.strip()
        for linha in IGNORE.splitlines()
        if linha.strip() and not linha.startswith("#")
    ]
    assert linhas[0] == "*"  # tudo fora, e só o que segue volta
    voltam = {linha[1:] for linha in linhas if linha.startswith("!")}
    assert voltam == {"pyproject.toml", "uv.lock", "src/"}
    copias = _instrucoes("COPY")
    origens = [c.split()[:-1] for c in copias if not c.startswith("--from=")]
    assert origens == [["pyproject.toml", "uv.lock"], ["src"]]
    assert [c for c in copias if c.startswith("--from=")] == [
        "--from=construir /app/.venv /app/.venv"
    ]


def test_instala_o_lock_com_o_extra_da_nuvem_e_o_uv_do_ci():
    assert DOCKERFILE.count("uv sync --locked --extra nuvem") == 2
    ci = (RAIZ / ".github" / "workflows" / "testes.yml").read_text()
    (versao_ci,) = re.findall(r'version: "([\d.]+)"', ci)
    assert f"uv=={versao_ci}" in DOCKERFILE


def test_roda_sem_root_e_sem_log_de_acesso():
    (usuario,) = _instrucoes("USER")
    assert not usuario.startswith(("0", "root"))
    (comando,) = _instrucoes("CMD")
    assert "lifeos.nuvem.motor:app" in comando and "--no-access-log" in comando
    assert "VIKING_STORE=firestore" in DOCKERFILE


def test_a_imagem_confere_que_o_motor_e_o_fuso_existem():
    """Uma imagem que constrói sem o pacote (ou sem a base de fusos) passaria no build e cairia
    no primeiro pedido: o `RUN test -f` e o `ZoneInfo` reprovam o build antes."""
    assert "test -f /app/.venv/lib/python3.12/site-packages/lifeos/nuvem/motor.py" in DOCKERFILE
    assert "zoneinfo.ZoneInfo(" in DOCKERFILE
