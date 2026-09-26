"""`viking gmail`: o caminho de validação no Mac sem gastar Gemini. Sempre contra o Gmail falso."""

import sys

import pytest

from lifeos import cli
from lifeos.gmail import service


def _rodar(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["viking", "gmail", *args])
    with pytest.raises(SystemExit) as saida:
        cli.main()
    return saida.value.code


def test_login_confere_a_conta(gmail, monkeypatch, capsys):
    assert _rodar(monkeypatch, "--login") == 0
    assert "dono@example.com" in capsys.readouterr().out


def test_login_sem_token_sai_com_erro(monkeypatch, capsys):
    def sem_token():
        raise FileNotFoundError("Credenciais OAuth não encontradas")

    monkeypatch.setattr(service, "get_gmail_service", sem_token)
    assert _rodar(monkeypatch, "--login") == 2
    assert "Não consegui entrar no Gmail" in capsys.readouterr().err


def test_padrao_sao_os_nao_lidos_de_hoje(gmail, monkeypatch, capsys):
    _rodar(monkeypatch)
    assert gmail["consultas"][0].startswith("is:unread in:inbox after:")


def test_raio_x_sem_numero_usa_30_dias(gmail, monkeypatch, capsys):
    _rodar(monkeypatch, "--raio-x")
    assert gmail["consultas"] == ["in:inbox newer_than:30d"]


def test_buscar_e_ler_imprimem_o_texto_do_chat(gmail, monkeypatch, capsys):
    gmail["nova"]("a1", assunto="Boleto", partes=[gmail["parte"]("text/plain", "Olá")])
    _rodar(monkeypatch, "--buscar", "boleto", "--max", "5")
    assert "Boleto" in capsys.readouterr().out
    _rodar(monkeypatch, "--ler", "a1")
    assert "Olá" in capsys.readouterr().out
