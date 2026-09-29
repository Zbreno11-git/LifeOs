"""`viking lembretes --enviar` (Sessão 9): um e-mail por lembrete vencido nas últimas 24 h, para a
própria conta do dono, e **um só**, mesmo rodado duas vezes ou em dois processos juntos.

Decisões do dono (2026-09-29): um e-mail por lembrete, com o assunto = título; vencidos há mais
de 24 h não saem (o comando lista quantos e quais). O envio é o livre da D46 (só para a conta,
dentro do limite de 20 em 24 h, no registro de ações). Tudo contra o Gmail falso do `conftest`.
"""

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from lifeos import banco, registro
from lifeos.gmail import envio as gmail_envio
from lifeos.reminders import envio, interface, service, store

DONO_TZ = ZoneInfo("America/Los_Angeles")
AGORA = datetime.now(UTC).replace(microsecond=0)
HORA = timedelta(hours=1)


@pytest.fixture(autouse=True)
def _fuso_do_dono(monkeypatch):
    monkeypatch.setattr("lifeos.config.TIMEZONE", DONO_TZ)


def _vencido(titulo, ha=HORA, corpo=""):
    return store.add(title=titulo, body=corpo, due_at=AGORA - ha)


def _assuntos(gmail):
    return [e["mensagem"]["Subject"] for e in gmail["enviados"]]


def test_dois_vencidos_saem_um_email_cada_com_o_titulo_no_assunto(gmail):
    _vencido("Dentista", corpo="levar o raio-x")
    _vencido("Pagar luz", ha=2 * HORA)
    store.add(title="Futuro", due_at=AGORA + HORA)
    store.add(title="Sem prazo")

    resultado = envio.enviar_vencidos(AGORA)

    assert _assuntos(gmail) == ["Pagar luz", "Dentista"]  # pelo prazo
    assert [e["mensagem"]["To"] for e in gmail["enviados"]] == ["dono@example.com"] * 2
    assert resultado.enviados == ["Pagar luz", "Dentista"]
    assert not resultado.parcial
    corpo = gmail["enviados"][1]["mensagem"].get_body(("plain",)).get_content()
    assert "levar o raio-x" in corpo
    prazo_local = (AGORA - HORA).astimezone(DONO_TZ)
    assert f"{prazo_local:%d/%m/%Y %H:%M}" in corpo  # no fuso do dono, não em UTC


def test_rodar_de_novo_nao_manda_de_novo(gmail):
    _vencido("Dentista")
    assert envio.enviar_vencidos(AGORA).enviados == ["Dentista"]
    assert len(gmail["enviados"]) == 1  # a primeira mandou de verdade

    segunda = envio.enviar_vencidos(AGORA + timedelta(minutes=10))

    assert segunda.enviados == []
    assert len(gmail["enviados"]) == 1
    (lido,) = [r for r in store.list_open() if r.title == "Dentista"]
    assert lido.envio_estado == interface.ENVIADO


def test_vencido_ha_mais_de_24h_nao_sai_e_e_listado(gmail):
    _vencido("Velho", ha=25 * HORA)
    _vencido("Recente")

    resultado = envio.enviar_vencidos(AGORA)

    assert _assuntos(gmail) == ["Recente"]
    assert resultado.atrasados == ["Velho"]
    assert not resultado.parcial  # listar o atrasado é informação, não falha
    assert [r.title for r in store.list_open() if r.enviado_em is None] == ["Velho"]


def test_limite_de_24h_para_no_meio_e_solta_o_resto(gmail, monkeypatch):
    monkeypatch.setattr(gmail_envio, "LIMITE_LIVRE", 2)
    for n in range(4):
        _vencido(f"L{n}", ha=(4 - n) * HORA)

    resultado = envio.enviar_vencidos(AGORA)

    assert _assuntos(gmail) == ["L0", "L1"]
    assert resultado.parcial and resultado.limite
    assert resultado.ficaram == 2
    monkeypatch.setattr(gmail_envio, "LIMITE_LIVRE", 20)
    assert envio.enviar_vencidos(AGORA).enviados == ["L2", "L3"]  # soltos: a próxima pega


def test_falha_que_pode_ter_enviado_nao_reenvia(gmail):
    _vencido("Dentista")
    gmail["falhar_send"].append(500)

    resultado = envio.enviar_vencidos(AGORA)

    assert resultado.incertos == ["Dentista"] and resultado.parcial
    assert envio.enviar_vencidos(AGORA).enviados == []
    assert gmail["enviados"] == []  # o dublê não guardou, e ninguém tentou de novo
    (lido,) = store.list_open()
    assert lido.envio_estado == interface.INCERTO
    (acao,) = [a for a in registro.recentes() if a.operacao == "gmail.enviar"]
    assert acao.estado == registro.INCERTA


def test_recusa_definitiva_solta_e_tenta_na_proxima(gmail):
    _vencido("Dentista")
    gmail["falhar_send"].append(400)

    resultado = envio.enviar_vencidos(AGORA)

    assert [t for t, _motivo in resultado.recusados] == ["Dentista"] and resultado.parcial
    assert envio.enviar_vencidos(AGORA).enviados == ["Dentista"]


def test_titulo_com_caractere_de_controle_e_recusado_e_solto(gmail):
    _vencido("Denti" + chr(0x202E) + "sta")

    resultado = envio.enviar_vencidos(AGORA)

    assert gmail["enviados"] == []
    ((_titulo, motivo),) = resultado.recusados
    assert "U+202E" in motivo
    (lido,) = store.list_open()
    assert lido.enviado_em is None


def test_reserva_de_outra_execucao_no_prazo_e_pulada_e_a_vencida_e_pega(gmail):
    alvo = _vencido("Dentista")
    assert store.reservar_envio(alvo.id, por="outra", ate=AGORA + HORA, agora=AGORA)

    assert envio.enviar_vencidos(AGORA).pulados == 1
    assert gmail["enviados"] == []

    assert envio.enviar_vencidos(AGORA + 2 * HORA).enviados == ["Dentista"]


def test_sem_login_nao_deixa_reserva_presa(gmail, monkeypatch):
    _vencido("Dentista")
    sem_token = {"agora": True}
    conta_de_verdade = gmail_envio.conta

    def conta():
        if sem_token["agora"]:
            raise gmail_envio.service.SemLogin("sem token")
        return conta_de_verdade()

    monkeypatch.setattr(gmail_envio, "conta", conta)
    with pytest.raises(gmail_envio.service.SemLogin):
        envio.enviar_vencidos(AGORA)
    sem_token["agora"] = False

    assert envio.enviar_vencidos(AGORA).enviados == ["Dentista"]  # nada ficou reservado


def test_o_envio_entra_no_registro_como_livre(gmail):
    _vencido("Dentista")
    envio.enviar_vencidos(AGORA)
    (acao,) = [a for a in registro.recentes() if a.operacao == "gmail.enviar"]
    assert acao.parametros["livre"] is True and acao.estado == registro.FEITA


# --- dois processos de verdade ----------------------------------------------------------------

_ENVIA = """
import sys, time
from datetime import datetime
from lifeos.gmail import envio as gmail_envio
from lifeos.reminders import envio

def novo(para, assunto, corpo):
    with open(sys.argv[1], "a") as f:
        f.write(assunto + "\\n")
    time.sleep(0.05)  # alarga a janela entre reservar e marcar
    rascunho = gmail_envio.Rascunho(para=("dono@example.com",), assunto=assunto, corpo=corpo)
    return gmail_envio.Pedido(rascunho, enviado=gmail_envio.service.Enviado("x", "t"))

gmail_envio.novo = novo
resultado = envio.enviar_vencidos(datetime.fromisoformat(sys.argv[2]))
print(len(resultado.enviados))
"""


def test_quatro_processos_juntos_mandam_cada_lembrete_uma_vez(tmp_path):
    """O Scheduler da S10 entrega "at least once", e o dono pode rodar o comando com o outro em
    curso: a reserva no banco é o que faz um envio só. Processos de verdade: a reserva é um
    `UPDATE` no SQLite, e uma thread dividiria a conexão."""
    for n in range(3):
        _vencido(f"L{n}", ha=(n + 1) * HORA)
    saidas = tmp_path / "enviados.txt"
    ambiente = {**os.environ, "VIKING_DB_PATH": str(banco.CAMINHO), "VIKING_TIMEZONE": "UTC"}
    processos = [
        subprocess.Popen(
            [sys.executable, "-c", _ENVIA, str(saidas), AGORA.isoformat()],
            env=ambiente,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(4)
    ]
    resultados = [p.communicate(timeout=60) for p in processos]

    assert [p.returncode for p in processos] == [0] * 4, [e for _o, e in resultados]
    assert sorted(saidas.read_text().splitlines()) == ["L0", "L1", "L2"]
    assert sum(int(o) for o, _e in resultados) == 3


# --- a CLI ------------------------------------------------------------------------------------


def _rodar(monkeypatch, *args):
    from lifeos import cli

    monkeypatch.setattr(sys, "argv", ["viking", "lembretes", *args])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


def test_cli_envia_e_sai_com_zero_sem_mostrar_o_endereco(gmail, monkeypatch, capsys):
    _vencido("Dentista")
    _vencido("Velho", ha=30 * HORA)

    assert _rodar(monkeypatch, "--enviar") == 0

    saida = capsys.readouterr().out
    assert "Dentista" in saida and "Velho" in saida and "24 h" in saida
    assert "@" not in saida


def test_cli_parcial_sai_com_dois(gmail, monkeypatch, capsys):
    _vencido("Dentista")
    gmail["falhar_send"].append(500)
    assert _rodar(monkeypatch, "--enviar") == 2
    assert "Não sei se" in capsys.readouterr().out


def test_cli_sem_login_sai_com_um(gmail, monkeypatch, capsys):
    _vencido("Dentista")

    def sem_login():
        raise gmail_envio.service.SemLogin("sem token")

    monkeypatch.setattr(gmail_envio, "conta", sem_login)
    assert _rodar(monkeypatch, "--enviar") == 1
    assert "Gmail" in capsys.readouterr().err


def test_cli_lista_os_pendentes_no_fuso_do_dono(monkeypatch, capsys):
    service.criar_lembrete("Dentista", quando="2026-10-01T14:00")
    service.criar_lembrete("Sem prazo")
    assert _rodar(monkeypatch) == 0
    saida = capsys.readouterr().out
    assert "Dentista (01/10/2026 14:00)" in saida and "Sem prazo" in saida
