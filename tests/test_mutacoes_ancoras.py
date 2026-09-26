"""As âncoras de `scripts/mutacoes.py` continuam valendo — sem rodar mutação nenhuma.

O script roda à mão e poucas vezes; uma refatoração que muda a linha que ele mira faria a lista
apodrecer em silêncio até a próxima rodada. Aqui a suíte normal reprova no mesmo dia: cada âncora
casa exatamente uma vez, a troca muda código (não comentário) e o teste esperado existe.
"""

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _script():
    if "mutacoes" in sys.modules:
        return sys.modules["mutacoes"]
    spec = importlib.util.spec_from_file_location("mutacoes", RAIZ / "scripts" / "mutacoes.py")
    modulo = importlib.util.module_from_spec(spec)
    # `@dataclass` com anotações adiadas procura o módulo em `sys.modules` ao montar a classe.
    sys.modules["mutacoes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_todas_as_ancoras_casam_uma_vez_e_nao_sao_inertes():
    mutacoes = _script()
    assert mutacoes._recusas(mutacoes.MUTACOES) == []


def test_teste_esperado_existe_no_arquivo():
    """Nome de teste renomeado deixaria a mutação sem juiz; a partida do script também confere."""
    for m in _script().MUTACOES:
        arquivo, nome = m.esperado.split("::")
        assert f"def {nome}(" in (RAIZ / arquivo).read_text(), m.esperado


def test_lista_cobre_as_regras_de_apagar_acessar_e_egress():
    """Piso derivado da própria lista: encolher sem querer reprova."""
    nomes = " ".join(m.nome for m in _script().MUTACOES)
    for tema in ("calendário", "mcp", "bloqueio", "envelope", "freio", "delimitador", "redação"):
        assert tema in nomes, tema
    assert len(_script().MUTACOES) >= 15
