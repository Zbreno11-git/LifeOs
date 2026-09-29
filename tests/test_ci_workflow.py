"""O workflow do CI não pode afrouxar calado (Sessão 7, D45).

O repo é público: o log do CI também é, e uma action puxada por tag pode mudar de conteúdo sem o
commit mudar. As perguntas: toda action está fixada por SHA? A permissão é só de leitura? Algum
segredo entra? A instalação é a do lock? O CI roda os mesmos portões do `AGENTS.md`? E o que o
scanner ignora está decidido, e ainda vale? Lê o arquivo como texto: sem dependência nova.
"""

import re
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


def test_ci_testa_os_pythons_das_nossas_maquinas():
    """O Mac do dono roda Python 3.13 e o VPS 3.12: o CI testa os dois, e a régua do lock também."""
    from tests.test_lock import PYTHONS

    (lista,) = re.findall(r"^\s+python: \[(.*)\]$", _codigo(), re.MULTILINE)
    assert [v.strip().strip('"') for v in lista.split(",")] == [f"3.{m}" for m in PYTHONS]


def _ignorados() -> list[str]:
    return re.findall(r"--ignore-vuln (\S+)", _codigo())


def test_scanner_roda_sobre_o_lock():
    codigo = _codigo()
    assert "uv export --frozen" in codigo
    assert "pip-audit==" in codigo


def test_scanner_nao_ignora_nenhuma_falha():
    """Desde 2026-09-28 (D45) nenhuma falha conhecida é ignorada: o cryptography está na 50.0.1.
    Ignorar uma volta a ser decisão do dono, escrita na D45, e este teste muda junto."""
    assert _ignorados() == []
    assert "--ignore-vuln" not in _codigo()


def _arquivos_do_mypy() -> list[str]:
    import tomllib

    return tomllib.loads((RAIZ / "pyproject.toml").read_text())["tool"]["mypy"]["files"]


def test_mypy_cobre_todo_modulo_que_abre_o_banco():
    """Portão de tipos nos módulos de dados (Sessão 9): quem importa `lifeos.banco` entra na lista
    do `pyproject`, derivado do código. Um módulo novo de dados que ficasse fora passaria sem
    checagem."""
    import ast

    cobertos = [RAIZ / caminho for caminho in _arquivos_do_mypy()]

    def coberto(arquivo: Path) -> bool:
        return any(arquivo == c or arquivo.is_relative_to(c) for c in cobertos if c.exists())

    usam = []
    for arquivo in (RAIZ / "src" / "lifeos").rglob("*.py"):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            nomes = []
            if isinstance(no, ast.ImportFrom) and no.module == "lifeos":
                nomes = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module == "lifeos.banco":
                nomes = ["banco"]
            if "banco" in nomes:
                usam.append(arquivo)
    assert len(usam) >= 3  # lembretes, registro, confirmações
    assert [a for a in [*usam, RAIZ / "src/lifeos/banco.py"] if not coberto(a)] == []


def test_scanner_de_segredos_le_o_historico_inteiro_antes_dos_testes():
    """Sessão 10 (D58): o repo virou privado e o secret scanning do GitHub sumiu; o gitleaks é a
    rede. Sem `fetch-depth: 0` o checkout traz um commit só e o scanner leria só ele; e o canário
    de `tests/test_gitleaks.py` é exigido, não pulado."""
    linhas = _linhas_de_codigo()
    codigo = _codigo()
    assert "fetch-depth: 0" in codigo
    scanner = [i for i, linha in enumerate(linhas) if "bash scripts/gitleaks.sh git " in linha]
    testes = [i for i, linha in enumerate(linhas) if "python -m pytest" in linha]
    assert len(scanner) == 1 and testes and scanner[0] < testes[0]
    assert "--staged" not in linhas[scanner[0]] and "--log-opts" not in linhas[scanner[0]]
    assert re.search(r'VIKING_EXIGIR_GITLEAKS: "1"', codigo)
