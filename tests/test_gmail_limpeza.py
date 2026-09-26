"""Limpeza da caixa: o que sai, o que nunca sai, e que só sai com o código (Sessão Gmail 2).

O Gmail falso (`tests/conftest.py`) avalia a consulta — `from:` por pedaço, como o real — e
registra o corpo de cada `batchModify`. A pergunta de cada teste é "que e-mail sairia da caixa
que o dono não aprovou, ou não queria?".
"""

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from lifeos import confirmacao
from lifeos.gmail import limpeza, oauth, service

LOJA = "ofertas@loja.example"


def _caixa(gmail):
    """Uma caixa típica: 3 comuns da loja, 3 protegidos da loja, 1 de outra pessoa. Inseridos do
    mais novo para o mais velho (é como o Gmail lista)."""
    gmail["nova"]("l3", de=f"Loja <{LOJA}>", assunto="Oferta 3")
    gmail["nova"]("estrela", de=f"Loja <{LOJA}>", rotulos=("INBOX", "STARRED"))
    gmail["nova"]("l2", de=f"Loja <{LOJA}>", assunto="Oferta 2", rotulos=("INBOX",))
    gmail["nova"]("importante", de=f"Loja <{LOJA}>", rotulos=("INBOX", "IMPORTANT"))
    anexo = [gmail["parte"]("application/pdf", "%PDF", nome="nota.pdf")]
    gmail["nova"]("anexo", de=f"Loja <{LOJA}>", partes=anexo)
    gmail["nova"]("l1", de=f"Loja <{LOJA}>", assunto="Oferta 1")
    gmail["nova"]("amiga", de="Amiga <amiga@x.example>")


def _na_caixa(gmail, email_id):
    return "INBOX" in gmail["mensagens"][email_id]["labelIds"]


# --- seleção -------------------------------------------------------------------------------


def test_seleciona_todos_do_remetente_menos_os_protegidos(gmail):
    _caixa(gmail)
    grupo = service.selecionar(LOJA).grupos[0]
    assert grupo.sai == ("l1", "l2", "l3")  # dos mais antigos para os mais novos
    assert dict(grupo.protegidos) == {"com estrela": 1, "importantes": 1, "com anexo": 1}
    assert grupo.assuntos == ("Oferta 3", "Oferta 2", "Oferta 1")
    assert gmail["modificacoes"] == []  # selecionar só lê


@pytest.mark.parametrize("frouxa", [False, True])
def test_protegidos_nunca_saem_nem_se_a_consulta_falhar(gmail, frouxa):
    """Com `consulta_frouxa`, o Gmail devolve até os de estrela: a conferência nos metadados e a
    lista de `has:attachment` têm de segurar sozinhas."""
    _caixa(gmail)
    gmail["consulta_frouxa"] = frouxa
    assert set(service.selecionar(LOJA).ids) == {"l1", "l2", "l3"}


def test_remetente_parecido_nao_entra(gmail):
    """`from:` do Gmail casa por pedaço: `ofertas@loja.example` acha também um impostor."""
    gmail["nova"]("falso", de=f"Loja <{LOJA}.golpe.example>")
    gmail["nova"]("l1", de=f"Loja <{LOJA}>")
    grupo = service.selecionar(LOJA).grupos[0]
    assert grupo.sai == ("l1",)
    assert grupo.outro_remetente == 1


@pytest.mark.parametrize(
    "pedido",
    [
        f"{LOJA} OR in:anywhere",
        f"{LOJA} in:anywhere",
        "*",
        "from:loja.example",
        "loja.example",
        f"{LOJA}, amiga",
        f"{LOJA}{chr(0x202E)}",
        "a@b",
    ],
)
def test_pedido_que_nao_e_endereco_exato_nao_consulta_nada(gmail, pedido):
    with pytest.raises(service.EntradaInvalida):
        service.selecionar(pedido)
    assert gmail["consultas"] == []


def test_endereco_entre_sinais_e_maiusculas_sao_aceitos(gmail):
    assert service.enderecos_validos(f" <{LOJA.upper()}> , {LOJA}") == [LOJA]


def test_remetentes_demais_recusados(gmail):
    pedidos = [f"r{i}@x.example" for i in range(service.MAX_REMETENTES_LIMPEZA + 1)]
    with pytest.raises(service.EntradaInvalida, match="no máximo"):
        service.selecionar(pedidos)


def test_teto_leva_os_mais_antigos_e_diz_quantos_sobram(gmail):
    for i in range(5, 0, -1):  # m5 é o mais novo
        gmail["nova"](f"m{i}", de=f"Loja <{LOJA}>")
    grupo = service.selecionar(LOJA, teto=3).grupos[0]
    assert grupo.sai == ("m1", "m2", "m3")
    assert grupo.sobram == 2


def test_teto_vale_para_a_proposta_inteira_na_ordem_pedida(gmail):
    for i in range(3):
        gmail["nova"](f"a{i}", de="A <a@x.example>")
        gmail["nova"](f"b{i}", de="B <b@x.example>")
    selecao = service.selecionar("a@x.example, b@x.example", teto=4)
    assert [len(g.sai) for g in selecao.grupos] == [3, 1]
    assert selecao.sobram == 2


def test_metadado_que_falhou_fica_na_caixa(gmail):
    _caixa(gmail)
    gmail["falhar_sempre"].add("l2")
    grupo = service.selecionar(LOJA).grupos[0]
    assert "l2" not in grupo.sai
    assert grupo.falharam == 1


# --- arquivar / desarquivar ------------------------------------------------------------------


def test_arquivar_so_tira_o_rotulo_inbox(gmail):
    _caixa(gmail)
    resultado = service.arquivar(["l1", "l2"])
    assert resultado.feitos == ("l1", "l2")
    assert gmail["modificacoes"] == [{"ids": ["l1", "l2"], "removeLabelIds": ["INBOX"]}]
    assert "l1" in gmail["mensagens"]  # nada apagado
    assert not _na_caixa(gmail, "l1") and _na_caixa(gmail, "l3")


def test_arquivar_em_lotes_de_no_maximo_mil(gmail):
    ids = [f"m{i}" for i in range(service.TETO_LIMPEZA + 1)]
    for i in ids:
        gmail["nova"](i)
    service.arquivar(ids)
    assert [len(m["ids"]) for m in gmail["modificacoes"]] == [service.TETO_LIMPEZA, 1]


def test_falha_no_arquivar_diz_o_que_nao_foi(gmail):
    _caixa(gmail)
    gmail["falhar_modify"] = 1
    resultado = service.arquivar(["l1", "l2"])
    assert resultado.feitos == () and resultado.falharam == ("l1", "l2")
    assert resultado.erro


def test_id_estranho_nunca_vai_para_o_batch(gmail):
    service.arquivar(["../x", "", "ok1"])
    assert gmail["modificacoes"] == [{"ids": ["ok1"], "removeLabelIds": ["INBOX"]}]


# --- o código: nada sai sem ele ---------------------------------------------------------------


def test_proposta_nao_arquiva_e_codigo_arquiva_uma_vez(gmail):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    assert proposta.codigo and gmail["modificacoes"] == []
    execucao = limpeza.confirmar(proposta.codigo)
    assert execucao.modificacao.feitos == ("l1", "l2", "l3")
    assert not any(_na_caixa(gmail, i) for i in ("l1", "l2", "l3"))
    assert all(_na_caixa(gmail, i) for i in ("estrela", "importante", "anexo", "amiga"))
    with pytest.raises(confirmacao.JaUsado):
        limpeza.confirmar(proposta.codigo)
    assert len(gmail["modificacoes"]) == 1


def test_codigo_errado_nao_toca_na_caixa(gmail):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    errado = f"{(int(proposta.codigo) + 1) % 10**confirmacao.DIGITOS:0{confirmacao.DIGITOS}d}"
    with pytest.raises(confirmacao.CodigoInvalido):
        limpeza.confirmar(errado)
    assert gmail["modificacoes"] == []


def test_confirmacao_so_arquiva_o_que_foi_aprovado_e_ainda_vale(gmail):
    """Entre a lista e o código: um aprovado ganhou estrela, outro o dono tirou da caixa à mão, e
    chegou e-mail novo do mesmo remetente. Sai só o que continua valendo, e nada novo."""
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    gmail["mensagens"]["l2"]["labelIds"].append("STARRED")
    gmail["mensagens"]["l3"]["labelIds"].remove("INBOX")
    gmail["nova"]("novo", de=f"Loja <{LOJA}>")
    novo = gmail["mensagens"].pop("novo")
    gmail["mensagens"] = {"novo": novo, **gmail["mensagens"]}  # no topo: o mais novo da caixa
    execucao = limpeza.confirmar(proposta.codigo)
    assert execucao.modificacao.feitos == ("l1",)
    assert execucao.fora == 2
    assert _na_caixa(gmail, "novo") and _na_caixa(gmail, "l2")


def test_falha_ao_reler_na_confirmacao_nao_se_passa_por_mudanca(gmail):
    """Um 429 na hora de conferir de novo não é "ganhou estrela": o dono precisa saber que foi
    falha, porque pedir a lista de novo resolve."""
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    gmail["falhar_sempre"].add("l2")
    execucao = limpeza.confirmar(proposta.codigo)
    assert (execucao.fora, execucao.nao_conferidos) == (0, 1)
    assert "l2" not in execucao.modificacao.feitos and _na_caixa(gmail, "l2")


def test_proposta_vazia_invalida_o_codigo_anterior(gmail):
    _caixa(gmail)
    anterior = limpeza.preparar(LOJA)
    vazia = limpeza.preparar("ninguem@x.example")
    assert vazia.codigo is None
    with pytest.raises(confirmacao.CodigoInvalido):
        limpeza.confirmar(anterior.codigo)
    assert gmail["modificacoes"] == []


# --- desfazer ---------------------------------------------------------------------------------


def test_desfazer_devolve_exatamente_os_arquivados_uma_vez(gmail):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    limpeza.confirmar(proposta.codigo)
    gmail["mensagens"]["amiga"]["labelIds"].remove("INBOX")  # arquivado pelo dono, não por nós
    limpeza.desfazer(proposta.codigo)
    assert gmail["modificacoes"][-1] == {"ids": ["l1", "l2", "l3"], "addLabelIds": ["INBOX"]}
    assert not _na_caixa(gmail, "amiga")
    with pytest.raises(confirmacao.JaUsado):
        limpeza.desfazer(proposta.codigo)


def test_desfazer_que_falhou_pode_ser_repetido(gmail):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    limpeza.confirmar(proposta.codigo)
    gmail["falhar_modify"] = 1
    assert limpeza.desfazer(proposta.codigo).modificacao.falharam == ("l1", "l2", "l3")
    assert limpeza.desfazer(proposta.codigo).modificacao.feitos == ("l1", "l2", "l3")
    assert _na_caixa(gmail, "l1")


def test_desfazer_depois_do_prazo_recusado(gmail, monkeypatch):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    limpeza.confirmar(proposta.codigo)
    monkeypatch.setattr(limpeza, "DESFAZER_POR", timedelta(0))
    with pytest.raises(confirmacao.Expirado):
        limpeza.desfazer(proposta.codigo)


def test_desfazer_proposta_nao_aprovada_recusado(gmail):
    _caixa(gmail)
    proposta = limpeza.preparar(LOJA)
    with pytest.raises(confirmacao.CodigoInvalido):
        limpeza.desfazer(proposta.codigo)
    assert gmail["modificacoes"] == []


# --- o escopo permite mais do que o Viking usa (D29) ------------------------------------------

_PROIBIDAS = {"send", "trash", "untrash", "import_", "insert", "delete", "batchDelete", "drafts"}


def test_codigo_do_gmail_nunca_chama_enviar_lixeira_ou_apagar():
    """`gmail.modify` autoriza enviar e mover para a lixeira (medido em `gmail.v1.json`). O que
    impede é não haver chamada: qualquer atributo com esses nomes em `gmail/` derruba o teste."""
    pasta = Path(oauth.__file__).parent
    achados = []
    for arquivo in sorted(pasta.glob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text())):
            if isinstance(no, ast.Attribute) and no.attr in _PROIBIDAS:
                achados.append(f"{arquivo.name}:{no.lineno} .{no.attr}")
    assert achados == []


def test_escopo_e_modify_e_nunca_o_de_acesso_total():
    assert oauth.SCOPES == ["https://www.googleapis.com/auth/gmail.modify"]
    pasta = Path(oauth.__file__).parent
    assert not any("mail.google.com" in a.read_text() for a in pasta.glob("*.py"))
