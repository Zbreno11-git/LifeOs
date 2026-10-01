"""O navegador no chat da nuvem, pelas mãos do Mac (Sessão 11, D61).

O relógio é falso (`prazo._relogio` e o `_dormir` da tool andam juntos), a fila é a do emulador, e
o "Mac" é uma função que pega e entrega pela fila num instante escolhido. As perguntas: sem o
`viking maos` ligado, a tarefa vence e nada roda? A tarefa nunca pede mais tempo do que o turno
tem? O que não cabe nem é criado? O resultado volta e é apagado? O Mac que pegou e sumiu vira "não
sei", nunca "não fiz"? E as rotas do motor: só o `viking-maos@` pega e entrega?
"""

import pytest

from lifeos import config, firestore_comum, prazo
from lifeos.assistant import na_nuvem
from lifeos.maos import fila, pedir

POR = "aaaa1111"


@pytest.fixture
def ff(firestore_limpo):
    from lifeos.maos import fila_firestore

    return fila_firestore


@pytest.fixture
def relogio(monkeypatch):
    """O relógio do prazo e o sono da tool andam juntos; `mac(t)` roda a cada leitura."""
    estado = {"t": 0.0, "mac": lambda _t: None, "dormiu": 0.0}
    monkeypatch.setattr(prazo, "_relogio", lambda: estado["t"])

    def dormir(segundos):
        estado["t"] += segundos
        estado["dormiu"] += segundos
        estado["mac"](estado["t"])

    monkeypatch.setattr(pedir, "_dormir", dormir)
    monkeypatch.setattr(config, "BROWSER_TIMEOUT_S", 180.0)
    return estado


def _tarefas(ff):
    return [s.to_dict() for s in firestore_comum.cliente().collection(ff.COLECAO).stream()]


def test_sem_as_maos_a_tarefa_vence_em_15_s_e_nada_roda(ff, relogio):
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        texto = na_nuvem.navegar_e_executar("https://example.com", "abrir a página")
    assert texto == pedir.DESLIGADO
    assert relogio["dormiu"] == fila.PEGAR_EM.total_seconds()
    assert _tarefas(ff) == []  # vencida e apagada: nenhuma mão a pega depois


def test_com_as_maos_o_resultado_volta_e_a_tarefa_some(ff, relogio):
    vistas = []

    def mac(_t):
        tarefa = ff.pegar(POR, agora=pedir._agora())
        if tarefa is not None:
            vistas.append(tarefa)
            ff.entregar(tarefa.id, POR, "✅ Concluído. Título: Example Domain")

    relogio["mac"] = mac
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        texto = na_nuvem.navegar_e_executar("https://example.com", "abrir a página", False)
    assert texto == "✅ Concluído. Título: Example Domain"
    ((tarefa),) = vistas
    assert tarefa.url == "https://example.com" and tarefa.manter_aberta is False
    assert _tarefas(ff) == []


def test_a_tarefa_nunca_pede_mais_do_que_o_turno_tem(ff, relogio):
    """220 s de turno: 60 para o Gemini seguinte, 15 para pegar, 20 de folga → 125 s, menos que os
    180 do navegador. O Mac recebe esse limite e o aplica."""
    vistas = []

    def mac(_t):
        tarefa = ff.pegar(POR, agora=pedir._agora())
        if tarefa is not None:
            vistas.append(tarefa)
            ff.entregar(tarefa.id, POR, "ok")

    relogio["mac"] = mac
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        na_nuvem.navegar_e_executar("https://example.com", "abrir")
    ((tarefa),) = vistas
    reserva = pedir.PROXIMO_MODELO_S + fila.PEGAR_EM.total_seconds() + pedir.FOLGA_S
    assert tarefa.limite_s == na_nuvem.PRAZO_DO_TURNO_S - reserva == 125
    assert pedir.limite_da_tarefa(None) == 180.0  # no Mac, sem prazo, vale o do navegador


def test_o_que_nao_cabe_no_turno_nem_e_criado(ff, relogio):
    with prazo.ate(100):  # 100 − 95 = 5 s: menos que o mínimo de uma tarefa
        texto = na_nuvem.navegar_e_executar("https://example.com", "abrir")
    assert texto.startswith("Não mandei ao navegador") and "faltam 100 s" in texto
    assert _tarefas(ff) == [] and relogio["dormiu"] == 0


def test_o_mac_que_pegou_e_sumiu_vira_nao_sei(ff, relogio):
    def mac(_t):
        ff.pegar(POR, agora=pedir._agora())  # pega e nunca entrega

    relogio["mac"] = mac
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        texto = na_nuvem.navegar_e_executar("https://example.com", "abrir")
    assert texto == pedir.NAO_SEI
    # parou a tempo de a chamada seguinte ao Gemini caber no turno
    assert prazo._relogio() <= na_nuvem.PRAZO_DO_TURNO_S - pedir.PROXIMO_MODELO_S


def test_pedido_torto_nao_vira_tarefa(ff, relogio):
    with prazo.ate(na_nuvem.PRAZO_DO_TURNO_S):
        texto = na_nuvem.navegar_e_executar("", "abrir")
    assert texto.startswith("Não mandei ao navegador") and "Nada foi feito" in texto
    assert _tarefas(ff) == []


def test_a_tool_da_nuvem_e_a_do_mac_com_o_mesmo_texto():
    from lifeos.assistant import agent

    assert na_nuvem.navegar_e_executar.__doc__ == agent.navegar_e_executar.__doc__
    assert "navegar_e_executar" not in na_nuvem.SO_NO_MAC
    assert na_nuvem.navegar_e_executar in na_nuvem.ferramentas()


# --- as rotas do motor ---------------------------------------------------------------------------

pytest.importorskip("starlette")
from starlette.testclient import TestClient
from tests import test_motor as motor_base

from lifeos.nuvem import motor

_nuvem = motor_base._nuvem
MAOS = f"viking-maos@{motor_base.PROJETO}.iam.gserviceaccount.com"


def _post(cliente, rota, corpo, email=MAOS):
    token = motor_base._token(email=email)
    return cliente.post(rota, json=corpo, headers={"Authorization": f"Bearer {token}"})


def test_as_maos_pegam_e_entregam_pelo_motor(ff):
    cliente = TestClient(motor.app)
    tarefa_id = ff.criar(
        "https://example.com", "abrir", manter_aberta=True, limite_s=60, agora=pedir._agora()
    )
    pega = _post(cliente, "/maos/pegar", {"por": POR})
    assert pega.status_code == 200
    assert pega.json()["tarefa"]["id"] == tarefa_id
    assert set(pega.json()["tarefa"]) == set(fila.CAMPOS)
    assert _post(cliente, "/maos/pegar", {"por": POR}).json() == {"tarefa": None}
    entrega = _post(cliente, "/maos/entregar", {"id": tarefa_id, "por": POR, "resultado": "ok"})
    assert entrega.json() == {"aceita": True}
    assert ff.situacao(tarefa_id).resultado == "ok"


def test_o_terminal_nao_entra_nas_portas_das_maos(ff):
    cliente = TestClient(motor.app)
    tarefa_id = ff.criar(
        "https://example.com", "abrir", manter_aberta=True, limite_s=60, agora=pedir._agora()
    )
    assert _post(cliente, "/maos/pegar", {"por": POR}, email=motor_base.CLI).status_code == 403
    corpo = {"id": tarefa_id, "por": POR, "resultado": "x"}
    assert _post(cliente, "/maos/entregar", corpo, email=motor_base.CLI).status_code == 403
    assert ff.situacao(tarefa_id).estado == fila.PENDENTE  # nada mudou


@pytest.mark.parametrize(
    ("rota", "corpo"),
    [
        ("/maos/pegar", {"por": "NAO-HEX"}),
        ("/maos/pegar", None),
        ("/maos/entregar", {"id": "a/b", "por": POR, "resultado": "x"}),
        ("/maos/entregar", {"id": "x", "por": POR}),
    ],
)
def test_pedido_torto_das_maos_e_400(ff, rota, corpo):
    resposta = _post(TestClient(motor.app), rota, corpo)
    assert resposta.status_code == 400


def test_entrega_grande_demais_e_recusada(ff, monkeypatch):
    monkeypatch.setattr(motor, "MAX_CORPO_DAS_MAOS", 100)
    corpo = {"id": "x", "por": POR, "resultado": "y" * 500}
    assert _post(TestClient(motor.app), "/maos/entregar", corpo).status_code == 400
