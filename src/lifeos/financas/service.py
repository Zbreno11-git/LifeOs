"""Finanças pela Pluggy: dados normalizados, sem texto para o modelo (isso é `financas/tools.py`).

Consulta a Pluggy a cada pergunta (decisão do dono: nada financeiro gravado em disco). Três
armadilhas medidas nas conexões do dono (2026-09-27, ver docs/fontes/pluggy-open-finance.md)
moram aqui, e não no texto:
- o sinal do `amount` muda entre conta corrente (gasto negativo) e cartão (gasto positivo): o
  sentido sai de `type`, e o valor é sempre positivo;
- pagar a fatura aparece nas duas contas, e há transferência entre contas próprias e
  investimento: `interna`, fora do gasto;
- o cartão traz parcelas com data no futuro: quem soma "o gasto do mês" corta em hoje.

As datas vêm em UTC (`03:00Z` é meia-noite em Brasília; `02:59Z` é 23:59 do dia anterior): o dia
de cada transação é o do fuso do Viking.

Só carrega o que as respostas usam: `paymentData` (CPF/CNPJ da contraparte), número de conta e
CPF do titular nunca saem daqui, porque nunca entram.

Pode ter `from __future__ import annotations`: nada daqui é tool do Gemini.
"""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from lifeos.browser._redacao import limpar_controles
from lifeos.config import TIMEZONE
from lifeos.financas import pluggy

MAX_BUSCA = 20
MAX_PERIODO_DIAS = 366
MAX_PAGINAS = 20  # por conta e período; a Pluggy devolveu até 351 transações numa página só
DESATUALIZADO = timedelta(hours=36)  # o Meu Pluggy sincroniza a cada 24 h
# Fatura é mensal: a mais recente com mais de 31 dias quer dizer que uma mais nova ainda não veio
# (as dos dois cartões do dono tinham 33 e 39 dias em 2026-09-27).
ATRASO_DA_FECHADA = timedelta(days=31)
MAX_FUTURO_DIAS = 2 * 366  # parcelas: as do dono iam até 2027

# Dinheiro que só mudou de lugar entre contas do dono, ou foi para/voltou de investimento
# (categorias e operações medidas nas conexões do dono). Não é gasto nem renda.
_CATEGORIAS_INTERNAS = frozenset(
    {
        "Credit card payment",
        "Same person transfer",
        "Transfer - Internal",
        "Investments",
        "Fixed income",
        "Variable income",
        "Proceeds interests and dividends",
    }
)
_OPERACOES_INTERNAS = frozenset(
    {
        "RESGATE_APLIC_FINANCEIRA",
        "RENDIMENTO_APLIC_FINANCEIRA",
        "PAGAMENTO_FATURA",
        "TRANSFERENCIA_MESMA_INSTITUICAO",
    }
)


class SemConexoes(pluggy.ErroPluggy):
    codigo = "sem_conexoes"


@dataclass(frozen=True)
class Conexao:
    id: str
    status: str
    atualizado: datetime | None


@dataclass(frozen=True)
class Conta:
    id: str
    nome: str
    cartao: bool
    # Na conta, o disponível. No cartão, o LIMITE USADO (= limite − disponível, medido), com as
    # parcelas futuras dentro — não é a fatura do mês. `balanceDueDate` não entra: é o vencimento
    # da última fatura fechada, já passado (medido), e viraria um "vence em" errado.
    saldo: float | None
    limite: float | None = None
    disponivel: float | None = None


@dataclass(frozen=True)
class Transacao:
    id: str
    conta: str
    cartao: bool
    dia: date
    descricao: str
    valor: float  # sempre positivo
    saida: bool
    categoria: str
    interna: bool
    pendente: bool
    parcela: str = ""  # "3/10"
    fatura: str = ""  # `creditCardMetadata.billId`; vazio = ainda sem fatura fechada


@dataclass(frozen=True)
class Fechada:
    valor: float | None
    fechamento: date | None
    vencimento: date | None


# --- tradução do formato da Pluggy -----------------------------------------------------------


def _instante(texto) -> datetime | None:
    try:
        instante = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    return instante if instante.tzinfo else instante.replace(tzinfo=TIMEZONE)


def _dia(texto) -> date | None:
    """Dia no fuso do Viking. `"2026-09-01T02:59:00.000Z"` é 31/08 em Brasília."""
    if isinstance(texto, str) and len(texto) == 10:
        try:
            return date.fromisoformat(texto)
        except ValueError:
            return None
    instante = _instante(texto)
    return instante.astimezone(TIMEZONE).date() if instante else None


def _data(texto) -> date | None:
    """Data de calendário (vencimento, fechamento): a Pluggy manda como meia-noite UTC
    (`T00:00:00.000Z` nas 25 faturas do dono, medido em 2026-09-27). Converter para Brasília
    daria o dia anterior: vale o que está escrito."""
    try:
        return date.fromisoformat(str(texto)[:10])
    except ValueError:
        return None


def _numero(valor) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor) if math.isfinite(valor) else None


def _texto(valor) -> str:
    return " ".join(limpar_controles(str(valor or "")).split())


def normalizar(texto: str) -> str:
    """Para busca: sem acento, sem caixa ("Aluguél" acha "ALUGUEL")."""
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def interna(categoria: str | None, operacao: str | None) -> bool:
    return categoria in _CATEGORIAS_INTERNAS or operacao in _OPERACOES_INTERNAS


# --- leitura ---------------------------------------------------------------------------------


class Financas:
    """Uma consulta: guarda contas e categorias enquanto responde uma pergunta."""

    def __init__(self, cliente: pluggy.Cliente, item_ids=None) -> None:
        from lifeos import config  # lido na hora, não na importação

        self._cliente = cliente
        self._ids = tuple(item_ids if item_ids is not None else config.PLUGGY_ITEM_IDS)
        if not self._ids:
            raise SemConexoes(
                "nenhuma conexão no .env (PLUGGY_ITEM_IDS); rode `viking financas --conectar`"
            )
        self._contas: list[tuple[Conta, dict]] | None = None
        self._categorias: dict[str, str] | None = None
        # Transações sem data ou valor legível: ficam fora da conta, mas a resposta diz quantas.
        self.ignoradas = 0

    def conexoes(self) -> list[Conexao]:
        saida = []
        for item_id in self._ids:
            item = self._cliente.conexao(item_id)
            saida.append(
                Conexao(item_id, _texto(item.get("status")), _instante(item.get("lastUpdatedAt")))
            )
        return saida

    def _brutas(self) -> list[tuple[Conta, dict]]:
        if self._contas is None:
            self._contas = []
            for item_id in self._ids:
                for bruta in self._cliente.get("/accounts", itemId=item_id).get("results") or []:
                    credito = bruta.get("creditData") or {}
                    conta = Conta(
                        id=str(bruta.get("id") or ""),
                        nome=_texto(bruta.get("marketingName") or bruta.get("name") or "conta"),
                        cartao=bruta.get("type") == "CREDIT",
                        saldo=_numero(bruta.get("balance")),
                        limite=_numero(credito.get("creditLimit")),
                        disponivel=_numero(credito.get("availableCreditLimit")),
                    )
                    self._contas.append((conta, bruta))
        return self._contas

    def contas(self) -> list[Conta]:
        return [conta for conta, _ in self._brutas()]

    def _nomes_de_categoria(self) -> dict[str, str]:
        if self._categorias is None:
            try:
                lista = self._cliente.get("/categories").get("results") or []
            except pluggy.ErroPluggy:
                lista = []  # sem tradução, fica o nome em inglês: não é motivo para falhar
            self._categorias = {
                str(c.get("id")): _texto(c.get("descriptionTranslated") or c.get("description"))
                for c in lista
                if c.get("id")
            }
        return self._categorias

    def transacoes(self, desde: date, ate: date, conta: Conta | None = None) -> list[Transacao]:
        """Transações com dia (no fuso do Viking) entre as datas, de todas as contas ou de uma."""
        nomes = self._nomes_de_categoria()
        # O filtro da Pluggy é por data em UTC: um dia a mais de cada lado, e o corte é aqui.
        pedido_de, pedido_ate = (
            (desde - timedelta(days=1)).isoformat(),
            (ate + timedelta(days=1)).isoformat(),
        )
        saida: list[Transacao] = []
        self.ignoradas = 0
        for atual, _ in self._brutas():
            if conta is not None and atual.id != conta.id:
                continue
            cursor = None
            for _pagina in range(MAX_PAGINAS):
                resposta = self._cliente.get(
                    "/v2/transactions",
                    accountId=atual.id,
                    dateFrom=pedido_de,
                    dateTo=pedido_ate,
                    after=cursor,
                )
                for bruta in resposta.get("results") or []:
                    transacao = self._transacao(bruta, atual, nomes)
                    if transacao is None:
                        self.ignoradas += 1
                    elif desde <= transacao.dia <= ate:
                        saida.append(transacao)
                cursor = resposta.get("next")
                if not cursor:
                    break
            else:
                raise pluggy.FalhaDaPluggy(
                    f"mais de {MAX_PAGINAS} páginas de transações numa conta: resposta incompleta"
                )
        return sorted(saida, key=lambda t: (t.dia, t.id), reverse=True)

    @staticmethod
    def _transacao(bruta: dict, conta: Conta, nomes: dict[str, str]) -> Transacao | None:
        dia = _dia(bruta.get("date"))
        valor = _numero(bruta.get("amount"))
        if dia is None or valor is None:
            return None
        categoria = bruta.get("category")
        metadado = bruta.get("creditCardMetadata") or {}
        total = metadado.get("totalInstallments")
        numero = metadado.get("installmentNumber")
        parcela = f"{numero}/{total}" if isinstance(total, int) and total > 1 and numero else ""
        return Transacao(
            id=str(bruta.get("id") or ""),
            conta=conta.nome,
            cartao=conta.cartao,
            dia=dia,
            descricao=_texto(bruta.get("description") or "(sem descrição)"),
            valor=abs(valor),
            saida=bruta.get("type") == "DEBIT",
            categoria=nomes.get(str(bruta.get("categoryId"))) or _texto(categoria) or "",
            interna=interna(categoria, bruta.get("operationType")),
            pendente=bruta.get("status") == "PENDING",
            parcela=parcela,
            fatura=_texto(metadado.get("billId")),
        )

    def ultima_fatura_fechada(self, conta: Conta) -> Fechada | None:
        faturas = self._cliente.get("/bills", accountId=conta.id).get("results") or []
        datadas = [(f, _data(f.get("dueDate"))) for f in faturas]
        datadas = [(f, d) for f, d in datadas if d is not None]
        if not datadas:
            return None
        fatura, vencimento = max(datadas, key=lambda par: par[1])
        return Fechada(
            _numero(fatura.get("totalAmount")), _data(fatura.get("billClosingDate")), vencimento
        )


# --- respostas --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Gastos:
    desde: date
    ate: date
    total: float
    por_categoria: tuple[tuple[str, float, int], ...]  # (categoria, total, quantas), maior primeiro
    maiores: tuple[Transacao, ...]
    entradas: float
    internas: int
    internas_total: float
    futuras: int  # saídas com data depois de hoje (parcelas), fora do total
    futuras_total: float
    pendentes: int  # dentro do total, ainda não confirmadas pelo banco
    ignoradas: int  # vieram sem data ou valor legível: fora de tudo, mas a resposta diz


def gastos(financas: Financas, desde: date, ate: date, *, hoje: date | None = None) -> Gastos:
    hoje = hoje or datetime.now(TIMEZONE).date()
    todas = financas.transacoes(desde, ate)
    externas = [t for t in todas if not t.interna]
    saidas = [t for t in externas if t.saida and t.dia <= hoje]
    futuras = [t for t in externas if t.saida and t.dia > hoje]
    # Crédito no cartão que não é pagamento de fatura (estorno) não é renda: fica fora.
    entradas = [t for t in externas if not t.saida and not t.cartao and t.dia <= hoje]
    grupos: dict[str, list[Transacao]] = {}
    for t in saidas:
        grupos.setdefault(t.categoria or "sem categoria", []).append(t)
    por_categoria = sorted(
        (
            (nome, round(sum(t.valor for t in lista), 2), len(lista))
            for nome, lista in grupos.items()
        ),
        key=lambda linha: -linha[1],
    )
    internas = [t for t in todas if t.interna]
    return Gastos(
        desde=desde,
        ate=ate,
        total=round(sum(t.valor for t in saidas), 2),
        por_categoria=tuple(por_categoria),
        maiores=tuple(sorted(saidas, key=lambda t: -t.valor)[:5]),
        entradas=round(sum(t.valor for t in entradas), 2),
        internas=len(internas),
        internas_total=round(sum(t.valor for t in internas), 2),
        futuras=len(futuras),
        futuras_total=round(sum(t.valor for t in futuras), 2),
        pendentes=sum(1 for t in saidas if t.pendente),
        ignoradas=financas.ignoradas,
    )


def buscar(
    financas: Financas, texto: str, desde: date, ate: date, valor: float | None = None
) -> tuple[list[Transacao], bool]:
    """(achadas, havia mais). Por pedaço da descrição (sem acento), e/ou por valor (±1%)."""
    chave = normalizar(texto.strip())
    achadas = []
    for t in financas.transacoes(desde, ate):
        if chave and chave not in normalizar(t.descricao):
            continue
        if valor is not None and abs(t.valor - valor) > max(0.01, abs(valor) * 0.01):
            continue
        achadas.append(t)
    return achadas[:MAX_BUSCA], len(achadas) > MAX_BUSCA


@dataclass(frozen=True)
class Fatura:
    conta: Conta
    fechada: Fechada | None  # a mais recente que a Pluggy tem
    atrasada: bool  # a fechada tem mais de `ATRASO_DA_FECHADA`: deve haver uma mais nova
    sem_fatura: float  # compras menos estornos depois do fechamento, ainda sem fatura
    sem_fatura_n: int
    futuras: int  # parcelas com data depois de hoje
    futuras_total: float


def fatura(financas: Financas, conta: Conta, *, hoje: date | None = None) -> Fatura:
    """Os fatos do cartão, sem inventar vencimento: a Pluggy não diz o da próxima fatura."""
    hoje = hoje or datetime.now(TIMEZONE).date()
    fechada = financas.ultima_fatura_fechada(conta)
    fechamento = fechada.fechamento if fechada else None
    desde = fechamento + timedelta(days=1) if fechamento else hoje - ATRASO_DA_FECHADA
    todas = financas.transacoes(desde, hoje + timedelta(days=MAX_FUTURO_DIAS), conta)
    externas = [t for t in todas if not t.interna]
    abertas = [t for t in externas if not t.fatura and t.dia <= hoje]
    futuras = [t for t in externas if t.saida and t.dia > hoje]
    return Fatura(
        conta=conta,
        fechada=fechada,
        atrasada=bool(fechamento and hoje - fechamento > ATRASO_DA_FECHADA),
        sem_fatura=round(sum(t.valor if t.saida else -t.valor for t in abertas), 2),
        sem_fatura_n=sum(1 for t in abertas if t.saida),
        futuras=len(futuras),
        futuras_total=round(sum(t.valor for t in futuras), 2),
    )
