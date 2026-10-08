"""O caminho do desastre (Sessão 11c, D63): `viking backup --restaurar ARQUIVO [--executar]`.

O backup sai da nuvem (o motor em processo, o Drive falso), a nuvem é esvaziada (o endpoint do
emulador que apaga tudo), e o Mac restaura pelo motor. As perguntas: o ensaio não grava nada? A
restauração deixa as três coleções como eram? Rodar de novo não duplica? O que já existe
diferente fica como está? Um arquivo adulterado é recusado antes de qualquer cópia?
"""

import json
import urllib.request

import pytest

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from tests import test_backup_rodada as rodada_base
from tests import test_lembretes_nuvem as nuvem_base
from tests import test_motor as motor_base
from tests.test_backup_rodada import _backup, _um_de_cada
from tests.test_lembretes_nuvem import _do_lado_da_nuvem

from lifeos import custos, registro
from lifeos.backup import formato, restaurar
from lifeos.memoria import receitas as memoria_receitas
from lifeos.memoria import store as memoria_store
from lifeos.reminders import transporte

FATO = "O usuário corre aos sábados."
_nuvem = motor_base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google
_contexto_limpo = nuvem_base._contexto_limpo  # autouse: a origem das ações volta ao fim
mac = nuvem_base.mac
falso = rodada_base.falso


def _estado_da_nuvem():
    with _do_lado_da_nuvem() as nuvem:
        lembretes = {str(r.id): transporte.impressao(r) for r in nuvem.todos()}
        acoes = registro.exportar()
        gastos = custos.exportar_gastos()
    return lembretes, acoes, gastos


def _esvaziar(emulador_firestore):
    from lifeos.reminders import store_firestore

    projeto = store_firestore._cliente().project
    pedido = urllib.request.Request(
        f"http://{emulador_firestore}/emulator/v1/projects/{projeto}/databases/(default)/documents",
        method="DELETE",
    )
    with urllib.request.urlopen(pedido, timeout=10):
        pass


@pytest.fixture
def arquivo(mac, falso, tmp_path, emulador_firestore):
    """O backup de uma nuvem com dois lembretes, ações e um gasto, salvo como o dono o baixaria;
    devolve o caminho e o estado da nuvem no momento do backup. A nuvem fica vazia."""
    _um_de_cada()
    with _do_lado_da_nuvem() as nuvem:
        concluido = nuvem.add(title="Pagar luz")
        nuvem.complete(concluido.id)
        memoria_store.gravar(  # Sessão 13: um fato, com vetor (o backup o leva sem)
            FATO, origem="chat", vetor=[1.0] + [0.0] * 767, sessao="s1", turno="s1:1"
        )
        memoria_receitas.propor("fechamento", ["veja a agenda", "mande por e-mail"], sessao="s1")
        memoria_receitas.guardar("s1")  # Sessão 13b: uma receita guardada
    antes = _estado_da_nuvem()
    assert _backup().status_code == 200
    (feito,) = falso.de_backup()
    caminho = tmp_path / feito["name"]
    caminho.write_bytes(feito["conteudo"])
    _esvaziar(emulador_firestore)
    assert _estado_da_nuvem() == ({}, [], [])
    return caminho, antes


def test_o_ensaio_conta_e_nao_grava(arquivo):
    caminho, _antes = arquivo
    relatorio = restaurar.restaurar(caminho, executar=False)
    assert relatorio.lembretes_a_copiar == 2 and relatorio.lembretes_iguais == 0
    assert _estado_da_nuvem() == ({}, [], [])


def test_restaura_as_tres_colecoes_num_banco_vazio(arquivo):
    caminho, (lembretes, acoes, gastos) = arquivo
    relatorio = restaurar.restaurar(caminho, executar=True)
    assert relatorio.copiados == {
        "lembretes": 2,
        "acoes": len(acoes),
        "gastos": 1,
        "memoria": 1,
        "receitas": 1,
    }
    with _do_lado_da_nuvem():
        (fato,) = memoria_store.todos()
        (receita,) = memoria_receitas.ativas()
    assert (receita.nome, receita.passos) == ("fechamento", ("veja a agenda", "mande por e-mail"))
    assert (fato.texto, fato.sessao, fato.ativo) == (FATO, "s1", True)
    assert fato.vetor_modelo is None  # sem vetor: o texto final manda reindexar
    assert "viking memoria --reindexar" in restaurar.texto(relatorio, executou=True)
    depois_lembretes, depois_acoes, depois_gastos = _estado_da_nuvem()
    assert depois_lembretes == lembretes
    assert depois_gastos == gastos
    # as ações de antes voltam inteiras; a restauração registra as próprias (importar, restaurar)
    assert [a for a in depois_acoes if a["id"] in {x["id"] for x in acoes}] == acoes
    novas = {a["operacao"] for a in depois_acoes if a not in acoes}
    assert novas == {"lembrete.importar", "backup.restaurar"}


def test_restaurar_de_novo_nao_duplica(arquivo):
    caminho, (lembretes, acoes, _gastos) = arquivo
    restaurar.restaurar(caminho, executar=True)
    relatorio = restaurar.restaurar(caminho, executar=True)
    assert relatorio.lembretes_iguais == 2
    assert relatorio.copiados == {
        "lembretes": 0,
        "acoes": 0,
        "gastos": 0,
        "memoria": 0,
        "receitas": 0,
    }
    assert relatorio.ja_iguais == {"acoes": len(acoes), "gastos": 1, "memoria": 1, "receitas": 1}
    assert _estado_da_nuvem()[0] == lembretes


def test_o_que_ja_existe_diferente_fica_como_esta(arquivo):
    caminho, (lembretes, _acoes, _gastos) = arquivo
    restaurar.restaurar(caminho, executar=True)
    with _do_lado_da_nuvem() as nuvem:
        (um, _outro) = sorted(nuvem.todos(), key=lambda r: r.title)
        nuvem._ref(um.id).update({"title": "mudado depois do desastre"})
    mudado = _estado_da_nuvem()[0][str(um.id)]
    relatorio = restaurar.restaurar(caminho, executar=True)
    assert relatorio.lembretes_diferentes == 1
    assert _estado_da_nuvem()[0][str(um.id)] == mudado != lembretes[str(um.id)]


def test_arquivo_adulterado_e_recusado_antes_de_copiar(arquivo):
    caminho, _antes = arquivo
    dados = json.loads(caminho.read_text())
    dados["lembretes"][0]["title"] = "trocado"
    caminho.write_text(json.dumps(dados))
    with pytest.raises(formato.BackupInvalido, match="impressão"):
        restaurar.restaurar(caminho, executar=True)
    assert _estado_da_nuvem() == ({}, [], [])


def _importar(conta, corpo):
    from starlette.testclient import TestClient
    from tests import test_motor as motor_base
    from tests.test_lembretes_nuvem import CONTAS

    from lifeos.nuvem import motor

    token = motor_base._token(email=CONTAS[conta])
    with _do_lado_da_nuvem():
        return TestClient(motor.app).post(
            "/backup/importar", json=corpo, headers={"Authorization": f"Bearer {token}"}
        )


@pytest.mark.parametrize("conta", ["maos", "agendador"])
def test_so_o_terminal_do_dono_restaura(firestore_limpo, conta):
    gasto = {"mes": "2026-10", "total": 1.0, "dias": {}}
    assert _importar(conta, {"acoes": [], "gastos": [gasto]}).status_code == 403
    assert _estado_da_nuvem() == ({}, [], [])


@pytest.mark.parametrize(
    "corpo",
    [
        {"acoes": [{"id": 1}], "gastos": []},
        {"acoes": [], "gastos": []},
        {"acoes": [], "gastos": [{"mes": "2026-10", "total": 1.0, "dias": {}}], "extra": 1},
    ],
    ids=["acao-torta", "vazio", "campo-a-mais"],
)
def test_lote_torto_e_recusado_sem_gravar(firestore_limpo, corpo):
    assert _importar("cli", corpo).status_code == 400
    assert _estado_da_nuvem() == ({}, [], [])
