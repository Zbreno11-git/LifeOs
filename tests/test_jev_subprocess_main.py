"""Testa `_jev_subprocess.main()` de ponta a ponta, fingindo `jev_ultrafast` e `browser_harness`
via `sys.modules` — este venv não tem (nem deve ter) o ambiente real do Jev instalado; ver o
comentário no topo de `_jev_subprocess.py`. Cobre os achados P1 de runner da auditoria do Codex:
estado terminal perdendo para os guardas de limite/loop/prazo (§10.2), e `usage`/`kept_open`
ausentes nos erros de loop e timeout (§10.3/§10.4).
"""

import json
import sys
import types
from typing import ClassVar

import pytest

from lifeos.browser import _jev_subprocess as runner


class _FakeAgent:
    """Substitui `jev_ultrafast.Agent`. `proximos_estados` é preenchido pelo teste antes de
    chamar `main()` e devolvido, em ordem, por `run()`."""

    proximos_estados: ClassVar[list[dict]] = []

    def __init__(self, url, goals):
        self.url = url
        self.goals = goals
        self.browser = types.SimpleNamespace(target="tgt-falso")
        self.fechada = False

    def snapshot(self):
        return self.proximos_estados[-1] if self.proximos_estados else {}

    def run(self):
        # Como o Jev real: `choose` é global de `jev_ultrafast.agent`, lida a cada passo — é isso
        # que faz o envelope de `instalar_protecao` valer. O 1º choose vem ANTES do 1º yield.
        modulo = sys.modules["jev_ultrafast.agent"]
        for estado in self.proximos_estados:
            modulo.choose(estado.get("page") or {}, self.goals, estado.get("history") or [])
            yield estado

    def close(self):
        self.fechada = True


@pytest.fixture()
def jev_falso(monkeypatch):
    """Injeta `jev_ultrafast` e `browser_harness.{admin,helpers}` falsos em `sys.modules` — os
    dois imports adiados que `main()`/`preparar_navegador()` fazem. `monkeypatch.setitem` desfaz
    isso sozinho no fim do teste."""
    fake_jev = types.ModuleType("jev_ultrafast")
    fake_jev.Agent = _FakeAgent

    # O que chegaria aos modelos remotos: cada chamada grava a página recebida. O `choose` devolve
    # uma decisão no formato do Jev real (`_FakeAgent.decisao`, trocável pelo teste do freio).
    enviados = {"choose": [], "field_context": []}
    fake_agent_mod = types.ModuleType("jev_ultrafast.agent")

    def choose_falso(page, goal, history):
        enviados["choose"].append(page)
        return _FakeAgent.decisao

    fake_agent_mod.choose = choose_falso
    fake_agent_mod.field_context = lambda goal, action, page, history: enviados[
        "field_context"
    ].append(page)
    fake_jev.agent = fake_agent_mod
    _FakeAgent.enviados = enviados

    fake_admin = types.ModuleType("browser_harness.admin")
    fake_admin.ensure_daemon = lambda: None
    fake_admin.daemon_browser_ready = lambda: True
    fake_admin.restart_daemon = lambda: None

    fake_helpers = types.ModuleType("browser_harness.helpers")
    fake_helpers.page_info = dict
    fake_helpers.cdp = lambda *a, **k: None

    monkeypatch.setitem(sys.modules, "jev_ultrafast", fake_jev)
    monkeypatch.setitem(sys.modules, "jev_ultrafast.agent", fake_agent_mod)
    monkeypatch.setitem(sys.modules, "browser_harness.admin", fake_admin)
    monkeypatch.setitem(sys.modules, "browser_harness.helpers", fake_helpers)

    _FakeAgent.proximos_estados = []
    _FakeAgent.decisao = {"choice": "wait", "usage": {}}
    return _FakeAgent


def _estado(status: str, n: int, usage: dict | None = None) -> dict:
    historico = [{"action": f"passo{i}", "kind": "click"} for i in range(1, n + 1)]
    estado = {
        "status": status,
        "elapsed_ms": n * 100,
        "history": historico,
        "page": {"url": f"https://x.com/{n}", "title": "T", "text": ""},
    }
    if usage is not None:
        estado["decisions"] = [{"usage": usage}]
    return estado


def _rodar(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["jev-runner", "--url", "https://x.com", "--goal", "g", *args])
    return runner.main()


def _linhas(capsys) -> list[dict]:
    saida = capsys.readouterr().out
    return [json.loads(linha) for linha in saida.splitlines() if linha.strip()]


def test_estado_terminal_vence_o_limite_de_acoes(jev_falso, monkeypatch, capsys):
    """C1: concluir EXATAMENTE na ação-limite é sucesso, não step_budget — o achado §10.2."""
    jev_falso.proximos_estados = [_estado("running", 1), _estado("running", 2), _estado("done", 3)]
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "3")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "result"
    assert terminal["status"] == "done"
    assert codigo == runner.EXIT_DONE


def test_step_budget_ainda_funciona_sem_estado_terminal(jev_falso, monkeypatch, capsys):
    """Controle negativo: sem chegar a done/blocked, o teto de ações continua parando a tarefa."""
    jev_falso.proximos_estados = [
        _estado("running", 1),
        _estado("running", 2),
        _estado("running", 3),
    ]
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "3")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "step_budget"
    assert codigo == runner.EXIT_ERROR


@pytest.mark.parametrize("fechar", [False, True])
def test_step_budget_kept_open_reflete_a_flag_fechar(jev_falso, monkeypatch, capsys, fechar):
    """C3: kept_open tem que refletir o que o `finally` realmente faz com a aba."""
    jev_falso.proximos_estados = [
        _estado("running", 1),
        _estado("running", 2),
        _estado("running", 3),
    ]
    args = ["--timeout", "5", "--max-acoes", "3"]
    if fechar:
        args.append("--fechar")
    _rodar(monkeypatch, *args)
    terminal = _linhas(capsys)[-1]
    assert terminal["kept_open"] is (not fechar)


def test_loop_detected_carrega_usage(jev_falso, monkeypatch, capsys):
    """C2: usage sumia do evento de loop_detected — o custo aconteceu, mas não aparecia."""
    padroes = [
        {"url": "https://x.com/a", "action": "A"},
        {"url": "https://x.com/b", "action": "B"},
    ]
    estados = []
    historico = []
    for i in range(6):
        passo = padroes[i % 2]
        historico = [*historico, {"action": passo["action"], "kind": "click"}]
        estados.append(
            {
                "status": "running",
                "elapsed_ms": (i + 1) * 100,
                "history": list(historico),
                "page": {"url": passo["url"], "title": "T", "text": ""},
                "decisions": [{"usage": {"input_tokens": 5}}],
            }
        )
    jev_falso.proximos_estados = estados
    codigo = _rodar(monkeypatch, "--timeout", "5", "--max-acoes", "50")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "loop_detected"
    assert terminal["usage"]["chamadas"] >= 1
    assert codigo == runner.EXIT_ERROR


def test_timeout_carrega_usage_e_kept_open(jev_falso, monkeypatch, capsys):
    """C2+C3: usage e kept_open sumiam do evento de timeout."""
    jev_falso.proximos_estados = [_estado("running", 1, usage={"input_tokens": 3})]
    codigo = _rodar(monkeypatch, "--timeout", "0", "--max-acoes", "50")
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "error"
    assert terminal["code"] == "timeout"
    assert terminal["usage"]["chamadas"] == 1
    assert terminal["kept_open"] is True
    assert codigo == runner.EXIT_INTERRUPTED


# --- privacidade: envelope de choose/field_context (§6.1) ------------------------------------


def _pagina_sensivel(url: str = "https://x.com/perfil") -> dict:
    return {
        "url": url + "?token=abc",
        "title": "Perfil de 529.982.247-25",
        "text": "cartão 4111 1111 1111 1111 e chave sk-" + "k" * 30,
    }


def test_choose_recebe_pagina_redigida_e_estado_fica_intacto(jev_falso, monkeypatch, capsys):
    """O que vai pro OpenRouter sai redigido; o dict do Jev (usado pra checar frescor) não muda."""
    estado = {**_estado("done", 1), "page": _pagina_sensivel()}
    original = dict(estado["page"])
    jev_falso.proximos_estados = [estado]
    _rodar(monkeypatch, "--timeout", "5")
    (enviada,) = jev_falso.enviados["choose"]
    assert "529.982.247-25" not in enviada["title"]
    assert "4111" not in enviada["text"] and "sk-" not in enviada["text"]
    assert "token=abc" not in enviada["url"]
    assert estado["page"] == original


def test_field_context_tambem_passa_pelo_envelope(jev_falso):
    import jev_ultrafast.agent as agente

    runner.instalar_protecao([])
    agente.field_context("meta", {"label": "Nome"}, _pagina_sensivel(), [])
    (enviada,) = jev_falso.enviados["field_context"]
    assert "529.982.247-25" not in enviada["title"]


def test_dominio_bloqueado_na_pagina_inicial_nao_sai_nada(jev_falso, monkeypatch, capsys):
    """Redirecionamento na página inicial: o 1º choose roda antes do 1º yield, então o bloqueio
    precisa estar no envelope — nenhuma chamada ao modelo, nenhuma página devolvida."""
    estado = {**_estado("running", 1), "page": _pagina_sensivel("https://www.itau.com.br/conta")}
    jev_falso.proximos_estados = [estado]
    codigo = _rodar(monkeypatch, "--timeout", "5", "--bloquear", "itau.com.br")
    terminal = _linhas(capsys)[-1]
    assert jev_falso.enviados["choose"] == []
    assert terminal["code"] == "dominio_bloqueado"
    assert "itau.com.br" in terminal["message"]
    assert "page_text" not in terminal and "title" not in terminal
    assert codigo == runner.EXIT_ERROR


def test_field_context_bloqueia_dominio(jev_falso):
    import jev_ultrafast.agent as agente

    runner.instalar_protecao(["mail.google.com"])
    with pytest.raises(RuntimeError, match="dominio-bloqueado"):
        agente.field_context("meta", {}, {"url": "https://mail.google.com/mail/u/0"}, [])
    assert jev_falso.enviados["field_context"] == []


@pytest.mark.parametrize("sumiu", ["choose", "field_context"])
def test_sem_as_funcoes_do_jev_recusa_navegar(jev_falso, monkeypatch, capsys, sumiu):
    """Fecha em falha: sem ponto de redação, nada de navegar — nem health check, nem Agent."""
    monkeypatch.delattr(sys.modules["jev_ultrafast.agent"], sumiu)
    jev_falso.proximos_estados = [_estado("done", 1)]
    codigo = _rodar(monkeypatch, "--timeout", "5")
    eventos = _linhas(capsys)
    assert eventos[-1]["code"] == "protecao_indisponivel"
    assert not any(e["type"] in {"health", "step"} for e in eventos)
    assert codigo == runner.EXIT_ERROR


def test_sem_o_modulo_agent_recusa_navegar(jev_falso, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "jev_ultrafast.agent", None)
    jev_falso.proximos_estados = [_estado("done", 1)]
    _rodar(monkeypatch, "--timeout", "5")
    assert _linhas(capsys)[-1]["code"] == "protecao_indisponivel"


# --- freio de cliques que agem sobre a conta (Sessão 4b, §5.2) -----------------------------


def _pagina_com_clique(rotulo: str, href: str | None = None, guards=None) -> dict:
    guard = [None] * 14
    guard[12] = href
    return {
        "url": "https://loja.example/conta",
        "title": "Minha conta",
        "text": "texto da página",
        "actions": [{"id": "e1", "kind": "click", "label": rotulo, "node": 7}],
        "guards": {"7": guard} if guards is None else guards,
    }


def _rodar_decidindo(jev_falso, monkeypatch, pagina: dict, decisao: dict) -> int:
    jev_falso.proximos_estados = [{**_estado("done", 0), "page": pagina}]
    jev_falso.decisao = decisao
    return _rodar(monkeypatch, "--timeout", "5")


def test_clique_em_sair_e_recusado_antes_de_executar(jev_falso, monkeypatch, capsys):
    """A tarefa para no envelope, antes de o Jev ter o que executar; a aba fica aberta, o rótulo
    vai na mensagem, e a decisão recusada (paga) entra no custo."""
    decisao = {"choice": "e1", "usage": {"prompt_tokens": 100}}
    codigo = _rodar_decidindo(jev_falso, monkeypatch, _pagina_com_clique("Sair"), decisao)
    eventos = _linhas(capsys)
    terminal = eventos[-1]
    assert terminal["code"] == "acao_sensivel"
    assert terminal["message"] == "acao-sensivel: sair: Sair"
    assert terminal["kept_open"] is True
    assert terminal["title"] == "Minha conta"  # não é domínio bloqueado: a página volta
    assert terminal["usage"] == {"prompt_tokens": 100, "chamadas": 1}
    assert not any(e["type"] == "step" for e in eventos)
    assert codigo == runner.EXIT_ERROR


@pytest.mark.parametrize(
    ("rotulo", "href", "categoria"),
    [
        ("link", "/logout", "sair"),
        ("Excluir minha conta", None, "conta"),
        ("Finalizar compra", None, "dinheiro"),
    ],
)
def test_cada_categoria_para_pelo_envelope(jev_falso, monkeypatch, capsys, rotulo, href, categoria):
    pagina = _pagina_com_clique(rotulo, href)
    _rodar_decidindo(jev_falso, monkeypatch, pagina, {"choice": "e1"})
    terminal = _linhas(capsys)[-1]
    assert terminal["code"] == "acao_sensivel"
    assert terminal["message"].startswith(f"acao-sensivel: {categoria}: ")


@pytest.mark.parametrize("decisao", [{"choice": "e1"}, {"choice": "DONE"}, {"choice": "wait"}])
def test_clique_comum_e_controles_seguem(jev_falso, monkeypatch, capsys, decisao):
    _rodar_decidindo(jev_falso, monkeypatch, _pagina_com_clique("Buscar"), decisao)
    terminal = _linhas(capsys)[-1]
    assert terminal["type"] == "result"
    assert terminal["status"] == "done"


@pytest.mark.parametrize("decisao", [None, {}, {"choice": 3}, "e1"])
def test_decisao_sem_choice_recusa_navegar(jev_falso, monkeypatch, capsys, decisao):
    """O freio não sabe o que seria clicado: fecha em falha, não deixa passar."""
    _rodar_decidindo(jev_falso, monkeypatch, _pagina_com_clique("Buscar"), decisao)
    assert _linhas(capsys)[-1]["code"] == "protecao_indisponivel"


@pytest.mark.parametrize("guards", ["sem", {"7": [None] * 13}, {"7": {"href": "/x"}}])
def test_layout_de_guards_diferente_recusa_navegar(jev_falso, monkeypatch, capsys, guards):
    pagina = _pagina_com_clique("Buscar", guards=guards)
    if guards == "sem":
        del pagina["guards"]
    _rodar_decidindo(jev_falso, monkeypatch, pagina, {"choice": "e1"})
    assert _linhas(capsys)[-1]["code"] == "protecao_indisponivel"


def _itens_do_array_js(fonte: str, abre: int) -> list[str]:
    """Itens de nível zero de um array literal de JS que começa em `fonte[abre] == "["`. Conta
    parênteses/colchetes/chaves e ignora vírgulas dentro de strings — `slice(0,6000)` tem uma."""
    itens, atual, profundidade, aspas = [], [], 0, None
    for c in fonte[abre + 1 :]:
        if aspas:
            aspas = None if c == aspas else aspas
        elif c in "'\"`":
            aspas = c
        elif c in "([{":
            profundidade += 1
        elif c in ")]}":
            if profundidade == 0:
                itens.append("".join(atual).strip())
                return itens
            profundidade -= 1
        elif c == "," and profundidade == 0:
            itens.append("".join(atual).strip())
            atual = []
            continue
        atual.append(c)
    raise AssertionError("array sem fim")


def test_contrato_do_freio_com_o_jev_real():
    """O freio só vale se (1) o Jev executar exatamente a ação que `choose` devolveu, achada pelo
    `id` em `page["actions"]`, e (2) `page["guards"][node]` tiver `href` e o texto do contêiner
    nos índices que `_acoes_sensiveis` lê. Se o upstream mudar qualquer um, o freio seria
    contornado ou cegado em silêncio — este teste falha antes. Lê o código, sem executar."""
    import ast

    from lifeos.browser import _acoes_sensiveis
    from lifeos.config import JEV_DIR

    agente = JEV_DIR / "jev_ultrafast" / "agent.py"
    snapshot = JEV_DIR / "jev_ultrafast" / "snapshot.js"
    if not agente.is_file() or not snapshot.is_file():
        pytest.skip(f"clone do Jev ausente em {JEV_DIR}")

    def chave(no) -> str | None:
        if isinstance(no, ast.Subscript) and isinstance(no.slice, ast.Constant):
            return no.slice.value
        return None

    arvore = ast.parse(agente.read_text())
    decide = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign)
        and chave(no.targets[0]) == "decision"
        and isinstance(no.value, ast.Call)
        and getattr(no.value.func, "id", None) == "choose"
    ]
    assert decide, 'o Jev não faz mais `state["decision"] = choose(...)`'
    escolhe = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign)
        and getattr(no.targets[0], "id", None) == "selected"
        and chave(no.value) == "choice"
    ]
    assert escolhe, 'o Jev não lê mais `selected = decision["choice"]`'
    busca = [
        gerador
        for gerador in ast.walk(arvore)
        if isinstance(gerador, ast.comprehension)
        and chave(gerador.iter) == "actions"
        and any(
            isinstance(cond, ast.Compare)
            and chave(cond.left) == "id"
            and getattr(cond.comparators[0], "id", None) == "selected"
            for cond in gerador.ifs
        )
    ]
    assert busca, 'o Jev não acha mais a ação por `a["id"] == selected` em `page["actions"]`'

    fonte = snapshot.read_text()
    inicio = fonte.index("cache.guard=")
    itens = _itens_do_array_js(fonte, fonte.index("return [", inicio) + len("return "))
    assert len(itens) == _acoes_sensiveis.GUARD_TAMANHO, itens
    assert "getAttribute('href')" in itens[_acoes_sensiveis.GUARD_HREF]
    assert "innerText" in itens[_acoes_sensiveis.GUARD_ESCOPO]


def test_contrato_com_o_jev_real():
    """O envelope só funciona se o Jev chamar `choose`/`field_context` como globais de
    `jev_ultrafast.agent`, importadas de `.model`. Se o upstream mudar isso (ex.: `model.choose(...)`
    ou um import local), o envelope seria contornado EM SILÊNCIO — este teste falha antes.
    Lê o código do clone, sem executar nada do Jev."""
    import ast

    from lifeos.config import JEV_DIR

    fonte = JEV_DIR / "jev_ultrafast" / "agent.py"
    if not fonte.is_file():
        pytest.skip(f"clone do Jev ausente em {JEV_DIR}")
    arvore = ast.parse(fonte.read_text())

    importados = {
        alias.asname or alias.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom) and no.module == "model" and no.level == 1
        for alias in no.names
    }
    chamados = {
        no.func.id
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }
    for nome in ("choose", "field_context"):
        assert nome in importados, f"{nome} não vem mais de `from .model import`"
        assert nome in chamados, f"{nome} não é mais chamado como nome global"
