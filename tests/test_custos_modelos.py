"""Sessão 12 (D65): a tarifa do modelo que respondeu e as cotas do dia (o modelo forte e a busca).

As perguntas: o 3.8 Flash custa o dobro a partir de 2027-01-01? Um modelo fora da tabela é
contado barato (subconta o teto) ou caro? O gancho troca o modelo da chamada e conta com a tarifa
dele? A 31ª busca do dia passa, mesmo com várias instâncias reservando juntas? O dia da cota é o do
dono? O gasto do forte entra na cota do dia sem mexer no `gastos/` (o formato do backup)?
"""

import threading
import types
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from lifeos import config, custos
from lifeos.assistant import turno
from lifeos.custos import Consumo, Sessao, do_gemini, instrumentar, tarifa

LA = ZoneInfo("America/Los_Angeles")


class _Usage:
    prompt_token_count = 1_000_000
    candidates_token_count = 0


# --- a tarifa ---------------------------------------------------------------------------------


def test_o_forte_dobra_em_2027():
    assert tarifa("gemini-3.8-flash", date(2026, 12, 31)) == (0.75, 3.75)
    assert tarifa("gemini-3.8-flash", date(2027, 1, 1)) == (1.50, 7.50)


def test_o_dia_a_dia_usa_as_tarifas_do_env():
    assert tarifa("gemini-3.5-flash-lite") == (
        config.PRECO_GEMINI_ENTRADA,
        config.PRECO_GEMINI_SAIDA,
    )


def test_modelo_fora_da_tabela_custa_a_tarifa_mais_cara():
    """Erra para o lado de parar: um modelo novo, sem tarifa, nunca é contado barato."""
    assert tarifa("gemini-9-ultra") == (1.50, 7.50)
    assert tarifa("") == (1.50, 7.50)


def test_o_prefixo_models_nao_muda_a_tarifa():
    assert tarifa("models/gemini-3.8-flash", date(2026, 10, 7)) == (0.75, 3.75)


def test_os_modelos_do_chat_estao_na_tabela():
    assert turno.MODELO in custos.TARIFAS
    assert getattr(turno, "MODELO_FORTE", turno.MODELO) in custos.TARIFAS


def test_o_custo_sai_da_tarifa_do_modelo_que_respondeu():
    lite = do_gemini(_Usage(), "gemini-3.5-flash-lite", date(2026, 10, 7))
    forte = do_gemini(_Usage(), "gemini-3.8-flash", date(2026, 10, 7))
    assert (lite.modelo, forte.modelo) == ("gemini-3.5-flash-lite", "gemini-3.8-flash")
    assert forte.custo == pytest.approx(0.75)
    assert lite.custo == pytest.approx(config.PRECO_GEMINI_ENTRADA)


def test_somar_consumos_de_modelos_diferentes_nao_inventa_um_nome():
    a = Consumo(entrada=1, modelo="gemini-3.5-flash-lite")
    assert (a + a).modelo == "gemini-3.5-flash-lite"
    assert (a + Consumo(entrada=1, modelo="gemini-3.8-flash")).modelo == ""
    assert (a + Consumo()).modelo == "gemini-3.5-flash-lite"


def test_o_resumo_do_turno_diz_cada_modelo():
    s = Sessao()
    s.iniciar_turno()
    s.registrar_gemini(do_gemini(_Usage(), "gemini-3.5-flash-lite"))
    s.registrar_gemini(do_gemini(_Usage(), "gemini-3.8-flash"))
    resumo = s.resumo_do_turno()
    assert "gemini-3.5-flash-lite:" in resumo and "gemini-3.8-flash:" in resumo
    s.iniciar_turno()
    s.registrar_gemini(do_gemini(_Usage(), "gemini-3.5-flash-lite"))
    assert "3.8" not in s.resumo_do_turno()  # o turno novo não herda o forte do anterior
    assert "gemini-3.8-flash" in s.total_formatado()  # a sessão inteira, sim


# --- o gancho troca o modelo e conta com a tarifa dele ----------------------------------------


class _Modelos:
    def __init__(self):
        self.modelos: list[str] = []

    def _generate_content(self, **kwargs):
        self.modelos.append(kwargs["model"])
        return types.SimpleNamespace(usage_metadata=_Usage())


def test_escolher_troca_o_modelo_que_sai_e_o_que_se_conta():
    s, vistos, modelos = Sessao(), [], _Modelos()
    client = types.SimpleNamespace(models=modelos)
    forte = {"ligado": False}
    instrumentar(
        client,
        sessao=s,
        escolher=lambda m: "gemini-3.8-flash" if forte["ligado"] else m,
        antes=vistos.append,
    )
    client.models._generate_content(model="gemini-3.5-flash-lite", contents="a")
    forte["ligado"] = True
    client.models._generate_content(model="gemini-3.5-flash-lite", contents="b")
    assert modelos.modelos == ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
    assert vistos == modelos.modelos  # o `antes` vê o modelo que vai sair, não o pedido
    assert set(s.por_modelo) == {"gemini-3.5-flash-lite", "gemini-3.8-flash"}


# --- as cotas do dia (o emulador) -------------------------------------------------------------


@pytest.fixture
def cotas(firestore_limpo):
    return custos.Cotas(forte_dia=0.30, buscas_dia=3, fuso=LA)


def test_a_busca_alem_da_cota_e_recusada(cotas):
    for _ in range(3):
        cotas.reservar_busca()
    with pytest.raises(custos.CotaAtingida, match="3 buscas"):
        cotas.reservar_busca()
    assert cotas.hoje()["buscas"] == 3  # a recusa não conta


def test_consultas_a_mais_contam_e_fecham_a_cota(cotas):
    cotas.reservar_busca()
    cotas.somar_buscas(2)  # o modelo fez 3 consultas numa busca
    with pytest.raises(custos.CotaAtingida):
        cotas.reservar_busca()


def test_reservas_juntas_nao_passam_da_cota(firestore_limpo):
    """Várias instâncias do motor reservando a última busca do dia ao mesmo tempo: só a cota
    passa. As exceções das threads são recolhidas (uma exceção em thread não reprova sozinha)."""
    cotas = custos.Cotas(forte_dia=0.30, buscas_dia=5, fuso=LA)
    juntas, passaram, recusadas, erros = 8, [], [], []
    largada = threading.Barrier(juntas)

    def reservar():
        try:
            largada.wait()
            cotas.reservar_busca()
            passaram.append(1)
        except custos.CotaAtingida:
            recusadas.append(1)
        except Exception as exc:  # noqa: BLE001 - recolhida para o assert
            erros.append(exc)

    threads = [threading.Thread(target=reservar) for _ in range(juntas)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert erros == []
    assert (len(passaram), len(recusadas)) == (5, 3)
    assert cotas.hoje()["buscas"] == 5


def test_o_forte_para_na_cota_do_dia(cotas):
    cotas.conferir_forte()
    cotas.somar_forte(0.29)
    cotas.conferir_forte()
    cotas.somar_forte(0.02)
    with pytest.raises(custos.CotaAtingida, match="modelo forte"):
        cotas.conferir_forte()


def test_o_dia_da_cota_e_o_do_dono_nao_o_do_utc(cotas):
    antes_da_meia_noite = datetime(2026, 10, 8, 6, 30, tzinfo=UTC)  # 23:30 do dia 7 em Seattle
    for _ in range(3):
        cotas.reservar_busca(agora=antes_da_meia_noite)
    with pytest.raises(custos.CotaAtingida):
        cotas.reservar_busca(agora=antes_da_meia_noite)
    cotas.reservar_busca(agora=datetime(2026, 10, 8, 7, 30, tzinfo=UTC))  # 00:30 do dia 8 lá


def test_a_cota_do_forte_nao_mexe_no_gasto_do_mes(cotas):
    """O `gastos/AAAA-MM` tem formato fechado (o backup) e o `Teto.somar` reescreve o mês: a cota
    mora noutro documento."""
    teto = custos.Teto(mes=10, dia=1, fuso=LA)
    teto.somar(0.10)
    cotas.somar_forte(0.05)
    cotas.reservar_busca()
    assert teto.gasto().dia == pytest.approx(0.10)
    assert [g["mes"] for g in custos.exportar_gastos()] == [datetime.now(LA).strftime("%Y-%m")]
    assert set(custos.exportar_gastos()[0]) == {"mes", "total", "dias"}
