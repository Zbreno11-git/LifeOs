"""A fila das mãos (Sessão 11, D61): o formato fechado da tarefa e a coleção `tarefas` no Firestore.

As perguntas: um campo a mais (um `liberar` vindo da nuvem) passa? Duas mãos pegam a mesma tarefa?
Uma tarefa vencida ainda é pega? Quem não pegou consegue entregar? O documento nasce inteiro e com
a data da TTL? O formato, contra as regras puras; o resto, contra o emulador.
"""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lifeos import firestore_comum
from lifeos.maos import fila

T0 = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)
JUNTAS = 16


def _tarefa(**mudancas):
    dados = {
        "id": str(uuid.uuid4()),
        "url": "https://example.com",
        "objetivo": "abrir a página",
        "manter_aberta": True,
        "limite_s": 120,
    }
    dados.update(mudancas)
    return dados


# --- o formato fechado (puro: o Mac valida com isto também) ------------------------------------


def test_a_tarefa_certa_passa():
    tarefa = fila.validar_tarefa(_tarefa())
    assert tarefa.url == "https://example.com" and tarefa.limite_s == 120.0
    assert tarefa.como_dict().keys() == set(fila.CAMPOS)


def test_um_campo_a_mais_e_recusado_inclusive_liberar():
    with pytest.raises(fila.TarefaInvalida, match="exatamente os campos"):
        fila.validar_tarefa(_tarefa(liberar={"categoria": "sair"}))
    with pytest.raises(fila.TarefaInvalida, match="exatamente os campos"):
        fila.validar_tarefa(_tarefa(extra=1))


@pytest.mark.parametrize(
    ("mudancas", "motivo"),
    [
        ({"id": "a/b"}, "UUID"),
        ({"url": ""}, "URL"),
        ({"url": "x" * (fila.MAX_URL + 1)}, "URL"),
        ({"objetivo": "  "}, "objetivo"),
        ({"manter_aberta": "sim"}, "manter_aberta"),
        ({"limite_s": True}, "limite_s"),
        ({"limite_s": "120"}, "limite_s"),
        ({"limite_s": fila.LIMITE_MIN_S - 1}, "entre"),
        ({"limite_s": fila.LIMITE_MAX_S + 1}, "entre"),
    ],
)
def test_campo_torto_e_recusado(mudancas, motivo):
    with pytest.raises(fila.TarefaInvalida, match=motivo):
        fila.validar_tarefa(_tarefa(**mudancas))


def test_sem_campo_e_recusado():
    dados = _tarefa()
    del dados["limite_s"]
    with pytest.raises(fila.TarefaInvalida):
        fila.validar_tarefa(dados)
    with pytest.raises(fila.TarefaInvalida):
        fila.validar_tarefa(["não", "é", "objeto"])


@pytest.mark.parametrize("por", ["", "ABC12345", "abc", "a" * 33, None, 12345678])
def test_quem_pega_tem_forma_fixa(por):
    with pytest.raises(fila.TarefaInvalida):
        fila.validar_por(por)


def test_resultado_grande_e_cortado_e_avisa():
    texto = fila.resultado_curto("x" * (fila.MAX_RESULTADO + 50))
    assert texto.startswith("x" * fila.MAX_RESULTADO) and "cortado" in texto
    assert fila.resultado_curto("curto") == "curto"


# --- a coleção `tarefas` (o emulador) ----------------------------------------------------------


@pytest.fixture
def ff(firestore_limpo):
    from lifeos.maos import fila_firestore

    return fila_firestore


def _criar(ff, agora=T0, **extra):
    dados = {"manter_aberta": True, "limite_s": 120, "agora": agora} | extra
    return ff.criar("https://example.com", "abrir a página", **dados)


def _cru(ff, tarefa_id):
    return firestore_comum.cliente().collection(ff.COLECAO).document(tarefa_id).get().to_dict()


def test_a_tarefa_nasce_inteira_com_os_prazos(ff):
    tarefa_id = _criar(ff)
    cru = _cru(ff, tarefa_id)
    assert set(cru) == set(ff._CAMPOS)
    assert cru["estado"] == fila.PENDENTE and cru["pega_por"] is None and cru["resultado"] is None
    assert firestore_comum.lido(cru["pegar_ate"]) == T0 + fila.PEGAR_EM
    assert firestore_comum.lido(cru["apagar_em"]) == T0 + fila.VIDA


def test_a_ttl_passa_do_turno_mais_longo():
    assert fila.VIDA > fila.PEGAR_EM + timedelta(seconds=fila.LIMITE_MAX_S)


def test_tarefa_torta_nem_e_gravada(ff):
    with pytest.raises(fila.TarefaInvalida):
        _criar(ff, limite_s=5)
    assert list(firestore_comum.cliente().collection(ff.COLECAO).stream()) == []


def test_pega_a_mais_antiga_e_so_uma_vez(ff):
    primeira = _criar(ff, agora=T0)
    segunda = _criar(ff, agora=T0 + timedelta(seconds=1))
    agora = T0 + timedelta(seconds=2)
    assert ff.pegar("aaaa1111", agora=agora).id == primeira
    assert ff.pegar("aaaa1111", agora=agora).id == segunda
    assert ff.pegar("aaaa1111", agora=agora) is None


def test_tarefa_vencida_nao_e_pega(ff):
    _criar(ff, agora=T0)
    depois = T0 + fila.PEGAR_EM + timedelta(seconds=1)
    assert ff.pegar("aaaa1111", agora=depois) is None
    assert ff.pegar("aaaa1111", agora=T0 + fila.PEGAR_EM) is not None  # no limite, ainda vale


def test_varias_maos_ao_mesmo_tempo_so_uma_pega(ff, monkeypatch):
    """Todas leem a tarefa pendente antes de qualquer uma gravar (a barreira no ponto entre ler e
    escrever): sem o comparar e trocar, todas levariam."""
    tarefa_id = _criar(ff)
    lidas = threading.Barrier(JUNTAS)
    monkeypatch.setattr(ff, "_depois_de_ler", lambda c: (lidas.wait(timeout=30), c)[1])
    resultados: list = []
    excecoes: list[BaseException] = []
    trava = threading.Lock()

    def rodar(n):
        try:
            r = ff.pegar(f"{n:08x}", agora=T0 + timedelta(seconds=1))
        except BaseException as exc:  # noqa: BLE001 - recolhida e afirmada abaixo (classe 4)
            with trava:
                excecoes.append(exc)
        else:
            with trava:
                resultados.append(r)

    threads = [threading.Thread(target=rodar, args=(n,)) for n in range(JUNTAS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads)
    assert excecoes == []
    pegas = [r for r in resultados if r is not None]
    assert len(pegas) == 1 and pegas[0].id == tarefa_id
    assert _cru(ff, tarefa_id)["estado"] == fila.PEGA


def test_so_quem_pegou_entrega(ff):
    tarefa_id = _criar(ff)
    ff.pegar("aaaa1111", agora=T0)
    assert not ff.entregar(tarefa_id, "bbbb2222", "outro")
    assert ff.entregar(tarefa_id, "aaaa1111", "Título: Example Domain")
    situacao = ff.situacao(tarefa_id)
    assert situacao.estado == fila.FEITA and situacao.resultado == "Título: Example Domain"
    assert not ff.entregar(tarefa_id, "aaaa1111", "de novo")  # já entregue


def test_tarefa_nao_pega_nao_se_entrega(ff):
    tarefa_id = _criar(ff)
    assert not ff.entregar(tarefa_id, "aaaa1111", "sem ter pegado")
    assert ff.situacao(tarefa_id).estado == fila.PENDENTE


def test_vencer_so_vence_a_pendente(ff):
    livre = _criar(ff)
    assert ff.vencer(livre) and ff.situacao(livre).estado == fila.VENCIDA
    assert ff.pegar("aaaa1111", agora=T0) is None  # vencida não volta à fila
    pega = _criar(ff)
    ff.pegar("aaaa1111", agora=T0)
    assert not ff.vencer(pega) and ff.situacao(pega).estado == fila.PEGA


def test_apagar_e_situacao_de_id_torto(ff):
    tarefa_id = _criar(ff)
    ff.apagar(tarefa_id)
    assert ff.situacao(tarefa_id) is None
    with pytest.raises(ValueError, match="UUID"):
        ff.situacao("a/b")


def test_documento_parcial_erra_alto(ff):
    from google.cloud.firestore import DELETE_FIELD

    tarefa_id = _criar(ff)
    firestore_comum.cliente().collection(ff.COLECAO).document(tarefa_id).update(
        {"resultado": DELETE_FIELD}
    )
    with pytest.raises(ValueError, match="sem os campos"):
        ff.situacao(tarefa_id)
