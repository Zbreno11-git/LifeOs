import re
import subprocess
import sys
from pathlib import Path

import pytest

from lifeos.browser.jev_runner import SCRIPT_PATH, BrowserResult
from lifeos.browser.mensagens import MENSAGENS, formatar


def _resultado(**kwargs) -> BrowserResult:
    base = {"status": "error", "goals": ("objetivo",)}
    return BrowserResult(**{**base, **kwargs})


@pytest.mark.parametrize("codigo", sorted(MENSAGENS))
def test_todo_codigo_tem_mensagem_utilizavel(codigo):
    texto = formatar(_resultado(error_code=codigo, error_detail="detalhe tecnico"))
    assert MENSAGENS[codigo] in texto
    assert "{" not in texto and "}" not in texto


def test_codigo_desconhecido_cai_no_generico_com_detalhe():
    texto = formatar(_resultado(error_code="codigo_que_nao_existe", error_detail="pane X"))
    assert "pane X" in texto


def test_erro_com_acoes_executadas_avisa_que_nada_foi_desfeito():
    texto = formatar(_resultado(error_code="model_http", steps=2))
    assert "Nada do que já foi feito" in texto


def test_falha_antes_de_agir_nao_fala_da_pagina():
    """uv/pasta/daemon ausentes falham antes de tocar em qualquer página — não confundir o usuário."""
    texto = formatar(_resultado(error_code="jev_dir_missing", error_detail="/tmp/x", steps=0))
    assert "desfeito" not in texto
    assert "/tmp/x" in texto


def test_erros_parciais_avisam_que_pode_estar_pela_metade():
    texto = formatar(_resultado(error_code="timeout", steps=4))
    assert "parcialmente feita" in texto
    assert "4 ações" in texto


def test_sucesso_marca_conteudo_nao_confiavel_e_relativiza_o_done():
    texto = formatar(
        _resultado(
            status="done",
            steps=3,
            elapsed_ms=4200,
            url="https://x.com",
            title="Titulo",
            history=({"action": "Click 'ok'"},),
            page_text="conteudo da pagina",
        )
    )
    assert "não é prova de sucesso" in texto
    assert "não confiável" in texto
    assert "4,2s" in texto
    assert "Click 'ok'" in texto


def test_blocked_nao_e_tratado_como_erro():
    texto = formatar(_resultado(status="blocked", steps=7, elapsed_ms=1000))
    assert "parou sem concluir" in texto
    assert "❌" not in texto


def test_runner_nao_importa_lifeos():
    """O runner roda sob o interpretador do Jev — não pode depender do pacote do Viking."""
    imports = re.findall(r"^\s*(?:from|import)\s+lifeos", SCRIPT_PATH.read_text(), re.MULTILINE)
    assert imports == []


def test_runner_compila_e_falha_sem_argumentos():
    origem = SCRIPT_PATH.read_text()
    compile(origem, str(SCRIPT_PATH), "exec")
    # Sem argumentos o argparse barra ANTES do `import jev_ultrafast`, então roda aqui.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], capture_output=True, text=True, check=False
    )
    assert proc.returncode != 0
    assert proc.stdout.strip() == ""
    assert Path(SCRIPT_PATH).name in proc.stderr or "usage" in proc.stderr


def test_imprimir_progresso_avisa_recuperacao_do_daemon(capsys):
    from lifeos.browser import imprimir_progresso

    imprimir_progresso({"type": "health", "state": "reiniciado"})
    imprimir_progresso({"type": "health", "state": "ok"})
    saida = capsys.readouterr().err
    assert "reiniciei" in saida
    assert saida.count("\n") == 1  # estado "ok" não polui a tela


def test_classificacao_de_preflight_no_runner():
    """O runner precisa reconhecer a própria falha de preflight, não cair em 'unknown'."""
    origem = SCRIPT_PATH.read_text()
    assert '"browser_not_ready"' in origem
    assert "browser-not-ready" in origem


def test_blocked_avisa_que_pode_ter_dado_certo():
    """Validado ao vivo: o executor devolveu 'blocked' numa tarefa que na verdade funcionou."""
    texto = formatar(
        _resultado(status="blocked", steps=1, url="https://www.iana.org/help/example-domains")
    )
    assert "não é prova de fracasso" in texto
