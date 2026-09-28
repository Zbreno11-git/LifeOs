"""O workflow do CI não pode afrouxar calado (Sessão 7, D45).

O repo é público: o log do CI também é, e uma action puxada por tag pode mudar de conteúdo sem o
commit mudar. As perguntas: toda action está fixada por SHA? A permissão é só de leitura? Algum
segredo entra? A instalação é a do lock? O CI roda os mesmos portões do `AGENTS.md`? E o que o
scanner ignora está decidido, e ainda vale? Lê o arquivo como texto: sem dependência nova.
"""

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOW = RAIZ / ".github" / "workflows" / "testes.yml"


def _linhas_de_codigo() -> list[str]:
    """As linhas do YAML sem os comentários (um `# v7.0.1` depois do SHA não conta como código)."""
    return [linha.split(" #")[0].rstrip() for linha in WORKFLOW.read_text().splitlines()]


def _codigo() -> str:
    return "\n".join(_linhas_de_codigo())


def test_toda_action_fixada_por_sha():
    usos = [linha.split("uses:", 1)[1].strip() for linha in _linhas_de_codigo() if "uses:" in linha]
    assert len(usos) == 2  # checkout e setup-uv: uma action nova entra aqui de propósito
    for uso in usos:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", uso), uso


def test_permissao_so_de_leitura():
    codigo = _codigo()
    assert re.search(r"^permissions:\n  contents: read$", codigo, re.MULTILINE)
    assert "write" not in codigo


def test_nenhum_segredo_nem_gatilho_com_segredo():
    codigo = _codigo()
    assert "secrets." not in codigo
    assert "pull_request_target" not in codigo


def test_checkout_nao_guarda_a_credencial():
    assert "persist-credentials: false" in _codigo()


def test_instala_so_o_que_esta_no_lock():
    codigo = _codigo()
    assert "uv sync --locked --extra dev" in codigo
    comandos = [linha.strip() for linha in _linhas_de_codigo() if "uv run" in linha]
    assert comandos  # sem nenhum, a checagem abaixo não checaria nada
    for comando in comandos:
        assert "uv run --locked " in comando, comando


def _comandos_do_agents() -> list[str]:
    """Os portões que o `AGENTS.md` manda rodar à mão: as linhas `python -m …` do bloco de comandos
    que não são o script de mutações (que roda à mão, fora do CI, de propósito)."""
    texto = (RAIZ / "AGENTS.md").read_text()
    bloco = texto.split("## Comandos", 1)[1].split("```bash", 1)[1].split("```", 1)[0]
    return [
        linha.split("#")[0].strip()
        for linha in bloco.splitlines()
        if linha.startswith("python -m ")
    ]


def test_ci_roda_os_portoes_do_agents():
    portoes = _comandos_do_agents()
    assert len(portoes) >= 3  # pytest, ruff check, ruff format --check
    codigo = _codigo()
    for portao in portoes:
        assert f"uv run --locked {portao}" in codigo, portao


def _ignorados() -> list[str]:
    return re.findall(r"--ignore-vuln (\S+)", _codigo())


def test_scanner_roda_sobre_o_lock():
    codigo = _codigo()
    assert "uv export --frozen" in codigo
    assert "pip-audit==" in codigo


def test_falha_ignorada_esta_decidida_na_d45():
    """Ignorar uma falha conhecida é decisão: cada ID ignorado tem de estar escrito na D45."""
    d45 = next(
        linha
        for linha in (RAIZ / "docs" / "decisoes.md").read_text().splitlines()
        if linha.startswith("| D45 |")
    )
    ignorados = _ignorados()
    assert ignorados == ["PYSEC-2026-3552", "PYSEC-2026-3553", "PYSEC-2026-3554"]
    for vuln in ignorados:
        assert vuln in d45, vuln


def test_a_isencao_acaba_quando_o_cryptography_sair_da_48():
    """Os 3 ignorados são do cryptography 48.0.1, a última com wheel para Mac Intel (medido em
    2026-09-28). Se o lock subir o cryptography, a isenção não vale mais: tire os `--ignore-vuln`
    e esta checagem."""
    lock = tomllib.loads((RAIZ / "uv.lock").read_text())
    (versao,) = [p["version"] for p in lock["package"] if p["name"] == "cryptography"]
    assert versao == "48.0.1"
