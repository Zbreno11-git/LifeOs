"""Cada efeito externo do Viking passa pelo registro de ações (Sessão 5, §7).

A régua mais importante é a do fim: lida do código, toda chamada que muda algo fora do Viking
(Google Calendar, Gmail, lembretes) está dentro de uma função que abre `registro.acao`. Um caminho
de mutação novo sem registro faz o teste cair, sem lista escrita à mão.
"""

import ast
from pathlib import Path

import pytest

from lifeos import registro
from lifeos.calendar import service as calendario_service
from lifeos.calendar import tools as calendario_tools
from lifeos.reminders import service as lembretes


class ErroHttp(Exception):
    """Imita o `HttpError` do googleapiclient: o status fica em `resp.status`."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


@pytest.fixture(autouse=True)
def _turno():
    origem = registro.ORIGEM.set("chat")
    turno = registro.TURNO.set("s:1")
    yield
    registro.TURNO.reset(turno)
    registro.ORIGEM.reset(origem)


def _acoes():
    return registro.do_turno("s:1")


def test_criar_evento_registra(calendario):
    calendario_tools.criar_evento("Dentista", "2026-10-01T10:00:00", "2026-10-01T11:00:00")
    (a,) = _acoes()
    assert (a.operacao, a.estado, a.resultado["event_id"]) == (
        "calendario.criar",
        "feita",
        "novo123",
    )


def test_apagar_guarda_o_evento_bruto_para_desfazer(calendario):
    calendario["evento"] = {
        "id": "abc",
        "summary": "Dentista",
        "description": "levar exames",
        "start": {"dateTime": "2026-10-01T10:00:00-03:00", "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": "2026-10-01T11:00:00-03:00"},
    }
    calendario_tools.apagar_evento_por_id("abc", "Dentista")
    (a,) = _acoes()
    assert a.operacao == "calendario.apagar" and a.desfazivel
    copia = registro.reivindicar_desfazer(a.id)
    assert copia["evento"]["description"] == "levar exames"  # o bruto, não o `Evento`
    assert copia["evento"]["start"]["timeZone"] == "America/Sao_Paulo"


def test_reagendar_guarda_o_horario_antigo(calendario):
    calendario["evento"] = {"summary": "Dentista", "start": {"date": "2026-10-01"}}
    calendario_tools.reagendar_evento_por_id(
        "abc", "Dentista", "2026-10-02T10:00:00", "2026-10-02T11:00:00"
    )
    (a,) = _acoes()
    copia = registro.reivindicar_desfazer(a.id)
    assert copia["start"] == {"date": "2026-10-01"}  # dia inteiro volta a ser dia inteiro
    assert copia["novo_start"]["dateTime"].startswith("2026-10-02T10:00")


def test_recusa_pelas_travas_nao_registra_nada(calendario):
    calendario_tools.apagar_evento_por_id("abc", "Outro título")
    calendario_tools.apagar_evento_por_id("", "Dentista")
    assert _acoes() == []


def test_falha_ao_montar_e_falhou(calendario):
    calendario["falhar_delete"] = True
    calendario_tools.apagar_evento_por_id("abc", "Dentista")
    (a,) = _acoes()
    assert a.estado == "falhou" and not a.pode_ter_acontecido


def test_4xx_do_google_e_falhou(calendario):
    calendario["erro_no_execute"] = ErroHttp(404)
    calendario_tools.apagar_evento_por_id("abc", "Dentista")
    assert _acoes()[0].estado == "falhou"


@pytest.mark.parametrize("erro", [ErroHttp(503), TimeoutError("timed out"), OSError("reset")])
def test_falha_depois_de_enviar_e_incerta(calendario, erro):
    calendario["erro_no_execute"] = erro
    calendario["aplicar_antes"] = True
    texto = calendario_tools.apagar_evento_por_id("abc", "Dentista")
    assert calendario["apagados"] == ["abc"]  # o Google aplicou...
    (a,) = _acoes()
    assert a.estado == "incerta" and a.pode_ter_acontecido  # ...e o registro não diz "falhou"
    assert texto.startswith("Não sei se apaguei o evento 'Dentista'")
    assert "confira no calendário antes de tentar de novo" in texto


def test_criar_com_resposta_ambigua_diz_que_nao_sabe(calendario, monkeypatch):
    def insert_que_aplica_e_falha(self, calendarId, body):
        self._estado["enviados"].append(body)
        return type(self.get("primary", "x"))({}, TimeoutError("timed out"))

    monkeypatch.setattr(
        type(calendario_service.get_calendar_service().events()),
        "insert",
        insert_que_aplica_e_falha,
    )
    texto = calendario_tools.criar_evento("Dentista", "2026-10-01T10:00:00", "2026-10-01T11:00:00")
    assert texto.startswith("Não sei se criei o evento 'Dentista'")
    assert _acoes()[0].estado == "incerta"


def test_lembrete_criar_e_concluir_registram():
    lembrete = lembretes.criar_lembrete("Pagar conta")
    lembretes.concluir(lembrete.id)
    lembretes.concluir(99999)
    ops = [(a.operacao, a.resultado) for a in _acoes()]
    assert ops == [
        ("lembrete.criar", {"id": lembrete.id, "titulo": "Pagar conta"}),
        ("lembrete.concluir", {"id": lembrete.id, "achado": True}),
        ("lembrete.concluir", {"id": 99999, "achado": False}),
    ]


def test_arquivar_no_gmail_registra(gmail):
    from lifeos.gmail import service as gmail_service

    gmail["nova"]("m1", de="Loja <loja@x.example>")
    gmail_service.arquivar(["m1"])
    (a,) = _acoes()
    assert (a.operacao, a.parametros, a.resultado["feitos"]) == (
        "gmail.arquivar",
        {"quantos": 1},
        1,
    )


# --- a régua: nenhum efeito externo sem registro -------------------------------------------

_MUTACOES = {"delete", "patch", "insert", "batchModify", "add", "complete"}


def _chama_registro(funcao: ast.AST) -> bool:
    return any(
        isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "acao"
        and getattr(no.func.value, "id", None) == "registro"
        for no in ast.walk(funcao)
    )


def _mutacoes_sem_registro() -> list[str]:
    raiz = Path(registro.__file__).parent
    faltando = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo.name.startswith("_jev") or arquivo.name == "_acoes_sensiveis.py":
            continue  # dentro do subprocesso do Jev: o registro é do lado do Viking (run_jev)
        arvore = ast.parse(arquivo.read_text())
        for funcao in ast.walk(arvore):
            if not isinstance(funcao, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for no in ast.walk(funcao):
                if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
                    continue
                nome, dono = no.func.attr, ast.unparse(no.func.value)
                externo = (
                    (nome in {"delete", "patch", "insert"} and dono.endswith("events()"))
                    or nome == "batchModify"
                    or (nome in {"add", "complete"} and dono == "store")
                )
                if externo and not _chama_registro(funcao):
                    faltando.append(f"{arquivo.relative_to(raiz)}:{no.lineno} {dono}.{nome}")
    return faltando


def test_todo_efeito_externo_passa_pelo_registro():
    assert _mutacoes_sem_registro() == []


def test_a_regua_enxerga_as_mutacoes():
    """Sem isto, uma régua que não acha nada ficaria verde à toa."""
    raiz = Path(registro.__file__).parent
    fonte = "\n".join(p.read_text() for p in raiz.rglob("*.py"))
    for nome in ("events().delete", "events().patch", "events().insert", "batchModify"):
        assert nome in fonte
    assert "store.add(" in fonte and "store.complete(" in fonte
    assert _MUTACOES
    assert calendario_service.FalhaDaApi("x", incerta=True).incerta
