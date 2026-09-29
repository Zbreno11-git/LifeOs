"""Serviço do calendário (`calendar/service.py`): devolve dado estruturado ou levanta erro de
domínio com código — o contrato que o MCP expõe. Inclui o bug latente que a extração corrigiu:
falha da API em criar/reagendar/listar subia como exceção crua."""

import pytest

from lifeos.calendar import service

_ITEM = {
    "id": "e1",
    "summary": "Dentista",
    "start": {"dateTime": "2026-10-02T10:00:00-03:00"},
    "end": {"dateTime": "2026-10-02T11:00:00-03:00"},
    "htmlLink": "http://cal/e1",
}


def test_proximos_devolve_eventos(calendario):
    calendario["itens"] = [_ITEM, {"id": "e2", "start": {"date": "2026-10-05"}}]
    primeiro, segundo = service.proximos()
    assert primeiro == service.Evento(
        id="e1",
        titulo="Dentista",
        inicio="2026-10-02T10:00:00-03:00",
        fim="2026-10-02T11:00:00-03:00",
        dia_inteiro=False,
        link="http://cal/e1",
    )
    assert segundo.titulo == "Sem título" and segundo.dia_inteiro


def test_por_data_invalida_e_entrada_invalida_sem_chamar_a_api(calendario):
    with pytest.raises(service.EntradaInvalida) as exc:
        service.por_data("2026-09-20", "2026-09-10")
    assert exc.value.codigo == "entrada_invalida" and exc.value.dados["campo"] == "data"
    assert calendario["consultas"] == []


def test_criar_devolve_o_que_foi_enviado_mais_id_e_link(calendario):
    evento = service.criar("Reunião", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00")
    assert evento.id == "novo123" and evento.link == "http://exemplo"
    assert evento.inicio == "2026-10-02T10:00:00-03:00" and evento.titulo == "Reunião"


def test_criar_dia_inteiro_tem_fim_exclusivo(calendario):
    evento = service.criar_dia_inteiro("Feriado", "2026-12-31")
    assert evento.dia_inteiro and evento.inicio == "2026-12-31" and evento.fim == "2027-01-01"


@pytest.mark.parametrize(
    ("inicio", "fim", "campo"),
    [("nada", "nada", "horario"), ("2026-10-02T11:00:00", "2026-10-02T10:00:00", "intervalo")],
)
def test_criar_horario_ruim(calendario, inicio, fim, campo):
    with pytest.raises(service.EntradaInvalida) as exc:
        service.criar("x", inicio, fim)
    assert exc.value.dados["campo"] == campo
    assert calendario["enviados"] == []


@pytest.mark.parametrize(
    ("event_id", "titulo", "campo"),
    [("", "Dentista", "event_id"), ("abc", "  ", "titulo_esperado")],
)
def test_apagar_recusa_alvo_vazio(calendario, event_id, titulo, campo):
    with pytest.raises(service.EntradaInvalida) as exc:
        service.apagar(event_id, titulo)
    assert exc.value.dados["campo"] == campo
    assert calendario["apagados"] == []


def test_apagar_titulo_divergente_carrega_o_titulo_real(calendario):
    with pytest.raises(service.TituloDivergente) as exc:
        service.apagar("abc", "Outra coisa")
    assert exc.value.codigo == "titulo_divergente"
    assert exc.value.dados["titulo_real"] == "Dentista"
    assert calendario["apagados"] == []


def test_apagar_inexistente(calendario):
    calendario["evento"] = None
    with pytest.raises(service.EventoNaoEncontrado) as exc:
        service.apagar("sumiu", "Dentista")
    assert exc.value.codigo == "nao_encontrado" and exc.value.dados["event_id"] == "sumiu"


def test_apagar_devolve_o_evento_apagado(calendario):
    evento = service.apagar("abc", "dentista")
    assert evento.titulo == "Dentista" and calendario["apagados"] == ["abc"]


@pytest.mark.parametrize(
    ("chave", "chamada"),
    [
        ("falhar_list", lambda: service.proximos()),
        ("falhar_list", lambda: service.buscar("x")),
        ("falhar_insert", lambda: service.criar("x", "2026-10-02T10:00", "2026-10-02T11:00")),
        ("falhar_insert", lambda: service.criar_dia_inteiro("x", "2026-10-02")),
        (
            "falhar_patch",
            lambda: service.reagendar("abc", "Dentista", "2026-10-02T10:00", "2026-10-02T11:00"),
        ),
        ("falhar_delete", lambda: service.apagar("abc", "Dentista")),
    ],
)
def test_falha_da_api_vira_erro_de_dominio(calendario, chave, chamada):
    """Antes da extração, só o delete tratava falha da API; o resto subia como exceção crua."""
    calendario[chave] = True
    with pytest.raises(service.FalhaDaApi) as exc:
        chamada()
    assert exc.value.codigo == "falha_api"


def test_falha_na_mutacao_informa_qual_evento(calendario):
    calendario["falhar_patch"] = True
    with pytest.raises(service.FalhaDaApi) as exc:
        service.reagendar("abc", "Dentista", "2026-10-02T10:00", "2026-10-02T11:00")
    assert exc.value.dados["titulo_real"] == "Dentista"


def test_reagendar_devolve_horario_novo(calendario):
    evento = service.reagendar(
        "abc", "Dentista", "2026-10-02T10:00:00-03:00", "2026-10-02T11:00:00-03:00"
    )
    assert (
        evento.inicio == "2026-10-02T10:00:00-03:00" and evento.fim == "2026-10-02T11:00:00-03:00"
    )


def test_titulo_de_convite_com_controle_chega_limpo(calendario):
    """Títulos vêm de terceiros (convites): caracteres de controle não passam (§6.3)."""
    calendario["itens"] = [
        {"id": "x", "summary": "\x1b[2JReunião \u202efdp", "start": {"date": "2026-10-01"}}
    ]
    (evento,) = service.proximos()
    assert evento.titulo == "[2JReunião fdp"


# --- paginação (Sessão 8b; skill `falha-ruidosa` §2: um teto silencioso é uma interrupção) -----


def _serie(n: int) -> list[dict]:
    """Uma série semanal que se repete `n` vezes (`singleEvents=True` devolve cada ocorrência)."""
    return [
        {"id": f"s{i}", "summary": "Aula", "start": {"date": f"2027-01-{i % 28 + 1:02d}"}}
        for i in range(n)
    ]


def test_busca_com_300_ocorrencias_vem_inteira(calendario):
    """Antes lia só a 1ª página: 250 de 300, sem aviso."""
    calendario["itens"] = _serie(300)
    eventos = service.buscar("Aula")
    assert len(eventos) == 300
    assert eventos.completa is True
    assert len(calendario["consultas"]) == 2


def test_busca_acima_do_teto_para_e_diz_que_esta_incompleta(calendario):
    calendario["itens"] = _serie(600)
    eventos = service.buscar("Aula")
    assert service.TETO_EVENTOS == 500
    assert len(eventos) == 500
    assert eventos.completa is False
    assert len(calendario["consultas"]) == 2


def test_exatamente_no_teto_e_completa(calendario):
    calendario["itens"] = _serie(500)
    eventos = service.buscar("Aula")
    assert len(eventos) == 500
    assert eventos.completa is True


def test_por_data_tambem_pagina(calendario):
    """O vizinho com o mesmo teto de 250 (erros, classe 6)."""
    calendario["itens"] = _serie(600)
    eventos = service.por_data("2027-01-01", "2027-12-31")
    assert len(eventos) == 500
    assert eventos.completa is False
    assert [c.get("pageToken") for c in calendario["consultas"]] == [None, "250"]


def test_busca_vem_na_ordem_do_inicio(calendario):
    """Com teto, os que ficam são os mais próximos: a ordem é pedida à API."""
    service.buscar("Aula")
    assert calendario["consultas"][0]["orderBy"] == "startTime"
    assert calendario["consultas"][0]["singleEvents"] is True


def test_proximos_pede_o_numero_e_e_completo(calendario):
    """`proximos` responde o que foi pedido (os N primeiros): completo por definição."""
    calendario["itens"] = _serie(30)
    eventos = service.proximos(10)
    assert len(eventos) == 10
    assert eventos.completa is True


def test_paginas_vazias_sem_fim_param_e_dizem_que_esta_incompleta(calendario):
    """A referência do `events.list` (lida em 2026-09-29): uma página pode vir "less than this
    value, or none at all, even if there are more events". Contar só eventos giraria para sempre."""
    calendario["paginas_vazias"] = True
    eventos = service.buscar("Aula")
    assert list(eventos) == []
    assert eventos.completa is False
    assert len(calendario["consultas"]) == service.MAX_PAGINAS
