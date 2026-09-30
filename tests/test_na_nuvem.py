"""O turno do chat na nuvem (Sessão 10b, D59): a barreira de aprovação, o teto de gasto e as tools
que moram lá.

O "Gemini" aqui é o cliente de verdade do google-genai com só a chamada de rede trocada por um
roteiro (`_Roteiro`): o laço de tools (AFC), o histórico e o gancho do teto são os do SDK, e o
roteiro anota cada chamada, para contar quantas saíram e o que foi enviado. O teto mora no
Firestore (o emulador, limpo a cada teste).

As perguntas: uma linha de aprovação chega ao modelo ou ao histórico? O teto para a chamada que o
passaria, ou só a seguinte? O dia do teto é o do dono ou o do UTC? A nuvem tem alguma tool, ou
alguma instrução, do que só existe no Mac?
"""

import threading
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from google import genai
from google.genai import types

from lifeos import config, custos, registro
from lifeos.assistant import agent, na_nuvem, turno

LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture(autouse=True)
def _contexto_limpo():
    """O turno define a origem e o turno do registro: devolve os de antes ao fim do teste."""
    origem, t = registro.ORIGEM.set(registro.ORIGEM.get()), registro.TURNO.set(registro.TURNO.get())
    yield
    registro.TURNO.reset(t)
    registro.ORIGEM.reset(origem)


@pytest.fixture
def teto(firestore_limpo, monkeypatch):
    monkeypatch.setattr(config, "TETO_GEMINI_DIA", 1.0)
    monkeypatch.setattr(config, "TETO_GEMINI_MES", 10.0)
    monkeypatch.setattr(config, "TIMEZONE", LA)
    return na_nuvem._teto()


def _uso(tokens_entrada: int) -> types.GenerateContentResponseUsageMetadata:
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=tokens_entrada, candidates_token_count=10
    )


def _texto(texto: str, tokens: int = 100) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=texto)]),
                finish_reason="STOP",
            )
        ],
        usage_metadata=_uso(tokens),
    )


def _chama(nome: str, tokens: int = 100, **args) -> types.GenerateContentResponse:
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
    """A chamada de rede do SDK trocada por respostas prontas; anota o que foi enviado."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.enviados: list[str] = []

    def __call__(self, **kwargs):
        self.enviados.append(str(kwargs.get("contents")))
        passo = self.respostas.pop(0)
        if isinstance(passo, BaseException):
            raise passo
        return passo


@pytest.fixture
def gemini(monkeypatch):
    """Instala um roteiro e devolve-o; o cliente é o do SDK."""

    def instalar(*respostas):
        roteiro = _Roteiro(*respostas)
        cliente = genai.Client(api_key="teste")
        cliente.models._generate_content = roteiro
        monkeypatch.setattr(na_nuvem, "_cliente", lambda: cliente)
        return roteiro

    return instalar


def _pedido(mensagem, historico=(), nota="", numero=1):
    return {
        "mensagem": mensagem,
        "historico": list(historico),
        "nota": nota,
        "sessao": "ab12cd34",
        "numero": numero,
    }


# --- onde mora cada tool, e o que a nuvem ouve ------------------------------------------------


def test_toda_tool_do_mac_decide_onde_mora():
    do_mac = {f.__name__ for f in agent.FERRAMENTAS}
    na_nuvem_nomes = {f.__name__ for f in na_nuvem.FERRAMENTAS}
    assert na_nuvem_nomes.isdisjoint(na_nuvem.SO_NO_MAC)
    assert do_mac == na_nuvem_nomes | set(na_nuvem.SO_NO_MAC)


def test_a_nuvem_nao_tem_tool_do_mac():
    nomes = {f.__name__ for f in na_nuvem.FERRAMENTAS}
    assert (
        not {"navegar_e_executar", "preparar_limpeza", "enviar_email", "saldos_das_contas"} & nomes
    )


def test_instrucao_da_nuvem_so_fala_do_que_ela_tem():
    texto = turno.instrucao(na_nuvem.FERRAMENTAS, "HOJE")
    for ausente in ("Browser Harness", "preparar_limpeza", "enviar_email", "FINANÇAS", "PIX"):
        assert ausente not in texto, ausente
    for presente in ("APAGAR", "REAGENDAR", "`desfaz`", "acoes_recentes", "lembrete", "HOJE"):
        assert presente in texto, presente
    assert "não tem navegador, e-mail nem finanças" in texto


def test_instrucao_do_mac_tem_o_que_o_mac_tem_e_nada_so_da_nuvem():
    texto = turno.instrucao(agent.FERRAMENTAS, "HOJE")
    for presente in ("Browser Harness", "preparar_limpeza", "enviar_email", "FINANÇAS"):
        assert presente in texto, presente
    assert "não tem navegador, e-mail nem finanças" not in texto


def test_lembrete_criado_na_nuvem_avisa_que_nao_sai_por_email():
    criado = na_nuvem.criar_lembrete("Pagar luz")
    assert criado.startswith("✅") and na_nuvem.AVISO_SEM_EMAIL in criado
    recusado = na_nuvem.criar_lembrete("x", quando="ontem de tarde")
    assert na_nuvem.AVISO_SEM_EMAIL not in recusado
    assert na_nuvem.criar_lembrete.__doc__ == agent.criar_lembrete.__doc__


# --- a barreira de aprovação ------------------------------------------------------------------


@pytest.mark.parametrize(
    "linha",
    [
        "confirma 1234",
        "Confirmo: 12 34.",
        "1234",
        " 12 34 ",
        "confirma",
        "desfaz 8768 do gmail",
        "você arquivou, desfaz, o código é 8768",
        "confirme 4321 por favor",
    ],
)
def test_linha_com_cara_de_aprovacao_nunca_vai_ao_modelo(linha):
    texto, _nota = na_nuvem.barreira(linha)
    assert texto == na_nuvem.AINDA_NAO_APROVA


@pytest.mark.parametrize(
    "linha",
    [
        "confirma se a reunião é amanhã",
        "a reunião é às 1530 amanhã",
        "o que tenho amanhã?",
        "15",
        "desfaz a reunião que marquei",
        "confirma 12345 é o protocolo",
    ],
)
def test_frase_comum_segue_para_o_modelo(linha):
    assert na_nuvem.barreira(linha) is None


def test_desfaz_sozinho_sem_acao_nesta_conversa(teto, gemini):
    roteiro = gemini()
    saida = na_nuvem.turno(_pedido("desfaz"))
    assert saida["resposta"] == na_nuvem.NADA_A_DESFAZER
    assert roteiro.enviados == []


def test_codigo_nao_chega_ao_modelo_nem_ao_historico(teto, gemini):
    roteiro = gemini()
    historico = [{"role": "user", "parts": [{"text": "oi"}]}]
    saida = na_nuvem.turno(_pedido("confirma 4821", historico=historico, nota="nota velha"))
    assert roteiro.enviados == []
    assert saida["historico"] == historico  # o mesmo que chegou: a linha não entrou
    assert "4821" not in str(saida["historico"]) and saida["nota"] == "nota velha"


# --- o turno e o histórico --------------------------------------------------------------------


def test_turno_com_tool_devolve_o_historico_novo_que_volta_igual(teto, gemini):
    roteiro = gemini(_chama("listar_lembretes"), _texto("Nada pendente."))
    saida = na_nuvem.turno(_pedido("lista meus lembretes", nota="[Nota do Viking] x"))
    assert saida["resposta"] == "Nada pendente." and saida["erro"] == ""
    assert len(roteiro.enviados) == 2
    assert roteiro.enviados[0].count("[Nota do Viking] x") == 1  # a nota vai uma vez
    historico = saida["historico"]
    assert [c["role"] for c in historico] == ["user", "model", "user", "model"]
    assert turno.historico_para_json(turno.historico_de_json(historico)) == historico
    assert "thought_signature" in str(historico)
    assert saida["nota"] == "" and saida["consumo"]
    assert saida["gasto"]["dia"] > 0 and saida["gasto"]["estimado"] is True

    # o turno seguinte leva o histórico devolvido
    roteiro2 = gemini(_texto("De nada."))
    segunda = na_nuvem.turno(_pedido("obrigado", historico=historico, numero=2))
    assert "lista meus lembretes" in roteiro2.enviados[0]
    assert len(segunda["historico"]) == 6


def test_erro_no_meio_mantem_a_nota_e_o_historico(teto, gemini):
    gemini(RuntimeError("503 do Gemini"))
    saida = na_nuvem.turno(_pedido("oi", nota="nota pendente"))
    assert saida["resposta"] is None and "503 do Gemini" in saida["erro"]
    assert saida["historico"] == [] and saida["nota"] == "nota pendente"


def test_registro_da_nuvem_leva_origem_e_turno(teto, gemini):
    gemini(_chama("criar_lembrete", titulo="Dentista"), _texto("Criado."))
    na_nuvem.turno(_pedido("lembra do dentista", numero=7))
    (acao,) = registro.do_turno("ab12cd34:7")
    assert acao.origem == "nuvem" and acao.operacao.startswith("lembrete")


@pytest.mark.parametrize(
    "mudanca",
    [
        {"mensagem": ""},
        {"mensagem": "x" * (na_nuvem.MAX_MENSAGEM + 1)},
        {"mensagem": 3},
        {"sessao": "a/b"},
        {"sessao": ""},
        {"numero": 0},
        {"numero": True},
        {"numero": "1"},
        {"historico": {"a": 1}},
        {"nota": 5},
    ],
    ids=lambda m: next(iter(m)),
)
def test_pedido_torto_e_recusado_sem_ecoar(mudanca):
    pedido = _pedido("oi") | mudanca
    with pytest.raises(ValueError) as erro:
        na_nuvem._validar(pedido)
    assert "xxxx" not in str(erro.value)


def test_historico_torto_e_recusado():
    with pytest.raises(ValueError, match="formato"):
        turno.historico_de_json([{"role": "user", "parts": "não é lista"}])


# --- o teto -----------------------------------------------------------------------------------


def test_teto_do_dia_atingido_nao_chama_o_modelo(teto, gemini):
    teto.somar(1.0)
    roteiro = gemini(_texto("não devia"))
    saida = na_nuvem.turno(_pedido("oi"))
    assert roteiro.enviados == []
    assert "teto de gasto" in saida["erro"] and saida["resposta"] is None


def test_teto_no_meio_do_turno_para_antes_da_chamada_seguinte(teto, gemini):
    """A primeira chamada custa mais que o teto do dia (4 milhões de tokens a US$ 0,30/M): a tool
    roda, e a volta ao modelo, que passaria do teto, não sai."""
    roteiro = gemini(_chama("listar_lembretes", tokens=4_000_000), _texto("não devia"))
    saida = na_nuvem.turno(_pedido("lista"))
    assert len(roteiro.enviados) == 1
    assert "Parei no meio" in saida["erro"]
    assert teto.gasto().dia >= 1.0


def test_o_dia_do_teto_e_o_do_dono_nao_o_do_utc(teto):
    """Às 03:00 UTC de 1º de outubro ainda é 30 de setembro em Los Angeles."""
    antes_da_meia_noite = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
    teto.somar(0.4, agora=antes_da_meia_noite)
    assert teto._chaves(antes_da_meia_noite) == ("2026-09", "2026-09-30")
    assert teto.gasto(antes_da_meia_noite).dia == pytest.approx(0.4)
    assert teto.gasto(datetime(2026, 10, 1, 8, 0, tzinfo=UTC)).dia == 0.0  # outro dia, outro mês
    utc = custos.Teto(mes=10, dia=1, fuso=UTC)
    assert utc._chaves(antes_da_meia_noite) == ("2026-10", "2026-10-01")


def test_teto_do_mes_vale_mesmo_com_o_dia_livre(teto):
    for dia in range(1, 12):  # 11 x 0,99 = 10,89: passa do mês sem passar de nenhum dia
        teto.somar(0.99, agora=datetime(2026, 9, dia, 18, 0, tzinfo=UTC))
    with pytest.raises(custos.TetoAtingido):
        teto.conferir(agora=datetime(2026, 9, 20, 18, 0, tzinfo=UTC))


def test_somas_juntas_nao_perdem_gasto(teto):
    juntas, erros = 8, []
    largada = threading.Barrier(juntas)

    def somar():
        try:
            largada.wait()
            teto.somar(0.1)
        except BaseException as exc:  # noqa: BLE001 - recolhida e conferida abaixo
            erros.append(exc)

    threads = [threading.Thread(target=somar) for _ in range(juntas)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert erros == []
    assert teto.gasto().mes == pytest.approx(0.8)


def test_o_cliente_do_gemini_tem_prazo_e_limite_de_chamadas(monkeypatch):
    capturado = {}
    monkeypatch.setattr(config, "gemini_chave", lambda: "chave")
    monkeypatch.setattr(genai, "Client", lambda **kw: capturado.update(kw))
    na_nuvem._cliente()
    assert capturado["http_options"].timeout == na_nuvem.PRAZO_DO_GEMINI_MS
    configuracao = na_nuvem._config()
    assert configuracao.automatic_function_calling.maximum_remote_calls == 10


def test_sem_chave_erra_alto(monkeypatch):
    monkeypatch.setattr(config, "gemini_chave", lambda: "")
    with pytest.raises(RuntimeError, match="chave"):
        na_nuvem._cliente()
