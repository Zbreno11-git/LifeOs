"""O arquivo do backup (Sessão 11c, D63): o formato e os gastos do teto.

`montar` só devolve o que `ler` aceita, e `ler` recusa o arquivo inteiro quando algo não bate,
sem ecoar o conteúdo na mensagem (a saída da CLI é colada em conversa). Cada recusa muda **um**
campo de um arquivo bom: o teste cai pela regra que ele diz provar, não por outra (erros, classe 4).
"""

import copy
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from lifeos import custos
from lifeos.backup import formato
from lifeos.reminders import interface, transporte
from lifeos.reminders.models import Reminder

AGORA = datetime(2026, 10, 7, 9, 0, 5, tzinfo=UTC)
SEGREDO = "Consulta secreta 7391"


def _lembrete(**mudar) -> Reminder:
    campos = {
        "id": "3f1d2c4b-5a69-4e7f-8a1b-2c3d4e5f6a7b",
        "type": "reminder",
        "title": SEGREDO,
        "body": "",
        "tags": [],
        "due_at": AGORA + timedelta(days=1),
        "completed_at": None,
        "source": "manual",
        "external_id": None,
        "metadata": {},
        "created_at": AGORA - timedelta(days=2),
        "updated_at": AGORA - timedelta(days=2),
        "enviado_em": None,
        "envio_estado": None,
    }
    campos.update(mudar)
    return Reminder(**campos)


def _acao(**mudar) -> dict:
    copia = {
        "id": 1_790_000_000_000_000_001,
        "turno": "nuvem:1",
        "origem": "chat",
        "operacao": "lembrete.criar",
        "parametros": json.dumps({"titulo": SEGREDO}),
        "estado": "feita",
        "resultado": json.dumps({"id": "x"}),
        "erro": "",
        "desfazer": None,
        "desfeita_em": None,
        "criada_em": "2026-10-06T17:00:00.000000+00:00",
        "terminada_em": "2026-10-06T17:00:01.250000+00:00",
    }
    copia.update(mudar)
    return copia


def _gasto(**mudar) -> dict:
    copia = {"mes": "2026-10", "total": 0.25, "dias": {"2026-10-06": 0.25}}
    copia.update(mudar)
    return copia


def _bom() -> dict:
    return formato.montar(
        [_lembrete(), _lembrete(id="9e8d7c6b-5a49-4382-9172-6a5b4c3d2e1f", title="outro")],
        [_acao()],
        [_gasto()],
        agora=AGORA,
        commit="abc1234",
    )


def test_ida_e_volta_preserva_tudo():
    dados = _bom()
    backup = formato.de_bytes(formato.para_bytes(dados))
    assert backup.contagens() == {"lembretes": 2, "acoes": 1, "gastos": 1}
    assert backup.criado_em == AGORA and backup.commit == "abc1234"
    assert [transporte.impressao(r) for r in backup.lembretes] == [
        transporte.impressao(_lembrete()),
        transporte.impressao(_lembrete(id="9e8d7c6b-5a49-4382-9172-6a5b4c3d2e1f", title="outro")),
    ]
    assert backup.acoes == [_acao()]
    assert backup.gastos == [_gasto()]


def test_um_lembrete_concluido_e_enviado_volta_igual():
    enviado = _lembrete(
        completed_at=AGORA, enviado_em=AGORA - timedelta(hours=1), envio_estado=interface.ENVIADO
    )
    backup = formato.ler(formato.montar([enviado], [], [], agora=AGORA, commit="x"))
    assert transporte.impressao(backup.lembretes[0]) == transporte.impressao(enviado)


def _recusado(dados: dict, trecho: str) -> None:
    with pytest.raises(formato.BackupInvalido, match=trecho) as exc:
        formato.ler(dados)
    assert SEGREDO not in str(exc.value)


def test_campo_a_mais_no_arquivo_e_recusado():
    dados = _bom()
    dados["extra"] = 1
    _recusado(dados, "exatamente os campos")


def test_versao_desconhecida_e_recusada():
    dados = _bom()
    dados["versao"] = 2
    _recusado(dados, "versão do backup desconhecida")


def test_outro_formato_e_recusado():
    dados = _bom()
    dados["formato"] = "outra-coisa"
    _recusado(dados, "não é um arquivo de backup")


def test_contagem_errada_e_recusada():
    dados = _bom()
    dados["contagens"]["acoes"] = 2
    _recusado(dados, "contagens")


def test_lembrete_alterado_no_arquivo_e_recusado_pela_impressao():
    dados = _bom()
    dados["lembretes"][0]["title"] = "trocado"
    _recusado(dados, "impressão")


def test_lembrete_torto_e_recusado_sem_ecoar():
    dados = _bom()
    dados["lembretes"][0]["id"] = "não é uuid"
    _recusado(dados, "lembrete 1")


def test_lembrete_repetido_e_recusado():
    dados = _bom()
    dados["lembretes"][1] = copy.deepcopy(dados["lembretes"][0])
    dados["impressoes"] = {dados["lembretes"][0]["id"]: next(iter(dados["impressoes"].values()))}
    dados["contagens"]["lembretes"] = 2
    _recusado(dados, "duas vezes")


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"extra": 1}, "exatamente os campos"),
        ({"id": "1"}, "inteiro positivo"),
        ({"id": True}, "inteiro positivo"),
        ({"id": 0}, "inteiro positivo"),
        ({"estado": None}, "estado tem de ser texto"),
        ({"desfazer": 3}, "desfazer tem de ser texto ou nulo"),
        ({"parametros": "[1]"}, "objeto JSON"),
        ({"parametros": "{"}, "objeto JSON"),
        ({"criada_em": None}, "criada_em"),
        ({"criada_em": "2026-10-06T17:00:00"}, "com fuso"),
        ({"criada_em": "2026-10-06T14:00:00.000000-03:00"}, "UTC com microssegundos"),
        ({"terminada_em": "ontem"}, "terminada_em"),
    ],
)
def test_acao_torta_e_recusada(mudar, trecho):
    dados = _bom()
    dados["acoes"][0].update(mudar)
    _recusado(dados, trecho)


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"extra": 1}, "exatamente os campos"),
        ({"mes": "2026-10-01"}, "AAAA-MM"),
        ({"total": "0.25"}, "número"),
        ({"total": True}, "número"),
        ({"total": float("nan")}, "número"),
        ({"total": -1}, "negativo"),
        ({"dias": {"2026-11-01": 0.1}}, "fora do mês"),
        ({"dias": {"2026-10-06": float("inf")}}, "número"),
        ({"dias": []}, "objeto"),
    ],
)
def test_gasto_torto_e_recusado(mudar, trecho):
    dados = _bom()
    dados["gastos"][0].update(mudar)
    _recusado(dados, trecho)


def test_montar_erra_no_dia_do_backup_e_nao_no_do_desastre():
    with pytest.raises(formato.BackupInvalido, match="ação 1"):
        formato.montar([], [_acao(estado=None)], [], agora=AGORA, commit="x")


def test_arquivo_que_nao_e_json_e_recusado():
    with pytest.raises(formato.BackupInvalido, match="não é JSON"):
        formato.de_bytes(b"\xff\xfe nada")


def test_nome_do_arquivo_em_utc_com_hora_e_minuto():
    seattle = AGORA.astimezone(timezone(timedelta(hours=-7)))
    assert formato.nome_do_arquivo(seattle) == "viking-backup-2026-10-07T0900Z.json"
    assert formato.nome_do_arquivo(AGORA + timedelta(minutes=1)) != formato.nome_do_arquivo(AGORA)


# --- os gastos do teto no Firestore (o emulador) -----------------------------------------------


def test_gastos_exportar_e_importar_num_banco_vazio(firestore_limpo):
    teto = custos.Teto(mes=10, dia=1, fuso=UTC)
    teto.somar(0.5, agora=datetime(2026, 9, 30, 12, tzinfo=UTC))
    teto.somar(0.25, agora=AGORA)
    copias = custos.exportar_gastos()
    assert [c["mes"] for c in copias] == ["2026-09", "2026-10"]
    assert [formato.gasto_conferido(c) for c in copias] == copias

    for snap in firestore_limpo._cliente().collection(custos.Teto.COLECAO).stream():
        snap.reference.delete()
    assert custos.exportar_gastos() == []
    assert [custos.importar_gasto(c) for c in copias] == ["criado", "criado"]
    assert custos.exportar_gastos() == copias


def test_gasto_existente_nunca_e_sobrescrito(firestore_limpo):
    teto = custos.Teto(mes=10, dia=1, fuso=UTC)
    teto.somar(0.25, agora=AGORA)
    (copia,) = custos.exportar_gastos()
    assert custos.importar_gasto(copia) == "igual"
    assert custos.importar_gasto({**copia, "total": 9.0}) == "diferente"
    assert custos.exportar_gastos() == [copia]


# --- a impressão do conteúdo: um arquivo novo só quando algo mudou (dono, 2026-10-07) ----------

_OUTRO = "9e8d7c6b-5a49-4382-9172-6a5b4c3d2e1f"
_DO_BACKUP = _acao(id=1_790_000_000_000_000_009, operacao=formato.OPERACAO_DO_BACKUP)


def _impressao(lembretes=None, acoes=None, gastos=None, *, agora=AGORA, commit="abc1234") -> str:
    dados = formato.montar(
        [_lembrete(), _lembrete(id=_OUTRO, title="outro")] if lembretes is None else lembretes,
        [_acao()] if acoes is None else acoes,
        [_gasto()] if gastos is None else gastos,
        agora=agora,
        commit=commit,
    )
    return formato.impressao_do_conteudo(formato.ler(dados))


def test_a_impressao_ignora_o_instante_o_commit_a_ordem_e_a_acao_do_proprio_backup():
    base = _impressao()
    assert _impressao(agora=AGORA + timedelta(days=1), commit="def5678") == base
    assert _impressao(lembretes=[_lembrete(id=_OUTRO, title="outro"), _lembrete()]) == base
    assert _impressao(acoes=[_acao(), _DO_BACKUP]) == base


@pytest.mark.parametrize(
    "mudanca",
    [
        {"lembretes": [_lembrete(title="mudou")]},
        {
            "lembretes": [
                _lembrete(),
                _lembrete(id=_OUTRO, title="outro"),
                _lembrete(id="0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d", title="novo"),
            ]
        },
        {"lembretes": [_lembrete(completed_at=AGORA), _lembrete(id=_OUTRO, title="outro")]},
        {"acoes": [_acao(), _acao(id=1_790_000_000_000_000_002, operacao="calendario.criar")]},
        {"acoes": [_acao(estado="desfeita")]},
        {"acoes": []},
        {"gastos": [_gasto(total=0.5, dias={"2026-10-06": 0.5})]},
    ],
    ids=[
        "titulo",
        "lembrete-novo",
        "concluido",
        "acao-nova",
        "acao-mudou",
        "acao-expirou",
        "gasto",
    ],
)
def test_qualquer_mudanca_do_conteudo_muda_a_impressao(mudanca):
    assert _impressao(**mudanca) != _impressao()


def test_a_impressao_de_um_arquivo_lido_de_volta_e_a_do_que_se_montou():
    """A rodada compara o que monta agora com o arquivo baixado do Drive: os dois caminhos."""
    dados = formato.montar(
        [_lembrete()],
        [_acao()],
        [{"mes": "2026-10", "total": 1, "dias": {"2026-10-06": 1}}],
        agora=AGORA,
        commit="abc1234",
    )
    lido = formato.de_bytes(formato.para_bytes(dados))
    assert formato.impressao_do_conteudo(lido) == formato.impressao_do_conteudo(formato.ler(dados))
