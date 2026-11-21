"""O turno pelo canal da voz (Sessão H1, D70): o mesmo turno da nuvem, pedido pela ponte de casa.

O turno roda inteiro, como em `tests/test_na_nuvem_gmail.py`: o cliente do google-genai com a rede
trocada por um roteiro, o Gmail falso, e as confirmações e o teto no Firestore (o emulador).

As perguntas: pela voz nasce a proposta mesmo sem o corpo dizer `interativo` (o canal de aprovação
são os dois toques no botão)? O código sai do texto que vai ser falado e vai só no campo
`aprovacao`? Ele aparece em mais algum lugar (o histórico, a nota, o que foi ao modelo, o log)? A
busca na web fica fora da voz, e só da voz? A forma da linha do código casa com quem a produz?
"""

import json
import logging
import re
from pathlib import Path

import pytest
from tests import test_na_nuvem as base
from tests import test_na_nuvem_gmail as gm
from tests.sentinela import aparece

from lifeos import confirmacao
from lifeos.assistant import agent, na_nuvem, turno

_contexto_limpo = base._contexto_limpo
teto = base.teto
gemini = base.gemini
nuvem = gm.nuvem
_chama, _texto = base._chama, base._texto
ANA, CODIGO, LOJA = gm.ANA, gm.CODIGO, gm.LOJA


def _pedido(mensagem, *, numero=1, historico=()):
    """O pedido da ponte: sem `interativo` (o canal decide, não o corpo)."""
    return {
        "mensagem": mensagem,
        "historico": list(historico),
        "nota": "",
        "sessao": "voz12345",
        "numero": numero,
    }


def _fora_da_aprovacao(saida: dict) -> str:
    return json.dumps({k: v for k, v in saida.items() if k != "aprovacao"}, ensure_ascii=False)


def test_pela_voz_o_envio_a_outra_pessoa_pede_os_dois_toques(nuvem, gemini, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    roteiro = gemini(
        _chama("enviar_email", para=ANA, assunto="Almoço", corpo="Amanhã às 12h?"),
        _texto("Li o e-mail para você; toque duas vezes para enviar."),
    )
    saida = na_nuvem.turno(_pedido("manda um e-mail para a Ana"), canal="voz")
    assert saida["aprovacao"] == [{"codigo": CODIGO}]
    (so_dele,) = saida["ao_dono"]
    assert "Amanhã às 12h?" in so_dele and na_nuvem.TOQUE_DUPLO in so_dele
    # o código só no campo `aprovacao`: nem no que vai ser falado, nem no histórico, nem na nota
    assert not aparece(CODIGO, _fora_da_aprovacao(saida))
    assert not any(aparece(CODIGO, enviado) for enviado in roteiro.enviados)
    assert capsys.readouterr() == ("", "")
    assert not aparece(CODIGO, caplog.text)
    assert nuvem["enviados"] == []

    gemini()  # os dois toques: a ponte manda o código de volta, e ele não vai ao modelo
    aprovado = na_nuvem.turno(_pedido(f"confirma {CODIGO}", numero=2), canal="voz")
    assert "Enviei" in aprovado["ao_dono"][0] and len(nuvem["enviados"]) == 1
    assert aprovado["aprovacao"] == []


def test_o_corpo_nao_desliga_a_aprovacao_da_voz_nem_liga_a_do_chat(nuvem, gemini):
    gemini(_chama("preparar_limpeza", remetentes=LOJA), _texto("Confira."))
    pedido = _pedido("arquiva os e-mails da loja") | {"interativo": False}
    saida = na_nuvem.turno(pedido, canal="voz")
    assert saida["aprovacao"] == [{"codigo": CODIGO}]
    assert not aparece(CODIGO, _fora_da_aprovacao(saida))


def test_o_chat_continua_sem_o_campo_e_com_o_codigo_no_ao_dono(nuvem, gemini):
    gemini(_chama("preparar_limpeza", remetentes=LOJA), _texto("Confira."))
    saida = na_nuvem.turno(gm._pedido("arquiva os e-mails da loja"))
    assert "aprovacao" not in saida and f"confirma {CODIGO}" in saida["ao_dono"][0]


def test_canal_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="canal"):
        na_nuvem.turno(_pedido("oi"), canal="pulso")


def _nomes(canal):
    marca = na_nuvem._CANAL.set(canal)
    try:
        return {f.__name__ for f in na_nuvem.ferramentas()}
    finally:
        na_nuvem._CANAL.reset(marca)


def test_a_busca_fica_fora_da_voz_e_so_dela():
    assert "buscar_na_web" in _nomes("chat")
    assert _nomes("voz") == _nomes("chat") - set(na_nuvem.FORA_DA_VOZ)
    assert set(na_nuvem.FORA_DA_VOZ) == {"buscar_na_web"}  # o dono pediu "absolutamente tudo"


def test_o_turno_devolve_o_canal_de_antes(nuvem, gemini):
    gemini(_texto("Oi!"))
    na_nuvem.turno(_pedido("oi"), canal="voz")
    assert na_nuvem._CANAL.get() == "chat"


def test_a_secao_da_voz_so_pela_voz_e_so_na_nuvem():
    presentes = na_nuvem.ferramentas()
    sem = turno.instrucao(presentes, "hoje", onde="nuvem")
    com = turno.instrucao(presentes, "hoje", onde="nuvem", voz=True)
    assert turno._VOZ not in sem and com.endswith(turno._VOZ)
    assert com.removesuffix("\n" + turno._VOZ) == sem  # o resto igual, byte a byte
    with pytest.raises(ValueError, match="voz"):
        turno.instrucao(agent.FERRAMENTAS, "hoje", onde="mac", voz=True)


def test_o_modelo_da_voz_recebe_a_secao_e_nao_recebe_a_busca(nuvem, gemini, monkeypatch):
    vistos = []
    original = na_nuvem._config

    def espiao(*args, **kwargs):
        config = original(*args, **kwargs)
        vistos.append(config)
        return config

    monkeypatch.setattr(na_nuvem, "_config", espiao)
    gemini(_texto("Oi!"))
    na_nuvem.turno(_pedido("oi"), canal="voz")
    (config,) = vistos
    assert turno._VOZ in config.system_instruction
    assert "buscar_na_web" not in {f.__name__ for f in config.tools}


def test_a_linha_do_codigo_casa_com_quem_a_produz():
    """Toda linha do `src/` que mostra um código com "confirma" (`gmail/tools.py`, e
    `browser/liberacao.py` no Mac) é reconhecida pela regex da voz depois de formatada."""
    produtores = 0
    for arquivo in Path(na_nuvem.__file__).parents[1].rglob("*.py"):
        for linha in arquivo.read_text().splitlines():
            if re.search(r"confirma \{[^}]*codigo\}", linha):
                produtores += 1
                formatada = re.sub(r"\{[^}]*codigo\}", "4821", linha)
                assert na_nuvem._CODIGO_NA_LINHA.findall(formatada) == ["4821"], (arquivo, linha)
    assert produtores >= 3


def test_o_codigo_some_do_texto_mesmo_fora_da_linha():
    texto = f"Para enviar, digite:  confirma {CODIGO}   (vale até 10:42)\nrepito: {CODIGO}."
    limpos, abertas = na_nuvem._aprovacoes_da_voz([texto, "nada aqui 12:30"])
    assert abertas == [{"codigo": CODIGO}]
    assert not any(aparece(CODIGO, b) for b in limpos)
    assert limpos[0].startswith(na_nuvem.TOQUE_DUPLO) and limpos[1] == "nada aqui 12:30"
    assert len(CODIGO) == confirmacao.DIGITOS
