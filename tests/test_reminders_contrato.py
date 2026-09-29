"""O contrato do store de lembretes (Sessão 9, D56): o que qualquer implementação tem de fazer igual.

Hoje há uma (SQLite, `reminders/store.py`); a Sessão 10 põe o Firestore no `IMPLEMENTACOES` e roda
estes mesmos testes. A semântica diverge onde o código parece igual (skill `dados-e-banco` §8):
por isso cada regra aqui é um comportamento, não uma consulta.

As regras: id UUID gerado no cliente (repetir o `add` com o mesmo id não duplica); só instantes
(horário sem fuso é recusado, a conversão é da borda); devolve em UTC; concluir de novo não muda a
hora; e a reserva de envio, que só uma execução ganha.
"""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from lifeos.reminders import interface, store

IMPLEMENTACOES = {"sqlite": store}

T0 = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)
MINUTO = timedelta(minutes=1)


@pytest.fixture(params=sorted(IMPLEMENTACOES))
def lembretes(request) -> interface.Lembretes:
    return IMPLEMENTACOES[request.param]


# --- identidade e tempo -----------------------------------------------------------------------


def test_add_gera_uuid4_e_devolve_em_utc(lembretes):
    criado = lembretes.add(
        title="Dentista", due_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone(-timedelta(hours=3)))
    )
    assert uuid.UUID(criado.id).version == 4
    assert criado.due_at == T0 and criado.due_at.utcoffset() == timedelta(0)
    assert criado.created_at.utcoffset() == timedelta(0)
    assert lembretes.get(criado.id) == criado


def test_add_repetido_com_o_mesmo_id_nao_duplica(lembretes):
    """O cliente gera o id: uma retentativa (tempo esgotado, Scheduler que chama duas vezes)
    devolve o que já existe, e nada muda nele."""
    meu_id = str(uuid.uuid4())
    primeiro = lembretes.add(title="Pagar luz", id=meu_id)
    segundo = lembretes.add(title="outro título", id=meu_id)
    assert segundo == primeiro
    assert [r.id for r in lembretes.list_open()] == [meu_id]


def test_horario_sem_fuso_e_recusado_e_nada_e_gravado(lembretes):
    with pytest.raises(ValueError, match="fuso"):
        lembretes.add(title="Sem fuso", due_at=datetime(2026, 10, 1, 10, 0))  # noqa: DTZ001
    assert lembretes.list_open() == []


def test_id_invalido_nao_e_encontrado(lembretes):
    assert lembretes.get("nao-existe") is None
    assert lembretes.complete("nao-existe") is None


def test_lista_os_abertos_pelo_instante_real_e_os_sem_prazo_no_fim(lembretes):
    mais_2 = timezone(timedelta(hours=2))
    lembretes.add(title="sem prazo")
    lembretes.add(title="mais tarde (UTC)", due_at=datetime(2026, 9, 25, 8, 0, tzinfo=UTC))
    lembretes.add(title="mais cedo (+02:00)", due_at=datetime(2026, 9, 25, 9, 0, tzinfo=mais_2))
    feito = lembretes.add(title="concluído", due_at=T0)
    lembretes.complete(feito.id)
    assert [r.title for r in lembretes.list_open()] == [
        "mais cedo (+02:00)",
        "mais tarde (UTC)",
        "sem prazo",
    ]


def test_concluir_de_novo_nao_muda_a_hora(lembretes):
    criado = lembretes.add(title="Pagar luz")
    primeira = lembretes.complete(criado.id)
    segunda = lembretes.complete(criado.id)
    assert primeira.completed_at is not None
    assert segunda.completed_at == primeira.completed_at


# --- vencidos e a reserva de envio ------------------------------------------------------------


def _com_prazo(lembretes, titulo, prazo):
    return lembretes.add(title=titulo, due_at=prazo)


def test_vencidos_so_os_abertos_nao_enviados_dentro_da_janela(lembretes):
    desde, ate = T0 - timedelta(hours=24), T0
    no_limite = _com_prazo(lembretes, "no limite de cima", ate)
    dentro = _com_prazo(lembretes, "dentro", T0 - timedelta(hours=1))
    _com_prazo(lembretes, "velho demais", desde - MINUTO)
    _com_prazo(lembretes, "futuro", T0 + MINUTO)
    lembretes.add(title="sem prazo")
    feito = _com_prazo(lembretes, "concluído", T0 - MINUTO)
    lembretes.complete(feito.id)
    enviado = _com_prazo(lembretes, "já enviado", T0 - 2 * MINUTO)
    assert lembretes.reservar_envio(enviado.id, por="x", ate=T0 + MINUTO, agora=T0)
    assert lembretes.marcar_envio(enviado.id, por="x", estado="enviado", agora=T0)

    assert [r.id for r in lembretes.vencidos(desde, ate)] == [dentro.id, no_limite.id]


def test_atrasados_sao_os_abertos_nao_enviados_de_antes_da_janela(lembretes):
    velho = _com_prazo(lembretes, "velho", T0 - timedelta(days=3))
    _com_prazo(lembretes, "recente", T0 - MINUTO)
    assert [r.id for r in lembretes.atrasados(T0 - timedelta(hours=24))] == [velho.id]


def test_so_uma_execucao_ganha_a_reserva(lembretes):
    alvo = _com_prazo(lembretes, "Dentista", T0)
    assert lembretes.reservar_envio(alvo.id, por="a", ate=T0 + 5 * MINUTO, agora=T0)
    assert not lembretes.reservar_envio(alvo.id, por="b", ate=T0 + 5 * MINUTO, agora=T0 + MINUTO)
    assert not lembretes.marcar_envio(alvo.id, por="b", estado="enviado", agora=T0 + MINUTO)


def test_reserva_vencida_pode_ser_pega_por_outra_execucao(lembretes):
    """Quem reservou morreu no meio: depois do prazo, outra execução tenta de novo."""
    alvo = _com_prazo(lembretes, "Dentista", T0)
    assert lembretes.reservar_envio(alvo.id, por="a", ate=T0 + 5 * MINUTO, agora=T0)
    assert lembretes.reservar_envio(alvo.id, por="b", ate=T0 + 11 * MINUTO, agora=T0 + 6 * MINUTO)
    assert not lembretes.marcar_envio(alvo.id, por="a", estado="enviado", agora=T0 + 7 * MINUTO)
    assert lembretes.marcar_envio(alvo.id, por="b", estado="enviado", agora=T0 + 7 * MINUTO)


def test_marcado_nao_se_reserva_nem_vence_de_novo(lembretes):
    alvo = _com_prazo(lembretes, "Dentista", T0)
    assert lembretes.reservar_envio(alvo.id, por="a", ate=T0 + MINUTO, agora=T0)
    assert lembretes.marcar_envio(alvo.id, por="a", estado="incerto", agora=T0)
    assert not lembretes.reservar_envio(
        alvo.id, por="b", ate=T0 + 9 * MINUTO, agora=T0 + 8 * MINUTO
    )
    assert lembretes.vencidos(T0 - MINUTO, T0 + MINUTO) == []
    lido = lembretes.get(alvo.id)
    assert (lido.envio_estado, lido.enviado_em) == ("incerto", T0)


def test_soltar_devolve_so_a_propria_reserva(lembretes):
    alvo = _com_prazo(lembretes, "Dentista", T0)
    assert lembretes.reservar_envio(alvo.id, por="a", ate=T0 + 5 * MINUTO, agora=T0)
    lembretes.soltar_envio(alvo.id, por="b")  # não é dela: nada muda
    assert not lembretes.reservar_envio(alvo.id, por="b", ate=T0 + 5 * MINUTO, agora=T0)
    lembretes.soltar_envio(alvo.id, por="a")
    assert lembretes.reservar_envio(alvo.id, por="b", ate=T0 + 5 * MINUTO, agora=T0)


def test_concluido_nao_se_reserva(lembretes):
    alvo = _com_prazo(lembretes, "Dentista", T0)
    lembretes.complete(alvo.id)
    assert not lembretes.reservar_envio(alvo.id, por="a", ate=T0 + MINUTO, agora=T0)
