"""O `viking.db` num lugar só, e a suíte nunca no banco de verdade (Sessão 9).

Medido em 2026-09-29: desde a Sessão 5, cada `pytest` gravava um lembrete "Pagar conta" no
`data/viking.db` real (132 no VPS, um por rodada; no Mac, no banco do dono). O `conftest` isolava
`confirmacao` e `registro`, e o store dos lembretes, o terceiro módulo do mesmo arquivo, abria o
caminho da config (erros, classe 6). Agora os três abrem por `banco.conectar()`, e o `conftest`
troca um nome só.
"""

import ast
import hashlib
from pathlib import Path

from lifeos import banco, config

RAIZ = Path(__file__).resolve().parents[1]
BANCO_REAL = RAIZ / "data" / "viking.db"


def _hash(caminho: Path) -> str | None:
    return hashlib.sha256(caminho.read_bytes()).hexdigest() if caminho.exists() else None


def test_a_config_da_suite_nao_aponta_para_o_banco_real():
    """A camada de fora: o `conftest` troca `VIKING_DB_PATH` antes de importar o `lifeos`."""
    assert not config.REMINDERS_DB_PATH.resolve().is_relative_to((RAIZ / "data").resolve())


def test_cada_teste_tem_o_proprio_banco(tmp_path):
    """A camada de dentro: o `autouse` troca `banco.CAMINHO` por um arquivo deste teste. Sem ela,
    a de fora ainda protegeria o banco real, e os testes dividiriam um banco só."""
    assert banco.CAMINHO == tmp_path / "viking.db"


def test_criar_e_concluir_lembrete_sem_fixture_nao_toca_o_banco_real():
    """O caminho do defeito medido: o serviço de lembretes, sem nenhuma fixture pedida."""
    from lifeos.reminders import service

    antes = _hash(BANCO_REAL)
    lembrete = service.criar_lembrete("Teste que não pode chegar ao banco real")
    service.concluir(lembrete.id)
    assert _hash(BANCO_REAL) == antes
    assert banco.CAMINHO.exists()  # foi para o banco do teste, não sumiu


def _chamadas_de_connect(arquivo: Path) -> int:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    return sum(
        1
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "connect"
        and getattr(no.func.value, "id", None) == "sqlite3"
    )


def test_so_o_banco_abre_o_sqlite():
    """Um módulo novo que abrisse o `viking.db` por conta própria escaparia do isolamento dos
    testes e das migrations. Piso: a régua acha a chamada que existe."""
    por_arquivo = {
        arquivo.relative_to(RAIZ).as_posix(): _chamadas_de_connect(arquivo)
        for arquivo in (RAIZ / "src").rglob("*.py")
    }
    assert {nome for nome, n in por_arquivo.items() if n} == {"src/lifeos/banco.py"}
