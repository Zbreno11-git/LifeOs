"""O script que apaga os "Pagar conta" que a suíte gravou no banco do dono (Sessão 9, pedido do
dono em 2026-09-29): sem `--aplicar` só conta; com ela, apaga só o que casa o critério exato, e
nunca um lembrete que uma pessoa escreveu ou concluiu.

O lixo foi gravado por `test_lembrete_criar_e_concluir_registram` (Sessão 5 → 9): título "Pagar
conta", corpo e tags vazios, sem prazo, `source` manual (o chat grava "viking-cli", o MCP "mcp"),
concluído na mesma chamada, em milissegundos (medido no VPS: ≤ 0,014 s).
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from lifeos import banco
from lifeos.reminders import service, store

RAIZ = Path(__file__).resolve().parents[1]


def _script():
    if "limpar_lembretes_de_teste" in sys.modules:
        return sys.modules["limpar_lembretes_de_teste"]
    caminho = RAIZ / "scripts" / "limpar_lembretes_de_teste.py"
    spec = importlib.util.spec_from_file_location("limpar_lembretes_de_teste", caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["limpar_lembretes_de_teste"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _concluido_depois(reminder_id: str, segundos: float) -> None:
    """Um lembrete que alguém concluiu `segundos` depois de criar."""
    conn = sqlite3.connect(banco.CAMINHO)
    (criado,) = conn.execute(
        "SELECT created_at FROM reminders WHERE id = ?", (reminder_id,)
    ).fetchone()
    from datetime import datetime, timedelta

    feito = (datetime.fromisoformat(criado) + timedelta(seconds=segundos)).isoformat(
        timespec="microseconds"
    )
    conn.execute("UPDATE reminders SET completed_at = ? WHERE id = ?", (feito, reminder_id))
    conn.commit()
    conn.close()


@pytest.fixture()
def banco_com_lixo():
    """3 lixos como a suíte os gravava, e os vizinhos legítimos que o critério não pode pegar."""
    for _ in range(3):
        lixo = service.criar_lembrete("Pagar conta")
        service.concluir(lixo.id)
    legitimos = {
        "aberto": service.criar_lembrete("Pagar conta"),
        "concluído horas depois": service.criar_lembrete("Pagar conta"),
        "com corpo": service.criar_lembrete("Pagar conta", corpo="a de luz"),
        "com prazo": service.criar_lembrete("Pagar conta", quando="2026-10-01T10:00-03:00"),
        "pelo chat": service.criar_lembrete("Pagar conta", source="viking-cli"),
        "outro título": service.criar_lembrete("Pagar a conta"),
    }
    _concluido_depois(legitimos["concluído horas depois"].id, 3 * 3600)
    for nome in ("com corpo", "com prazo", "pelo chat", "outro título"):
        service.concluir(legitimos[nome].id)
    return legitimos


def _ids() -> set[str]:
    conn = sqlite3.connect(banco.CAMINHO)
    try:
        return {i for (i,) in conn.execute("SELECT id FROM reminders")}
    finally:
        conn.close()


def test_sem_aplicar_so_conta(banco_com_lixo, capsys):
    antes = _ids()
    assert _script().main([]) == 0
    assert _ids() == antes
    saida = capsys.readouterr().out
    assert "Achei 3" in saida and "--aplicar" in saida


def test_aplicar_apaga_so_o_lixo(banco_com_lixo, capsys):
    assert len(_ids()) == 9
    assert _script().main(["--aplicar"]) == 0
    assert _ids() == {r.id for r in banco_com_lixo.values()}
    assert "Apaguei 3" in capsys.readouterr().out


def test_rodar_de_novo_nao_acha_nada(banco_com_lixo, capsys):
    _script().main(["--aplicar"])
    capsys.readouterr()
    assert _script().main(["--aplicar"]) == 0
    assert "Achei 0" in capsys.readouterr().out
    assert len(_ids()) == 6


def test_um_lembrete_de_verdade_concluido_em_menos_de_1s_pelo_mcp_fica(capsys):
    """O `source` separa: o MCP grava "mcp", o chat "viking-cli"."""
    r = service.criar_lembrete("Pagar conta", source="mcp")
    store.complete(r.id)
    _script().main(["--aplicar"])
    assert _ids() == {r.id}


@pytest.mark.parametrize("marca", ["migrando", "migrado"])
def test_depois_da_migracao_aplicar_recusa_e_nada_some(banco_com_lixo, capsys, marca):
    """Sessão 11: o `viking.db` virou a cópia de antes; apagar nela não tiraria nada da nuvem."""
    from lifeos.reminders import onde

    onde.marcar(marca)
    antes = _ids()
    assert _script().main(["--aplicar"]) == 1
    assert _ids() == antes
    assert "migraram para a nuvem" in capsys.readouterr().out
