"""Os lembretes do Mac na nuvem (Sessão 11, D61): a marca da migração 7, o caminho do Mac pelo
motor, a cópia (`viking lembretes --migrar`) e o envio pela nuvem (`POST /tarefas/lembretes`).

O motor roda **neste processo** (`TestClient(motor.app)`), com a verificação de token de verdade
(os helpers de `tests/test_motor.py`) e o Firestore do emulador. O Mac fala com ele pelo
`nuvem/cliente.py` de verdade: só a sessão HTTP é trocada por uma que manda o pedido ao
`TestClient` com o token da conta. Como Mac e motor dividem o processo, a sessão troca os stores
para os da nuvem (`config.STORE`, `service.store`, `envio.store`, `registro._STORE`) **só durante
cada pedido**: fora dele, o Mac vê o `viking.db` do teste, como no Mac de verdade.

As perguntas: depois de migrado, o Mac grava na nuvem e o `viking.db` não muda? No meio da cópia,
nada se grava? A cópia só acontece com o envio da nuvem ligado, copia tudo, confere e não
sobrescreve? Uma queda no meio retoma? O envio pela nuvem só entra pela conta do agendador,
responde só contagens e não relê os atrasados?
"""

import json
import logging
import sqlite3
import sys
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from tests.sentinela import aparece

pytest.importorskip("starlette")  # o extra da nuvem; o Mac não o instala
from starlette.testclient import TestClient
from tests import banco_antigo
from tests import test_motor as motor_base

from lifeos import banco, config, registro, registro_firestore, registro_sqlite
from lifeos.gmail import envio as gmail_envio
from lifeos.nuvem import cliente, motor
from lifeos.reminders import agendador, envio, interface, onde, service, store, transporte

_nuvem = motor_base._nuvem  # autouse: o projeto, a URL e os certificados falsos do Google

LA = ZoneInfo("America/Los_Angeles")
AGORA = datetime.now(UTC)
HORA = timedelta(hours=1)
CONTAS = {
    "cli": motor_base.CLI,
    "maos": f"viking-maos@{motor_base.PROJETO}.iam.gserviceaccount.com",
    "agendador": f"viking-agendador@{motor_base.PROJETO}.iam.gserviceaccount.com",
}


@contextmanager
def _do_lado_da_nuvem():
    """O motor, com o token do Gmail montado (o arquivo nunca é lido: o Gmail dos testes é o
    falso) e tudo no Firestore. Devolve os do Mac ao sair."""
    from lifeos.reminders import store_firestore

    salvo = (config.STORE, config.GMAIL_TOKEN_ARQUIVO, service.store, envio.store, registro._STORE)
    config.STORE, config.GMAIL_TOKEN_ARQUIVO = "firestore", "/segredos/gmail/token.json"
    service.store = envio.store = store_firestore
    registro._STORE = registro_firestore
    try:
        yield store_firestore
    finally:
        (
            config.STORE,
            config.GMAIL_TOKEN_ARQUIVO,
            service.store,
            envio.store,
            registro._STORE,
        ) = salvo


class _SessaoNoMotor:
    """O `AuthorizedSession` do Mac, mandando ao motor deste processo com o token da conta."""

    def __init__(self, http, email, rotas):
        self.http, self.email, self.rotas = http, email, rotas

    def request(self, metodo, url, json=None, timeout=None):
        assert url.startswith(config.NUVEM_URL)
        rota = url.removeprefix(config.NUVEM_URL)
        self.rotas.append(rota)
        cabecalho = {"Authorization": f"Bearer {motor_base._token(email=self.email)}"}
        with _do_lado_da_nuvem():
            return self.http.request(metodo, rota, json=json, headers=cabecalho)


@pytest.fixture
def mac(firestore_limpo, monkeypatch):
    """O Mac, com o `viking.db` do teste, falando com o motor em processo. Devolve as rotas
    pedidas, em ordem."""
    monkeypatch.setattr(config, "TIMEZONE", LA)
    http = TestClient(motor.app)
    rotas: list[str] = []
    contas = {cliente.CLI: CONTAS["cli"], cliente.MAOS: CONTAS["maos"]}
    monkeypatch.setattr(
        cliente, "_sessao", lambda conta=cliente.CLI: _SessaoNoMotor(http, contas[conta], rotas)
    )
    return rotas


@pytest.fixture(autouse=True)
def _contexto_limpo():
    """O motor marca a origem das ações: devolve a de antes ao fim do teste."""
    origem = registro.ORIGEM.set(registro.ORIGEM.get())
    yield
    registro.ORIGEM.reset(origem)


def _ligar_envio(quando=None):
    """Como se o agendador da nuvem tivesse terminado uma rodada em `quando` (agora)."""
    with _do_lado_da_nuvem():
        agendador._ref().set({"ultima": quando or datetime.now(UTC)})


def _na_nuvem() -> dict:
    with _do_lado_da_nuvem() as nuvem:
        snaps = nuvem._cliente().collection(nuvem.COLECAO).stream()
        return {s.id: nuvem._lembrete(s) for s in snaps}


def _impressoes_do_mac() -> dict:
    return {r.id: transporte.impressao(r) for r in store.todos()}


def _acoes(registro_de_quem) -> list:
    return registro_de_quem.recentes(desde=AGORA - timedelta(days=1), limite=50)


def _tres_no_mac():
    """Um aberto, um concluído e um já enviado por e-mail: o que a migração tem de levar."""
    aberto = store.add(title="Dentista", due_at=AGORA + HORA, tags=["saude"])
    concluido = store.add(title="Pagar luz", type="note", metadata={"conta": "luz"})
    store.complete(concluido.id)
    enviado = store.add(title="Ligar pra mãe", body="domingo", due_at=AGORA - HORA)
    assert store.reservar_envio(enviado.id, por="x", ate=AGORA + HORA, agora=AGORA)
    assert store.marcar_envio(enviado.id, por="x", estado=interface.ENVIADO, agora=AGORA)
    return aberto, concluido, enviado


def _cli(monkeypatch, *args):
    from lifeos import cli

    monkeypatch.setattr(sys, "argv", ["viking", "lembretes", *args])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


# --- o Mac depois de migrado ---------------------------------------------------------------------


def test_depois_de_migrado_o_mac_grava_na_nuvem_e_o_viking_db_nao_muda(mac):
    store.add(title="Antigo do Mac")
    mac_antes = _impressoes_do_mac()
    acoes_do_mac = len(_acoes(registro_sqlite))
    onde.marcar(onde.MIGRADO)

    criado = service.criar_lembrete("Dentista", quando="2026-10-02T10:00", source="viking-cli")
    outro = service.criar_lembrete("Comprar pão")
    concluido = service.concluir(criado.id)

    nuvem = _na_nuvem()
    assert set(nuvem) == {criado.id, outro.id}
    # o fuso do Mac (a borda) decidiu o instante: 10h em Los Angeles
    assert nuvem[criado.id].due_at == datetime(2026, 10, 2, 17, 0, tzinfo=UTC)
    assert nuvem[criado.id].source == "viking-cli"
    assert concluido.completed_at is not None and nuvem[criado.id].completed_at is not None
    assert [r.title for r in service.pendentes()] == ["Comprar pão"]  # a lista é a da nuvem
    assert _impressoes_do_mac() == mac_antes  # o `viking.db` virou cópia congelada
    # o registro é o da nuvem, onde a ação aconteceu (D57); o Mac não registra de novo
    assert len(_acoes(registro_sqlite)) == acoes_do_mac
    da_nuvem = [(a.operacao, a.origem, a.estado) for a in _acoes(registro_firestore)]
    assert sorted(da_nuvem) == [
        ("lembrete.concluir", "mac", "feita"),
        ("lembrete.criar", "mac", "feita"),
        ("lembrete.criar", "mac", "feita"),
    ]


def test_no_meio_da_copia_nada_se_grava_e_a_lista_e_a_do_mac(mac):
    from lifeos.assistant import agent

    aberto = store.add(title="Dentista")
    mac_antes = _impressoes_do_mac()
    onde.marcar(onde.MIGRANDO)

    with pytest.raises(onde.MigracaoEmCurso):
        service.criar_lembrete("Novo")
    with pytest.raises(onde.MigracaoEmCurso):
        service.concluir(aberto.id)
    assert [r.title for r in service.pendentes()] == ["Dentista"]
    texto = agent.criar_lembrete("Novo")
    assert texto.startswith("⚠️ Lembretes fora de alcance") and "nada se grava aqui" in texto
    assert _impressoes_do_mac() == mac_antes and _na_nuvem() == {}
    assert mac == []  # nem perguntou à nuvem


def test_nuvem_fora_vira_uma_mensagem_no_chat_no_mcp_e_na_cli(mac, monkeypatch, capsys):
    import requests
    from tests.test_mcp_server import _chamar as chamar_mcp

    from lifeos.assistant import agent

    class _Fora:
        def request(self, *_a, **_k):
            raise requests.ConnectionError("rede")

    monkeypatch.setattr(cliente, "_sessao", lambda conta=cliente.CLI: _Fora())
    onde.marcar(onde.MIGRADO)

    assert agent.listar_lembretes().startswith("⚠️ Lembretes fora de alcance agora: a nuvem")
    assert "a nuvem não respondeu" in agent.concluir_lembrete("x")
    resultado = chamar_mcp("viking_criar_lembrete", {"titulo": "Dentista"})
    assert resultado.is_error and resultado.structured_content == {"erro": "indisponivel"}
    capsys.readouterr()
    assert _cli(monkeypatch) == 1
    saida = capsys.readouterr()
    assert "a nuvem não respondeu" in saida.err and "Traceback" not in saida.err


def test_o_mcp_depois_de_migrado_grava_na_nuvem_sem_escrever_no_stdout(mac, capsys):
    """O stdout do servidor MCP é o protocolo: o caminho novo (o cliente da nuvem) não imprime."""
    from tests.test_mcp_server import _chamar as chamar_mcp

    onde.marcar(onde.MIGRADO)
    capsys.readouterr()
    resultado = chamar_mcp("viking_criar_lembrete", {"titulo": "Dentista"})
    assert not resultado.is_error
    assert capsys.readouterr().out == ""
    ((lembrete),) = _na_nuvem().values()
    assert (lembrete.title, lembrete.source) == ("Dentista", "mcp")


def test_enviar_no_mac_depois_de_migrado_recusa_e_nada_sai(mac, gmail, monkeypatch, capsys):
    store.add(title="Dentista", due_at=AGORA - HORA)
    for estado in (onde.MIGRANDO, onde.MIGRADO):
        onde.marcar(estado)
        assert _cli(monkeypatch, "--enviar") == 1
        assert "quem os envia por e-mail é a nuvem" in capsys.readouterr().err
    assert gmail["enviados"] == []


# --- a cópia: `viking lembretes --migrar` -------------------------------------------------------


def test_o_ensaio_conta_e_nao_copia_nada(mac, monkeypatch, capsys):
    _tres_no_mac()
    _ligar_envio()
    assert _cli(monkeypatch, "--migrar") == 0
    saida = capsys.readouterr().out
    assert "3 lembrete(s) (2 aberto(s), 1 concluído(s), 1 já enviado(s)" in saida
    assert "Ensaio: nada foi copiado" in saida and "ligado." in saida
    assert "Dentista" not in saida  # só contagens: a saída é colada em conversa
    assert _na_nuvem() == {} and onde.estado() is None
    assert "/lembretes/importar" not in mac


def test_executar_sem_o_envio_da_nuvem_ligado_recusa_e_nao_marca(mac, monkeypatch, capsys):
    _tres_no_mac()
    _ligar_envio(datetime.now(UTC) - agendador.LIGADO_POR - timedelta(seconds=5))  # velho
    assert _cli(monkeypatch, "--migrar", "--executar") == 1
    assert "o envio por e-mail da nuvem ainda não está ligado" in capsys.readouterr().err
    assert _na_nuvem() == {} and onde.estado() is None
    with sqlite3.connect(banco.CAMINHO) as conn:
        assert conn.execute("SELECT count(*) FROM lembretes_na_nuvem").fetchone() == (0,)


def test_com_o_envio_ligado_copia_tudo_confere_e_marca_migrado(mac, monkeypatch, capsys):
    aberto, concluido, enviado = _tres_no_mac()
    _ligar_envio()
    assert _cli(monkeypatch, "--migrar", "--executar") == 0
    saida = capsys.readouterr().out
    assert "✅ Migrado: 3 copiado(s), todos conferidos" in saida and "Dentista" not in saida
    nuvem = _na_nuvem()
    assert {i: transporte.impressao(r) for i, r in nuvem.items()} == _impressoes_do_mac()
    assert nuvem[concluido.id].completed_at is not None and nuvem[concluido.id].type == "note"
    assert nuvem[enviado.id].envio_estado == interface.ENVIADO  # não sai de novo pela nuvem
    assert onde.estado() == onde.MIGRADO
    assert {r.id for r in service.pendentes()} == {aberto.id, enviado.id}  # agora, da nuvem
    copia = [a for a in _acoes(registro_firestore) if a.operacao == "lembrete.importar"]
    assert [(a.estado, a.resultado) for a in copia] == [
        ("feita", {"criados": 3, "iguais": 0, "diferentes": 0})
    ]


def test_rodar_de_novo_depois_de_migrado_nao_copia_nada(mac, monkeypatch, capsys):
    _tres_no_mac()
    _ligar_envio()
    assert _cli(monkeypatch, "--migrar", "--executar") == 0
    mac.clear()
    capsys.readouterr()
    assert _cli(monkeypatch, "--migrar", "--executar") == 0
    assert "Este Mac já migrou" in capsys.readouterr().out
    assert "/lembretes/importar" not in mac


def test_uma_queda_no_meio_deixa_migrando_e_rodar_de_novo_termina(mac, monkeypatch, capsys):
    monkeypatch.setattr(transporte, "MAX_LOTE", 2)
    for n in range(5):
        store.add(title=f"Lembrete {n}")
    _ligar_envio()
    importar = cliente.importar_lembretes
    lotes = []

    def cai_no_segundo(sessao, lote):
        lotes.append(len(lote))
        if len(lotes) == 2:
            raise cliente.ErroDaNuvem("a nuvem não respondeu (rede, ou o motor fora do ar)")
        return importar(sessao, lote)

    monkeypatch.setattr(cliente, "importar_lembretes", cai_no_segundo)
    assert _cli(monkeypatch, "--migrar", "--executar") == 1
    erro = capsys.readouterr().err
    assert "A cópia ficou pela metade: rode de novo" in erro
    assert onde.estado() == onde.MIGRANDO and len(_na_nuvem()) == 2
    with pytest.raises(onde.MigracaoEmCurso):
        service.criar_lembrete("no meio")

    monkeypatch.setattr(cliente, "importar_lembretes", importar)
    assert _cli(monkeypatch, "--migrar", "--executar") == 0
    saida = capsys.readouterr().out
    assert "Na nuvem já iguais: 2." in saida and "✅ Migrado: 3 copiado(s)" in saida
    nuvem = _na_nuvem()
    assert {i: transporte.impressao(r) for i, r in nuvem.items()} == _impressoes_do_mac()
    assert len(nuvem) == 5 and onde.estado() == onde.MIGRADO


def test_um_id_com_outro_conteudo_na_nuvem_nao_e_sobrescrito_e_nao_marca(mac, monkeypatch, capsys):
    aberto, _concluido, _enviado = _tres_no_mac()
    with _do_lado_da_nuvem() as nuvem:
        outro = transporte.de_dict({**transporte.para_dict(aberto), "title": "Outro título"})
        assert nuvem.importar(outro) == nuvem.CRIADO
    _ligar_envio()
    assert _cli(monkeypatch, "--migrar", "--executar") == 1
    assert "1 lembrete(s) já estão na nuvem com outro conteúdo" in capsys.readouterr().err
    assert {i: r.title for i, r in _na_nuvem().items()} == {aberto.id: "Outro título"}
    assert onde.estado() is None


def test_importar_de_novo_e_igual_e_diferente_nunca_sobrescreve(mac):
    aberto, _concluido, _enviado = _tres_no_mac()
    lote = [transporte.para_dict(aberto)]
    sessao = cliente.sessao_de_chat()
    assert cliente.importar_lembretes(sessao, lote)["criados"] == [aberto.id]
    assert cliente.importar_lembretes(sessao, lote)["iguais"] == [aberto.id]
    mudado = [{**lote[0], "title": "Mudou"}]
    assert cliente.importar_lembretes(sessao, mudado)["diferentes"] == [aberto.id]
    assert _na_nuvem()[aberto.id].title == "Dentista"


def test_a_nuvem_que_diz_que_gravou_e_nao_gravou_e_pega_pela_conferencia(mac, monkeypatch, capsys):
    """A conferência relê: um `importar` que respondeu "criado" sem gravar não vira "migrado"."""
    from lifeos.reminders import store_firestore

    _tres_no_mac()
    _ligar_envio()
    monkeypatch.setattr(store_firestore, "importar", lambda _l: store_firestore.CRIADO)
    assert _cli(monkeypatch, "--migrar", "--executar") == 1
    assert "a conferência achou 3 lembrete(s)" in capsys.readouterr().err
    assert onde.estado() == onde.MIGRANDO


def test_um_item_torto_no_lote_e_nada_e_gravado(mac):
    aberto, concluido, _enviado = _tres_no_mac()
    torto = {**transporte.para_dict(concluido), "id": "nao-e-uuid"}
    with pytest.raises(cliente.ErroDaNuvem, match="HTTP 400: o id do lembrete tem de ser um UUID"):
        cliente.importar_lembretes(cliente.sessao_de_chat(), [transporte.para_dict(aberto), torto])
    assert _na_nuvem() == {}


@pytest.mark.parametrize(
    ("rota", "corpo", "trecho"),
    [
        ("/lembretes/criar", {"titulo": "x", "quando": "2026-10-02T10:00"}, "instante com fuso"),
        ("/lembretes/criar", {"titulo": "  "}, "precisa de um título"),
        ("/lembretes/criar", {"titulo": 3}, "titulo tem de ser texto"),
        ("/lembretes/concluir", {}, "o id do lembrete"),
        ("/lembretes/importar", {"lembretes": []}, "de 1 a 100"),
        ("/lembretes/importar", {"lembretes": "x"}, "de 1 a 100"),
    ],
)
def test_pedido_torto_do_mac_e_400_e_nada_muda(mac, rota, corpo, trecho):
    with pytest.raises(cliente.ErroDaNuvem, match=f"HTTP 400: .*{trecho}"):
        cliente._chamar(cliente.sessao_de_chat(), "POST", rota, corpo=corpo)
    assert _na_nuvem() == {}


@pytest.mark.parametrize("conta", ["maos", "agendador"])
@pytest.mark.parametrize(
    ("metodo", "rota"),
    [
        ("POST", "/lembretes/criar"),
        ("POST", "/lembretes/concluir"),
        ("POST", "/lembretes/importar"),
        ("GET", "/lembretes/impressoes"),
    ],
)
def test_so_o_terminal_do_dono_fala_com_os_lembretes(firestore_limpo, conta, metodo, rota):
    token = motor_base._token(email=CONTAS[conta])
    corpo = {"titulo": "x"} if metodo == "POST" else None
    with _do_lado_da_nuvem():
        resposta = TestClient(motor.app).request(
            metodo, rota, json=corpo, headers={"Authorization": f"Bearer {token}"}
        )
    assert resposta.status_code == 403
    assert _na_nuvem() == {}


# --- o envio pela nuvem: `POST /tarefas/lembretes` ----------------------------------------------


def _rodada(conta="agendador"):
    token = motor_base._token(email=CONTAS[conta])
    with _do_lado_da_nuvem():
        return TestClient(motor.app).post(
            "/tarefas/lembretes", headers={"Authorization": f"Bearer {token}"}
        )


def _ligado() -> bool:
    with _do_lado_da_nuvem():
        return agendador.ligado()


@pytest.mark.parametrize("conta", ["cli", "maos"])
def test_so_o_agendador_dispara_a_rodada(firestore_limpo, gmail, conta):
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title="Dentista", due_at=AGORA - HORA)
    assert _rodada(conta).status_code == 403
    assert gmail["enviados"] == [] and not _ligado()


def test_a_rodada_envia_responde_so_contagens_e_liga_o_envio(firestore_limpo, gmail):
    titulo = "Consulta secreta 4417"
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title=titulo, due_at=AGORA - HORA)
    assert not _ligado()
    resposta = _rodada()
    assert resposta.status_code == 200
    assert resposta.json() == {
        "enviados": 1,
        "incertos": 0,
        "recusados": 0,
        "pulados": 0,
        "ficaram": 0,
        "parou": False,
        "limite": False,
        "resumo": "memória desligada",  # o resumo da semana (Sessão 13): os testes a desligam
    }
    assert not aparece("4417", resposta.text)
    assert [e["mensagem"]["Subject"] for e in gmail["enviados"]] == [titulo]
    assert _ligado()
    assert _rodada().json()["enviados"] == 0  # a segunda rodada não manda de novo


def test_a_rodada_nao_rele_os_atrasados(firestore_limpo, gmail, monkeypatch):
    from lifeos.reminders import store_firestore

    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title="Velho", due_at=AGORA - 30 * HORA)
    lidos = []
    atrasados = store_firestore.atrasados
    monkeypatch.setattr(
        store_firestore, "atrasados", lambda antes_de: lidos.append(1) or atrasados(antes_de)
    )
    assert _rodada().status_code == 200
    assert lidos == []
    with _do_lado_da_nuvem():  # o controle: o dublê conta quando a CLI lista
        assert envio.enviar_vencidos(AGORA).atrasados == ["Velho"]
    assert lidos == [1]


def test_rodada_que_parou_nao_liga_o_envio(firestore_limpo, gmail, monkeypatch):
    def sem_login():
        raise gmail_envio.service.SemLogin("sem o token do Gmail na nuvem")

    monkeypatch.setattr(gmail_envio, "conta", sem_login)
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title="Dentista", due_at=AGORA - HORA)
    resposta = _rodada()
    assert resposta.status_code == 200 and resposta.json()["parou"] is True
    assert not _ligado()


def test_rodada_que_falha_responde_so_o_tipo_e_o_log_nao_tem_titulo(
    firestore_limpo, monkeypatch, caplog
):
    def explode():
        raise RuntimeError("Consulta secreta")

    monkeypatch.setattr(agendador, "rodar", explode)
    caplog.set_level(logging.DEBUG)
    resposta = _rodada()
    assert resposta.status_code == 500
    assert resposta.json() == {"erro": "a rodada falhou (RuntimeError)"}
    assert "secreta" not in caplog.text


def test_versao_diz_se_o_envio_esta_ligado(mac):
    def envio_ligado():
        return cliente.capacidades(cliente.sessao_de_chat())["envio_de_lembretes"]

    assert envio_ligado() is False
    _ligar_envio()
    assert envio_ligado() is True
    _ligar_envio(datetime.now(UTC) - agendador.LIGADO_POR - timedelta(seconds=5))
    assert envio_ligado() is False


def test_fora_da_nuvem_o_envio_nunca_esta_ligado(firestore_limpo):
    _ligar_envio()
    assert agendador.ligado() is False  # o Mac (`VIKING_STORE=sqlite`) não pergunta ao Firestore


def test_sem_o_gmail_no_motor_o_envio_nunca_esta_ligado(firestore_limpo):
    """Uma rodada sem nada vencido termina sem parar mesmo sem o token do Gmail: sem esta regra, a
    migração do Mac seguiria com um envio que pararia no primeiro vencido."""
    _ligar_envio()
    assert _ligado()
    with _do_lado_da_nuvem():
        config.GMAIL_TOKEN_ARQUIVO = ""  # o contexto devolve o do Mac ao sair
        assert agendador.ligado() is False
    assert config.GMAIL_TOKEN_ARQUIVO == ""  # o Mac não tem o token na nuvem


def test_o_aviso_do_lembrete_na_nuvem_segue_o_envio(firestore_limpo, monkeypatch):
    from lifeos.assistant import na_nuvem

    monkeypatch.setattr(config, "TIMEZONE", LA)
    with _do_lado_da_nuvem():
        sem_envio = na_nuvem.criar_lembrete("Dentista")
    _ligar_envio()
    with _do_lado_da_nuvem():
        com_envio = na_nuvem.criar_lembrete("Pagar luz")
    assert sem_envio.startswith("✅") and sem_envio.endswith(na_nuvem.AVISO_SEM_EMAIL)
    assert com_envio.startswith("✅") and na_nuvem.AVISO_SEM_EMAIL not in com_envio


# --- a migração 7 num banco com dados ------------------------------------------------------------


def test_a_migracao_7_num_banco_da_6_com_dados_nao_muda_os_lembretes(monkeypatch):
    """O banco do dono hoje é o da 6, com lembretes: a 7 só cria a tabela da marca, vazia."""
    banco_antigo.criar(banco.CAMINHO)
    todas = banco.MIGRACOES
    monkeypatch.setattr(banco, "MIGRACOES", todas[:6])
    with banco.conectar():
        pass
    store.add(title="Depois da 6", due_at=AGORA + HORA)
    antes = banco_antigo.linhas(banco.CAMINHO, "reminders")
    assert len(antes) == 5  # os 4 do banco antigo e o novo
    monkeypatch.setattr(banco, "MIGRACOES", todas)

    assert onde.estado() is None  # a primeira abertura aplica a 7

    assert banco_antigo.linhas(banco.CAMINHO, "reminders") == antes
    with sqlite3.connect(banco.CAMINHO) as conn:
        assert conn.execute("SELECT max(numero) FROM migracoes").fetchone() == (7,)
    onde.marcar(onde.MIGRANDO)
    onde.marcar(onde.MIGRADO)  # uma linha só, trocada
    with sqlite3.connect(banco.CAMINHO) as conn:
        assert conn.execute("SELECT id, estado FROM lembretes_na_nuvem").fetchall() == [
            (1, "migrado")
        ]
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO lembretes_na_nuvem (id, estado, em) VALUES (2, 'migrado', 'x')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE lembretes_na_nuvem SET estado = 'talvez'")


def test_marca_desconhecida_e_recusada():
    with pytest.raises(ValueError, match="estado desconhecido"):
        onde.marcar("talvez")


def test_o_que_a_nuvem_responde_nao_tem_titulo_nas_impressoes(mac):
    """A conferência só leva impressões: nenhum título sai pela rota."""
    store.add(title="Consulta secreta")
    resposta = cliente._chamar(cliente.sessao_de_chat(), "GET", "/lembretes/impressoes")
    assert resposta == {"impressoes": {}, "instantes": {}}
    with _do_lado_da_nuvem() as nuvem:
        nuvem.add(title="Consulta secreta")
    resposta = cliente._chamar(cliente.sessao_de_chat(), "GET", "/lembretes/impressoes")
    assert len(resposta["impressoes"]) == 1 and "secreta" not in json.dumps(resposta)
    (instantes,) = resposta["instantes"].values()  # desde a 11c: quando nasceu e quando mudou
    assert set(instantes) == {"criado", "mudou"}
