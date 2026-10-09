"""A prova real do backup (Sessão 11c, D63): `viking backup --conferir`, no Mac.

O backup é feito pelo motor em processo (`POST /tarefas/backup`, o Drive falso) e conferido pelo
caminho do Mac de verdade: baixa do Drive, restaura num `viking.db` temporário e vazio, e compara
com a nuvem pelo motor. As perguntas: restaura inteiro? O `viking.db` real fica intocado (o do Mac
está migrado: a marca "migrado" mora nele)? O que mudou ou nasceu depois do backup é separado de
uma divergência de verdade, e a divergência sai com 1?
"""

import hashlib
from argparse import Namespace

import pytest

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from tests import test_backup_rodada as rodada_base
from tests import test_lembretes_nuvem as nuvem_base
from tests import test_motor as motor_base
from tests.test_backup_rodada import _backup, _um_de_cada
from tests.test_lembretes_nuvem import _do_lado_da_nuvem

from lifeos import banco, cli, registro
from lifeos.backup import conferir
from lifeos.reminders import onde, store

_nuvem = motor_base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google
_contexto_limpo = nuvem_base._contexto_limpo  # autouse: a origem das ações volta ao fim
mac = nuvem_base.mac
falso = rodada_base.falso

TITULO = "Consulta secreta 5823"


def _sha_do_banco_real() -> str:
    return hashlib.sha256(banco.CAMINHO.read_bytes()).hexdigest()


@pytest.fixture
def backup_feito(mac, falso):
    """A nuvem com um lembrete, uma ação e um mês de gasto, o backup feito, e o Mac migrado."""
    _um_de_cada()
    assert _backup().status_code == 200
    onde.marcar(onde.MIGRADO)
    return falso


def test_restaura_inteiro_num_banco_vazio_e_bate_com_a_nuvem(backup_feito):
    antes = _sha_do_banco_real()
    relatorio = conferir.conferir()
    assert relatorio.no_arquivo == {
        "lembretes": 1,
        "acoes": 1,
        "gastos": 1,
        "memoria": 0,
        "receitas": 0,
        "documentos": 0,
        "trechos": 0,
    }
    assert relatorio.restaurados == relatorio.no_arquivo
    assert (relatorio.iguais, relatorio.divergentes, relatorio.sumiram) == (1, 0, 0)
    assert relatorio.certo
    assert _sha_do_banco_real() == antes  # o real não recebeu nada
    assert store.todos() == [] and registro.recentes() == []
    assert onde.estado() == onde.MIGRADO


def test_o_que_mudou_ou_nasceu_depois_do_backup_nao_e_divergencia(backup_feito):
    with _do_lado_da_nuvem() as nuvem:
        (lembrete,) = nuvem.todos()
        nuvem.complete(lembrete.id)
        nuvem.add(title="Novo depois")
    relatorio = conferir.conferir()
    assert (relatorio.iguais, relatorio.mudaram_depois, relatorio.novos_depois) == (0, 1, 1)
    assert relatorio.certo


def test_diferente_sem_ter_mudado_depois_e_divergencia(backup_feito, monkeypatch, capsys):
    with _do_lado_da_nuvem() as nuvem:
        (lembrete,) = nuvem.todos()
        nuvem._ref(lembrete.id).update({"title": "trocado por fora"})  # sem mexer no updated_at
    relatorio = conferir.conferir()
    assert relatorio.divergentes == 1 and not relatorio.certo
    assert cli._backup(Namespace(conferir=True, restaurar=None, executar=False, login=False)) == 1
    saida = capsys.readouterr().out
    assert "❌ Divergências: 1 diferentes" in saida and "5823" not in saida


def test_sumido_da_nuvem_e_faltando_no_backup_sao_divergencia(backup_feito):
    from datetime import UTC, datetime

    from lifeos.reminders.models import Reminder

    with _do_lado_da_nuvem() as nuvem:
        (lembrete,) = nuvem.todos()
        nuvem._ref(lembrete.id).delete()
        velho = datetime(2026, 1, 1, tzinfo=UTC)
        nuvem.importar(
            Reminder(
                id="7c1f6a2e-3b4d-4e5f-8a9b-0c1d2e3f4a5b",
                type="reminder",
                title="nasceu antes e não está no arquivo",
                created_at=velho,
                updated_at=velho,
            )
        )
    relatorio = conferir.conferir()
    assert (relatorio.sumiram, relatorio.faltaram) == (1, 1)
    assert not relatorio.certo


def test_sem_backup_no_drive_diz_isso(mac, falso):
    with pytest.raises(conferir.SemBackup):
        conferir.conferir()


def test_o_banco_temporario_nasce_vazio_e_devolve_o_real():
    real = banco.CAMINHO
    with conferir.banco_temporario() as caminho:
        assert caminho != real and banco.CAMINHO == caminho
        assert onde.estado() is None and store.todos() == []
    assert banco.CAMINHO == real and not caminho.exists()
