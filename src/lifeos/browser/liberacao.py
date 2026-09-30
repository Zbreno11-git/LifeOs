"""Liberar, uma vez, um clique que o freio recusou (Sessão 5, D38).

O freio (`_acoes_sensiveis`) recusa sair, mexer na conta e gastar dinheiro. Quando o clique
recusado é de **sair** ou **conta**, o Viking propõe liberá-lo: o código aparece só no terminal do
dono (`ao_dono`), nunca no texto que o Gemini lê. Aprovado, o Viking abre de novo a página da
recusa e o executor persegue um objetivo escrito aqui ("clicar no botão «Sair»"), com
`--liberar-uma`: o subprocesso deixa passar só aquele clique, uma vez. **Dinheiro nunca**.

Quem aprova é o laço do chat (`assistant/agent.aprovacao_local`) ou `viking browser` (`cli.py`),
nunca uma tool — a mesma regra da limpeza do Gmail (D26/D30). A URL reaberta é a **redigida**
(a mesma do registro): uma URL com token ou código de login não vai ao banco nem é reaberta.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from lifeos import ao_dono as ao_dono_
from lifeos import aprovacoes, confirmacao, custos
from lifeos.browser import _acoes_sensiveis
from lifeos.browser._redacao import limpar_controles
from lifeos.browser.jev_runner import BrowserResult, run_jev
from lifeos.browser.mensagens import formatar
from lifeos.config import TIMEZONE

ACAO = aprovacoes.NAVEGADOR_CLIQUE
# A reexecução é curta: abrir, achar o botão, clicar e declarar conclusão.
TIMEOUT_S = 60.0
MAX_ACOES = 5
MAX_URL_EXIBIDA = 100

AVISO_AO_GEMINI = (
    "O Viking mostrou ao usuário, fora de você, como liberar só esse clique, uma vez (você não "
    "vê o código). Se ele quiser, ele mesmo digita a aprovação no terminal: não repita a tarefa "
    "nem peça o código."
)
_CATEGORIAS = {"sair": "sair da conta", "conta": "mexer na conta"}


def terminal_interativo() -> bool:
    """O código só se mostra a uma pessoa: sem terminal nos dois lados (`--json`, pipe, MCP),
    não há proposta (`lifeos/ao_dono.py`)."""
    return ao_dono_.interativo()


def ao_dono(texto: str) -> None:
    """Fora do retorno da tool: o Gemini só lê o que a função devolve (`lifeos/ao_dono.py`)."""
    ao_dono_.mostrar(texto)


def _exibido(resultado: BrowserResult) -> str:
    """O rótulo como a página o mostrou, da mensagem do freio (`acao-sensivel: <cat>: <rótulo>`)."""
    _, _, resto = (resultado.error_detail or "").partition("acao-sensivel: ")
    return resto.partition(": ")[2].strip()


def propor(resultado: BrowserResult) -> confirmacao.Proposta | None:
    """A proposta de liberar o clique recusado, ou `None` se ele não se libera. Confere de novo o
    que o subprocesso já conferiu: categoria de dinheiro, digital fora da forma, site diferente."""
    bruto = resultado.acao_sensivel
    if resultado.error_code != "acao_sensivel" or not resultado.liberavel or bruto is None:
        return None
    digital = {c: bruto[c] for c in sorted(_acoes_sensiveis.CAMPOS_DIGITAL)}
    try:
        _acoes_sensiveis.ler_liberacao(json.dumps(digital))
    except ValueError:
        return None
    if _acoes_sensiveis.esquema_host(bruto["url"]) != digital["esquema_host"]:
        return None
    dados = {"url": bruto["url"], "digital": digital, "exibido": _exibido(resultado)}
    try:
        return confirmacao.propor(ACAO, dados)
    except confirmacao.ErroConfirmacao:
        return None


def texto_da_proposta(proposta: confirmacao.Proposta, *, no_chat: bool = True) -> str:
    dados = proposta.dados
    digital = dados["digital"]
    botao = limpar_controles(dados["exibido"] or digital["rotulo"])
    url = limpar_controles(dados["url"])
    if len(url) > MAX_URL_EXIBIDA:
        url = url[:MAX_URL_EXIBIDA] + "…"
    quando = proposta.expira.astimezone(TIMEZONE).strftime("%H:%M")
    como = (
        f"digite `confirma {proposta.codigo}`" if no_chat else f"digite o código {proposta.codigo}"
    )
    return (
        f"🔐 O navegador parou antes de clicar em «{botao}» "
        f"({_CATEGORIAS[digital['categoria']]}) em {digital['esquema_host']}.\n"
        f"   Se era isso mesmo, o Viking faz só esse clique, uma vez: abre de novo {url} e clica "
        "nesse botão — em nenhum outro que saia da conta, mexa nela ou gaste dinheiro.\n"
        f"   Para liberar, {como} (vale até as {quando})."
    )


def clicar_aprovado(
    codigo: str, *, on_progress: Callable[[dict], None] | None = None
) -> tuple[str, BrowserResult]:
    """Gasta o código e faz o clique liberado numa execução curta. (texto para o dono, resultado).
    O objetivo é do Viking; nada do objetivo original volta. `ErroConfirmacao` se o código não
    serve."""
    aprovado = confirmacao.consumir(ACAO, codigo)
    dados = aprovado.dados
    digital = _acoes_sensiveis.ler_liberacao(json.dumps(dados["digital"]))
    botao = dados["exibido"] or digital["rotulo"]
    resultado = run_jev(
        dados["url"],
        [f"clicar no botão «{botao}»"],
        timeout_s=TIMEOUT_S,
        max_acoes=MAX_ACOES,
        liberar=digital,
        on_progress=on_progress,
    )
    confirmacao.registrar(aprovado.id, {"status": resultado.status, "liberado": resultado.liberado})
    custos.SESSAO.navegador = custos.SESSAO.navegador + custos.do_jev(resultado.usage)
    return texto_do_clique(limpar_controles(botao), resultado), resultado


def texto_do_clique(botao: str, resultado: BrowserResult) -> str:
    if resultado.liberado and resultado.status != "error":
        return f"✅ Cliquei em «{botao}», uma vez. A aba ficou aberta."
    if resultado.liberado and resultado.error_code == "acao_sensivel":
        return (
            f"✅ Cliquei em «{botao}», uma vez. Depois o executor quis outro clique que age sobre "
            "a conta, e eu parei: nada além disso foi clicado."
        )
    if resultado.liberado:
        return (
            f"⚠️ Liberei o clique em «{botao}», e depois o executor falhou: o clique pode ter "
            f"acontecido — confira a aba.\n{formatar(resultado)}"
        )
    if resultado.status == "error" and not resultado.steps:
        # Ocupado por outra tarefa (Sessão 6), sem uv, sem Chrome...: nem abriu a página.
        return (
            f"Não cliquei em «{botao}»: a tarefa não chegou a começar, e o código foi gasto. Se "
            f"ainda quiser, peça a tarefa de novo.\n{formatar(resultado)}"
        )
    return f"Não cliquei em «{botao}»: o executor não chegou a esse botão.\n{formatar(resultado)}"


def nota_do_clique(resultado: BrowserResult) -> str:
    """O que o Gemini fica sabendo, sem código nem texto da página."""
    if resultado.liberado and (
        resultado.status != "error" or resultado.error_code == "acao_sensivel"
    ):
        return "o usuário liberou um clique no navegador, e o Viking o fez (uma vez)"
    if resultado.liberado:
        return "o usuário liberou um clique no navegador; ele pode ter sido feito antes de um erro"
    return "o usuário liberou um clique no navegador, e o executor não chegou ao botão: nada mudou"
