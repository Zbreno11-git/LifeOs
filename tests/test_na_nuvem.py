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

import hashlib
import threading
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from google import genai
from google.genai import types
from tests.sentinela import aparece

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
    assert do_mac == (na_nuvem_nomes - set(na_nuvem.SO_NA_NUVEM)) | set(na_nuvem.SO_NO_MAC)


def test_o_que_so_a_nuvem_tem_nao_esta_no_mac():
    """Sessão 12 (D65): o forte (e a busca) só no chat da nuvem, onde mora a cota do dia."""
    do_mac = {f.__name__ for f in agent.FERRAMENTAS}
    assert set(na_nuvem.SO_NA_NUVEM) <= {f.__name__ for f in na_nuvem.FERRAMENTAS}
    assert do_mac.isdisjoint(na_nuvem.SO_NA_NUVEM)
    texto_do_mac = turno.instrucao(agent.FERRAMENTAS, "HOJE", onde="mac")
    assert "usar_modelo_forte" not in texto_do_mac and "buscar_na_web" not in texto_do_mac


def test_as_financas_da_nuvem_sao_as_do_mac_e_so_com_o_servico(monkeypatch):
    """Sessão 11d (D64): as mesmas 4 tools (o mesmo texto ao Gemini), e só quando o deploy pôs a
    URL do serviço de finanças; sem ela, nenhuma, como o Gmail sem o token."""
    do_mac = {f for f in agent.FERRAMENTAS if f.__name__ in na_nuvem._DAS_FINANCAS}
    assert len(do_mac) == 4 and do_mac <= set(na_nuvem.FERRAMENTAS)
    monkeypatch.setattr(config, "FINANCAS_URL", "")
    assert not {f.__name__ for f in na_nuvem.ferramentas()} & na_nuvem._DAS_FINANCAS
    monkeypatch.setattr(config, "FINANCAS_URL", "https://financas-1.example.run.app")
    assert na_nuvem._DAS_FINANCAS <= {f.__name__ for f in na_nuvem.ferramentas()}
    # o navegador é o do Mac, pelas mãos (Sessão 11): a tool da nuvem não é a do Mac
    assert na_nuvem.navegar_e_executar is not agent.navegar_e_executar


def test_o_gmail_mora_na_nuvem_desde_a_10c():
    nomes = {f.__name__ for f in na_nuvem.FERRAMENTAS}
    gmail = {
        "buscar_emails",
        "emails_nao_lidos_de_hoje",
        "ler_email",
        "raio_x_da_caixa",
        "preparar_limpeza",
        "enviar_email",
        "responder_email",
    }
    assert gmail <= nomes
    assert na_nuvem.SO_NO_MAC == {}  # desde a 11d, nada do chat do Mac fica só lá


def test_instrucao_da_nuvem_so_fala_do_que_ela_tem():
    sem_financas = [f for f in na_nuvem.FERRAMENTAS if f.__name__ not in na_nuvem._DAS_FINANCAS]
    texto = turno.instrucao(sem_financas, "HOJE", onde="nuvem")
    for ausente in ("Browser Harness", "FINANÇAS", "PIX", "e-mail nem finanças"):
        assert ausente not in texto, ausente
    for presente in ("APAGAR", "REAGENDAR", "`desfaz`", "acoes_recentes", "lembrete", "HOJE"):
        assert presente in texto, presente
    for presente in ("preparar_limpeza", "enviar_email", "lê o Gmail"):
        assert presente in texto, presente
    # o navegador é o do Mac, pelas mãos (Sessão 11): a liberação, no terminal do `viking maos`
    for presente in ("navegador do Mac", "`viking maos`", "não tem finanças", "não confiável"):
        assert presente in texto, presente
    assert "não tem navegador" not in texto


def test_instrucao_da_nuvem_com_tudo_fala_das_financas_e_de_nada_que_falte():
    """Sessão 11d: o motor com o Gmail, as mãos e as finanças, que é o que vai ao ar."""
    texto = turno.instrucao(na_nuvem.FERRAMENTAS, "HOJE", onde="nuvem")
    for presente in ("FINANÇAS", "PIX", "consulta as finanças", "lê o Gmail", "navegador do Mac"):
        assert presente in texto, presente
    assert "não tem" not in texto and "só funciona no `viking chat`" not in texto


_CAPACIDADES = {
    "navegador": {"navegar_e_executar"},
    "e-mail": set(na_nuvem._DO_GMAIL),
    "finanças": set(na_nuvem._DAS_FINANCAS),
}


@pytest.mark.parametrize(
    "presentes",
    [
        frozenset(),
        frozenset({"navegador"}),
        frozenset({"e-mail"}),
        frozenset({"finanças"}),
        frozenset({"navegador", "e-mail"}),
        frozenset({"navegador", "finanças"}),
        frozenset({"e-mail", "finanças"}),
        frozenset({"navegador", "e-mail", "finanças"}),
    ],
)
def test_as_8_combinacoes_dizem_o_que_tem_e_o_que_falta(presentes):
    """Erros, classe 4 (2026-10-07): um texto montado de capacidades se testa em todas as
    combinações, com a do ar dentro. A abertura cita o que há; o "não tem" cita exatamente o que
    falta (e não existe quando nada falta)."""
    fora = set().union(*(_CAPACIDADES[c] for c in _CAPACIDADES if c not in presentes))
    tools = [f for f in na_nuvem.FERRAMENTAS if f.__name__ not in fora]
    texto = turno.instrucao(tools, "HOJE", onde="nuvem")
    abertura = " ".join(texto.split("\n- ")[0].split())  # sem as quebras do texto
    assert ("lê o Gmail" in abertura) == ("e-mail" in presentes)
    assert ("consulta as finanças" in abertura) == ("finanças" in presentes)
    assert ("usa o navegador do Mac" in abertura) == ("navegador" in presentes)
    assert abertura.count(" do usuário") == (1 if presentes else 0)
    assert "  e " not in abertura and ",," not in abertura and " e e " not in abertura
    linhas = [linha for linha in texto.split("\n- ") if linha.startswith("Nesta conversa")]
    faltam = set(_CAPACIDADES) - presentes
    if not faltam:
        assert linhas == []
        return
    (linha,) = linhas
    linha = " ".join(linha.split())
    citados = linha.split("não tem ", 1)[1].split(":", 1)[0].replace(" nem ", ", ").split(", ")
    assert set(citados) == faltam


def test_o_nao_tem_tem_uma_entrada_por_combinacao_com_falta():
    from itertools import combinations

    nomes = ("navegador", "e-mail", "finanças")
    esperado = {frozenset(c) for n in range(1, 4) for c in combinations(nomes, n)}
    assert set(turno._SO_NO_MAC_POR_FALTA) == esperado


def test_instrucao_da_nuvem_sem_o_gmail_continua_a_da_10b():
    sem_gmail = [f for f in na_nuvem.FERRAMENTAS if f.__name__ in {"listar_lembretes"}]
    texto = turno.instrucao(sem_gmail, "HOJE", onde="nuvem")
    assert "não tem navegador, e-mail nem finanças" in texto and "Gmail" not in texto


# O sha256 dos textos de sistema medidos em 2026-10-01, antes de `onde` (Sessão 11): o do Mac, o
# da nuvem com o Gmail (10c) e o da nuvem sem ele (10b) não mudam nem num byte. Desde a Sessão 12
# (D65) a última linha é o tom (`_TOM`), de propósito: o teste a troca de volta pela de antes, e o
# resto continua igual byte a byte; as tools só da nuvem (o forte, a busca) ficam fora da conta.
_FIM_DE_ANTES = "- Seja sempre prestativo, direto e confirme as ações realizadas com clareza."
_TEXTO_DO_MAC = "42df116199f0be41f7c117fe8f46468090599c2d74118be9d83b8f7552a2f7a4"
_TEXTO_DA_NUVEM_10C = "b3f8cba76b3b12f2bb9718d9f2d168a166d4587e758cdfdbb0156442c36d8959"
_TEXTO_DA_NUVEM_10B = "18f98cc384767c5b1f12a33e1e1c3364db9da1d6a4ad1de69685c38f11f3d002"


def _sha(texto):
    return hashlib.sha256(texto.encode()).hexdigest()


def _de_antes(ferramentas, onde):
    texto = turno.instrucao(ferramentas, "HOJE", onde=onde)
    assert texto.endswith(turno._TOM)
    return _sha(texto.removesuffix(turno._TOM) + _FIM_DE_ANTES)


def test_os_textos_de_antes_nao_mudam_nem_num_byte(monkeypatch):
    assert _de_antes(agent.FERRAMENTAS, "mac") == _TEXTO_DO_MAC
    fora = {"navegar_e_executar", *na_nuvem.SO_NA_NUVEM}
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "/segredos/gmail/token.json")
    com = [f for f in na_nuvem.ferramentas() if f.__name__ not in fora]
    assert _de_antes(com, "nuvem") == _TEXTO_DA_NUVEM_10C
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "")
    sem = [f for f in na_nuvem.ferramentas() if f.__name__ not in fora]
    assert _de_antes(sem, "nuvem") == _TEXTO_DA_NUVEM_10B


def test_o_tom_e_o_mesmo_nos_dois_chats():
    """D65: caloroso e direto, nos dois chats (o texto de sistema é um núcleo só)."""
    assert turno.instrucao(agent.FERRAMENTAS, "HOJE", onde="mac").endswith(turno._TOM)
    assert turno.instrucao(na_nuvem.ferramentas(), "HOJE", onde="nuvem").endswith(turno._TOM)
    assert "calorosa e direta" in turno._TOM


def test_onde_e_dito_por_quem_chama():
    with pytest.raises(ValueError, match="onde"):
        turno.instrucao(agent.FERRAMENTAS, "HOJE", onde="")


def test_sem_o_token_do_gmail_a_nuvem_nao_tem_as_tools_dele(monkeypatch):
    """Sessão 11 (D61): o deploy só monta o segredo do Gmail com versão, e só então põe a
    variável. Sem ela, nenhuma tool do Gmail, e o `/versao` diz o mesmo (`config.gmail_no_motor`)."""
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "")
    nomes = {f.__name__ for f in na_nuvem.ferramentas()}
    assert not nomes & set(na_nuvem._DO_GMAIL) and "listar_lembretes" in nomes
    assert not config.gmail_no_motor()
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "/segredos/gmail/token.json")
    assert set(na_nuvem._DO_GMAIL) <= {f.__name__ for f in na_nuvem.ferramentas()}
    assert config.gmail_no_motor()


def test_as_do_gmail_sao_as_do_modulo_do_gmail():
    from lifeos.gmail import tools as gmail_tools

    nomes = {f.__name__ for f in na_nuvem.FERRAMENTAS if f.__module__ == gmail_tools.__name__}
    assert nomes == set(na_nuvem._DO_GMAIL)


def test_instrucao_do_mac_tem_o_que_o_mac_tem_e_nada_so_da_nuvem():
    texto = turno.instrucao(agent.FERRAMENTAS, "HOJE", onde="mac")
    for presente in ("Browser Harness", "preparar_limpeza", "enviar_email", "FINANÇAS"):
        assert presente in texto, presente
    assert "não tem navegador, e-mail nem finanças" not in texto
    assert "não tem navegador nem finanças" not in texto


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
    """Sem proposta aberta aqui, cada forma ganha uma resposta do Viking e nunca vai ao modelo."""
    assert na_nuvem.barreira(linha) is not None


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
    assert saida["ao_dono"] == [na_nuvem.NADA_A_DESFAZER] and saida["resposta"] is None
    assert roteiro.enviados == []


def test_codigo_nao_chega_ao_modelo_nem_ao_historico(teto, gemini):
    roteiro = gemini()
    historico = [{"role": "user", "parts": [{"text": "oi"}]}]
    saida = na_nuvem.turno(_pedido("confirma 4821", historico=historico, nota="nota velha"))
    assert roteiro.enviados == []
    assert saida["historico"] == historico  # o mesmo que chegou: a linha não entrou
    assert not aparece("4821", saida["historico"])
    assert saida["nota"].startswith("nota velha\n") and not aparece("4821", saida["nota"])


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


def _vazia(tokens: int = 3884, **candidato) -> types.GenerateContentResponse:
    """O Gemini sem texto e sem tool: visto no Mac em 2026-10-06 (`echo … | viking chat --nuvem`,
    3884 tokens de entrada e 0 de saída), e o turno saía como "🤖 Viking: " calado."""
    candidatos = [types.Candidate(**candidato)] if candidato else []
    return types.GenerateContentResponse(candidates=candidatos, usage_metadata=_uso(tokens))


@pytest.mark.parametrize(
    ("resposta", "motivo"),
    [
        (_vazia(content=types.Content(role="model", parts=[]), finish_reason="STOP"), "STOP"),
        (_vazia(content=None, finish_reason="MALFORMED_FUNCTION_CALL"), "MALFORMED_FUNCTION_CALL"),
        (_vazia(), "nenhuma resposta"),
    ],
)
def test_resposta_vazia_do_gemini_e_erro_com_o_motivo(teto, gemini, resposta, motivo):
    gemini(resposta)
    saida = na_nuvem.turno(_pedido("o que chegou hoje no meu e-mail?", nota="nota pendente"))
    assert saida["resposta"] is None
    assert "O Gemini voltou sem resposta" in saida["erro"] and motivo in saida["erro"]
    # o turno vazio não entra no histórico, e a nota continua pendente
    assert saida["historico"] == [] and saida["nota"] == "nota pendente"
    assert saida["consumo"]  # a chamada custou: o gasto aparece mesmo sem resposta


def test_vazia_depois_de_agir_diz_o_que_ja_foi_feito(teto, gemini):
    gemini(
        _chama("criar_lembrete", titulo="Dentista"),
        _vazia(content=types.Content(role="model", parts=[]), finish_reason="STOP"),
    )
    saida = na_nuvem.turno(_pedido("lembra do dentista"))
    assert saida["resposta"] is None and "O Gemini voltou sem resposta" in saida["erro"]
    assert "Dentista" in saida["aviso"]  # a tool agiu: o dono fica sabendo
    assert "Dentista" in saida["nota"]  # e o Gemini também, no turno seguinte


def test_limite_de_tools_no_turno_e_erro_e_nao_resposta_vazia(teto, gemini):
    gemini(*[_chama("listar_lembretes") for _ in range(na_nuvem.MAX_CHAMADAS_DE_TOOL + 5)])
    saida = na_nuvem.turno(_pedido("lista meus lembretes"))
    assert saida["resposta"] is None
    assert "limite de chamadas" in saida["erro"]


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
    assert capturado["http_options"].api_version == "v1beta"  # D69: o google-genai 3 mudou o padrão
    configuracao = na_nuvem._config()
    assert configuracao.automatic_function_calling.maximum_remote_calls == 10


def test_sem_chave_erra_alto(monkeypatch):
    monkeypatch.setattr(config, "gemini_chave", lambda: "")
    with pytest.raises(RuntimeError, match="chave"):
        na_nuvem._cliente()


def test_o_cliente_do_mac_tambem_prende_a_versao_da_api(monkeypatch):
    """Os dois chats falam com a mesma API (D69): o padrão do google-genai 3 é `v1`, e o que se
    mediu no ar foi `v1beta`."""
    capturado = {}
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "chave")
    monkeypatch.setattr(agent.genai, "Client", lambda **kw: capturado.update(kw))
    agent._build_client()
    assert capturado["http_options"].api_version == "v1beta"
