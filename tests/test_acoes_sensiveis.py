"""Freio de cliques que agem sobre a conta (Sessão 4b, §5.2) — a regra pura.

O encaixe no Jev (o envelope que chama `motivo()` antes do clique) é testado em
`test_jev_subprocess_main.py`. Caracteres invisíveis são montados com `chr()`: escrever o escape
Unicode direto já gravou o caractere literal no código-fonte três vezes (ver `docs/erros.md`,
classe 5).
"""

import re
import sys
import time
from pathlib import Path

import pytest

from lifeos.browser import _acoes_sensiveis as a

ZERO_WIDTH = chr(0x200B)
RLO = chr(0x202E)
NUL = chr(0)


def _clique(rotulo, guard=None):
    return a.motivo({"kind": "click", "label": rotulo}, guard)


def _guard(href=None, escopo=None):
    guard = [None] * a.GUARD_TAMANHO
    guard[a.GUARD_HREF] = href
    guard[a.GUARD_ESCOPO] = escopo
    return guard


# --- as três categorias do dono ------------------------------------------------------------


@pytest.mark.parametrize(
    "rotulo",
    [
        "Sair",
        "Log out",
        "Logout",
        "Sign out",
        "Log off",
        "Desconectar",
        "Encerrar sessão",
        "Sair da conta",
        "Sair de todos os dispositivos",
    ],
)
def test_sair_e_recusado(rotulo):
    assert _clique(rotulo).startswith("sair: ")


@pytest.mark.parametrize(
    "rotulo",
    [
        "Excluir minha conta",
        "Delete account",
        "Encerrar conta",
        "Desativar perfil",
        "Cancelar assinatura",
        "Cancel subscription",
        "Cancelamento do plano",
        "Account deletion",
        "Trocar senha",
        "Change password",
        "Alterar e-mail",
        "Desativar autenticação de dois fatores",
        "Remover telefone",
    ],
)
def test_mexer_na_conta_e_recusado(rotulo):
    assert _clique(rotulo).startswith("conta: ")


@pytest.mark.parametrize(
    "rotulo",
    [
        "Comprar agora",
        "Buy now",
        "Finalizar pedido",
        "Finalizar compra",
        "Place order",
        "Confirmar pagamento",
        "Pagar com Pix",
        "Pay",
        "Checkout",
        "Transferir",
        "Enviar dinheiro",
        "Assine já",
        "Assinar agora",
        "Subscribe",
        "Doar",
    ],
)
def test_dinheiro_e_recusado(rotulo):
    assert _clique(rotulo).startswith("dinheiro: ")


# --- tentativas de disfarce ----------------------------------------------------------------


@pytest.mark.parametrize(
    "disfarcado",
    [
        "SAIR",
        "  sair  ",
        "Log-Out",
        "sign_out",
        "Sa" + ZERO_WIDTH + "ir",
        "Sa" + NUL + "ir",
        RLO + "Sair",
        "".join(chr(0xFF00 + ord(c) - 0x20) for c in "SAIR"),  # letras de largura total
        "Sair\n",
    ],
)
def test_disfarce_nao_escapa_do_freio(disfarcado):
    assert _clique(disfarcado).startswith("sair: ")


def test_acento_e_caixa_nao_escapam():
    assert _clique("EXCLUSÃO DA CONTA").startswith("conta: ")
    assert _clique("Cancelar inscrição").startswith("conta: ")


def test_rotulo_na_mensagem_sai_sem_invisiveis():
    motivo = _clique("Sa" + ZERO_WIDTH + "ir" + RLO)
    assert motivo == "sair: Sair"


# --- vizinhos legítimos seguem livres -----------------------------------------------------


@pytest.mark.parametrize(
    "rotulo",
    [
        "Buscar",
        "Minha conta",
        "Configurações da conta",
        "Criar conta",
        "Entrar",
        "Login",
        "Adicionar ao carrinho",
        "Ver carrinho",
        "PayPal",
        "Buying guide",
        "Enviar",
        "Publicar",
        "Saiba mais",
        "Próxima página",
        "Planos e preços",
        "Esqueci minha senha",
    ],
)
def test_vizinho_legitimo_passa(rotulo):
    assert _clique(rotulo) is None


def test_texto_corrido_longo_nao_e_comando():
    """Card de artigo de ajuda: mais de MAX_PALAVRAS palavras não é um botão de ação."""
    assert _clique("Como excluir sua conta do Google: artigo completo da central de ajuda") is None


def test_falso_positivo_aceito_sair_do_modo_tela_cheia():
    """Decisão da Sessão 4b: o freio erra para o lado de parar. Se um dia isto incomodar, a
    exceção entra aqui com o caso medido — não se afrouxa o `^sair` às cegas."""
    assert _clique("Sair do modo tela cheia").startswith("sair: ")


@pytest.mark.parametrize("tipo", ["fill", "scroll", "wait"])
def test_digitar_rolar_e_esperar_nao_sao_julgados(tipo):
    """O Jev não aperta Enter depois de digitar: o envio seria o clique seguinte."""
    assert a.motivo({"kind": tipo, "label": "Excluir conta"}) is None


@pytest.mark.parametrize(
    ("rotulo", "categoria"),
    [("Ações → Excluir conta", "conta"), ("Conta → Sair", "sair"), ("Pagamento → Pix", "dinheiro")],
)
def test_opcao_perigosa_de_select_e_recusada(rotulo, categoria):
    """O Jev dispara `change` ao escolher a opção, e o site pode enviar nesse evento."""
    assert a.motivo({"kind": "select", "label": rotulo}).startswith(f"{categoria}: ")


def test_select_comum_passa():
    assert a.motivo({"kind": "select", "label": "Ordenar por → Mais recentes"}) is None


# --- href: link só com ícone ----------------------------------------------------------------


@pytest.mark.parametrize(
    "href",
    [
        "/logout",
        "https://x.com/auth/sign-out",
        "/conta/sair.php",
        "/index.php?action=logout",
        "/?logout=1",
        "/users/log_off",
    ],
)
def test_link_de_sair_so_com_icone(href):
    assert _clique("link", _guard(href=href)).startswith("sair: ")


@pytest.mark.parametrize(
    "href", ["/blog/como-sair-da-divida", "/logouts-historicos", "mailto:sair@x.com", "#", ""]
)
def test_href_parecido_passa(href):
    assert _clique("link", _guard(href=href)) is None


# --- contêiner: o botão genérico do diálogo de confirmação -------------------------------


def test_excluir_generico_num_dialogo_de_excluir_conta():
    escopo = (
        "Tem certeza que deseja excluir sua conta? Isso não pode ser desfeito. Excluir Cancelar"
    )
    assert _clique("Excluir", _guard(escopo=escopo)).startswith("conta: ")
    assert _clique("Sim", _guard(escopo=escopo)).startswith("conta: ")


def test_confirmar_generico_no_checkout():
    escopo = "Resumo do pedido\nTotal R$ 50,00\nCartão de crédito final 1234\nConfirmar"
    assert _clique("Confirmar", _guard(escopo=escopo)).startswith("dinheiro: ")


def test_excluir_generico_fora_de_contexto_de_conta_passa():
    assert _clique("Excluir", _guard(escopo="Tarefas de hoje: comprar pão")) is None
    assert _clique("Excluir", _guard(escopo="Lista de tarefas\nLavar o carro")) is None


def test_generico_sem_escopo_passa():
    assert _clique("Confirmar", _guard()) is None
    assert _clique("Confirmar") is None


# --- layout do guard do Jev ----------------------------------------------------------------


def test_guard_none_e_legitimo():
    assert a.contexto(None) == ("", "")


@pytest.mark.parametrize("estranho", [[None] * 13, [None] * 15, {"href": "/logout"}, "x"])
def test_layout_de_guard_inesperado_levanta(estranho):
    """Quem chama transforma isso em `protecao_indisponivel`: frear às cegas não é frear."""
    with pytest.raises(ValueError, match="layout de guard"):
        a.motivo({"kind": "click", "label": "link"}, estranho)


# --- robustez ------------------------------------------------------------------------------


def test_entrada_gigante_nao_explode():
    """Detector de custo quadrático, não benchmark: o limite é generoso de propósito."""
    inicio = time.perf_counter()
    _clique("sair " * 40_000)
    _clique("Excluir", _guard(escopo="excluir " * 5_000))
    _clique("Excluir", _guard(escopo="conta excluir " * 3_000))
    assert time.perf_counter() - inicio < 2


def test_acao_vazia_ou_sem_rotulo():
    assert a.motivo({}) is None
    assert a.motivo({"kind": "click"}) is None
    assert a.motivo({"kind": "click", "label": None}) is None


def test_freio_so_usa_stdlib():
    """Roda dentro do ambiente do Jev, onde `lifeos` não existe."""
    fonte = Path(a.__file__).read_text()
    assert re.findall(r"^\s*(?:from|import)\s+lifeos", fonte, re.MULTILINE) == []
    modulos = re.findall(r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", fonte, re.MULTILINE)
    assert set(modulos) <= set(sys.stdlib_module_names)
