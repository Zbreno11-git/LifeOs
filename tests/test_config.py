"""`lifeos.config` é importado por todo módulo do Viking — um bug aqui derruba qualquer comando.
Testa as funções puras de resolução de caminho e validação numérica diretamente, e um caso de
ponta a ponta via subprocesso (a única forma segura de provar "isso quebra o import de verdade"
sem contaminar o `sys.modules` do resto da suíte)."""

import os
import subprocess
import sys

import pytest

from lifeos import config

# --- _path_env -----------------------------------------------------------------------------


def test_path_env_sem_variavel_usa_o_default(monkeypatch, tmp_path):
    monkeypatch.delenv("VIKING_TESTE_PATH", raising=False)
    default = tmp_path / "default.json"
    assert config._path_env("VIKING_TESTE_PATH", default) == default


def test_path_env_relativo_ancora_em_repo_root_nao_no_cwd(monkeypatch, tmp_path):
    """O achado real: hoje um valor relativo resolve contra o cwd de quem chamou o comando."""
    monkeypatch.setenv("VIKING_TESTE_PATH", "secrets/alguma_coisa.json")
    monkeypatch.chdir(tmp_path)  # cwd bem longe de REPO_ROOT, de propósito
    resultado = config._path_env("VIKING_TESTE_PATH", config.REPO_ROOT / "default.json")
    assert resultado == config.REPO_ROOT / "secrets" / "alguma_coisa.json"


def test_path_env_absoluto_passa_direto(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_PATH", "/tmp/algum/caminho.json")
    resultado = config._path_env("VIKING_TESTE_PATH", config.REPO_ROOT / "default.json")
    assert resultado == config.Path("/tmp/algum/caminho.json").resolve()


def test_path_env_expande_til_antes_de_ancorar(monkeypatch):
    """Ordem importa: expanduser() tem que rodar ANTES do join com REPO_ROOT, senão "~" vira um
    caractere literal dentro do caminho do repo em vez de virar a pasta pessoal real."""
    monkeypatch.setenv("VIKING_TESTE_PATH", "~/alguma-pasta")
    resultado = config._path_env("VIKING_TESTE_PATH", config.REPO_ROOT / "default.json")
    assert "~" not in resultado.parts
    assert resultado == (config.Path.home() / "alguma-pasta").resolve()


# --- _float_env / _int_env -------------------------------------------------------------------


def test_float_env_usa_default_quando_env_ausente(monkeypatch):
    monkeypatch.delenv("VIKING_TESTE_NUM", raising=False)
    assert config._float_env("VIKING_TESTE_NUM", "180") == 180.0


def test_float_env_valor_nao_numerico_levanta_erro_com_nome_da_variavel(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_NUM", "abc")
    with pytest.raises(ValueError, match="VIKING_TESTE_NUM"):
        config._float_env("VIKING_TESTE_NUM", "180")


@pytest.mark.parametrize("bruto", ["nan", "inf", "-inf", "Infinity"])
def test_float_env_rejeita_nan_e_infinito(monkeypatch, bruto):
    """float() do Python aceita "nan"/"inf" sem levantar ValueError — sem esta checagem, um
    timeout não-finito quebra comparações a jusante em silêncio (NaN nunca é <= nada)."""
    monkeypatch.setenv("VIKING_TESTE_NUM", bruto)
    with pytest.raises(ValueError, match="finito"):
        config._float_env("VIKING_TESTE_NUM", "180")


def test_float_env_recusa_zero_e_negativo_por_padrao(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_NUM", "0")
    with pytest.raises(ValueError):
        config._float_env("VIKING_TESTE_NUM", "180")
    monkeypatch.setenv("VIKING_TESTE_NUM", "-5")
    with pytest.raises(ValueError):
        config._float_env("VIKING_TESTE_NUM", "180")


def test_float_env_inclusive_aceita_zero(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_NUM", "0")
    assert config._float_env("VIKING_TESTE_NUM", "180", inclusive=True) == 0.0


def test_float_env_inclusive_ainda_recusa_negativo(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_NUM", "-0.01")
    with pytest.raises(ValueError):
        config._float_env("VIKING_TESTE_NUM", "180", inclusive=True)


def test_int_env_usa_default_quando_env_ausente(monkeypatch):
    monkeypatch.delenv("VIKING_TESTE_INT", raising=False)
    assert config._int_env("VIKING_TESTE_INT", "30") == 30


def test_int_env_valor_nao_numerico_levanta_erro_com_nome_da_variavel(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_INT", "trinta")
    with pytest.raises(ValueError, match="VIKING_TESTE_INT"):
        config._int_env("VIKING_TESTE_INT", "30")


def test_int_env_recusa_zero_e_negativo(monkeypatch):
    monkeypatch.setenv("VIKING_TESTE_INT", "0")
    with pytest.raises(ValueError):
        config._int_env("VIKING_TESTE_INT", "30")
    monkeypatch.setenv("VIKING_TESTE_INT", "-1")
    with pytest.raises(ValueError):
        config._int_env("VIKING_TESTE_INT", "30")


def test_defaults_atuais_nao_regrediram():
    """Guarda de regressão: os valores publicados hoje continuam os mesmos depois da validação."""
    assert config.BROWSER_TIMEOUT_S == 180.0
    assert config.BROWSER_MAX_ACOES == 30
    assert config.PRECO_GEMINI_ENTRADA == 0.30
    assert config.PRECO_GEMINI_SAIDA == 2.50


# --- integração via subprocesso ---------------------------------------------------------------


def test_env_invalido_derruba_o_import_com_mensagem_clara():
    """Prova de ponta a ponta: precisa ser subprocesso, porque `lifeos.config` (e tudo que o
    importa) já está em `sys.modules` neste processo de teste — um `importlib.reload` não
    atualizaria os nomes já importados em outros módulos."""
    resultado = subprocess.run(
        [sys.executable, "-c", "import lifeos.config"],
        capture_output=True,
        text=True,
        env={**os.environ, "VIKING_BROWSER_TIMEOUT_S": "abc"},
        cwd=str(config.REPO_ROOT / "src"),
        check=False,
    )
    assert resultado.returncode != 0
    assert "VIKING_BROWSER_TIMEOUT_S" in resultado.stderr
