"""O `firmware/viking-voz/coleta.py` (H2): a conferência dos quadros da coleta da wake word, sem a
placa. O que decide se um WAV serve para o treino é o checksum, o seq e o tempo; e nada de voz pode
cair dentro do repo, que é público."""

import importlib.util
import json
import re
import struct
import sys
import wave
from array import array
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
FIRMWARE = RAIZ / "firmware" / "viking-voz" / "src" / "main.cpp"
_spec = importlib.util.spec_from_file_location(
    "coleta_viking", RAIZ / "firmware" / "viking-voz" / "coleta.py"
)
coleta = importlib.util.module_from_spec(_spec)
sys.modules["coleta_viking"] = coleta
_spec.loader.exec_module(coleta)


def _quadro(seq: int, t_us: int, amostras=None, flags: int = 0) -> bytes:
    """Um quadro como o `coletar()` do firmware monta (little-endian)."""
    amostras = amostras if amostras is not None else [seq % 100] * coleta.BLOCO
    corpo = struct.pack("<IIHH", seq, t_us, len(amostras), flags) + struct.pack(
        f"<{len(amostras)}h", *amostras
    )
    return b"VKC1" + corpo + struct.pack("<I", coleta.fnv1a32(corpo))


def _sequencia(n: int, *, pular_seq=(), salto_de_tempo_em=None, t0=0) -> list:
    cont, quadros = coleta.Continuidade(), []
    t = t0
    for k in range(n):
        if k in pular_seq:
            t += coleta.US_POR_BLOCO
            continue
        if salto_de_tempo_em is not None and k == salto_de_tempo_em:
            t += 200_000  # 200 ms sumiram sem o seq pular (o DMA do I2S transbordou)
        quadros.append(coleta.Quadro(k, t & 0xFFFFFFFF, 0, array("h", [0] * coleta.BLOCO)))
        t += coleta.US_POR_BLOCO
    for q in quadros:
        cont.anotar(q)
    return cont


def test_o_fnv1a_bate_com_os_valores_conhecidos():
    assert coleta.fnv1a32(b"") == 0x811C9DC5
    assert coleta.fnv1a32(b"a") == 0xE40C292C
    assert coleta.fnv1a32(b"foobar") == 0xBF9CF968


def test_um_quadro_inteiro_vira_um_quadro_com_os_campos_certos():
    amostras = list(range(-256, 256))
    leitor = coleta.Leitor()
    (q,) = leitor.alimentar(_quadro(7, 123_456, amostras, flags=1))
    assert (q.seq, q.t_us, q.flags) == (7, 123_456, 1)
    assert list(q.amostras) == amostras
    assert leitor.checksums_errados == 0


def test_quadros_em_pedacos_quaisquer_saem_inteiros_e_na_ordem():
    dados = b"".join(_quadro(s, s * 32_000) for s in range(3))
    leitor, saida = coleta.Leitor(), []
    for i in range(0, len(dados), 7):
        saida += leitor.alimentar(dados[i : i + 7])
    assert [q.seq for q in saida] == [0, 1, 2]


def test_o_texto_entre_os_quadros_vira_linha_e_nao_estraga_os_quadros():
    dados = (
        b"== Viking voz (H1) ==\r\ncoleta: ganho=2 taxa=16000\n"
        + _quadro(0, 0)
        + b"\ncoleta: status seq=1 descartados=0\n"
        + _quadro(1, 32_000)
    )
    leitor = coleta.Leitor()
    quadros = leitor.alimentar(dados)
    assert [q.seq for q in quadros] == [0, 1]
    assert "coleta: ganho=2 taxa=16000" in leitor.texto
    assert "coleta: status seq=1 descartados=0" in leitor.texto


def test_um_quadro_com_checksum_errado_e_contado_e_jogado_fora():
    ruim = bytearray(_quadro(1, 32_000))
    ruim[40] ^= 0xFF  # uma amostra trocada no caminho
    leitor = coleta.Leitor()
    quadros = leitor.alimentar(_quadro(0, 0) + bytes(ruim) + _quadro(2, 64_000))
    assert [q.seq for q in quadros] == [0, 2]
    assert leitor.checksums_errados == 1


def test_a_sequencia_limpa_nao_tem_lacuna_nem_buraco_e_mede_a_taxa():
    resumo = _sequencia(200).resumo()
    assert resumo["lacunas"] == [] and resumo["perdidos"] == 0
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["taxa_medida_hz"] == pytest.approx(16_000, rel=1e-6)
    assert (resumo["blocos"], resumo["primeiro_seq"], resumo["ultimo_seq"]) == (200, 0, 199)


def test_um_quadro_perdido_vira_lacuna_no_formato_combinado():
    resumo = _sequencia(50, pular_seq={10}).resumo()
    # [o seq que faltou, a amostra do WAV onde o buraco fica]: 10 blocos recebidos antes dele
    assert resumo["lacunas"] == [[10, 10 * coleta.BLOCO]]
    assert resumo["perdidos"] == 1


def test_um_buraco_de_tempo_sem_o_seq_pular_e_suspeita():
    resumo = _sequencia(300, salto_de_tempo_em=150).resumo()
    assert resumo["lacunas"] == []
    assert resumo["suspeita_de_buraco"] is True


def test_uma_trava_curta_que_o_dma_recupera_nao_e_buraco():
    # o laço parou 80 ms depois do bloco 99; o DMA guardou o áudio, e as leituras seguintes vieram
    # 1 ms uma da outra até alcançar o tempo certo: o tempo sempre anda para a frente, e nenhuma
    # amostra se perdeu
    cont, fim_da_trava = coleta.Continuidade(), 100 * coleta.US_POR_BLOCO + 80_000
    for k in range(300):
        t = k * coleta.US_POR_BLOCO
        if k >= 100:
            t = max(t, fim_da_trava + (k - 100) * 1_000)
        cont.anotar(coleta.Quadro(k, t, 0, array("h", [0] * coleta.BLOCO)))
    resumo = cont.resumo()
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["maior_afastamento_s"] >= 0.07  # o tremor aparece, mas não é degrau


def test_um_tempo_que_anda_para_tras_nao_vira_uma_volta_do_micros():
    cont = coleta.Continuidade()
    for k, t in enumerate([0, 32_000, 64_000, 60_000, 96_000]):
        cont.anotar(coleta.Quadro(k, t, 0, array("h", [0] * coleta.BLOCO)))
    assert cont._t_continuo == 96_000  # não 2**32 a mais


def test_o_micros_que_da_a_volta_nao_vira_buraco():
    resumo = _sequencia(100, t0=2**32 - 5 * coleta.US_POR_BLOCO).resumo()
    assert resumo["suspeita_de_buraco"] is False
    assert resumo["taxa_medida_hz"] == pytest.approx(16_000, rel=1e-6)


def test_o_take_tem_meio_segundo_antes_do_fale_e_quatro_depois():
    assert coleta.recorte_do_take(5 * 16_000, 10 * 16_000) == (72_000, 144_000)
    assert coleta.recorte_do_take(1_000, 10 * 16_000) == (0, 65_000)  # no começo, corta no zero


def test_o_wav_e_o_seq_json_saem_no_formato_combinado(tmp_path):
    amostras = array("h", [0, 1, -1, 32767, -32768] * 100)
    wav = tmp_path / "s" / "take_001.wav"
    coleta.gravar_wav(wav, amostras)
    with wave.open(str(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16_000)
        lidas = array("h", w.readframes(w.getnframes()))
    assert list(lidas) == list(amostras)
    json_ = coleta.gravar_seq(wav, _sequencia(3).resumo(ganho=2))
    assert json_.name == "take_001.seq.json"
    dados = json.loads(json_.read_text())
    assert {"blocos", "primeiro_seq", "ultimo_seq", "lacunas", "ganho"} <= dados.keys()


def test_nenhum_destino_dentro_do_repo_e_o_nome_da_sessao_tem_forma(tmp_path):
    with pytest.raises(ValueError, match="dentro do repo"):
        coleta.destino_seguro(RAIZ / "data", "2026-11-22_piloto", "real_positive")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        coleta.destino_seguro(tmp_path, "piloto", "real_positive")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        coleta.destino_seguro(tmp_path, "2026-11-22_../../x", "real_positive")
    pasta = coleta.destino_seguro(tmp_path, "2026-11-22_piloto", "real_negative")
    assert pasta == (tmp_path / "real_negative" / "2026-11-22_piloto").resolve()


def test_os_niveis_contam_a_saturacao_e_o_rms_por_100_ms():
    amostras = array("h", [1000] * 1600 + [0] * 1600 + [32767] * 10)
    nv = coleta.niveis(amostras)
    assert (nv["pico"], nv["rms_100ms_max"], nv["rms_100ms_min"], nv["saturadas"]) == (
        32767,
        1000,
        0,
        10,
    )


def _take(barulho=None, forca=400) -> array:
    """3,5 s de um fundo fraco (ruído determinístico na faixa) com uma fala (um tom de 500 Hz) em
    1,2–1,9 s, e um barulho opcional somado em 0,45–0,70 s, a janela antes da fala."""
    import math
    import random

    sorteio = random.Random(7)
    amostras = [sorteio.gauss(0, 15) for _ in range(int(3.5 * coleta.TAXA))]

    def somar(de, ate, hz, amplitude):
        for i in range(int(de * coleta.TAXA), int(ate * coleta.TAXA)):
            amostras[i] += amplitude * math.sin(2 * math.pi * hz * i / coleta.TAXA)

    somar(1.2, 1.9, 500, 3_000)
    if barulho is not None:
        somar(0.45, 0.70, barulho, forca)
    return array("h", (int(a) for a in amostras))


def test_o_barulho_que_atrapalha_a_frase_e_apontado():
    assert coleta.pre_fala(_take())["pre_fala_barulho"] is False
    com_barulho = coleta.pre_fala(_take(barulho=1_000, forca=1_500))
    assert com_barulho["pre_fala_barulho"] is True
    # metade da amplitude da fala. O barulho ocupa 3 dos 10 trechos ativos (um pela metade) e puxa a
    # média deles: sqrt((7 + 2 x 0,25 + 0,125) / 10) = 0,873; 0,5 / 0,873 = 0,573
    assert com_barulho["pre_fala_sobre_a_fala"] == pytest.approx(0.573, abs=0.01)


def test_a_respiracao_na_sala_quieta_nao_e_apontada():
    # a H2c1: o fundo caiu de 51 para 16, e a régua sobre o fundo (1,4×) acusou 18 de 38 takes por um
    # som muito abaixo da fala. Este está a mais de 5× o fundo, e a ~8% da fala (o pior dos 38, dele)
    medida = coleta.pre_fala(_take(barulho=1_000, forca=240))
    assert medida["pre_fala_sobre_a_fala"] * medida["fala_na_banda"] > 5 * medida["fundo_na_banda"]
    assert medida["pre_fala_sobre_a_fala"] == pytest.approx(0.08, abs=0.02)
    assert medida["pre_fala_barulho"] is False


def test_o_ronco_abaixo_da_faixa_do_modelo_nao_conta_como_barulho():
    # 20 Hz: o ronco que o piloto mostrou, que o frontend do treino (125–7500 Hz) não vê
    assert coleta.pre_fala(_take(barulho=20, forca=3_000))["pre_fala_barulho"] is False


def test_o_quadro_do_coleta_py_e_o_do_firmware():
    fonte = FIRMWARE.read_text()
    assert "constexpr char MAGICO[4] = {'V', 'K', 'C', '1'};" in fonte
    assert coleta.MAGICO == b"VKC1"
    assert "constexpr int QUADRO_BYTES = 4 + 4 + 4 + 2 + 2 + BLOCO * 2 + 4;" in fonte
    assert coleta.QUADRO_BYTES == 4 + 4 + 4 + 2 + 2 + coleta.BLOCO * 2 + 4
    bloco = re.findall(r"constexpr int BLOCO = (\d+);", fonte)
    taxa = re.findall(r"constexpr uint32_t TAXA = (\d+);", fonte)
    assert bloco == [str(coleta.BLOCO)] and taxa == [str(coleta.TAXA)]
    # o Mac lê o ganho gravado na placa desta linha, na entrada da coleta
    assert 'Serial.printf("\\ncoleta: ganho=%d' in fonte


class _PortaFalsa:
    """A porta da placa: cada `read` devolve o próximo pedaço; guarda o que foi pedido. `reage` pode
    devolver bytes novos quando um pedido chega, como o firmware faz."""

    def __init__(self, pedacos=(), reage=None):
        self.pedacos, self.pedidos, self.reage, self.fechada = list(pedacos), [], reage, False

    def read(self, n):
        return self.pedacos.pop(0) if self.pedacos else b""

    def write(self, dados):
        self.pedidos.append(dados)
        if self.reage:
            self.pedacos += self.reage(dados)

    def flush(self):
        pass

    def close(self):
        self.fechada = True


def test_o_ganho_vem_da_entrada_e_da_linha_de_status():
    # sem nada depois da linha: o leitor não pode segurar o fim dela
    for linha in (b"coleta: ganho=2 taxa=16000\r\n", b"coleta: status ganho=2 seq=9\r\n"):
        placa = coleta.Placa(_PortaFalsa([linha]))
        placa.ler()
        assert placa.ganho == 2
    fonte = FIRMWARE.read_text()
    assert 'Serial.printf("\\ncoleta: status ganho=%d' in fonte


def test_os_pedidos_sao_os_do_firmware_e_o_sinal_cabe_com_folga_no_prazo_dele():
    fonte = FIRMWARE.read_text()
    assert re.findall(r'PEDIDO_COLETA\[\] = "([^"]+)"', fonte) == ["VKC1 COLETA"]
    assert re.findall(r'PEDIDO_USO\[\] = "([^"]+)"', fonte) == ["VKC1 USO"]
    assert coleta.PEDIDO_COLETA == b"VKC1 COLETA\n" and coleta.PEDIDO_USO == b"VKC1 USO\n"
    (sinal_ms,) = re.findall(r"constexpr uint32_t SINAL_MS = (\d+);", fonte)
    assert coleta.SINAL_S * 1000 * 5 <= int(sinal_ms)  # perder 4 sinais seguidos não derruba


def _funcao(nome: str) -> str:
    """O corpo de uma função do firmware, da assinatura à chave que a fecha na coluna 0."""
    forma = re.compile(rf"^void {nome}\([^\n]*\{{\n(.*?)^\}}", re.MULTILINE | re.DOTALL)
    achados = forma.findall(FIRMWARE.read_text())
    assert len(achados) == 1, f"{nome}: {len(achados)}"
    return achados[0]


def test_o_firmware_liga_no_uso_e_so_o_pedido_o_poe_na_coleta():
    fonte = FIRMWARE.read_text()
    assert "bool emColeta = false;" in fonte and fonte.count("emColeta = true;") == 1
    assert "emColeta = true;" in _funcao("entrarNaColeta")
    assert fonte.count("entrarNaColeta();") == 1
    assert "if (lerPedido() == Pedido::Coleta) {\n    entrarNaColeta();" in _funcao("loop")
    # o boot do uso não espera por pedido nenhum, e não existe mais um firmware só de coleta
    assert "lerPedido" not in _funcao("setup")
    assert "MODO_COLETA" not in fonte
    assert "coleta" not in (FIRMWARE.parents[1] / "platformio.ini").read_text()


def test_a_coleta_volta_ao_uso_pelo_pedido_e_sem_o_sinal_do_mac():
    laco = _funcao("lacoDaColeta")
    assert 'if (pedido == Pedido::Uso) voltarAoUso("pedido do Mac");' in laco
    assert 'if (millis() - ultimoSinal > SINAL_MS) voltarAoUso("sem sinal do Mac");' in laco
    assert "ESP.restart();" in _funcao("voltarAoUso")


def test_entrar_insiste_no_pedido_e_so_volta_com_o_ganho_e_um_quadro():
    porta = _PortaFalsa([b"== Viking voz (H1) ==\n", b"", b"coleta: ganho=2 taxa=16000\n"])
    placa = coleta.Placa(porta)
    with pytest.raises(SystemExit, match="não entrou na coleta"):
        placa.entrar(prazo_s=0.1)  # o ganho sem nenhum quadro ainda não é coleta
    assert porta.pedidos[0] == coleta.PEDIDO_COLETA and placa.na_coleta is False
    porta.pedacos = [_quadro(0, 0)]
    placa.entrar(prazo_s=1)
    assert placa.na_coleta is True


def test_o_lixo_do_boot_nao_conta_como_checksum_errado_do_arquivo():
    ruim = bytearray(_quadro(0, 0))
    ruim[50] ^= 0xFF
    placa = coleta.Placa(_PortaFalsa([b"coleta: ganho=2\n" + bytes(ruim) + _quadro(1, 32_000)]))
    placa.entrar(prazo_s=1)
    assert placa.leitor.checksums_errados == 0


def test_na_coleta_o_sinal_se_repete_e_fora_dela_nao(monkeypatch):
    agora = [100.0]
    monkeypatch.setattr(coleta.time, "monotonic", lambda: agora[0])
    porta = _PortaFalsa()
    placa = coleta.Placa(porta)
    placa.ler()
    assert porta.pedidos == []
    placa.na_coleta, placa.ultimo_sinal = True, 100.0
    for _ in range(7):  # 7 leituras, 1 s entre elas: um sinal a cada 2 s
        placa.ler()
        agora[0] += 1.0
    assert porta.pedidos == [coleta.PEDIDO_COLETA] * 3


def test_fechar_pede_o_uso_e_espera_o_pronto(monkeypatch):
    monkeypatch.setattr(coleta, "VOLTAR_S", 1.0)

    def reage(pedido):
        return [_quadro(9, 0), b">>> PRONTO: segure <<<\r\n"] if b"USO" in pedido else []

    porta = _PortaFalsa(reage=reage)
    placa = coleta.Placa(porta)
    placa.na_coleta = True
    assert placa.fechar() is True
    assert porta.pedidos == [coleta.PEDIDO_USO] and porta.fechada


def test_fechar_sem_o_pronto_nao_diz_que_a_voz_voltou(monkeypatch, capsys):
    monkeypatch.setattr(coleta, "VOLTAR_S", 0.05)
    porta = _PortaFalsa()
    assert coleta.Placa(porta).fechar() is False
    assert porta.fechada and "não vi o PRONTO" in capsys.readouterr().out


def _rodada(monkeypatch, quadros, depois=None):
    """Um `coleta.abrir` falso: a placa já na coleta, com os quadros dados, um por leitura. Depois
    deles, `depois` é levantado (o Ctrl-C ou a queda da porta)."""

    class _Placa(coleta.Placa):
        def __init__(self):
            super().__init__(_PortaFalsa())
            self.ganho, self.na_coleta, self.fila, self.fechou = 2, True, list(quadros), 0

        def ler(self):
            if self.fila:
                return [self.fila.pop(0)]
            raise depois or KeyboardInterrupt

        def fechar(self):
            self.fechou += 1
            return True

    placa = _Placa()
    monkeypatch.setattr(coleta, "abrir", lambda url: placa)
    monkeypatch.setattr(coleta, "agora", lambda: _as("2026-11-23T15:00"))
    return placa


def _as(texto):
    from datetime import datetime

    return datetime.fromisoformat(texto).astimezone()


@pytest.mark.parametrize(
    ("instante", "serve"),
    [
        ("2026-11-23T00:01", True),
        ("2026-11-23T23:59", True),
        ("2026-11-24T05:59", True),  # a sessão da noite que passou da meia-noite
        ("2026-11-24T06:01", False),
        ("2026-11-22T23:00", False),
    ],
)
def test_a_pasta_de_outro_dia_e_recusada(monkeypatch, instante, serve):
    monkeypatch.setattr(coleta, "agora", lambda: _as(instante))
    if serve:
        coleta.conferir_dia("2026-11-23_c9_takes")
    else:
        with pytest.raises(ValueError, match="outro dia"):
            coleta.conferir_dia("2026-11-23_c9_takes")


@pytest.mark.parametrize("modo", ["sala", "takes"])
def test_gravar_na_pasta_de_outro_dia_nem_abre_a_placa(monkeypatch, tmp_path, modo):
    _rodada(monkeypatch, [])
    monkeypatch.setattr(coleta, "agora", lambda: _as("2026-11-25T15:00"))

    def nunca(url):
        raise AssertionError("abriu a placa")

    monkeypatch.setattr(coleta, "abrir", nunca)
    extra = ["--minutos", "1"] if modo == "sala" else ["--n", "1"]
    comum = ["--sessao", "2026-11-23_c9_x", "--raiz", str(tmp_path)]
    with pytest.raises(ValueError, match="outro dia"):
        coleta.main([modo, *comum, *extra])
    assert not list(tmp_path.iterdir())


def _quadros(n, valor=1000, pular=()):
    return [
        coleta.Quadro(k, k * coleta.US_POR_BLOCO, 0, array("h", [valor] * coleta.BLOCO))
        for k in range(n)
        if k not in pular
    ]


def _sala(tmp_path):
    comum = ["--minutos", "60", "--raiz", str(tmp_path)]
    codigo = coleta.main(["sala", "--sessao", "2026-11-23_c9_estudio", *comum])
    return codigo, tmp_path / "real_negative" / "2026-11-23_c9_estudio"


def test_a_sala_sai_em_partes_contiguas_sem_perder_amostra(monkeypatch, tmp_path):
    monkeypatch.setattr(coleta, "PARTE_S", 2)
    placa = _rodada(monkeypatch, _quadros(150))
    codigo, pasta = _sala(tmp_path)
    assert codigo == 0 and placa.fechou == 1
    partes = sorted(pasta.glob("*.wav"))
    assert [p.name for p in partes] == ["parte_001.wav", "parte_002.wav", "parte_003.wav"]
    resumos = [json.loads(p.with_suffix(".seq.json").read_text()) for p in partes]
    assert sum(len(coleta._ler_wav(p)) for p in partes) == 150 * coleta.BLOCO
    assert [r["segue_a_parte_anterior"] for r in resumos] == [None, True, True]
    assert all(r["lacunas"] == [] and r["ganho"] == 2 for r in resumos)
    assert all(r["rms_100ms_min"] == 1000 for r in resumos)  # o resto < 100 ms não vira mínimo 0


def test_o_quadro_perdido_na_emenda_das_partes_aparece(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(coleta, "PARTE_S", 2)
    na_emenda = -(-2 * coleta.TAXA // coleta.BLOCO)  # o 1º quadro da 2ª parte
    _rodada(monkeypatch, _quadros(100, pular={na_emenda}))
    _, pasta = _sala(tmp_path)
    segunda = json.loads((pasta / "parte_002.seq.json").read_text())
    assert segunda["segue_a_parte_anterior"] is False and segunda["lacunas"] == []
    assert "emenda" in capsys.readouterr().out


def test_a_placa_que_reinicia_no_meio_reprova_a_parte_e_so_ela(monkeypatch, tmp_path):
    # o Mac dormiu mais de 30 s (ou a placa caiu): ela volta à coleta com o seq e o tempo do zero
    monkeypatch.setattr(coleta, "PARTE_S", 2)
    antes, depois = _quadros(80), _quadros(100)
    _rodada(monkeypatch, antes + depois)
    codigo, pasta = _sala(tmp_path)
    resumos = [json.loads(p.read_text()) for p in sorted(pasta.glob("*.seq.json"))]
    vereditos = [coleta._veredito(r) for r in resumos]
    assert codigo == 1 and len(resumos) == 3
    assert vereditos[0].startswith("✅") and vereditos[1].startswith("❌")  # o reinício é na 2ª
    assert vereditos[2].startswith("✅")


def test_a_queda_no_meio_guarda_o_que_ja_veio(monkeypatch, tmp_path):
    placa = _rodada(monkeypatch, _quadros(100), depois=OSError("a USB saiu"))
    with pytest.raises(OSError):
        _sala(tmp_path)
    (wav,) = (tmp_path / "real_negative" / "2026-11-23_c9_estudio").glob("*.wav")
    assert len(coleta._ler_wav(wav)) == 100 * coleta.BLOCO and wav.with_suffix(".seq.json").exists()
    assert placa.fechou == 1


def test_o_wav_no_disco_vale_antes_de_a_parte_fechar(tmp_path):
    parte = coleta.Parte(tmp_path, 1, None)
    for q in _quadros(100):
        parte.anotar(q)
    parte._wav._file.flush()  # o que um kill -9 deixaria já escrito pelo sistema
    assert len(coleta._ler_wav(parte.caminho)) == 3 * coleta.TAXA  # 3 dos 3,2 s


def test_o_sigterm_salva_como_o_ctrl_c(monkeypatch, tmp_path):
    import os
    import signal

    antes = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}

    def ninguem_tratou(*_):  # sem o tratador do `main`, o SIGTERM derrubaria o próprio pytest
        raise AssertionError("o coleta.py não tratou o SIGTERM")

    signal.signal(signal.SIGTERM, ninguem_tratou)
    placa = _rodada(monkeypatch, _quadros(40))
    original = placa.ler

    def ler():
        if not placa.fila:
            os.kill(os.getpid(), signal.SIGTERM)
            return []
        return original()

    placa.ler = ler
    try:
        codigo, pasta = _sala(tmp_path)
    finally:
        for s, tratador in antes.items():
            signal.signal(s, tratador)
    assert codigo == 0 and placa.fechou == 1 and (pasta / "parte_001.seq.json").exists()


def test_as_saturadas_dizem_em_que_segundo(monkeypatch, tmp_path):
    quadros = _quadros(100)
    quadros[50].amostras[0] = 32767  # a amostra 25.600: o segundo 1
    _rodada(monkeypatch, quadros)
    _, pasta = _sala(tmp_path)
    resumo = json.loads((pasta / "parte_001.seq.json").read_text())
    assert resumo["saturadas"] == 1 and resumo["saturou_em_s"] == [1]


def test_os_niveis_juntados_sao_os_do_arquivo_inteiro():
    a, b = array("h", [100] * 16_000), array("h", [0] * 8_000 + [32767] * 8_000)
    junto = coleta.juntar_niveis(coleta.juntar_niveis(None, coleta.niveis(a)), coleta.niveis(b))
    assert junto == coleta.niveis(a + b)


def test_as_frases_da_rodada_uma_por_take():
    assert coleta.frases_da_rodada("Hey Viking", None, 3) == ["Hey Viking"] * 3
    assert coleta.frases_da_rodada("x", " Hey King ; ei, Vi;", 10) == ["Hey King", "ei, Vi"]
    with pytest.raises(ValueError, match="nenhuma frase"):
        coleta.frases_da_rodada("x", " ; ", 10)


def test_o_take_leva_a_dica_e_a_frase_e_continua_a_numeracao(monkeypatch, tmp_path, capsys):
    relogio = [0.0]
    monkeypatch.setattr(coleta.time, "time", lambda: relogio[0])

    def rodar(*extra):
        placa = _rodada(monkeypatch, _quadros(2_000))
        original = placa.ler

        def ler():
            relogio[0] += 0.032
            return original()

        placa.ler = ler
        comum = ["--sessao", "2026-11-23_c9_takes", "--raiz", str(tmp_path)]
        assert coleta.main(["takes", *comum, *extra]) == 0

    rodar("--n", "2", "--dica", "50 cm, voz normal")
    rodar("--frases", "Hey King", "--dica", "1 m")
    pasta = tmp_path / "real_positive" / "2026-11-23_c9_takes"
    lidos = [json.loads(p.read_text()) for p in sorted(pasta.glob("*.seq.json"))]
    assert [(r["frase"], r["dica"]) for r in lidos] == [
        ("Hey Viking", "50 cm, voz normal"),
        ("Hey Viking", "50 cm, voz normal"),
        ("Hey King", "1 m"),
    ]
    saida = capsys.readouterr().out
    assert "50 cm, voz normal" in saida and "FALE AGORA: Hey King" in saida


def _sessao_pronta(raiz: Path) -> None:
    pares = [("real_positive", "2026-11-23_c9_takes", "take_001", {"frase": "Hey Viking"})]
    pares.append(("real_negative", "2026-11-23_c9_estudio", "parte_001", {}))
    pares.append(("real_positive", "2026-11-22_piloto", "take_001", {"frase": "de outra sessão"}))
    for tipo, sessao, nome, extra in pares:
        wav = raiz / tipo / sessao / f"{nome}.wav"
        coleta.gravar_wav(wav, array("h", [100, -100] * 16_000))
        coleta.gravar_seq(wav, _sequencia(62).resumo(ganho=2, checksums_errados=0, **extra))


def test_o_pacote_leva_so_a_sessao_com_somas_que_batem(tmp_path):
    import hashlib
    import zipfile

    _sessao_pronta(tmp_path)
    destino = coleta.montar_pacote(tmp_path, "2026-11-23_c9", "o take 1 foi de pé")
    with zipfile.ZipFile(destino) as z:
        nomes = {n.removeprefix("2026-11-23_c9/") for n in z.namelist()}
        assert nomes == {
            "LEIA-ME.md",
            "SHA256SUMS",
            "real_positive/2026-11-23_c9_takes/take_001.wav",
            "real_positive/2026-11-23_c9_takes/take_001.seq.json",
            "real_negative/2026-11-23_c9_estudio/parte_001.wav",
            "real_negative/2026-11-23_c9_estudio/parte_001.seq.json",
        }
        somas = z.read("2026-11-23_c9/SHA256SUMS").decode().splitlines()
        assert len(somas) == 5
        for linha in somas:
            soma, nome = linha.split("  ")
            assert hashlib.sha256(z.read(f"2026-11-23_c9/{nome}")).hexdigest() == soma
        leia_me = z.read("2026-11-23_c9/LEIA-ME.md").decode()
    assert "o take 1 foi de pé" in leia_me and "estúdio normal: 0.0 min" in leia_me
    assert "sem o ganho: nenhum" in leia_me
    with pytest.raises(ValueError, match="já existe"):
        coleta.montar_pacote(tmp_path, "2026-11-23_c9")


def test_o_pacote_aponta_o_arquivo_ruim_e_o_barulho_antes_da_fala(tmp_path):
    import zipfile

    _sessao_pronta(tmp_path)
    take = tmp_path / "real_positive" / "2026-11-23_c9_takes" / "take_001.wav"
    ruim = _sequencia(62, pular_seq={10}).resumo(ganho=2, frase="x", pre_fala_barulho=True)
    coleta.gravar_seq(take, ruim)
    with zipfile.ZipFile(coleta.montar_pacote(tmp_path, "2026-11-23_c9")) as z:
        linhas = z.read("2026-11-23_c9/LEIA-ME.md").decode().splitlines()
    (com_lacuna,) = [li for li in linhas if li.startswith("- com lacuna")]
    (barulho,) = [li for li in linhas if li.startswith("- com barulho")]
    assert "take_001" in com_lacuna and "take_001" in barulho


def test_o_pacote_recusa_o_wav_sem_seq_o_repo_e_o_prefixo_torto(tmp_path):
    _sessao_pronta(tmp_path)
    (tmp_path / "real_negative" / "2026-11-23_c9_estudio" / "parte_001.seq.json").unlink()
    with pytest.raises(ValueError, match=r"não tem o \.seq\.json"):
        coleta.montar_pacote(tmp_path, "2026-11-23_c9")
    assert not list(tmp_path.glob("*.zip*"))
    with pytest.raises(ValueError, match="dentro do repo"):
        coleta.montar_pacote(RAIZ / "data", "2026-11-23_c9")
    with pytest.raises(ValueError, match="AAAA-MM-DD"):
        coleta.montar_pacote(tmp_path, "../c9")


def test_a_sala_para_na_amostra_certa_sem_deixar_um_resto(monkeypatch, tmp_path):
    monkeypatch.setattr(coleta, "PARTE_S", 2)
    placa = _rodada(monkeypatch, _quadros(500))  # 16 s de quadros, e o pedido é de 4 s
    # vários quadros por leitura, como na porta de verdade: o corte tem de ser no meio de uma
    placa.ler = lambda: [placa.fila.pop(0) for _ in range(min(7, len(placa.fila)))]
    comum = ["--minutos", str(4 / 60), "--raiz", str(tmp_path)]
    assert coleta.main(["sala", "--sessao", "2026-11-23_c9_estudio", *comum]) == 0
    partes = sorted((tmp_path / "real_negative" / "2026-11-23_c9_estudio").glob("*.wav"))
    tamanhos = [len(coleta._ler_wav(p)) for p in partes]
    assert sum(tamanhos) == 125 * coleta.BLOCO and len(partes) == 2


def test_o_resto_de_uma_gravacao_fica_fora_do_pacote_e_o_leia_me_diz(tmp_path):
    import zipfile

    _sessao_pronta(tmp_path)
    resto = tmp_path / "real_negative" / "2026-11-23_c9_estudio" / "parte_002.wav"
    coleta.gravar_wav(resto, array("h", [0] * coleta.BLOCO))
    coleta.gravar_seq(resto, _sequencia(1).resumo(ganho=2))
    with zipfile.ZipFile(coleta.montar_pacote(tmp_path, "2026-11-23_c9")) as z:
        nomes, leia_me = z.namelist(), z.read("2026-11-23_c9/LEIA-ME.md").decode()
    assert not any("parte_002" in n for n in nomes) and any("parte_001.wav" in n for n in nomes)
    assert "de fora, menores que 1 s" in leia_me and "parte_002" in leia_me
    assert "arquivos: 2;" in leia_me


def test_a_nota_vai_ao_seq_json_e_ao_leia_me_e_se_soma(tmp_path):
    import zipfile

    _sessao_pronta(tmp_path)
    take = "real_positive/2026-11-23_c9_takes/take_001.wav"
    antes = (tmp_path / take).read_bytes()
    comum = ["anotar", "--arquivo", take, "--raiz", str(tmp_path)]
    assert coleta.main([*comum, "--texto", "tosse depois"]) == 0
    assert coleta.main([*comum, "--texto", "cadência lenta"]) == 0
    dados = json.loads((tmp_path / take).with_suffix(".seq.json").read_text())
    assert dados["nota"] == "tosse depois; cadência lenta" and dados["ganho"] == 2
    assert (tmp_path / take).read_bytes() == antes
    with zipfile.ZipFile(coleta.montar_pacote(tmp_path, "2026-11-23_c9")) as z:
        leia_me = z.read("2026-11-23_c9/LEIA-ME.md").decode()
    (linha,) = [li for li in leia_me.splitlines() if take in li and li.startswith("|")]
    assert linha.endswith("| tosse depois; cadência lenta |")
    with pytest.raises(ValueError, match="não é um WAV"):
        coleta.main(["anotar", "--arquivo", "x.wav", "--raiz", str(tmp_path), "--texto", "y"])


def test_os_niveis_na_faixa_nao_ouvem_o_ronco():
    import math

    def tom(hz):
        n = range(2 * coleta.TAXA)
        return [1000 * math.sin(2 * math.pi * hz * i / coleta.TAXA) for i in n]

    assert coleta.niveis_na_faixa(tom(20))["p50"] < 40
    assert coleta.niveis_na_faixa(tom(1_000))["p50"] == pytest.approx(707, rel=0.02)


def test_um_arquivo_sem_o_ganho_nao_sai_como_bom():
    resumo = _sequencia(10).resumo(ganho=None)
    assert not coleta._veredito(resumo).startswith("✅")
    assert coleta._veredito(_sequencia(10).resumo(ganho=2)).startswith("✅")


def test_o_ganho_esta_congelado_em_2():
    """O dono congelou o ganho em 2 (2026-11-22): mudar é retreinar a wake word. Quem mudar este
    número tem de avisar o agente do Colab antes (o comentário do `GANHO` no firmware)."""
    assert re.findall(r"constexpr int GANHO = (\d+);", FIRMWARE.read_text()) == ["2"]
