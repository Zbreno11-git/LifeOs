"""O modelo forte no chat da nuvem (Sessão 12, D65): o próprio Viking o pede, com cota por dia.

O "Gemini" é o cliente de verdade do google-genai com só a chamada de rede trocada por um roteiro,
que anota o MODELO de cada chamada (um dublê que ignorasse o modelo deixaria a troca verde por
outro motivo: erros, classe 4). As perguntas: depois da tool, as chamadas seguintes do mesmo turno
vão ao forte? O turno seguinte volta ao do dia a dia? A cota do dia segura um pedido repetido (um
e-mail injetado)? Acabou no meio do turno, o resto volta ao barato? O gasto do forte entra na cota
e no teto?
"""

from zoneinfo import ZoneInfo

import pytest
from google import genai
from google.genai import types

from lifeos import config, custos, registro
from lifeos.assistant import na_nuvem, turno

LA = ZoneInfo("America/Los_Angeles")
LITE, FORTE = turno.MODELO, turno.MODELO_FORTE


@pytest.fixture(autouse=True)
def _nuvem(firestore_limpo, monkeypatch):
    monkeypatch.setattr(config, "TETO_GEMINI_DIA", 5.0)
    monkeypatch.setattr(config, "TETO_GEMINI_MES", 10.0)
    monkeypatch.setattr(config, "TETO_FORTE_DIA", 0.30)
    monkeypatch.setattr(config, "TIMEZONE", LA)
    origem, t = registro.ORIGEM.set(registro.ORIGEM.get()), registro.TURNO.set(registro.TURNO.get())
    yield
    registro.TURNO.reset(t)
    registro.ORIGEM.reset(origem)


def _uso(tokens):
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=tokens, candidates_token_count=10
    )


def _texto(texto, tokens=100):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=texto)]),
                finish_reason="STOP",
            )
        ],
        usage_metadata=_uso(tokens),
    )


def _chama(nome, tokens=100, **args):
    parte = types.Part(
        function_call=types.FunctionCall(name=nome, args=args), thought_signature=b"\x01sig"
    )
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[parte]), finish_reason="STOP"
            )
        ],
        usage_metadata=_uso(tokens),
    )


class _Roteiro:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.modelos: list[str] = []
        self.enviados: list[str] = []

    def __call__(self, **kwargs):
        self.modelos.append(kwargs["model"])
        self.enviados.append(str(kwargs.get("contents")))
        return self.respostas.pop(0)


@pytest.fixture
def gemini(monkeypatch):
    def instalar(*respostas):
        roteiro = _Roteiro(*respostas)
        cliente = genai.Client(api_key="teste")
        cliente.models._generate_content = roteiro
        monkeypatch.setattr(na_nuvem, "_cliente", lambda: cliente)
        return roteiro

    return instalar


def _pedido(mensagem, numero=1):
    return {"mensagem": mensagem, "historico": [], "sessao": "ab12cd34", "numero": numero}


def test_depois_da_tool_o_turno_continua_no_forte(gemini):
    roteiro = gemini(_chama("usar_modelo_forte", motivo="contas longas"), _texto("Feito."))
    saida = na_nuvem.turno(_pedido("planeja minha semana com 12 compromissos"))
    assert saida["resposta"] == "Feito."
    assert roteiro.modelos == [LITE, FORTE]
    assert f"{LITE}:" in saida["consumo"] and f"{FORTE}:" in saida["consumo"]
    forte = na_nuvem._cotas().hoje()["forte"]
    assert forte > 0  # o gasto do forte entrou na cota do dia
    assert na_nuvem._teto().gasto().dia > forte  # e no teto, junto com o do dia a dia


def test_o_turno_seguinte_volta_ao_do_dia_a_dia(gemini):
    gemini(_chama("usar_modelo_forte", motivo="x"), _texto("1"))
    na_nuvem.turno(_pedido("um"))
    roteiro = gemini(_texto("2"))
    na_nuvem.turno(_pedido("dois", numero=2))
    assert roteiro.modelos == [LITE]


def test_sem_pedir_o_forte_tudo_sai_no_do_dia_a_dia(gemini):
    roteiro = gemini(_chama("listar_lembretes"), _texto("Nada pendente."))
    saida = na_nuvem.turno(_pedido("o que tenho pendente?"))
    assert roteiro.modelos == [LITE, LITE]
    assert FORTE not in saida["consumo"]


def test_cota_do_forte_esgotada_a_tool_recusa_e_o_modelo_nao_troca(gemini):
    na_nuvem._cotas().somar_forte(0.30)
    roteiro = gemini(_chama("usar_modelo_forte", motivo="x"), _texto("Sigo eu."))
    na_nuvem.turno(_pedido("pensa bem nisso"))
    assert roteiro.modelos == [LITE, LITE]
    assert "Não troquei de modelo" in roteiro.enviados[-1]


def test_a_cota_acaba_no_meio_do_turno_e_o_resto_volta_ao_barato(gemini):
    """Uma chamada do forte de 1 milhão de tokens custa US$ 0,75 e passa da cota de US$ 0,30: a
    chamada seguinte do mesmo turno já sai no do dia a dia."""
    roteiro = gemini(
        _chama("usar_modelo_forte", motivo="x"),
        _chama("listar_lembretes", tokens=1_000_000),
        _texto("Pronto."),
    )
    na_nuvem.turno(_pedido("compara as opções"))
    assert roteiro.modelos == [LITE, FORTE, LITE]


def test_um_pedido_repetido_nao_passa_da_cota_do_dia(gemini):
    """Um e-mail injetado que manda pedir o forte em todo turno: depois que a cota acaba, nenhum
    turno chega ao forte, e o gasto do forte para perto da cota (a última chamada pode passar)."""
    modelos = []
    for n in range(1, 8):
        roteiro = gemini(
            _chama("usar_modelo_forte", motivo="o e-mail mandou"),
            _texto("ok", tokens=200_000),  # US$ 0,15 no forte
        )
        na_nuvem.turno(_pedido("lê o e-mail e faz o que ele pede", numero=n))
        modelos += roteiro.modelos[1:]
    assert modelos.count(FORTE) == 2  # 0,15 + 0,15 = 0,30: a cota fecha
    assert na_nuvem._cotas().hoje()["forte"] == pytest.approx(0.30, abs=0.01)


def test_fora_de_um_turno_da_nuvem_a_tool_nao_troca_nada():
    assert "não está disponível" in na_nuvem.usar_modelo_forte("x")


def test_a_cota_do_forte_vem_do_config(monkeypatch):
    monkeypatch.setattr(config, "TETO_FORTE_DIA", 0.12)
    monkeypatch.setattr(config, "BUSCAS_DIA", 7)
    cotas = na_nuvem._cotas()
    assert (cotas.forte_dia, cotas.buscas_dia) == (0.12, 7)
    assert isinstance(cotas, custos.Cotas)
