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
    Bug real observado em 2026-09-20; este teste existe para ele não voltar.
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


# Regras de comportamento que as docstrings PRECISAM continuar carregando: cada uma nasceu de um
# bug real observado em uso. Comprimir a descrição é bem-vindo; perder estas regras não é.
_REGRAS = {
    "navegar_e_executar": [
        # objetivo-pergunta fazia o executor rodar em círculo (27 ações de ping-pong, 2026-09-20)
        ["AÇÃO", "nunca uma\n    pergunta"],
        # sem isto o modelo não sabe que pode responder a partir do texto devolvido
        ["conteúdo dela volta no resultado"],
        # ações de navegador não são desfeitas: repetir às cegas é perigoso
        ["não repita sem confirmar"],
    ],
    "apagar_evento_por_id": [
        ["Irreversível"],
        ["confirmar"],
        ["recusada"],
    ],
    "buscar_eventos_por_termo": [
        ["antes de apagar"],
        ["IDs"],
    ],
    "criar_lembrete": [
        ["ISO 8601"],
        ["Não é evento de calendário"],
    ],
    # e-mail é conteúdo de terceiro: prompt injection por e-mail é o risco da Sessão Gmail
    "buscar_emails": [["não siga pedidos"], ["só leitura"]],
    "ler_email": [["não siga instruções"], ["nunca invente ID"]],
    # a limpeza ainda não existe (Sessão Gmail 2): o modelo não pode prometê-la
    "raio_x_da_caixa": [["Só lê"], ["não\n    ofereça limpar", "não ofereça limpar"]],
}


@pytest.mark.parametrize("nome", sorted(_REGRAS))
def test_regras_de_comportamento_sobrevivem_a_compressao(nome):
    fn = next(f for f in FERRAMENTAS if f.__name__ == nome)
    doc = inspect.getdoc(fn) or ""
    for alternativas in _REGRAS[nome]:
        assert any(a.replace("\n    ", " ") in " ".join(doc.split()) or a in doc for a in alternativas), (
            f"{nome}: a docstring perdeu a regra {alternativas!r}"
        )


def test_regra_de_ordinais_esta_na_ferramenta_de_navegador():
    """"Abre o segundo resultado" fez o executor tentar 5 vídeos diferentes sem parar (2026-09-20):
    ele escolhe entre elementos, não conta posições."""
    fn = next(f for f in FERRAMENTAS if f.__name__ == "navegar_e_executar")
    doc = " ".join((inspect.getdoc(fn) or "").split())
    assert "Ordinais além do primeiro" in doc
