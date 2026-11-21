"""A ponte de casa da voz do estúdio (Sessão H1, D70), sem rede, sem HA e sem alto-falante.

O HA, o motor e o `aplay` são dublês que anotam o que receberam. A credencial é a de verdade: a
chave gerada por `terminal.gerar` assina a asserção que o `google-auth` mandaria ao Google, e o
certificado que ela gera passa no `casa-chave` do VPS (`scripts/nuvem.py`).

As perguntas: com o interruptor desligado ou o HA fora, alguma coisa sai para a nuvem? O que o HA
reconhece chega ao Viking? O código de aprovação chega ao alto-falante ou ao TTS? Dois toques fora
da janela aprovam? Um token errado chega à ponte? A pasta aberta para outros usuários é aceita?
"""

import ast
import importlib.util
import json
import stat
import sys
from pathlib import Path

import pytest

pytest.importorskip("starlette")
from cryptography import x509
from google.auth import jwt
from google.oauth2 import service_account
from starlette.testclient import TestClient

from lifeos.casa import config, ponte, remoto, servidor, som, terminal
from lifeos.casa.ha import HA, Interruptor, RespostaDoHA

CODIGO = "6284"
CONTA = "viking-casa@viking-teste.iam.gserviceaccount.com"
URL = "https://motor-123.southamerica-east1.run.app"
WAV = b"RIFF....WAVEfmt "  # a ponte não abre o áudio: quem confere é o motor


# --- dublês --------------------------------------------------------------------------------------


class _HA:
    def __init__(self, *, ligado=True, reconhece=None):
        self.interruptor = Interruptor(ligado, "" if ligado else "o interruptor está desligado")
        self.reconhece = reconhece or {}
        self.ouviu: list[str] = []

    def ligado(self):
        return self.interruptor

    def conversar(self, texto):
        self.ouviu.append(texto)
        return self.reconhece.get(texto)


class _Motor:
    def __init__(self, ouvido="o que tenho amanhã?", respostas=()):
        self.ouvido = ouvido
        self.respostas = list(respostas)
        self.pedidos: list[dict] = []
        self.falas: list[str] = []
        self.ouvidos = 0

    def ouvir(self, _wav):
        self.ouvidos += 1
        return self.ouvido

    def responder(self, pedido):
        self.pedidos.append(json.loads(json.dumps(pedido)))  # a foto do pedido naquele momento
        passo = self.respostas.pop(0)
        if isinstance(passo, BaseException):
            raise passo
        return passo

    def falar(self, texto):
        self.falas.append(texto)
        yield texto.encode()


class _Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


def _resposta(texto="Amanhã você tem dentista às três.", **extra):
    return {
        "resposta": texto,
        "ao_dono": [],
        "aprovacao": [],
        "historico": [{"role": "user"}],
        "nota": "",
        "erro": "",
        "aviso": "",
    } | extra


def _ponte(motor, ha, relogio=None):
    tocados: list[bytes] = []

    def tocar(pedacos):
        dado = b"".join(pedacos)
        tocados.append(dado)
        return len(dado)

    return ponte.Ponte(motor, ha, tocar, relogio or _Relogio()), tocados


# --- o caminho de uma fala -------------------------------------------------------------------------


def test_interruptor_desligado_nada_sai_para_a_nuvem():
    ha = _HA(ligado=False)
    motor = _Motor()
    p, tocados = _ponte(motor, ha)
    assert p.falou(WAV).estado == "desligado"
    assert p.tocou_duas_vezes().estado == "desligado"
    assert motor.ouvidos == 0 and motor.pedidos == [] and motor.falas == [] and tocados == []


def test_o_que_o_ha_reconhece_nao_chega_ao_viking():
    ha = _HA(reconhece={"liga a luz do estúdio": RespostaDoHA("Ligado", fez=True)})
    motor = _Motor(ouvido="liga a luz do estúdio")
    p, tocados = _ponte(motor, ha)
    resultado = p.falou(WAV)
    assert (resultado.estado, resultado.origem) == ("ok", "ha")
    assert motor.pedidos == [] and motor.falas == ["Ligado"] and tocados == [b"Ligado"]


def test_o_que_o_ha_nao_reconhece_vai_ao_viking():
    ha = _HA()
    motor = _Motor(respostas=[_resposta()])
    p, tocados = _ponte(motor, ha)
    resultado = p.falou(WAV)
    assert (resultado.estado, resultado.origem) == ("ok", "viking")
    (pedido,) = motor.pedidos
    assert pedido["mensagem"] == "o que tenho amanhã?" and pedido["numero"] == 1
    assert "interativo" not in pedido  # o canal decide no motor, não o corpo
    assert ha.ouviu == ["o que tenho amanhã?"]
    assert tocados == [b"Amanh\xc3\xa3 voc\xc3\xaa tem dentista \xc3\xa0s tr\xc3\xaas."]


def test_sem_fala_nada_vai_ao_turno():
    motor = _Motor(ouvido="   ")
    p, _ = _ponte(motor, _HA())
    assert p.falou(WAV).estado == "vazio" and motor.pedidos == []


def test_a_conversa_continua_e_zera_depois_de_parada():
    relogio = _Relogio()
    segunda = _resposta("Ok.", historico=[{"role": "user"}, {"role": "model"}], nota="n1")
    motor = _Motor(respostas=[_resposta(nota="n0"), segunda, _resposta()])
    p, _ = _ponte(motor, _HA(), relogio)
    p.falou(WAV)
    relogio.agora += 60
    p.falou(WAV)
    relogio.agora += ponte.INATIVA_S + 1
    p.falou(WAV)
    primeiro, segundo, terceiro = motor.pedidos
    assert segundo["sessao"] == primeiro["sessao"] and segundo["numero"] == 2
    assert segundo["historico"] == [{"role": "user"}] and segundo["nota"] == "n0"
    assert terceiro["sessao"] != primeiro["sessao"] and terceiro["numero"] == 1
    assert terceiro["historico"] == [] and terceiro["nota"] == ""


def test_erro_do_motor_vira_estado_e_nao_quebra():
    motor = _Motor(respostas=[remoto.ErroDoMotor("o turno: HTTP 500", status=500)])
    p, tocados = _ponte(motor, _HA())
    assert p.falou(WAV).estado == "erro" and tocados == []


def test_uma_fala_por_vez():
    p, _ = _ponte(_Motor(respostas=[_resposta()]), _HA())
    p._uma_por_vez.acquire()
    try:
        with pytest.raises(ponte.Ocupada):
            p.falou(WAV)
    finally:
        p._uma_por_vez.release()


# --- a aprovação pelos dois toques ------------------------------------------------------------


_PREVIA = (
    "─" * 30
    + "\nPara: ana@example.org\nAmanhã às 12h?\nPara confirmar, toque duas vezes no botão do "
    + "aparelho.\n"
    + "─" * 30
)


def _com_aprovacao():
    return _resposta(
        "Li o e-mail; toque duas vezes para enviar.",
        ao_dono=[_PREVIA],
        aprovacao=[{"codigo": CODIGO}],
    )


def test_os_dois_toques_mandam_o_codigo_e_ele_nunca_e_falado():
    relogio = _Relogio()
    enviado = _resposta(None, ao_dono=["Enviei o e-mail para ana@example.org."])
    motor = _Motor(respostas=[_com_aprovacao(), enviado])
    p, tocados = _ponte(motor, _HA(), relogio)
    assert p.falou(WAV).estado == "aguardando"
    falado = motor.falas[0]
    assert "Amanhã às 12h?" in falado and "─" not in falado and CODIGO not in falado
    relogio.agora += ponte.JANELA_S - 1
    assert p.tocou_duas_vezes().estado == "ok"
    assert [pedido["mensagem"] for pedido in motor.pedidos] == [
        "o que tenho amanhã?",
        f"confirma {CODIGO}",
    ]
    assert motor.pedidos[1]["sessao"] == motor.pedidos[0]["sessao"]
    assert not any(CODIGO in f for f in motor.falas) and not any(
        CODIGO.encode() in t for t in tocados
    )
    assert p.tocou_duas_vezes().estado == "nada"  # uma vez só


def test_dois_toques_depois_da_janela_nao_aprovam():
    relogio = _Relogio()
    motor = _Motor(respostas=[_com_aprovacao()])
    p, _ = _ponte(motor, _HA(), relogio)
    p.falou(WAV)
    relogio.agora += ponte.JANELA_S + 1
    assert p.tocou_duas_vezes().estado == "nada" and len(motor.pedidos) == 1


def test_a_janela_abre_depois_da_fala():
    """Um e-mail longo leva tempo para ser lido: o minuto conta de quando a fala termina."""
    relogio = _Relogio()
    motor = _Motor(respostas=[_com_aprovacao(), _resposta("Ok.")])

    def tocar_devagar(pedacos):
        b"".join(pedacos)
        relogio.agora += 50  # 50 s lendo o e-mail
        return 1

    p = ponte.Ponte(motor, _HA(), tocar_devagar, relogio)
    p.falou(WAV)
    relogio.agora += 30
    assert p.tocou_duas_vezes().estado == "ok"


def test_uma_fala_nova_fecha_a_aprovacao_aberta():
    motor = _Motor(respostas=[_com_aprovacao(), _resposta("Ok.")])
    p, _ = _ponte(motor, _HA())
    p.falou(WAV)
    p.falou(WAV)
    assert p.tocou_duas_vezes().estado == "nada"
    assert [pedido["mensagem"] for pedido in motor.pedidos] == ["o que tenho amanhã?"] * 2


def test_dois_toques_sem_nada_aberto():
    motor = _Motor()
    p, _ = _ponte(motor, _HA())
    assert p.tocou_duas_vezes().estado == "nada" and motor.pedidos == []


def test_o_codigo_aberto_e_mascarado_se_vier_no_texto_e_os_outros_numeros_nao():
    vazou = _com_aprovacao() | {"resposta": f"Código {CODIGO}. Em 2026 custa 1500."}
    motor = _Motor(respostas=[vazou])
    p, _ = _ponte(motor, _HA())
    p.falou(WAV)
    (falado,) = motor.falas
    assert CODIGO not in falado and "2026" in falado and "1500" in falado


def test_codigo_torto_na_resposta_e_ignorado():
    motor = _Motor(respostas=[_resposta(aprovacao=[{"codigo": "12a4"}, "x", {"codigo": 6284}])])
    p, _ = _ponte(motor, _HA())
    assert p.falou(WAV).estado == "ok"  # nada aberto: só um código de 4 dígitos em texto vale


# --- o servidor da rede de casa ---------------------------------------------------------------------


TOKEN = "t" * 43


class _PonteFalsa:
    def __init__(self, resultado=None, erro=None):
        self.resultado = resultado or ponte.Resultado("ok", "viking")
        self.erro, self.chamadas = erro, []

    def falou(self, wav):
        self.chamadas.append(("falou", wav))
        if self.erro:
            raise self.erro
        return self.resultado

    def tocou_duas_vezes(self):
        self.chamadas.append(("toque",))
        return self.resultado


def _cliente(falsa):
    return TestClient(servidor.app(falsa, TOKEN))


@pytest.mark.parametrize(
    "cabecalho", [None, "Bearer errado", f"Basic {TOKEN}", "Bearer ", f"Bearer {TOKEN}x"]
)
def test_sem_o_token_do_aparelho_nada_chega_a_ponte(cabecalho):
    falsa = _PonteFalsa()
    cliente = _cliente(falsa)
    cabecalhos = {"Authorization": cabecalho} if cabecalho else {}
    assert cliente.post("/falar", content=WAV, headers=cabecalhos).status_code == 401
    assert cliente.post("/toque", headers=cabecalhos).status_code == 401
    assert cliente.get("/saude", headers=cabecalhos).status_code == 401
    assert falsa.chamadas == []


def test_com_o_token_a_fala_e_o_toque_chegam():
    falsa = _PonteFalsa(ponte.Resultado("aguardando", "viking", "segredo da fala"))
    cliente = _cliente(falsa)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    resposta = cliente.post("/falar", content=WAV, headers=auth)
    assert resposta.json() == {"estado": "aguardando", "origem": "viking"}  # a fala não vai
    assert cliente.post("/toque", headers=auth).status_code == 200
    assert cliente.get("/saude", headers=auth).json() == {"ok": True}
    assert falsa.chamadas == [("falou", WAV), ("toque",)]


def test_audio_grande_ou_vazio_nao_chega_a_ponte():
    falsa = _PonteFalsa()
    cliente = _cliente(falsa)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    grande = b"x" * (servidor.MAX_WAV + 1)
    assert cliente.post("/falar", content=grande, headers=auth).status_code == 413
    assert cliente.post("/falar", content=b"", headers=auth).status_code == 400
    assert falsa.chamadas == []


def test_ocupada_e_429_e_erro_e_so_o_tipo(caplog):
    auth = {"Authorization": f"Bearer {TOKEN}"}
    ocupada = _cliente(_PonteFalsa(erro=ponte.Ocupada("x")))
    assert ocupada.post("/falar", content=WAV, headers=auth).status_code == 429
    quebra = _cliente(_PonteFalsa(erro=RuntimeError("o dono disse: segredo")))
    resposta = quebra.post("/falar", content=WAV, headers=auth)
    assert resposta.status_code == 500 and "segredo" not in resposta.text
    assert "segredo" not in caplog.text


def test_toda_rota_da_ponte_comeca_pelo_token():
    arvore = ast.parse(Path(servidor.__file__).read_text())
    funcoes = {n.name: n for n in ast.walk(arvore) if isinstance(n, ast.AsyncFunctionDef)}
    for rota in servidor.ROTAS:
        corpo = funcoes[rota.endpoint.__name__].body
        if isinstance(corpo[0], ast.Expr) and isinstance(corpo[0].value, ast.Constant):
            corpo = corpo[1:]
        assert ast.unparse(corpo[0]) == "_conferir(request)", rota.path
    assert "add_route" not in Path(servidor.__file__).read_text()


def test_o_token_do_aparelho_e_comparado_em_tempo_constante():
    fonte = Path(servidor.__file__).read_text()
    assert "hmac.compare_digest" in fonte and "== esperado" not in fonte


def test_token_curto_e_recusado():
    with pytest.raises(ValueError, match="curto"):
        servidor.app(_PonteFalsa(), "curto")


# --- o Home Assistant -------------------------------------------------------------------------------


class _Resposta:
    def __init__(self, status=200, dados=None):
        self.status_code, self._dados = status, dados

    def json(self):
        if self._dados is None:
            raise ValueError("sem JSON")
        return self._dados


class _HTTP:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.pedidos = resposta, erro, []

    def get(self, url, **kwargs):
        self.pedidos.append(("GET", url, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta

    post = get


def _ha(resposta=None, erro=None):
    http = _HTTP(resposta, erro)
    return HA("http://127.0.0.1:8123/", "tok-ha", "input_boolean.viking_voz", http), http


@pytest.mark.parametrize(
    ("resposta", "erro", "ligado"),
    [
        (_Resposta(200, {"state": "on"}), None, True),
        (_Resposta(200, {"state": "off"}), None, False),
        (_Resposta(200, {"state": "unavailable"}), None, False),
        (_Resposta(404, {}), None, False),
        (_Resposta(401, {}), None, False),
        (_Resposta(200, None), None, False),
        (None, ConnectionError("fora"), False),
    ],
)
def test_o_interruptor_falha_fechado(resposta, erro, ligado):
    ha, http = _ha(resposta, erro)
    assert ha.ligado().ligado is ligado
    (_, url, kwargs) = http.pedidos[0]
    assert url == "http://127.0.0.1:8123/api/states/input_boolean.viking_voz"
    assert kwargs["headers"]["Authorization"] == "Bearer tok-ha"


def _do_ha(tipo, codigo=None, fala="Ligado"):
    corpo = {"response_type": tipo, "speech": {"plain": {"speech": fala}}, "data": {}}
    if codigo:
        corpo["data"] = {"code": codigo}
    return _Resposta(200, {"response": corpo, "conversation_id": "x"})


@pytest.mark.parametrize(
    ("resposta", "esperado"),
    [
        (_do_ha("action_done"), RespostaDoHA("Ligado", fez=True)),
        (_do_ha("query_answer", fala="Está desligada"), RespostaDoHA("Está desligada", fez=False)),
        (_do_ha("error", "no_intent_match", "Não entendi"), None),
        (_do_ha("error", "no_valid_targets", "Não achei a varanda"), RespostaDoHA("Não achei a varanda", fez=False)),
        (_Resposta(500, {}), None),
        (_Resposta(200, {"x": 1}), None),
        (_Resposta(200, None), None),
    ],
)  # fmt: skip
def test_o_agente_local_do_ha(resposta, esperado):
    ha, http = _ha(resposta)
    assert ha.conversar("liga a luz") == esperado
    (_, url, kwargs) = http.pedidos[0]
    assert url.endswith("/api/conversation/process")
    assert kwargs["json"] == {
        "text": "liga a luz",
        "language": "pt-BR",
        "agent_id": "conversation.home_assistant",
    }


def test_ha_fora_na_conversa_segue_para_o_viking():
    ha, _ = _ha(erro=ConnectionError("fora"))
    assert ha.conversar("oi") is None


# --- o motor visto da ponte -----------------------------------------------------------------------


class _RespostaDoMotor(_Resposta):
    def __init__(self, status=200, dados=None, pedacos=()):
        super().__init__(status, dados)
        self.pedacos, self.fechada = list(pedacos), False

    def iter_content(self, _tamanho):
        yield from self.pedacos

    def close(self):
        self.fechada = True


class _HTTPDoMotor:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.pedidos = resposta, erro, []

    def request(self, metodo, url, **kwargs):
        self.pedidos.append((metodo, url, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta


def test_o_motor_ouve_responde_e_fala():
    http = _HTTPDoMotor(_RespostaDoMotor(200, {"texto": "oi"}))
    motor = remoto.Motor(URL + "/", http)
    assert motor.ouvir(b"wav") == "oi"
    metodo, url, kwargs = http.pedidos[-1]
    assert (metodo, url) == ("POST", URL + "/voz/ouvir") and kwargs["data"] == b"wav"
    http.resposta = _RespostaDoMotor(200, pedacos=[b"a", b"", b"b"])
    assert b"".join(motor.falar("Oi.")) == b"ab" and http.resposta.fechada
    assert http.pedidos[-1][2]["json"] == {"texto": "Oi."} and http.pedidos[-1][2]["stream"]


@pytest.mark.parametrize(("status", "teto"), [(429, True), (403, False), (502, False)])
def test_o_erro_do_motor_diz_o_status(status, teto):
    motor = remoto.Motor(URL, _HTTPDoMotor(_RespostaDoMotor(status, {"erro": "o teto"})))
    with pytest.raises(remoto.ErroDoMotor) as erro:
        motor.ouvir(b"wav")
    assert erro.value.status == status and erro.value.teto is teto


def test_o_motor_fora_e_erro_do_motor():
    motor = remoto.Motor(URL, _HTTPDoMotor(erro=ConnectionError("dns")))
    with pytest.raises(remoto.ErroDoMotor, match="ConnectionError"):
        motor.responder({})


# --- a configuração e a credencial ---------------------------------------------------------------


@pytest.fixture
def preparada(tmp_path, monkeypatch):
    base = tmp_path / "viking-casa"
    monkeypatch.setenv("VIKING_CASA_PASTA", str(base))
    token = terminal.gerar(
        base,
        nomes=["laptop.local", "laptop", "192.168.0.10"],
        conta=CONTA,
        motor_url=URL,
        ha_url="http://127.0.0.1:8123",
        ha_token="tok-ha",
        interruptor=config.INTERRUPTOR_PADRAO,
        porta=config.PORTA_PADRAO,
    )
    return base, token


def test_preparar_cria_tudo_fechado(preparada):
    base, token = preparada
    assert stat.S_IMODE(base.stat().st_mode) == 0o700
    for nome in (
        config.ARQUIVO,
        config.PRIVADA,
        config.PUBLICA,
        config.TLS_CHAVE,
        config.TLS_CERTIFICADO,
    ):
        assert stat.S_IMODE((base / nome).stat().st_mode) == 0o600, nome
    cfg = config.carregar(base)
    assert cfg.aparelho_token == token and len(token) >= 40 and cfg.chave_id == ""
    assert b"PRIVATE" not in (base / config.PUBLICA).read_bytes()


def test_preparar_nunca_sobrescreve(preparada):
    base, _ = preparada
    with pytest.raises(FileExistsError):
        terminal.gerar(base, nomes=["x"], conta=CONTA, motor_url=URL, ha_url="h",
                       ha_token="t", interruptor="i", porta=1)  # fmt: skip


@pytest.mark.parametrize("nome", [config.ARQUIVO, config.PRIVADA, config.TLS_CHAVE, "."])
def test_pasta_ou_arquivo_aberto_e_recusado(preparada, nome):
    base, _ = preparada
    (base / nome).chmod(0o755 if nome == "." else 0o644)
    with pytest.raises(config.ConfigInsegura, match="permissão"):
        config.carregar(base)


def test_sem_preparar_diz_o_que_fazer(tmp_path):
    with pytest.raises(config.ConfigInsegura, match="--preparar"):
        config.carregar(tmp_path)


def test_a_chave_gerada_aqui_assina_o_que_o_google_receberia(preparada):
    base, _ = preparada
    cfg = config.carregar(base)
    credenciais = service_account.IDTokenCredentials.from_service_account_info(
        cfg.credencial(), target_audience=URL
    )
    assert not credenciais._use_iam_endpoint  # o JWT vai ao token_uri: sem TokenCreator
    assercao = credenciais._make_authorization_grant_assertion()
    certificado = (base / config.PUBLICA).read_bytes()
    dados = jwt.decode(assercao, certs=certificado, audience="https://oauth2.googleapis.com/token")
    assert dados["iss"] == CONTA and dados["target_audience"] == URL


def test_o_certificado_da_conta_passa_no_casa_chave_do_vps(preparada):
    base, _ = preparada
    spec = importlib.util.spec_from_file_location(
        "nuvem_script_casa", Path(__file__).resolve().parents[1] / "scripts" / "nuvem.py"
    )
    nuvem = importlib.util.module_from_spec(spec)
    sys.modules["nuvem_script_casa"] = nuvem
    spec.loader.exec_module(nuvem)
    assert len(nuvem.conferir_certificado(base / config.PUBLICA).split(":")) == 32
    with pytest.raises(ValueError, match="PRIVADA"):
        nuvem.conferir_certificado(base / config.PRIVADA)


def test_o_https_da_ponte_vale_para_os_nomes_do_laptop(preparada):
    base, _ = preparada
    certificado = x509.load_pem_x509_certificate((base / config.TLS_CERTIFICADO).read_bytes())
    nomes = certificado.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert nomes.get_values_for_type(x509.DNSName) == ["laptop.local", "laptop"]
    assert [str(ip) for ip in nomes.get_values_for_type(x509.IPAddress)] == ["192.168.0.10"]


def test_gravar_o_id_da_chave(preparada, capsys):
    base, _ = preparada
    assert terminal.gravar_chave_id("abc") == 1
    chave_id = "0123456789abcdef0123456789abcdef01234567"
    assert terminal.gravar_chave_id(chave_id) == 0
    assert config.carregar(base).chave_id == chave_id
    assert stat.S_IMODE((base / config.ARQUIVO).stat().st_mode) == 0o600


# --- o alto-falante -------------------------------------------------------------------------------


def test_o_tocador_manda_os_pedacos_ao_aplay(tmp_path):
    saida = tmp_path / "som.raw"
    tocador = som.Tocador(["sh", "-c", f"cat > {saida}"])
    assert tocador.tocar([b"ab", b"cd"]) == 4
    assert saida.read_bytes() == b"abcd"


def test_o_tocador_tem_teto_de_tempo():
    tocador = som.Tocador(["sleep", "30"], max_s=0.2)

    def pedacos():
        yield b"x" * 70_000  # passa do buffer do pipe: o `sleep` não lê, e o teto o mata

    assert tocador.tocar(pedacos()) == 0


def test_o_comando_do_aplay_e_o_formato_do_motor():
    assert som.COMANDO[:1] == ("aplay",) and "24000" in som.COMANDO and "S16_LE" in som.COMANDO
