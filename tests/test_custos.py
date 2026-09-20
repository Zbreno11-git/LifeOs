import types

from lifeos.custos import Consumo, Sessao, dinheiro, do_gemini, do_jev, instrumentar


class _Usage:
    prompt_token_count = 1000
    candidates_token_count = 200


class _UsageCompleta:
    """Metadata com todos os campos cobrados: prompt, tool_use_prompt (entrada), candidates e
    thoughts (saída) — os dois últimos que a auditoria apontou como ignorados."""

    prompt_token_count = 1000
    tool_use_prompt_token_count = 300
    candidates_token_count = 200
    thoughts_token_count = 150


def test_dinheiro_nao_arredonda_fracao_de_centavo_para_zero():
    assert dinheiro(0.0000137) == "US$ 0,000014"
    assert dinheiro(1.5) == "US$ 1,50"


def test_gemini_estima_a_partir_dos_tokens():
    c = do_gemini(_Usage())
    assert (c.entrada, c.saida, c.chamadas) == (1000, 200, 1)
    assert c.estimado is True
    assert c.custo > 0


def test_gemini_sem_metadata_nao_inventa():
    assert do_gemini(None) == Consumo()


def test_jev_usa_o_custo_real_quando_o_provedor_informa():
    c = do_jev({"cost": 0.000041, "prompt_tokens": 900, "completion_tokens": 12, "chamadas": 3})
    assert c.custo == 0.000041
    assert c.estimado is False
    assert (c.entrada, c.saida, c.chamadas) == (900, 12, 3)


def test_jev_sem_custo_nao_inventa_numero():
    """Se o endpoint não mandar custo, preferimos mostrar zero marcado como estimado a chutar."""
    c = do_jev({"prompt_tokens": 500, "chamadas": 2})
    assert c.custo == 0.0
    assert c.estimado is True


def test_sessao_soma_as_duas_fontes():
    s = Sessao()
    s.gemini = s.gemini + do_gemini(_Usage())
    s.navegador = s.navegador + do_jev({"cost": 0.001, "chamadas": 1})
    assert s.total == s.gemini.custo + 0.001
    texto = s.total_formatado()
    assert "Gemini" in texto and "Navegador" in texto and "Total da sessão" in texto


def test_gemini_conta_thinking_e_tool_use_prompt():
    """Achado da auditoria: thoughts_token_count e tool_use_prompt_token_count existem no SDK
    instalado e eram ignorados, subcontando justamente os turnos com ferramenta."""
    c = do_gemini(_UsageCompleta())
    assert c.entrada == 1000 + 300
    assert c.saida == 200 + 150


def test_sessao_turno_acumula_desde_iniciar_turno():
    s = Sessao()
    s.iniciar_turno()
    s.registrar_gemini(do_gemini(_Usage()))
    s.registrar_gemini(do_gemini(_Usage()))
    assert s.turno().chamadas == 2
    assert s.gemini.chamadas == 2
    s.iniciar_turno()
    assert s.turno().chamadas == 0
    assert s.gemini.chamadas == 2  # o total da sessão não é zerado, só o do turno


class _ModelosFalsos:
    """Simula `client.models`: cada chamada devolve uma resposta com usage_metadata próprio."""

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.chamadas = 0

    def _generate_content(self, **kwargs):
        self.chamadas += 1
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _resposta(usage):
    return types.SimpleNamespace(usage_metadata=usage)


def test_instrumentar_conta_cada_chamada_do_afc_nao_so_a_ultima():
    """O SDK reatribui `response` a cada volta do laço de AFC; sem o gancho, só a última resposta
    (a que não chama nenhuma tool) aparece no usage_metadata visível pelo chat."""
    s = Sessao()
    modelos = _ModelosFalsos([_resposta(_Usage()), _resposta(_Usage()), _resposta(_Usage())])
    client = types.SimpleNamespace(models=modelos)

    ok = instrumentar(client, sessao=s)
    assert ok is True

    client.models._generate_content()
    client.models._generate_content()
    client.models._generate_content()

    assert s.gemini.chamadas == 3
    assert s.gemini.entrada == 3000


def test_instrumentar_duas_vezes_nao_dobra_o_custo():
    s = Sessao()
    modelos = _ModelosFalsos([_resposta(_Usage())])
    client = types.SimpleNamespace(models=modelos)

    assert instrumentar(client, sessao=s) is True
    assert instrumentar(client, sessao=s) is False  # já instrumentado, não reaplica

    client.models._generate_content()
    assert s.gemini.chamadas == 1


def test_instrumentar_chamada_que_falha_nao_apaga_a_anterior():
    s = Sessao()
    modelos = _ModelosFalsos([_resposta(_Usage()), RuntimeError("erro de rede")])
    client = types.SimpleNamespace(models=modelos)
    instrumentar(client, sessao=s)

    client.models._generate_content()
    try:
        client.models._generate_content()
    except RuntimeError:
        pass

    assert s.gemini.chamadas == 1  # a primeira, que já custou, continua contabilizada


def test_instrumentar_sem_o_gancho_do_sdk_nao_quebra():
    """Acoplamento consciente a um atributo privado do google-genai: se ele sumir numa versão
    futura, `instrumentar` vira no-op em vez de derrubar o assistente."""
    client = types.SimpleNamespace(models=types.SimpleNamespace())
    assert instrumentar(client) is False


def test_acoplamento_com_o_sdk_real_ainda_vale():
    """Documenta a dependência: se este teste falhar, o google-genai removeu/renomeou
    `Models._generate_content` e `instrumentar()` em custos.py precisa ser revisto."""
    from google import genai

    client = genai.Client(api_key="chave-falsa-so-para-instanciar")
    assert hasattr(client.models, "_generate_content")
