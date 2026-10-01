"""O Gmail no chat da nuvem e a aprovação pela rede (Sessão 10c, D60).

O turno roda inteiro: o cliente do google-genai com a rede trocada por um roteiro
(`tests/test_na_nuvem.py`), o Gmail falso do `conftest`, e as confirmações, o registro e o teto no
Firestore (o emulador). `config.STORE` fica em `firestore`, como no motor: um `print` esquecido no
caminho vira erro (`ao_dono.SemCanal`), não um código no log.

As perguntas: o código aparece em algum lugar além do campo `ao_dono` (o texto do modelo, o
histórico, a nota, o stdout, o log)? A linha que aprova chega ao modelo? Sem terminal do lado do
dono, nasce uma proposta? Três erradas cancelam pela rede?
"""

import itertools
import json
import logging

import pytest
from tests import test_na_nuvem as base
from tests.sentinela import aparece

from lifeos import ao_dono, config, confirmacao, confirmacao_firestore, registro, registro_firestore
from lifeos.assistant import na_nuvem

# As fixtures e o roteiro do turno da nuvem são os de `tests/test_na_nuvem.py`.
_contexto_limpo = base._contexto_limpo
teto = base.teto
gemini = base.gemini
_chama, _texto = base._chama, base._texto

LOJA = "ofertas@loja.example"
ANA = "ana@example.org"
SENTINELA = 6284  # o primeiro código sorteado: dá para procurar sem ambiguidade
CODIGO = f"{SENTINELA:04d}"


@pytest.fixture
def nuvem(teto, gmail, monkeypatch):
    """O motor: tudo no Firestore (o emulador), o Gmail falso, o primeiro código é o sentinela."""
    monkeypatch.setattr(config, "STORE", "firestore")
    # O motor com o token do Gmail montado (o arquivo nunca é lido: o Gmail é o falso).
    monkeypatch.setattr(config, "GMAIL_TOKEN_ARQUIVO", "/segredos/gmail/token.json")
    monkeypatch.setattr(confirmacao, "_STORE", confirmacao_firestore)
    monkeypatch.setattr(registro, "_STORE", registro_firestore)
    sorteios = itertools.chain([SENTINELA], itertools.count(1000))
    monkeypatch.setattr(confirmacao.secrets, "randbelow", lambda _n: next(sorteios))
    gmail["nova"]("l1", de=f"Loja <{LOJA}>", assunto="Oferta 1")
    gmail["nova"]("l2", de=f"Loja <{LOJA}>", assunto="Oferta 2")
    return gmail


def _pedido(mensagem, *, historico=(), numero=1, interativo=True):
    return {
        "mensagem": mensagem,
        "historico": list(historico),
        "nota": "",
        "sessao": "ab12cd34",
        "numero": numero,
        "interativo": interativo,
    }


def _sem_ao_dono(saida: dict) -> str:
    return json.dumps({k: v for k, v in saida.items() if k != "ao_dono"}, ensure_ascii=False)


def _propor_limpeza(gemini):
    roteiro = gemini(_chama("preparar_limpeza", remetentes=LOJA), _texto("Confira e aprove."))
    return roteiro, na_nuvem.turno(_pedido("arquiva os e-mails da loja"))


# --- o código só no campo `ao_dono` -----------------------------------------------------------


def test_o_codigo_da_limpeza_so_volta_no_campo_ao_dono(nuvem, gemini, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    roteiro, saida = _propor_limpeza(gemini)
    assert saida["resposta"] == "Confira e aprove." and saida["erro"] == ""
    (so_dele,) = saida["ao_dono"]
    assert f"confirma {CODIGO}" in so_dele and LOJA in so_dele
    assert not aparece(CODIGO, _sem_ao_dono(saida))  # nem o histórico, nem a nota, nem o texto
    assert not any(aparece(CODIGO, enviado) for enviado in roteiro.enviados)
    assert capsys.readouterr() == ("", "")  # no motor, o stdout e o stderr são o log
    assert not aparece(CODIGO, caplog.text)
    assert [p.codigo for p in confirmacao.abertas("gmail.arquivar")] == [CODIGO]


def test_aprovar_pela_nuvem_arquiva_sem_passar_pelo_modelo(nuvem, gemini):
    _, primeira = _propor_limpeza(gemini)
    roteiro = gemini()
    saida = na_nuvem.turno(_pedido(f"confirma {CODIGO}", historico=primeira["historico"], numero=2))
    assert roteiro.enviados == []
    assert saida["historico"] == primeira["historico"]  # a linha não entrou
    assert saida["resposta"] is None and "Arquivei 2" in saida["ao_dono"][0]
    assert not aparece(CODIGO, _sem_ao_dono(saida))
    assert [m["removeLabelIds"] for m in nuvem["modificacoes"]] == [["INBOX"]]
    (acao,) = [a for a in registro.recentes(dias=1) if a.operacao == "gmail.arquivar"]
    assert acao.origem == "nuvem"


def test_tres_erradas_pela_nuvem_cancelam_a_limpeza(nuvem, gemini):
    _propor_limpeza(gemini)
    gemini()
    textos = [na_nuvem.turno(_pedido("confirma 0001", numero=n))["ao_dono"][0] for n in (2, 3, 4)]
    assert "mais 2 tentativas" in textos[0] and "cancelei" in textos[2]
    certo = na_nuvem.turno(_pedido(f"confirma {CODIGO}", numero=5))["ao_dono"][0]
    assert certo.startswith("Não fiz nada")
    assert nuvem["modificacoes"] == []


def test_envio_a_outra_pessoa_pela_nuvem(nuvem, gemini):
    roteiro = gemini(
        _chama("enviar_email", para=ANA, assunto="Almoço", corpo="Amanhã às 12h?"),
        _texto("Confira o e-mail e aprove."),
    )
    saida = na_nuvem.turno(_pedido("manda para a Ana"))
    (so_dele,) = saida["ao_dono"]
    assert f"confirma {CODIGO}" in so_dele and "Amanhã às 12h?" in so_dele
    assert not aparece(CODIGO, _sem_ao_dono(saida))
    assert not any(aparece(CODIGO, enviado) for enviado in roteiro.enviados)
    assert nuvem["enviados"] == []

    gemini()
    aprovado = na_nuvem.turno(_pedido(f"confirma {CODIGO}", numero=2))
    assert "Enviei" in aprovado["ao_dono"][0]
    assert len(nuvem["enviados"]) == 1


# --- sem terminal do lado do dono, nenhuma proposta ---------------------------------------------


def test_sem_terminal_a_limpeza_nao_propoe_nem_le_o_gmail(nuvem, gemini):
    gemini(_chama("preparar_limpeza", remetentes=LOJA), _texto("Não deu."))
    saida = na_nuvem.turno(_pedido("arquiva os e-mails da loja", interativo=False))
    assert saida["ao_dono"] == [] and confirmacao.abertas("gmail.arquivar") == []
    assert nuvem["consultas"] == []  # recusou antes de gastar cota


def test_sem_terminal_o_envio_a_outra_pessoa_nao_propoe(nuvem, gemini):
    gemini(
        _chama("enviar_email", para=ANA, assunto="Oi", corpo="Olá"),
        _texto("Não deu."),
    )
    saida = na_nuvem.turno(_pedido("manda para a Ana", interativo=False))
    assert saida["ao_dono"] == [] and confirmacao.abertas("gmail.enviar") == []
    assert nuvem["enviados"] == []


def test_pedido_de_terminal_antigo_conta_como_sem_terminal(nuvem, gemini):
    """Um `viking chat --nuvem` de antes da 10c não manda `interativo`: ninguém lê o código."""
    gemini(_chama("preparar_limpeza", remetentes=LOJA), _texto("Não deu."))
    pedido = _pedido("arquiva os e-mails da loja")
    del pedido["interativo"]
    saida = na_nuvem.turno(pedido)
    assert saida["ao_dono"] == [] and confirmacao.abertas("gmail.arquivar") == []


@pytest.mark.parametrize("valor", ["sim", 1, None])
def test_interativo_torto_e_recusado(valor):
    with pytest.raises(ValueError, match="interativo"):
        na_nuvem.turno(_pedido("oi") | {"interativo": valor})


# --- a porta `ao_dono` -------------------------------------------------------------------------


def test_na_nuvem_sem_coletor_mostrar_erra_alto_e_nao_imprime(monkeypatch, capsys):
    monkeypatch.setattr(config, "STORE", "firestore")
    with pytest.raises(ao_dono.SemCanal):
        ao_dono.mostrar(f"confirma {CODIGO}")
    assert capsys.readouterr().out == ""
    assert ao_dono.interativo() is False


def test_no_mac_mostrar_vai_ao_terminal(monkeypatch, capsys):
    monkeypatch.setattr(config, "STORE", "sqlite")
    ao_dono.mostrar("só para o dono")
    assert capsys.readouterr().out == "só para o dono\n"


def test_o_coletor_so_vale_dentro_do_bloco():
    with ao_dono.coletar(interativo=True) as lista:
        ao_dono.mostrar("a")
        assert ao_dono.pela_rede() and ao_dono.interativo()
    assert lista == ["a"]
    assert not ao_dono.pela_rede()
