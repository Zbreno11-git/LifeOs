"""Protege o contrato entre as tools do Viking e o function-calling do google-genai."""

import inspect

import pytest
from google.genai import _automatic_function_calling_util as afc

from lifeos.assistant.agent import FERRAMENTAS


@pytest.mark.parametrize("fn", FERRAMENTAS, ids=lambda f: f.__name__)
def test_anotacoes_sao_tipos_reais(fn):
    """`from __future__ import annotations` transforma anotações em strings e o google-genai
    valida argumentos com isinstance() — com string vira
    `isinstance() arg 2 must be a type...` em toda chamada que passe argumento.
    Bug real observado em 2026-09-21; este teste existe para ele não voltar.
    """
    for nome, p in inspect.signature(fn).parameters.items():
        assert not isinstance(p.annotation, str), (
            f"{fn.__name__}({nome}): anotação virou string — remova "
            f"`from __future__ import annotations` do módulo que define esta tool"
        )


@pytest.mark.parametrize("fn", FERRAMENTAS, ids=lambda f: f.__name__)
def test_schema_aceito_pelo_google_genai(fn):
    for p in inspect.signature(fn).parameters.values():
        afc._parse_schema_from_parameter("VERTEX_AI", p, fn.__name__)


@pytest.mark.parametrize("fn", FERRAMENTAS, ids=lambda f: f.__name__)
def test_toda_tool_tem_docstring(fn):
    """A docstring vira a descrição que o modelo lê para decidir se chama a tool."""
    assert (fn.__doc__ or "").strip()


def test_hoje_tem_dia_da_semana_valido():
    from lifeos.assistant.agent import _DIAS, _hoje

    texto = _hoje()
    assert any(dia in texto for dia in _DIAS)
    assert "domingo-feira" not in texto and "sábado-feira" not in texto
