from lifeos.custos import Consumo, Sessao, dinheiro, do_gemini, do_jev


class _Usage:
    prompt_token_count = 1000
    candidates_token_count = 200


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
