"""Um lembrete pela rede (Sessão 11, D61): o formato que o Mac manda ao motor na migração e a
impressão que confere a cópia.

Puro: nada de rede nem de banco. As perguntas: o que sai do Mac volta igual do outro lado (pelo
JSON, como na rede)? Um formato torto é recusado inteiro, sem ecoar o conteúdo? A impressão muda
com **qualquer** campo (a conferência da migração depende disso) e não muda com o fuso em que o
mesmo instante foi escrito?
"""

import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from lifeos.reminders import interface, transporte
from lifeos.reminders.models import Reminder

MENOS_3 = timezone(timedelta(hours=-3))
ID = "6f1d2c3b-4a5e-4f60-8a7b-9c0d1e2f3a4b"


def _lembrete(**mudancas) -> Reminder:
    dados = {
        "id": ID,
        "type": "reminder",
        "title": "Dentista",
        "body": "levar o raio-x",
        "tags": ["saude", "casa"],
        "due_at": datetime(2026, 10, 2, 10, 0, tzinfo=MENOS_3),
        "completed_at": datetime(2026, 10, 2, 14, 0, 0, 123456, tzinfo=UTC),
        "source": "viking-cli",
        "external_id": "ext-1",
        "metadata": {"origem": "teste", "n": 2},
        "created_at": datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 2, 14, 0, 0, 123456, tzinfo=UTC),
        "enviado_em": datetime(2026, 10, 2, 13, 0, 1, tzinfo=UTC),
        "envio_estado": interface.ENVIADO,
    }
    dados.update(mudancas)
    return Reminder(**dados)


def _pela_rede(lembrete: Reminder) -> dict:
    return json.loads(json.dumps(transporte.para_dict(lembrete), ensure_ascii=False))


def test_o_que_sai_do_mac_volta_igual_pelo_json():
    original = _lembrete()
    volta = transporte.de_dict(_pela_rede(original))
    assert volta == original  # instantes comparados como instantes
    assert volta.due_at.utcoffset() == timedelta(0)  # e chegam em UTC
    assert transporte.impressao(volta) == transporte.impressao(original)


def test_um_lembrete_aberto_sem_prazo_nem_envio_tambem_vai():
    aberto = _lembrete(
        due_at=None, completed_at=None, enviado_em=None, envio_estado=None, external_id=None
    )
    assert transporte.de_dict(_pela_rede(aberto)) == aberto


def test_os_campos_do_formato_sao_todos_os_do_lembrete():
    """Um campo novo no `Reminder` que não entra no formato ficaria fora da cópia em silêncio."""
    assert set(transporte.CAMPOS) == set(Reminder.__dataclass_fields__)


def _trocar(dados: dict, campo: str) -> dict:
    """O mesmo lembrete com um campo diferente, ainda válido."""
    outro = dict(dados)
    valor = dados[campo]
    if campo == "id":
        outro[campo] = str(uuid.uuid4())
    elif campo == "tags":
        outro[campo] = [*valor, "nova"]
    elif campo == "metadata":
        outro[campo] = {**valor, "n": 3}
    elif campo == "envio_estado":
        outro[campo] = interface.INCERTO
    elif campo in transporte._INSTANTES:
        momento = datetime.fromisoformat(valor) + timedelta(microseconds=1)
        outro[campo] = momento.isoformat()
    else:
        outro[campo] = f"{valor}x"
    return outro


def test_a_impressao_muda_com_qualquer_campo():
    base = transporte.para_dict(_lembrete())
    impressao = transporte.impressao(transporte.de_dict(base))
    vistos = []
    for campo in transporte.CAMPOS:
        outro = transporte.de_dict(_trocar(base, campo))
        assert transporte.impressao(outro) != impressao, campo
        vistos.append(campo)
    assert len(vistos) == len(transporte.CAMPOS) == 14


def test_o_mesmo_instante_em_outro_fuso_tem_a_mesma_impressao():
    em_utc = _lembrete(due_at=datetime(2026, 10, 2, 13, 0, tzinfo=UTC))
    em_brasilia = _lembrete(due_at=datetime(2026, 10, 2, 10, 0, tzinfo=MENOS_3))
    assert transporte.impressao(em_utc) == transporte.impressao(em_brasilia)


@pytest.mark.parametrize(
    ("mudanca", "trecho"),
    [
        ({"a_mais": 1}, "exatamente os campos"),
        ({"id": "1"}, "UUID"),
        ({"id": "../acoes/1"}, "UUID"),
        ({"title": 5}, "title tem de ser texto"),
        ({"tags": "saude"}, "tags"),
        ({"tags": ["ok", 1]}, "tags"),
        ({"metadata": []}, "metadata"),
        ({"external_id": 7}, "external_id"),
        ({"envio_estado": "talvez"}, "envio_estado desconhecido"),
        ({"due_at": "2026-10-02T10:00:00"}, "due_at tem de ser um instante"),
        ({"due_at": "amanhã"}, "due_at tem de ser um instante"),
        ({"enviado_em": 1759410000}, "enviado_em tem de ser um instante"),
        ({"created_at": None}, "obrigatórios"),
        ({"updated_at": None}, "obrigatórios"),
    ],
)
def test_formato_torto_e_recusado_sem_ecoar_o_conteudo(mudanca, trecho):
    dados = {**transporte.para_dict(_lembrete(title="Segredo do dono")), **mudanca}
    with pytest.raises(transporte.LembreteInvalido, match=trecho) as erro:
        transporte.de_dict(dados)
    assert "Segredo" not in str(erro.value)


def test_campo_a_menos_e_recusado():
    dados = transporte.para_dict(_lembrete())
    del dados["envio_estado"]
    with pytest.raises(transporte.LembreteInvalido, match="exatamente os campos"):
        transporte.de_dict(dados)


@pytest.mark.parametrize("bruto", [None, [], "lembrete", 3])
def test_o_que_nao_e_objeto_e_recusado(bruto):
    with pytest.raises(transporte.LembreteInvalido):
        transporte.de_dict(bruto)


def test_horario_sem_fuso_nao_sai_do_mac():
    with pytest.raises(transporte.LembreteInvalido, match="sem fuso"):
        sem_fuso = datetime(2026, 10, 2, 10, 0)  # o caso que recusa
        transporte.para_dict(_lembrete(due_at=sem_fuso))
