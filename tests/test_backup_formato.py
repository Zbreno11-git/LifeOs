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
from lifeos.memoria import store as memoria_store
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


def _fato(**mudar) -> dict:
    copia = {
        "id": "0c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f",
        "texto": "O usuário corre aos sábados.",
        "origem": "chat",
        "sessao": "ab12cd34",
        "turno": "ab12cd34:3",
        "criado_em": "2026-10-06T17:00:00.000000+00:00",
        "ativo": True,
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    copia.update(mudar)
    return copia


def _receita(**mudar) -> dict:
    copia = {
        "id": "7a8b9c0d-1e2f-4a3b-8c4d-5e6f7a8b9c0d",
        "nome": "fechamento da semana",
        "passos": ["veja a agenda da semana que vem", "mande tudo por e-mail"],
        "estado": "guardada",
        "ativo": True,
        "origem": "chat",
        "sessao": "ab12cd34",
        "turno": "ab12cd34:4",
        "criado_em": "2026-10-06T17:00:00.000000+00:00",
        "guardada_em": "2026-10-06T17:01:00.000000+00:00",
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    copia.update(mudar)
    return copia


def _documento(**mudar) -> dict:
    copia = {
        "id": "3d4e5f6a-7b8c-4d9e-8f0a-1b2c3d4e5f6a",
        "nome": "treino.md",
        "tema": "treino",
        "bytes": 120,
        "n_trechos": 1,
        "impressao": "a" * 64,
        "origem": "viking documentos",
        "estado": "aprendido",
        "ativo": True,
        "criado_em": "2026-10-06T17:00:00.000000+00:00",
        "aprendido_em": "2026-10-06T17:00:05.000000+00:00",
        "invalida_em": None,
        "substituido_por": None,
        "esquecido_em": None,
        "apagar_em": None,
    }
    copia.update(mudar)
    return copia


def _trecho(**mudar) -> dict:
    copia = {
        "id": "4e5f6a7b-8c9d-4e0f-8a1b-2c3d4e5f6a7b",
        "documento": "3d4e5f6a-7b8c-4d9e-8f0a-1b2c3d4e5f6a",
        "arquivo": "treino.md",
        "tema_lido": "treino",
        "ordem": 0,
        "linha_de": 3,
        "linha_ate": 4,
        "secao": "Perna",
        "texto": "Agachamento, quatro séries de oito.",
        "ativo": True,
        "apagar_em": None,
    }
    copia.update(mudar)
    return copia


def _bom(memoria=None, receitas=None, documentos=None, trechos=None) -> dict:
    return formato.montar(
        [_lembrete(), _lembrete(id="9e8d7c6b-5a49-4382-9172-6a5b4c3d2e1f", title="outro")],
        [_acao()],
        [_gasto()],
        agora=AGORA,
        commit="abc1234",
        memoria=memoria,
        receitas=receitas,
        documentos=documentos,
        trechos=trechos,
    )


def _versao_3(dados: dict) -> dict:
    """O mesmo arquivo como a 13b o escrevia (sem os documentos)."""
    v3 = copy.deepcopy(dados)
    assert v3.pop("documentos") == [] and v3.pop("trechos") == []
    del v3["contagens"]["documentos"], v3["contagens"]["trechos"]
    v3["versao"] = 3
    return v3


def _versao_2(dados: dict) -> dict:
    """O mesmo arquivo como a 13 o escrevia (sem as receitas)."""
    v2 = _versao_3(dados)
    assert v2.pop("receitas") == []
    del v2["contagens"]["receitas"]
    v2["versao"] = 2
    return v2


def _versao_1(dados: dict) -> dict:
    """O mesmo arquivo como a 11c o escrevia (sem a memória)."""
    v1 = _versao_2(dados)
    assert v1.pop("memoria") == []
    del v1["contagens"]["memoria"]
    v1["versao"] = 1
    return v1


def test_ida_e_volta_preserva_tudo():
    dados = _bom()
    backup = formato.de_bytes(formato.para_bytes(dados))
    assert backup.contagens() == {
        "lembretes": 2,
        "acoes": 1,
        "gastos": 1,
        "memoria": 0,
        "receitas": 0,
        "documentos": 0,
        "trechos": 0,
    }
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
    dados["versao"] = 5
    _recusado(dados, "versão do backup desconhecida")
    dados["versao"] = True  # bool é int no Python: não pode passar por 1
    _recusado(dados, "versão do backup desconhecida")


# --- a memória (Sessão 13, D66): a versão 2 ------------------------------------------------------


def test_o_arquivo_da_versao_1_continua_se_lendo():
    backup = formato.ler(_versao_1(_bom()))
    assert backup.memoria == [] and backup.contagens()["lembretes"] == 2


def test_a_versao_1_nao_aceita_o_campo_da_memoria_nem_a_2_sem_ele():
    v1 = _versao_1(_bom())
    v1["memoria"] = []
    _recusado(v1, "exatamente os campos")
    v2 = _versao_2(_bom())
    del v2["memoria"]
    _recusado(v2, "exatamente os campos")


def test_a_memoria_vai_e_volta_sem_vetor():
    esquecido = _fato(
        id="1d2e3f4a-5b6c-4d7e-8f90-1a2b3c4d5e6f",
        texto="O usuário toca violão.",
        ativo=False,
        esquecido_em="2026-10-07T10:00:00.000000+00:00",
        apagar_em="2026-11-06T10:00:00.000000+00:00",
    )
    backup = formato.de_bytes(formato.para_bytes(_bom([_fato(), esquecido])))
    assert backup.memoria == [_fato(), esquecido]
    assert backup.contagens()["memoria"] == 2
    assert all("vetor" not in f for f in backup.memoria)


def test_a_memoria_vazia_nao_muda_a_impressao_de_um_arquivo_da_versao_1():
    """O primeiro backup depois do deploy da 13, sem fato nenhum, não sobe um arquivo à toa."""
    v2 = formato.ler(_versao_2(_bom()))
    v1 = formato.ler(_versao_1(_bom()))
    assert formato.impressao_do_conteudo(v2) == formato.impressao_do_conteudo(v1)
    com_fato = formato.ler(_bom([_fato()]))
    assert formato.impressao_do_conteudo(com_fato) != formato.impressao_do_conteudo(v2)
    esquecido = formato.ler(_bom([_fato(ativo=False)]))
    assert formato.impressao_do_conteudo(esquecido) != formato.impressao_do_conteudo(com_fato)


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"id": "../gastos"}, "UUID"),
        ({"texto": "  "}, "texto"),
        ({"origem": "email"}, "origem"),
        ({"ativo": "sim"}, "ativo"),
        ({"substituido_por": "x"}, "substituido_por"),
        ({"criado_em": None}, "criado_em"),
        ({"invalida_em": "2026-10-07T10:00:00+00:00"}, "invalida_em"),
        ({"vetor": [0.1]}, "exatamente os campos"),
    ],
)
def test_um_fato_torto_recusa_o_arquivo(mudar, trecho):
    dados = _bom([_fato()])
    dados["memoria"][0].update(mudar)
    _recusado(dados, trecho)


def test_a_contagem_da_memoria_e_conferida_e_o_id_nao_repete():
    dados = _bom([_fato()])
    dados["contagens"]["memoria"] = 2
    _recusado(dados, "contagens")
    dados = _bom([_fato()])
    dados["memoria"].append(dict(dados["memoria"][0]))
    dados["contagens"]["memoria"] = 2
    _recusado(dados, "aparece duas vezes")


def test_o_formato_do_fato_e_o_do_store():
    assert set(_fato()) == set(memoria_store.CAMPOS_DA_COPIA)


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


# --- as receitas (Sessão 13b, D67): a versão 3 ---------------------------------------------------


def test_o_arquivo_da_versao_2_continua_se_lendo():
    backup = formato.ler(_versao_2(_bom([_fato()])))
    assert backup.receitas == [] and backup.memoria == [_fato()]


def test_a_versao_2_nao_aceita_o_campo_das_receitas_nem_a_3_sem_ele():
    v2 = _versao_2(_bom())
    v2["receitas"] = []
    _recusado(v2, "exatamente os campos")
    v3 = _bom()
    del v3["receitas"]
    _recusado(v3, "exatamente os campos")


def test_as_receitas_vao_e_voltam_com_todos_os_estados():
    proposta = _receita(
        id="2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
        estado="proposta",
        ativo=False,
        guardada_em=None,
        apagar_em="2026-10-07T17:00:00.000000+00:00",
    )
    backup = formato.de_bytes(formato.para_bytes(_bom(receitas=[_receita(), proposta])))
    assert backup.receitas == [_receita(), proposta]
    assert backup.contagens()["receitas"] == 2


def test_as_receitas_vazias_nao_mudam_a_impressao_de_um_arquivo_da_versao_2():
    """O primeiro backup depois do deploy da 13b, sem receita, não sobe um arquivo à toa."""
    v3 = formato.ler(_bom([_fato()]))
    v2 = formato.ler(_versao_2(_bom([_fato()])))
    assert formato.impressao_do_conteudo(v3) == formato.impressao_do_conteudo(v2)
    com_receita = formato.ler(_bom([_fato()], [_receita()]))
    assert formato.impressao_do_conteudo(com_receita) != formato.impressao_do_conteudo(v3)


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"id": "../gastos"}, "UUID"),
        ({"nome": " "}, "nome"),
        ({"passos": []}, "passos"),
        ({"passos": "veja a agenda"}, "passos"),
        ({"passos": ["ok", 3]}, "passos"),
        ({"estado": "ativa"}, "estado"),
        ({"origem": "email"}, "origem"),
        ({"ativo": "sim"}, "ativo"),
        ({"sessao": None}, "sessao"),
        ({"substituido_por": "x"}, "substituido_por"),
        ({"criado_em": None}, "criado_em"),
        ({"guardada_em": "2026-10-07T10:00:00+00:00"}, "guardada_em"),
        ({"vetor": [1.0]}, "exatamente os campos"),
    ],
)
def test_receita_torta_recusa_o_arquivo(mudar, trecho):
    dados = _bom(receitas=[_receita()])
    dados["receitas"][0].update(mudar)
    _recusado(dados, trecho)


def test_receita_repetida_recusa_o_arquivo():
    dados = _bom(receitas=[_receita()])
    dados["receitas"].append(dict(dados["receitas"][0]))
    dados["contagens"]["receitas"] = 2
    _recusado(dados, "aparece duas vezes")


def test_o_formato_da_receita_e_o_do_store():
    from lifeos.memoria import receitas

    assert set(_receita()) == set(receitas.CAMPOS_DA_COPIA)


def test_a_contagem_das_receitas_confere():
    dados = _bom(receitas=[_receita()])
    dados["contagens"]["receitas"] = 0
    _recusado(dados, "contagens")


# --- os documentos (Sessão 14, D68): a versão 4 --------------------------------------------------


def test_o_arquivo_da_versao_3_continua_se_lendo():
    backup = formato.ler(_versao_3(_bom([_fato()], [_receita()])))
    assert backup.documentos == [] and backup.trechos == [] and backup.receitas == [_receita()]


def test_a_versao_3_nao_aceita_os_documentos_nem_a_4_sem_eles():
    v3 = _versao_3(_bom())
    v3["documentos"] = []
    _recusado(v3, "exatamente os campos")
    v4 = _bom()
    del v4["trechos"]
    _recusado(v4, "exatamente os campos")


def test_os_documentos_e_os_trechos_vao_e_voltam():
    esquecido = _documento(
        id="5f6a7b8c-9d0e-4f1a-8b2c-3d4e5f6a7b8c",
        ativo=False,
        esquecido_em="2026-10-07T17:00:00.000000+00:00",
        apagar_em="2026-11-06T17:00:00.000000+00:00",
    )
    dados = _bom(documentos=[_documento(), esquecido], trechos=[_trecho()])
    backup = formato.de_bytes(formato.para_bytes(dados))
    assert backup.documentos == [_documento(), esquecido] and backup.trechos == [_trecho()]
    assert backup.contagens()["documentos"] == 2 and backup.contagens()["trechos"] == 1


def test_os_documentos_vazios_nao_mudam_a_impressao_de_um_arquivo_da_versao_3():
    """O primeiro backup depois do deploy da 14, sem documento, não sobe um arquivo à toa."""
    v4 = formato.ler(_bom([_fato()], [_receita()]))
    v3 = formato.ler(_versao_3(_bom([_fato()], [_receita()])))
    assert formato.impressao_do_conteudo(v4) == formato.impressao_do_conteudo(v3)
    com_documento = formato.ler(_bom(documentos=[_documento()], trechos=[_trecho()]))
    assert formato.impressao_do_conteudo(com_documento) != formato.impressao_do_conteudo(
        formato.ler(_bom())
    )


def test_um_trecho_sem_o_documento_no_arquivo_e_recusado():
    dados = _bom(documentos=[_documento()], trechos=[_trecho()])
    dados["documentos"] = []
    dados["contagens"]["documentos"] = 0
    _recusado(dados, "documento que não está no backup")


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"id": "../gastos"}, "UUID"),
        ({"nome": " "}, "nome"),
        ({"tema": ""}, "tema"),
        ({"bytes": -1}, "bytes"),
        ({"n_trechos": True}, "n_trechos"),
        ({"estado": "ativo"}, "estado"),
        ({"origem": "e-mail"}, "origem"),
        ({"ativo": "sim"}, "ativo"),
        ({"substituido_por": "x"}, "substituido_por"),
        ({"criado_em": None}, "criado_em"),
        ({"apagar_em": "amanhã"}, "apagar_em"),
    ],
)
def test_documento_torto_e_recusado(mudar, trecho):
    dados = _bom(documentos=[_documento()], trechos=[_trecho()])
    dados["documentos"] = [_documento(**mudar)]
    _recusado(dados, trecho)


@pytest.mark.parametrize(
    ("mudar", "trecho"),
    [
        ({"id": "x"}, "UUID"),
        ({"documento": "x"}, "UUID"),
        ({"texto": " "}, "texto"),
        ({"arquivo": 3}, "arquivo"),
        ({"secao": None}, "secao"),
        ({"ordem": -1}, "ordem"),
        ({"linha_de": "3"}, "linha_de"),
        ({"ativo": 1}, "ativo"),
        ({"apagar_em": "x"}, "apagar_em"),
        ({"vetor": [0.1]}, "exatamente os campos"),
    ],
)
def test_trecho_torto_e_recusado(mudar, trecho):
    dados = _bom(documentos=[_documento()], trechos=[_trecho()])
    dados["trechos"] = [_trecho(**mudar)]
    _recusado(dados, trecho)


def test_um_trecho_repetido_e_recusado():
    dados = _bom(documentos=[_documento()], trechos=[_trecho()])
    dados["trechos"] = [_trecho(), _trecho()]
    dados["contagens"]["trechos"] = 2
    _recusado(dados, "aparece duas vezes")
