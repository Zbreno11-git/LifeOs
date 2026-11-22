"""As rotas da voz no motor (Sessão H1, D70) e o módulo `assistant/voz.py`.

A identidade é a de verdade (as chaves e o token de `tests/test_motor.py`). O Gemini nunca é
chamado pela rede: as rotas têm o trabalho trocado por dublês, e as funções de `voz` recebem um
cliente do SDK com a chamada de rede trocada por um roteiro.

As perguntas: só a ponte de casa entra nas rotas da voz, e ela só nelas? Um áudio torto, grande ou
de outro formato para antes do modelo? O teto vira 429? O streaming manda as frases na ordem e
para no erro? A transcrição e a fala vão ao modelo sem tools e sem a conversa?
"""

import io
import json
import struct
import wave

import pytest
from google import genai
from google.genai import types
from tests import test_motor as base

pytest.importorskip("starlette")
from starlette.testclient import TestClient

from lifeos import custos
from lifeos.assistant import voz
from lifeos.nuvem import motor

_nuvem = base._nuvem
PROJETO = base.PROJETO
CASA = f"viking-casa@{PROJETO}.iam.gserviceaccount.com"
ROTAS_DA_VOZ = ("/voz/saude", "/voz/ouvir", "/voz/responder", "/voz/falar")


def _token_da_casa():
    return base._token(email=CASA)


def _wav(segundos=1.0, taxa=16_000, canais=1, largura=2, quadros=None):
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(canais)
        arquivo.setsampwidth(largura)
        arquivo.setframerate(taxa)
        n = int(segundos * taxa) if quadros is None else quadros
        arquivo.writeframes(b"\x00" * (n * canais * largura))
    return saida.getvalue()


@pytest.fixture
def cliente():
    return TestClient(motor.app)


def _post(cliente, rota, corpo, token, **cabecalhos):
    return cliente.post(
        rota, content=corpo, headers={"Authorization": f"Bearer {token}"} | cabecalhos
    )


# --- quem entra ---------------------------------------------------------------------------------


def test_as_rotas_da_voz_sao_so_da_casa():
    for rota in ROTAS_DA_VOZ:
        assert motor.QUEM_FALA[rota] == frozenset({motor.CASA}), rota
    fora = [
        r for r, quem in motor.QUEM_FALA.items() if motor.CASA in quem and r not in ROTAS_DA_VOZ
    ]
    assert fora == []  # a casa não entra em nenhuma outra porta (nem no `/chat`)


def test_a_casa_entra_na_saude_e_o_terminal_nao(cliente):
    assert base._get(cliente, "/voz/saude", _token_da_casa()).json() == {
        "ok": True,
        "commit": "abc123",
    }
    assert base._get(cliente, "/voz/saude", base._token()).status_code == 403
    assert base._get(cliente, "/voz/saude").status_code == 401


@pytest.mark.parametrize("rota", ["/versao", "/lembretes", "/fumaca/segredos", "/memoria"])
def test_a_casa_nao_entra_nas_portas_do_terminal(cliente, rota):
    assert base._get(cliente, rota, _token_da_casa()).status_code == 403


def test_a_casa_nao_conversa_pelo_chat_nem_pelas_maos(cliente, monkeypatch):
    chamados = []
    monkeypatch.setattr(motor, "_turno", lambda dados: chamados.append(dados) or {})
    for rota in ("/chat", "/maos/pegar", "/memoria/esquecer", "/documentos/aprender"):
        assert _post(cliente, rota, b"{}", _token_da_casa()).status_code == 403, rota
    assert chamados == []


@pytest.mark.parametrize("rota", ["/voz/ouvir", "/voz/responder", "/voz/falar"])
def test_o_terminal_e_as_maos_nao_entram_na_voz(cliente, rota, monkeypatch):
    monkeypatch.setattr(motor, "_ouvir", lambda _w: pytest.fail("ouviu"))
    monkeypatch.setattr(motor, "_turno_da_voz", lambda _d: pytest.fail("conversou"))
    monkeypatch.setattr(motor, "_cliente_da_voz", lambda: pytest.fail("falou"))
    for token in (
        base._token(),
        base._token(email=f"viking-maos@{PROJETO}.iam.gserviceaccount.com"),
    ):
        assert _post(cliente, rota, _wav(), token).status_code == 403


def test_o_limite_do_motor_e_o_do_audio():
    assert motor.MAX_CORPO_DA_VOZ == voz.MAX_WAV
    assert motor.MAX_CORPO_DA_FALA >= voz.MAX_TEXTO_FALADO * 4  # 4 bytes por caractere no pior caso


# --- ouvir ---------------------------------------------------------------------------------------


@pytest.fixture
def ouvidos(monkeypatch):
    recebidos = []

    def ouvir(wav):
        recebidos.append(wav)
        return "liga a luz do estúdio"

    monkeypatch.setattr(motor, "_ouvir", ouvir)
    return recebidos


def test_ouvir_devolve_o_texto_e_a_duracao(cliente, ouvidos):
    wav = _wav(2.5)
    resposta = _post(cliente, "/voz/ouvir", wav, _token_da_casa())
    assert resposta.status_code == 200
    assert resposta.json() == {"texto": "liga a luz do estúdio", "segundos": 2.5}
    assert ouvidos == [wav]


@pytest.mark.parametrize(
    "corpo",
    [
        b"isto nao e um wav",
        _wav(taxa=44_100),
        _wav(canais=2),
        _wav(largura=1),
        _wav(segundos=0.1),
        _wav()[:-100],  # o cabeçalho diz um tamanho e o corpo traz menos
        b"",
    ],
)
def test_audio_torto_para_antes_do_modelo(cliente, ouvidos, corpo):
    assert _post(cliente, "/voz/ouvir", corpo, _token_da_casa()).status_code == 400
    assert ouvidos == []


def test_audio_grande_demais_para_sem_ler(cliente, ouvidos):
    grande = _wav(quadros=voz.MAX_WAV // 2 + 1)
    assert _post(cliente, "/voz/ouvir", grande, _token_da_casa()).status_code == 413
    declarado = _post(
        cliente, "/voz/ouvir", b"x", _token_da_casa(), **{"content-length": str(voz.MAX_WAV + 1)}
    )
    assert declarado.status_code == 413
    assert ouvidos == []


def _gasto():
    return custos.Gasto(dia=1.2, mes=3.0, teto_dia=1.0, teto_mes=10.0)


def test_o_teto_vira_429_e_o_erro_so_o_tipo(cliente, monkeypatch, caplog):
    def teto(_wav):
        raise custos.TetoAtingido(_gasto())

    monkeypatch.setattr(motor, "_ouvir", teto)
    resposta = _post(cliente, "/voz/ouvir", _wav(), _token_da_casa())
    assert resposta.status_code == 429 and "teto" in resposta.json()["erro"]

    def quebra(_wav):
        raise RuntimeError("segredo do dono: Dentista secreto")

    monkeypatch.setattr(motor, "_ouvir", quebra)
    resposta = _post(cliente, "/voz/ouvir", _wav(), _token_da_casa())
    assert resposta.status_code == 502 and "Dentista" not in resposta.text
    assert "Dentista" not in caplog.text


# --- responder -----------------------------------------------------------------------------------


def test_responder_roda_o_turno_pelo_canal_da_voz(cliente, monkeypatch):
    recebidos = []

    def turno(dados):
        recebidos.append(dados)
        return {"resposta": "Amanhã você tem dentista.", "aprovacao": []}

    monkeypatch.setattr(motor, "_turno_da_voz", turno)
    monkeypatch.setattr(motor, "_turno", lambda _d: pytest.fail("foi pelo chat"))
    resposta = _post(
        cliente, "/voz/responder", b'{"mensagem": "o que tenho amanha?"}', _token_da_casa()
    )
    assert resposta.status_code == 200 and resposta.json()["resposta"].startswith("Amanhã")
    assert recebidos == [{"mensagem": "o que tenho amanha?"}]


def test_responder_chama_o_turno_com_o_canal_voz(monkeypatch):
    from lifeos.assistant import na_nuvem

    vistos = []
    monkeypatch.setattr(na_nuvem, "turno", lambda dados, canal="chat": vistos.append(canal) or {})
    motor._turno_da_voz({"mensagem": "oi"})
    assert vistos == ["voz"]


def test_responder_torto_e_400(cliente, monkeypatch):
    monkeypatch.setattr(motor, "_turno_da_voz", lambda _d: (_ for _ in ()).throw(ValueError("x")))
    assert _post(cliente, "/voz/responder", b"nao e json", _token_da_casa()).status_code == 400
    assert _post(cliente, "/voz/responder", b"{}", _token_da_casa()).status_code == 400


# --- falar ---------------------------------------------------------------------------------------


@pytest.fixture
def falas(monkeypatch):
    ditas = []
    monkeypatch.setattr(motor, "_cliente_da_voz", lambda: "cliente")

    def falar_frase(cliente, frase):
        assert cliente == "cliente"
        if "quebra" in frase:
            raise RuntimeError("segredo")
        ditas.append(frase)
        return frase.encode()[:4]

    monkeypatch.setattr(voz, "falar_frase", falar_frase)
    return ditas


def test_falar_manda_as_frases_na_ordem(cliente, falas):
    texto = (
        "Amanhã você tem dentista às três da tarde. Quer que eu lembre uma hora antes? Combinado."
    )
    resposta = _post(cliente, "/voz/falar", f'{{"texto": "{texto}"}}'.encode(), _token_da_casa())
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("audio/L16")
    assert falas == voz.frases(texto) and len(falas) >= 2
    assert resposta.content == b"".join(f.encode()[:4] for f in falas)


def test_falar_para_no_meio_quando_uma_frase_falha(cliente, falas, caplog):
    texto = "Primeira frase que é longa o bastante para ficar sozinha aqui. " + (
        "Agora a segunda quebra aqui no meio, longa o bastante também. Terceira nunca sai daqui."
    )
    # A frase que falha derruba a conexão (o cliente de teste a vê como a exceção do servidor): a
    # ponte vê a falha, nunca um fim normal com meio áudio.
    with pytest.raises(RuntimeError):
        _post(cliente, "/voz/falar", f'{{"texto": "{texto}"}}'.encode(), _token_da_casa())
    assert len(falas) == 1
    assert "RuntimeError" in caplog.text and "segredo" not in caplog.text


def test_falar_inteiro_recusa_o_que_nao_cabe_antes_do_modelo(cliente, falas):
    longo = " ".join(
        f"Frase número {i} que é longa o bastante para ficar sozinha." for i in range(20)
    )
    assert not voz.cabe_inteiro(longo) and len(voz.frases(longo)) == voz.MAX_FRASES
    corpo = json.dumps({"texto": longo, "inteiro": True}).encode()
    resposta = _post(cliente, "/voz/falar", corpo, _token_da_casa())
    assert resposta.status_code == 413 and falas == []
    sem_inteiro = json.dumps({"texto": longo}).encode()
    assert _post(cliente, "/voz/falar", sem_inteiro, _token_da_casa()).status_code == 200


def test_a_voz_sem_o_teto_preso_fecha(monkeypatch):
    """O gancho do teto depende de um método interno do SDK: sem ele, a voz não gasta."""
    from lifeos.assistant import na_nuvem

    monkeypatch.setattr(na_nuvem, "_cliente", lambda: object())
    monkeypatch.setattr(na_nuvem, "_teto", lambda: object())
    monkeypatch.setattr(custos, "instrumentar", lambda *_a, **_k: False)
    with pytest.raises(RuntimeError, match="teto"):
        motor._cliente_da_voz()


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Mande para joao_silva@exemplo.com.", ["Mande para joao_silva@exemplo.com."]),
        ("# Agenda\n**Amanhã** às _três_.", ["Agenda Amanhã às três."]),
        ("Pronto.\n🎉\n—", ["Pronto."]),
    ],
)
def test_as_frases_tiram_o_markdown_e_o_que_nao_se_diz(texto, esperado):
    assert voz.frases(texto) == esperado


def test_falar_com_erro_na_primeira_frase_e_status(cliente, monkeypatch):
    monkeypatch.setattr(motor, "_cliente_da_voz", lambda: "cliente")

    def teto(_c, _f):
        raise custos.TetoAtingido(_gasto())

    monkeypatch.setattr(voz, "falar_frase", teto)
    assert _post(cliente, "/voz/falar", b'{"texto": "oi"}', _token_da_casa()).status_code == 429


@pytest.mark.parametrize(
    "corpo", [b"nao e json", b'{"texto": 3}', b'{"texto": "   "}', b"[]", b'{"texto": "**"}']
)
def test_falar_torto_e_400(cliente, falas, corpo):
    assert _post(cliente, "/voz/falar", corpo, _token_da_casa()).status_code == 400
    assert falas == []


def test_falar_texto_longo_demais_e_recusado(cliente, falas):
    longo = ('{"texto": "' + "a" * (voz.MAX_TEXTO_FALADO + 1) + '"}').encode()
    assert _post(cliente, "/voz/falar", longo, _token_da_casa()).status_code == 400
    assert falas == []


# --- o módulo da voz -----------------------------------------------------------------------------


def test_conferir_wav_devolve_a_duracao():
    assert voz.conferir_wav(_wav(3.0)) == 3.0


def test_frases_juntam_as_curtas_e_cortam_as_longas():
    assert voz.frases("Oi. Tudo bem? Sim.") == ["Oi. Tudo bem? Sim."]
    longa = "palavra " * 120
    pedacos = voz.frases(longa)
    assert all(len(p) <= voz.MAX_FRASE for p in pedacos) and len(pedacos) >= 2
    assert voz.frases("**Negrito** e `código`.") == ["Negrito e código."]
    assert len(voz.frases("Uma frase completa aqui, longa o suficiente. " * 40)) == voz.MAX_FRASES
    assert voz.frases("") == []


class _Roteiro:
    def __init__(self, resposta):
        self.resposta = resposta
        self.pedidos = []

    def __call__(self, **kwargs):
        self.pedidos.append(kwargs)
        return self.resposta


def _cliente(resposta):
    roteiro = _Roteiro(resposta)
    cliente = genai.Client(api_key="teste")
    cliente.models._generate_content = roteiro
    return cliente, roteiro


def _com_parte(parte):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[parte]))]
    )


def test_transcrever_manda_so_o_pedido_e_o_audio():
    cliente, roteiro = _cliente(_com_parte(types.Part(text="  liga a luz\x1b[31m  ")))
    wav = _wav()
    ouvido = voz.transcrever(cliente, wav)
    assert ouvido.startswith("liga a luz") and "\x1b" not in ouvido and ouvido == ouvido.strip()
    (pedido,) = roteiro.pedidos
    assert pedido["model"] == voz.MODELO_DE_OUVIR
    config = pedido["config"]
    assert not config.tools and not config.system_instruction
    (conteudo,) = pedido["contents"]
    partes = conteudo.parts
    assert [p.text for p in partes if p.text] == [voz.PEDIDO_DE_TRANSCRICAO]
    assert [p.inline_data.mime_type for p in partes if p.inline_data] == ["audio/wav"]


def _wav_de_saida(taxa=voz.TAXA_DE_SAIDA):
    saida = io.BytesIO()
    with wave.open(saida, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        arquivo.writeframes(struct.pack("<4h", 1, 2, 3, 4))
    return saida.getvalue()


@pytest.mark.parametrize(
    ("dado", "tipo", "esperado"),
    [
        (b"\x01\x02\x03\x04", "audio/L16;codec=pcm;rate=24000", b"\x01\x02\x03\x04"),
        (_wav_de_saida(), "audio/wav", struct.pack("<4h", 1, 2, 3, 4)),
    ],
)
def test_falar_frase_devolve_o_pcm(dado, tipo, esperado):
    parte = types.Part(inline_data=types.Blob(data=dado, mime_type=tipo))
    cliente, roteiro = _cliente(_com_parte(parte))
    assert voz.falar_frase(cliente, "Oi.") == esperado
    (pedido,) = roteiro.pedidos
    assert pedido["model"] == voz.MODELO_DE_FALAR
    (conteudo,) = pedido["contents"]
    (parte_dita,) = conteudo.parts
    assert parte_dita.text == "Oi."  # só a frase, sem instrução colada
    assert not pedido["config"].tools and not pedido["config"].system_instruction


@pytest.mark.parametrize("estilo", [None, voz.ESTILO_BRASILEIRO])
def test_o_estilo_vai_fora_do_texto_e_o_idioma_na_configuracao(monkeypatch, estilo):
    """O sotaque (C6, 2026-11-22): o idioma no `SpeechConfig`, o estilo no `speech_metadata` da
    parte, e o texto falado igual à frase (a página manda não pôr instrução no texto)."""
    monkeypatch.setattr(voz, "ESTILO", estilo)
    parte = types.Part(inline_data=types.Blob(data=b"\x01\x02", mime_type="audio/L16;rate=24000"))
    cliente, roteiro = _cliente(_com_parte(parte))
    voz.falar_frase(cliente, "Li o e-mail.")
    (pedido,) = roteiro.pedidos
    (conteudo,) = pedido["contents"]
    (parte_dita,) = conteudo.parts
    assert parte_dita.text == "Li o e-mail."
    assert pedido["config"].speech_config.language_code == voz.IDIOMA == "pt-BR"
    assert pedido["config"].speech_config.voice_config.prebuilt_voice_config.voice_name == voz.VOZ
    if estilo:
        assert parte_dita.speech_metadata.style == estilo
    else:
        assert parte_dita.speech_metadata is None


@pytest.mark.parametrize(
    "parte",
    [
        types.Part(text="não sei falar"),
        types.Part(inline_data=types.Blob(data=b"\xff\xfb", mime_type="audio/mpeg")),
        types.Part(inline_data=types.Blob(data=b"\x00\x00", mime_type="audio/L16;rate=16000")),
        types.Part(inline_data=types.Blob(data=_wav_de_saida(16_000), mime_type="audio/wav")),
    ],
)
def test_falar_frase_sem_o_audio_certo_e_erro(parte):
    cliente, _ = _cliente(_com_parte(parte))
    with pytest.raises(voz.SemAudio):
        voz.falar_frase(cliente, "Oi.")


def test_os_modelos_da_voz_tem_tarifa_no_teto():
    """A voz gasta pelo mesmo teto (D59): um modelo sem tarifa cobraria a mais cara, mas o
    modelo que o C6 escolher entra na tabela com a tarifa lida na página."""
    assert voz.MODELO_DE_OUVIR in custos.TARIFAS and voz.MODELO_DE_FALAR in custos.TARIFAS
