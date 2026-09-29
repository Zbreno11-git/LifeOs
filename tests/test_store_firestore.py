"""O que só o store do Firestore tem (Sessão 10, D58); o comportamento comum está no contrato
(`tests/test_reminders_contrato.py`). Contra o emulador (`conftest.emulador_firestore`).

- todo documento inteiro, com `None` explícito: a consulta `== None` não casa campo ausente, e um
  lembrete gravado pela metade sumiria dos vencidos em silêncio;
- um documento parcial (escrito por fora) erra alto na leitura;
- instantes com microssegundos, de volta como `datetime` comum em UTC;
- sob pytest, nenhum cliente sem o emulador (o VPS tem o login do dono vivo);
- a disputa que não termina vira erro, nunca "não" (o "não" diz que outra execução pegou).
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from lifeos.reminders import store_firestore

T0 = datetime(2026, 10, 1, 13, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture
def fs(firestore_limpo):
    return firestore_limpo


def _cru(reminder_id):
    return fs_cliente().collection(store_firestore.COLECAO).document(reminder_id).get().to_dict()


def fs_cliente():
    return store_firestore._cliente()


def test_todo_documento_tem_todos_os_campos_em_cada_passo(fs):
    lembrete = fs.add(title="Dentista", due_at=T0)
    campos = set(store_firestore._CAMPOS)
    assert set(_cru(lembrete.id)) == campos
    assert _cru(lembrete.id)["completed_at"] is None  # presente e nulo, não ausente

    assert fs.reservar_envio(lembrete.id, por="a", ate=T0 + timedelta(minutes=5), agora=T0)
    assert set(_cru(lembrete.id)) == campos
    fs.soltar_envio(lembrete.id, por="a")
    assert set(_cru(lembrete.id)) == campos
    assert fs.reservar_envio(lembrete.id, por="b", ate=T0 + timedelta(minutes=5), agora=T0)
    assert fs.marcar_envio(lembrete.id, por="b", estado="enviado", agora=T0)
    fs.complete(lembrete.id)
    assert set(_cru(lembrete.id)) == campos


def test_documento_parcial_erra_alto_na_leitura(fs):
    lembrete = fs.add(title="Dentista")
    ref = fs_cliente().collection(store_firestore.COLECAO).document(lembrete.id)
    from google.cloud import firestore

    ref.update({"enviado_em": firestore.DELETE_FIELD})
    with pytest.raises(ValueError, match="enviado_em"):
        fs.get(lembrete.id)


def test_microssegundos_e_fuso_voltam_iguais(fs):
    mais_5 = timezone(timedelta(hours=5, minutes=30))
    lembrete = fs.add(title="x", due_at=T0.astimezone(mais_5))
    lido = fs.get(lembrete.id)
    assert lido.due_at == T0 and lido.due_at.microsecond == 123456
    assert type(lido.due_at) is datetime and lido.due_at.tzinfo is UTC


def test_sob_pytest_sem_emulador_nenhum_cliente_nasce(monkeypatch):
    monkeypatch.setattr(store_firestore, "_CLIENTE", None)
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(RuntimeError, match="emulador"):
        store_firestore._cliente()


class _MudouSempre:
    """Um documento que outra execução sempre muda entre a leitura e a escrita."""

    id = "x"

    def get(self):
        class Snap:
            exists = True
            update_time = None

        return Snap()

    def update(self, _mudanca, option=None):
        from google.api_core.exceptions import FailedPrecondition

        raise FailedPrecondition("mudou")


def test_disputa_que_nao_termina_e_erro_nao_resposta(fs, monkeypatch):
    chamadas = []

    def decidir(_snap):
        chamadas.append(1)
        return {"campo": 1}, True

    with pytest.raises(store_firestore.PerdeuADisputa):
        store_firestore._trocar(_MudouSempre(), decidir)
    assert len(chamadas) == store_firestore.TENTATIVAS  # relê e decide de novo a cada volta
