"""Serviço do Gmail contra um Gmail falso no formato da API real (`tests/conftest.py`, `gmail`).

O que decide aqui: falha nunca vira vazio (lidos a menos são contados, teto vira "piso"), o corpo
sai legível nos formatos reais (base64url sem padding, charset da parte, só HTML), e texto de
terceiro chega sem caractere de controle. O que o Gemini lê é testado em `test_gmail_tools.py`.
"""

from datetime import datetime

import pytest

from lifeos.config import TIMEZONE
from lifeos.gmail import service

ESC = chr(0x1B)
RLO = chr(0x202E)


# --- buscar ---------------------------------------------------------------------------------


def test_buscar_devolve_os_campos_da_mensagem(gmail):
    gmail["nova"](
        "a1",
        de='"Loja X" <Ofertas@Loja.example>',
        assunto="50% hoje",
        trecho="Só hoje &#39;tudo&#39;",
        rotulos=("INBOX", "UNREAD", "CATEGORY_PROMOTIONS"),
        lista=True,
    )
    (email,) = service.buscar("from:loja").emails
    assert (email.id, email.remetente, email.endereco) == ("a1", "Loja X", "ofertas@loja.example")
    assert email.assunto == "50% hoje"
    assert email.trecho == "Só hoje 'tudo'"
    assert email.nao_lido and email.lista and email.categorias == ("promoções",)
    assert gmail["consultas"] == ["from:loja"]


def test_buscar_respeita_o_teto(gmail):
    for i in range(30):
        gmail["nova"](f"m{i}")
    busca = service.buscar("x", max_resultados=999)
    assert len(busca.emails) == service.MAX_RESULTADOS
    assert busca.mais


def test_busca_que_coube_inteira_nao_diz_que_tem_mais(gmail):
    gmail["nova"]("a")
    assert not service.buscar("x", max_resultados=5).mais


def test_quem_falha_uma_vez_ganha_nova_tentativa(gmail):
    """429 em rajada é o caso comum do lote: uma pausa e uma nova tentativa resolvem."""
    gmail["nova"]("a")
    gmail["nova"]("b")
    gmail["falhar_uma_vez"].add("b")
    busca = service.buscar("x")
    assert [e.id for e in busca.emails] == ["a", "b"]
    assert busca.falharam == 0


def test_quem_falha_sempre_e_contado_nunca_somido(gmail):
    gmail["nova"]("a")
    gmail["nova"]("b")
    gmail["falhar_sempre"].add("b")
    busca = service.buscar("x")
    assert [e.id for e in busca.emails] == ["a"]
    assert busca.falharam == 1


def test_lote_inteiro_fora_do_ar_conta_todos(gmail):
    gmail["nova"]("a")
    gmail["falhar_lote"] = True
    busca = service.buscar("x")
    assert busca.emails == () and busca.falharam == 1


def test_lotes_nao_passam_do_tamanho_configurado(gmail):
    for i in range(60):
        gmail["nova"](f"m{i}")
    service.raio_x()
    assert max(gmail["lotes"]) <= service.LOTE


def test_falha_na_busca_vira_erro_de_dominio(gmail):
    gmail["falhar_list"] = True
    with pytest.raises(service.FalhaDaApi):
        service.buscar("x")


def test_sem_login_vira_erro_de_dominio(monkeypatch):
    def sem_token():
        raise FileNotFoundError("Credenciais OAuth não encontradas")

    monkeypatch.setattr(service, "get_gmail_service", sem_token)
    with pytest.raises(service.SemLogin, match="Credenciais"):
        service.buscar("x")


def test_texto_de_terceiro_chega_sem_controle(gmail):
    gmail["nova"]("a", de=f"Ban{RLO}co <x@y.example>", assunto=f"{ESC}[2JOi", trecho=f"a{ESC}b")
    (email,) = service.buscar("x").emails
    assert RLO not in email.remetente and ESC not in email.assunto and ESC not in email.trecho


def test_assunto_codificado_rfc2047_e_decodificado(gmail):
    gmail["nova"]("a", assunto="=?UTF-8?B?UHJvbW/Dp8Ojbw==?=")
    (email,) = service.buscar("x").emails
    assert email.assunto == "Promoção"


def test_nao_lidos_de_hoje_comeca_na_meia_noite_do_fuso(gmail):
    agora = datetime(2026, 9, 26, 15, 30, tzinfo=TIMEZONE)
    meia_noite = datetime(2026, 9, 26, tzinfo=TIMEZONE)
    assert service.consulta_de_hoje(agora) == (
        f"is:unread in:inbox after:{int(meia_noite.timestamp())}"
    )
    service.nao_lidos_de_hoje()
    assert gmail["consultas"][0].startswith("is:unread in:inbox after:")


# --- ler ------------------------------------------------------------------------------------


def test_ler_prefere_texto_plano(gmail):
    gmail["nova"](
        "a",
        partes=[
            gmail["parte"]("text/plain", "Olá, tudo bem?"),
            gmail["parte"]("text/html", "<p>versão html</p>"),
        ],
    )
    completo = service.ler("a")
    assert completo.corpo == "Olá, tudo bem?"
    assert not completo.truncado and completo.anexos == 0
    assert gmail["gets"] == [("a", "full")]


def test_ler_so_html_vira_texto_sem_script(gmail):
    html = (
        "<html><head><style>p{color:red}</style></head><body><p>Linha 1</p>"
        "<script>roubar()</script><div>Linha&nbsp;2 &amp; fim</div></body></html>"
    )
    gmail["nova"]("a", partes=[gmail["parte"]("text/html", html)])
    corpo = service.ler("a").corpo
    assert "Linha 1" in corpo and "Linha 2 & fim" in corpo
    assert "roubar" not in corpo and "color" not in corpo


def test_ler_respeita_o_charset_da_parte(gmail):
    gmail["nova"]("a", partes=[gmail["parte"]("text/plain", "Promoção válida", "iso-8859-1")])
    assert service.ler("a").corpo == "Promoção válida"


def test_charset_desconhecido_nao_derruba(gmail):
    parte = gmail["parte"]("text/plain", "texto")
    parte["headers"] = [{"name": "Content-Type", "value": 'text/plain; charset="x-inventado"'}]
    gmail["nova"]("a", partes=[parte])
    assert service.ler("a").corpo == "texto"


def test_multipart_aninhado_e_anexo_contado(gmail):
    aninhado = {
        "mimeType": "multipart/alternative",
        "parts": [gmail["parte"]("text/plain", "corpo de dentro")],
    }
    anexo = gmail["parte"]("application/pdf", "%PDF", nome="fatura.pdf")
    gmail["nova"]("a", partes=[aninhado, anexo])
    completo = service.ler("a")
    assert completo.corpo == "corpo de dentro" and completo.anexos == 1


def test_corpo_longo_e_cortado_e_avisa(gmail):
    gmail["nova"]("a", partes=[gmail["parte"]("text/plain", "x" * (service.MAX_CORPO + 10))])
    completo = service.ler("a")
    assert len(completo.corpo) == service.MAX_CORPO and completo.truncado


def test_corpo_com_controle_sai_limpo(gmail):
    gmail["nova"]("a", partes=[gmail["parte"]("text/plain", f"oi{ESC}[31m{RLO} fim")])
    corpo = service.ler("a").corpo
    assert ESC not in corpo and RLO not in corpo


@pytest.mark.parametrize("ruim", ["", "   ", "../../etc", "a/b", "id com espaço", "x" * 65])
def test_id_estranho_e_recusado_antes_da_api(gmail, ruim):
    with pytest.raises(service.EntradaInvalida):
        service.ler(ruim)
    assert gmail["gets"] == []


def test_id_inexistente_vira_nao_encontrado(gmail):
    with pytest.raises(service.NaoEncontrado):
        service.ler("sumiu123")


# --- raio-x ---------------------------------------------------------------------------------


def test_raio_x_agrupa_por_remetente_e_ordena_pelos_nao_abertos(gmail):
    for i in range(3):
        gmail["nova"](f"n{i}", de="News <news@jornal.example>", lista=True)
    gmail["nova"]("p1", de="Amiga <amiga@x.example>", rotulos=("INBOX",))
    gmail["nova"]("p2", de="Amiga <amiga@x.example>", rotulos=("INBOX", "UNREAD"))
    gmail["nova"](
        "o1", de="Loja <l@loja.example>", rotulos=("INBOX", "UNREAD", "CATEGORY_PROMOTIONS")
    )
    raio = service.raio_x(30)
    assert [r.endereco for r in raio.remetentes] == [
        "news@jornal.example",
        "amiga@x.example",
        "l@loja.example",
    ]
    news = raio.remetentes[0]
    assert (news.total, news.nao_lidos, news.lista) == (3, 3, True)
    assert raio.remetentes[2].promocoes == 1
    assert (raio.lidos, raio.falharam, raio.no_teto) == (6, 0, False)
    assert gmail["consultas"] == ["in:inbox newer_than:30d"]


def test_raio_x_no_teto_avisa_que_e_piso(gmail):
    gmail["por_pagina"] = 50  # obriga a paginar
    for i in range(service.MAX_RAIO_X + 5):
        gmail["nova"](f"m{i}")
    raio = service.raio_x()
    assert raio.lidos == service.MAX_RAIO_X
    assert raio.no_teto


def test_raio_x_exatamente_no_teto_sem_mais_nada_nao_e_piso(gmail):
    for i in range(service.MAX_RAIO_X):
        gmail["nova"](f"m{i}")
    assert not service.raio_x().no_teto


def test_raio_x_conta_quem_nao_pode_ser_lido(gmail):
    gmail["nova"]("a")
    gmail["nova"]("b")
    gmail["falhar_sempre"].add("a")
    raio = service.raio_x()
    assert (raio.lidos, raio.falharam) == (1, 1)


@pytest.mark.parametrize(("pedido", "usado"), [(0, 1), (-5, 1), (9999, 365)])
def test_janela_do_raio_x_tem_limites(gmail, pedido, usado):
    service.raio_x(pedido)
    assert gmail["consultas"] == [f"in:inbox newer_than:{usado}d"]
