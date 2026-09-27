"""Finanças: os dados da Pluggy viram contas e gastos certos? Pluggy falsa no formato medido.

O formato foi medido nas conexões do dono em 2026-09-27 (docs/fontes/pluggy-open-finance.md,
"Formato real dos dados"); os valores e as descrições daqui são inventados. As três armadilhas que
fariam o total de gastos sair errado têm cada uma um teste que cai sozinho: sentido pelo sinal (o
sinal muda entre conta e cartão), fatura paga contada duas vezes, parcela futura no total.

A Pluggy falsa responde no `_abrir` do cliente, então os parâmetros que saem de verdade
(`dateFrom`, `dateTo`, `after`) também estão sob teste. Ela filtra pela data em UTC, como a
Pluggy: quem pede só o período exato perde a borda do fuso.
"""

import io
import json
import re
import urllib.error
import urllib.parse
from datetime import date
from zoneinfo import ZoneInfo

import pytest

from lifeos.financas import pluggy, service

ITEM = "0f8c2a3e-1b2c-4d5e-8f90-123456789abc"
CONTA = "aaaaaaaa-0000-4000-8000-000000000001"
CARTAO = "aaaaaaaa-0000-4000-8000-000000000002"
DOCUMENTO = "52998224725"  # CPF de teste (dígito verificador válido) da contraparte de um PIX
NUMERO_DA_CONTA = "98765-4"
HOJE = date(2026, 9, 20)
_DATA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
SETEMBRO = (date(2026, 9, 1), date(2026, 9, 30))


@pytest.fixture(autouse=True)
def _brasilia(monkeypatch):
    # O VPS está em UTC e, sem VIKING_TIMEZONE, o Viking usa o fuso da máquina (medido): sem isto,
    # 02:59Z cairia no mesmo dia e os testes de borda passariam por acaso.
    monkeypatch.setattr(service, "TIMEZONE", ZoneInfo("America/Sao_Paulo"))


def _t(id, dia, valor, tipo, categoria=None, **extra):
    """Transação no formato da Pluggy; `dia` curto vira meia-noite de Brasília (03:00Z)."""
    bruta = {
        "id": id,
        "description": extra.pop("description", f"COMPRA {id.upper()}"),
        "amount": valor,
        "type": tipo,
        "date": dia if "T" in dia else f"{dia}T03:00:00.000Z",
        "status": extra.pop("status", "POSTED"),
        "merchant": None,
    }
    if categoria is not None:
        bruta["category"] = categoria
        bruta["categoryId"] = extra.pop("categoryId", None)
    bruta.update(extra)
    return bruta


def _parcela(n, total, id_fatura="f1"):
    return {
        "creditCardMetadata": {
            "installmentNumber": n,
            "totalInstallments": total,
            "purchaseDate": "2026-09-12T03:00:00.000Z",
            "billId": id_fatura,
        }
    }


# Conta corrente: gasto vem NEGATIVO. Pagar a fatura sai daqui e aparece de novo no cartão.
DA_CONTA = [
    _t("c1", "2026-09-10", -100.0, "DEBIT", "Groceries", categoryId="05050000"),
    _t(
        "c2",
        "2026-09-10",
        -500.0,
        "DEBIT",
        "Credit card payment",
        categoryId="05100000",
        operationType="PAGAMENTO_FATURA",
    ),
    _t(
        "c3",
        "2026-09-11",
        -50.0,
        "DEBIT",
        "Transfer - PIX",
        categoryId="05070000",
        description="PIX ENVIADO",
        paymentData={
            "payer": {"documentNumber": {"type": "CPF", "value": "00000000191"}},
            "receiver": {
                "documentNumber": {"type": "CPF", "value": DOCUMENTO},
                "accountNumber": NUMERO_DA_CONTA,
            },
        },
    ),
    _t("c4", "2026-09-05", 3000.0, "CREDIT", "Salary", categoryId="01010000"),
    _t("c5", "2026-09-07", 200.0, "CREDIT", operationType="RESGATE_APLIC_FINANCEIRA"),
    _t("c6", "2026-09-12", -30.0, "DEBIT"),  # sem categoria (6 de 65 numa conta, medido)
    _t("c7", "2026-09-06", -300.0, "DEBIT", "Investments", categoryId="03000000"),
]

# Cartão: gasto vem POSITIVO; parcelas futuras já aparecem, PENDING.
DO_CARTAO = [
    _t("k1", "2026-09-08", 80.0, "DEBIT", "Restaurants", categoryId="08010000"),
    _t("k2", "2026-09-10", 500.0, "CREDIT", "Credit card payment", categoryId="05100000"),
    _t("k3", "2026-09-09", 15.0, "CREDIT", "Restaurants", categoryId="08010000"),  # estorno
    _t("k4", "2026-09-12", 25.0, "DEBIT", "Electronics", **_parcela(1, 10)),
    _t("k5", "2026-09-28", 25.0, "DEBIT", "Electronics", status="PENDING", **_parcela(2, 10)),
    _t("k6", "2026-09-15", 60.0, "DEBIT", "Restaurants", categoryId="08010000", status="PENDING"),
]

CATEGORIAS = [
    {"id": "05050000", "description": "Groceries", "descriptionTranslated": "Supermercado"},
    {"id": "08010000", "description": "Restaurants", "descriptionTranslated": "Restaurantes"},
    {"id": "05070000", "description": "Transfer - PIX", "descriptionTranslated": "PIX"},
    {"id": "01010000", "description": "Salary", "descriptionTranslated": "Salário"},
]

CONTAS = [
    {
        "id": CONTA,
        "type": "BANK",
        "subtype": "CHECKING_ACCOUNT",
        "name": "Conta Corrente",
        "marketingName": None,
        "number": NUMERO_DA_CONTA,
        "taxNumber": DOCUMENTO,
        "owner": "TITULAR DE TESTE",
        "balance": 1234.56,
    },
    {
        "id": CARTAO,
        "type": "CREDIT",
        "subtype": "CREDIT_CARD",
        "name": "Cartao",
        "marketingName": "Cartão Roxo",
        "number": "1234",
        "balance": 820.5,
        "creditData": {
            "creditLimit": 5000.0,
            "availableCreditLimit": 4179.5,
            "balanceCloseDate": None,
            "balanceDueDate": "2026-10-10",
            "minimumPayment": 120.0,
        },
    },
]


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture()
def pluggy_falsa(monkeypatch):
    """`estado["transacoes"][conta]`, `estado["pagina"]` (itens por página), `estado["pedidos"]`."""
    estado = {
        "transacoes": {CONTA: list(DA_CONTA), CARTAO: list(DO_CARTAO)},
        "contas": list(CONTAS),
        "categorias": list(CATEGORIAS),
        "faturas": {CARTAO: []},
        "item": {"id": ITEM, "status": "UPDATED", "lastUpdatedAt": "2026-09-19T12:00:00.000Z"},
        "pagina": 500,
        "cursor_sem_fim": False,
        "falhar": set(),
        "pedidos": [],
    }

    def responder(caminho, q):
        if caminho in estado["falhar"]:
            return 500, {"codeDescription": "erro interno"}
        if caminho == "/auth":
            return 200, {"apiKey": "chave"}
        if caminho == f"/items/{ITEM}":
            return 200, estado["item"]
        if caminho == "/accounts":
            return 200, {"results": estado["contas"] if q.get("itemId") == ITEM else []}
        if caminho == "/categories":
            return 200, {"results": estado["categorias"]}
        if caminho == "/bills":
            return 200, {"results": estado["faturas"].get(q.get("accountId"), [])}
        if caminho == "/v2/transactions":
            todas = [
                t
                for t in estado["transacoes"].get(q.get("accountId"), [])
                # Data ilegível passa: é o lixo que o código tem de aguentar.
                if not _DATA.fullmatch(str(t.get("date"))[:10])
                or q["dateFrom"] <= str(t.get("date"))[:10] <= q["dateTo"]
            ]
            inicio = int(q.get("after") or 0)
            fim = inicio + estado["pagina"]
            proximo = str(fim) if fim < len(todas) or estado["cursor_sem_fim"] else None
            return 200, {"results": todas[inicio:fim], "next": proximo}
        return 404, {"codeDescription": "não existe"}

    def abrir(pedido):
        partes = urllib.parse.urlsplit(pedido.full_url)
        q = dict(urllib.parse.parse_qsl(partes.query))
        estado["pedidos"].append((pedido.get_method(), partes.path, q))
        status, corpo = responder(partes.path, q)
        dados = json.dumps(corpo).encode()
        if status >= 400:
            raise urllib.error.HTTPError(pedido.full_url, status, "erro", {}, io.BytesIO(dados))
        return _Resposta(dados)

    monkeypatch.setattr(pluggy, "_abrir", abrir)
    return estado


def _financas():
    return service.Financas(pluggy.Cliente("id-do-app", "segredo"), [ITEM])


def _por_id(transacoes):
    return {t.id: t for t in transacoes}


# --- contas e conexões ------------------------------------------------------------------------


def test_contas_com_saldo_e_dados_do_cartao(pluggy_falsa):
    conta, cartao = _financas().contas()
    assert (conta.nome, conta.cartao, conta.saldo) == ("Conta Corrente", False, 1234.56)
    assert (cartao.nome, cartao.cartao, cartao.saldo) == ("Cartão Roxo", True, 820.5)
    assert (cartao.limite, cartao.disponivel) == (5000.0, 4179.5)
    assert cartao.vencimento == date(2026, 10, 10)  # `balanceDueDate` vem só com a data
    assert conta.limite is None and conta.vencimento is None


def test_contas_pedidas_uma_vez_por_consulta(pluggy_falsa):
    financas = _financas()
    financas.contas()
    financas.transacoes(*SETEMBRO)
    assert [p for p in pluggy_falsa["pedidos"] if p[1] == "/accounts"] == [
        ("GET", "/accounts", {"itemId": ITEM})
    ]


def test_conexao_com_status_e_ultima_sincronizacao(pluggy_falsa):
    (conexao,) = _financas().conexoes()
    assert conexao.status == "UPDATED"
    assert conexao.atualizado.isoformat() == "2026-09-19T12:00:00+00:00"


def test_sem_conexoes_explica_como_conectar(monkeypatch):
    monkeypatch.setattr("lifeos.config.PLUGGY_ITEM_IDS", ())
    with pytest.raises(service.SemConexoes, match="--conectar"):
        service.Financas(pluggy.Cliente("id", "segredo"))


def test_ids_lidos_da_config_na_hora(pluggy_falsa, monkeypatch):
    monkeypatch.setattr("lifeos.config.PLUGGY_ITEM_IDS", (ITEM,))
    assert len(service.Financas(pluggy.Cliente("id", "segredo")).contas()) == 2


def test_documento_e_numero_de_conta_nunca_entram(pluggy_falsa):
    financas = _financas()
    texto = repr(financas.contas()) + repr(financas.transacoes(*SETEMBRO))
    for proibido in (DOCUMENTO, "00000000191", NUMERO_DA_CONTA, "TITULAR DE TESTE"):
        assert proibido not in texto


# --- transações: sentido, período, fuso, cursor -----------------------------------------------


def test_sentido_vem_do_tipo_e_valor_e_sempre_positivo(pluggy_falsa):
    t = _por_id(_financas().transacoes(*SETEMBRO))
    assert (t["c1"].valor, t["c1"].saida) == (100.0, True)  # conta: DEBIT negativo
    assert (t["k1"].valor, t["k1"].saida) == (80.0, True)  # cartão: DEBIT positivo
    assert (t["c4"].valor, t["c4"].saida) == (3000.0, False)
    assert (t["k3"].valor, t["k3"].saida) == (15.0, False)


@pytest.mark.parametrize(
    ("data", "dia"),
    [
        ("2026-09-01T03:00:00.000Z", date(2026, 9, 1)),  # meia-noite em Brasília
        ("2026-09-01T02:59:00.000Z", date(2026, 8, 31)),  # 23:59 do dia anterior
        ("2026-10-01T02:59:00.000Z", date(2026, 9, 30)),
        ("2026-09-15", date(2026, 9, 15)),  # só a data: é esse o dia, sem fuso
    ],
)
def test_dia_no_fuso_de_brasilia(data, dia):
    assert service._dia(data) == dia


def test_borda_do_mes_segue_o_fuso_e_nao_o_utc(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [
            _t("antes", "2026-09-01T02:59:00.000Z", -1.0, "DEBIT"),
            _t("primeiro", "2026-09-01T03:00:00.000Z", -2.0, "DEBIT"),
            _t("ultimo", "2026-10-01T02:59:00.000Z", -3.0, "DEBIT"),
            _t("depois", "2026-10-01T03:00:00.000Z", -4.0, "DEBIT"),
        ]
    }
    financas = _financas()
    assert {t.id for t in financas.transacoes(*SETEMBRO)} == {"primeiro", "ultimo"}
    assert {t.id for t in financas.transacoes(date(2026, 8, 1), date(2026, 8, 31))} == {"antes"}


def test_pede_um_dia_a_mais_de_cada_lado(pluggy_falsa):
    _financas().transacoes(*SETEMBRO)
    pedidos = [q for _m, caminho, q in pluggy_falsa["pedidos"] if caminho == "/v2/transactions"]
    assert {(q["accountId"], q["dateFrom"], q["dateTo"]) for q in pedidos} == {
        (CONTA, "2026-08-31", "2026-10-01"),
        (CARTAO, "2026-08-31", "2026-10-01"),
    }


def test_segue_o_cursor_ate_o_fim(pluggy_falsa):
    pluggy_falsa["pagina"] = 2
    assert len(_financas().transacoes(*SETEMBRO)) == len(DA_CONTA) + len(DO_CARTAO)
    cursores = [q.get("after") for _m, c, q in pluggy_falsa["pedidos"] if c == "/v2/transactions"]
    assert cursores == [None, "2", "4", "6", None, "2", "4"]


def test_cursor_sem_fim_falha_alto_em_vez_de_devolver_parte(pluggy_falsa):
    pluggy_falsa["pagina"] = 1
    pluggy_falsa["cursor_sem_fim"] = True
    with pytest.raises(pluggy.FalhaDaPluggy, match="incompleta"):
        _financas().transacoes(*SETEMBRO)


def test_ordem_mais_recente_primeiro(pluggy_falsa):
    dias = [t.dia for t in _financas().transacoes(*SETEMBRO)]
    assert dias == sorted(dias, reverse=True)


def test_categoria_em_portugues_e_sem_traducao_fica_o_nome(pluggy_falsa):
    t = _por_id(_financas().transacoes(*SETEMBRO))
    assert t["c1"].categoria == "Supermercado"
    assert t["k4"].categoria == "Electronics"  # sem `categoryId`: fica o nome da Pluggy
    assert t["c6"].categoria == ""


def test_categorias_fora_do_ar_nao_derrubam_a_consulta(pluggy_falsa):
    pluggy_falsa["falhar"].add("/categories")
    assert _por_id(_financas().transacoes(*SETEMBRO))["c1"].categoria == "Groceries"


def test_transacoes_fora_do_ar_falham_alto(pluggy_falsa):
    pluggy_falsa["falhar"].add("/v2/transactions")
    with pytest.raises(pluggy.FalhaDaPluggy, match="500"):
        _financas().transacoes(*SETEMBRO)


def test_parcela_pendente_e_movimento_interno(pluggy_falsa):
    t = _por_id(_financas().transacoes(*SETEMBRO))
    assert (t["k4"].parcela, t["k5"].parcela, t["k1"].parcela) == ("1/10", "2/10", "")
    assert (t["k5"].pendente, t["k4"].pendente) == (True, False)
    assert {i for i, x in t.items() if x.interna} == {"c2", "c5", "c7", "k2"}


def test_compra_a_vista_com_metadado_nao_vira_parcela(pluggy_falsa):
    pluggy_falsa["transacoes"] = {CARTAO: [_t("v", "2026-09-10", 9.0, "DEBIT", **_parcela(1, 1))]}
    assert _financas().transacoes(*SETEMBRO)[0].parcela == ""


def test_descricao_sem_controles_e_espacos_juntos(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [_t("x", "2026-09-10", -1.0, "DEBIT", description="LOJA\x1b[2J  \u202eX\n Y")]
    }
    assert _financas().transacoes(*SETEMBRO)[0].descricao == "LOJA[2J X Y"


@pytest.mark.parametrize(
    "ruim",
    [
        {"amount": None},
        {"amount": "10.0"},
        {"amount": True},
        {"amount": float("nan")},
        {"date": "ontem"},
        {"date": None},
    ],
)
def test_transacao_sem_valor_ou_data_fica_fora_e_e_contada(pluggy_falsa, ruim):
    boa = _t("boa", "2026-09-10", -10.0, "DEBIT")
    pluggy_falsa["transacoes"] = {CONTA: [boa, {**boa, "id": "ruim", **ruim}]}
    financas = _financas()
    assert [t.id for t in financas.transacoes(*SETEMBRO)] == ["boa"]
    assert financas.ignoradas == 1
    financas.transacoes(*SETEMBRO)
    assert financas.ignoradas == 1  # conta a última consulta, não acumula


# --- gastos: as três armadilhas ---------------------------------------------------------------


def _gastos():
    return service.gastos(_financas(), *SETEMBRO, hoje=HOJE)


def test_total_de_gastos(pluggy_falsa):
    # mercado 100 + PIX 50 + sem categoria 30 + restaurante 80 + parcela 25 + pendente 60
    assert _gastos().total == 345.0


def test_gasto_no_cartao_conta_mesmo_vindo_positivo(pluggy_falsa):
    pluggy_falsa["transacoes"] = {CARTAO: [_t("k", "2026-09-10", 80.0, "DEBIT", "Restaurants")]}
    assert _gastos().total == 80.0


def test_gasto_na_conta_conta_mesmo_vindo_negativo(pluggy_falsa):
    pluggy_falsa["transacoes"] = {CONTA: [_t("c", "2026-09-10", -100.0, "DEBIT", "Groceries")]}
    assert _gastos().total == 100.0


def test_fatura_paga_nao_conta_em_dobro(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [DA_CONTA[1]],  # sai da conta como "Credit card payment"
        CARTAO: [DO_CARTAO[0], DO_CARTAO[1]],  # a compra de 80 e o pagamento chegando
    }
    g = _gastos()
    assert g.total == 80.0
    assert (g.internas, g.internas_total) == (2, 1000.0)
    assert g.entradas == 0.0


def test_pagamento_de_fatura_so_pela_operacao_tambem_e_interno(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [_t("p", "2026-09-10", -500.0, "DEBIT", operationType="PAGAMENTO_FATURA")]
    }
    assert (_gastos().total, _gastos().internas) == (0.0, 1)


def test_parcela_futura_fica_fora_do_total_e_e_contada(pluggy_falsa):
    g = _gastos()
    assert (g.futuras, g.futuras_total) == (1, 25.0)
    assert "k5" not in {t.id for t in g.maiores}


def test_hoje_entra_no_total(pluggy_falsa):
    pluggy_falsa["transacoes"] = {CARTAO: [_t("h", HOJE.isoformat(), 7.0, "DEBIT")]}
    assert (_gastos().total, _gastos().futuras) == (7.0, 0)


def test_investimento_e_resgate_nao_sao_gasto_nem_renda(pluggy_falsa):
    pluggy_falsa["transacoes"] = {CONTA: [DA_CONTA[4], DA_CONTA[6]]}
    g = _gastos()
    assert (g.total, g.entradas, g.internas, g.internas_total) == (0.0, 0.0, 2, 500.0)


def test_entrada_e_o_que_chegou_na_conta_sem_estorno_do_cartao(pluggy_falsa):
    assert _gastos().entradas == 3000.0


def test_pendente_do_passado_entra_e_e_contado(pluggy_falsa):
    g = _gastos()
    assert g.pendentes == 1
    assert "k6" in {t.id for t in g.maiores}


def test_gastos_por_categoria_maior_primeiro_com_sem_categoria(pluggy_falsa):
    assert _gastos().por_categoria == (
        ("Restaurantes", 140.0, 2),
        ("Supermercado", 100.0, 1),
        ("PIX", 50.0, 1),
        ("sem categoria", 30.0, 1),
        ("Electronics", 25.0, 1),
    )


def test_categorias_somam_o_total(pluggy_falsa):
    g = _gastos()
    assert round(sum(linha[1] for linha in g.por_categoria), 2) == g.total


def test_cinco_maiores(pluggy_falsa):
    assert [t.id for t in _gastos().maiores] == ["c1", "k1", "k6", "c3", "c6"]


def test_gastos_levam_as_ignoradas(pluggy_falsa):
    pluggy_falsa["transacoes"][CONTA].append({"id": "sem-valor", "type": "DEBIT", "amount": None})
    assert _gastos().ignoradas == 1


def test_centavos_somam_sem_erro_de_ponto_flutuante(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CARTAO: [_t(f"k{i}", "2026-09-10", 0.1, "DEBIT") for i in range(3)]
    }
    assert _gastos().total == 0.3


# --- busca ------------------------------------------------------------------------------------


def _buscar(texto, valor=None):
    return service.buscar(_financas(), texto, *SETEMBRO, valor=valor)


def test_busca_sem_acento_e_sem_caixa(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [
            _t("a", "2026-09-05", -1500.0, "DEBIT", description="PAGTO ALUGUÉL SET"),
            _t("b", "2026-09-06", -30.0, "DEBIT", description="PADARIA"),
        ]
    }
    achadas, mais = _buscar("aluguel")
    assert ([t.id for t in achadas], mais) == (["a"], False)


def test_busca_por_valor_com_folga_de_um_por_cento(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [
            _t("perto", "2026-09-05", -1510.0, "DEBIT"),
            _t("longe", "2026-09-06", -1520.0, "DEBIT"),
        ]
    }
    assert [t.id for t in _buscar("", valor=1500.0)[0]] == ["perto"]


def test_busca_por_texto_e_valor_juntos(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [
            _t("a", "2026-09-05", -1500.0, "DEBIT", description="ALUGUEL"),
            _t("b", "2026-09-06", -80.0, "DEBIT", description="ALUGUEL BICICLETA"),
        ]
    }
    assert [t.id for t in _buscar("aluguel", valor=1500.0)[0]] == ["a"]


def test_busca_para_em_vinte_e_avisa_que_havia_mais(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [_t(f"u{i:02}", "2026-09-10", -5.0, "DEBIT", description="UBER") for i in range(21)]
    }
    achadas, mais = _buscar("uber")
    assert (len(achadas), mais) == (service.MAX_BUSCA, True)


def test_busca_com_exatamente_vinte_nao_avisa(pluggy_falsa):
    pluggy_falsa["transacoes"] = {
        CONTA: [_t(f"u{i:02}", "2026-09-10", -5.0, "DEBIT", description="UBER") for i in range(20)]
    }
    assert _buscar("uber")[1] is False


# --- fatura fechada ---------------------------------------------------------------------------


def test_ultima_fatura_fechada_e_a_de_vencimento_mais_recente(pluggy_falsa):
    pluggy_falsa["faturas"][CARTAO] = [
        {"id": "f1", "dueDate": "2026-08-10T00:00:00.000Z", "totalAmount": 700.0},
        {"id": "f2", "dueDate": "2026-09-10T00:00:00.000Z", "totalAmount": 812.34},
        {"id": "f0", "dueDate": "2026-07-10T00:00:00.000Z", "totalAmount": 600.0},
    ]
    financas = _financas()
    fechada = financas.ultima_fatura_fechada(financas.contas()[1])
    # 00:00Z é 21:00 do dia 9 em Brasília, mas o vencimento é o dia 10: data, não instante.
    assert fechada == service.Fechada(812.34, date(2026, 9, 10))


@pytest.mark.parametrize("ruim", [None, "", "sem data", "2026-13-01"])
def test_data_ilegivel_nao_vira_vencimento(ruim):
    assert service._data(ruim) is None


def test_sem_fatura_fechada(pluggy_falsa):
    financas = _financas()
    assert financas.ultima_fatura_fechada(financas.contas()[1]) is None
