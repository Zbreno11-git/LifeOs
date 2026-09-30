"""Contabilidade de uso dos modelos, para o usuário ver o que cada mensagem custou.

Duas fontes, com confiabilidade diferente:

- **Jev/OpenRouter**: o próprio provedor devolve `usage` em cada chamada, e quando vem um campo de
  custo ele é usado como valor real. É exato.
- **Gemini**: a API devolve contagem de tokens, não preço. O custo aqui é *estimativa*, calculada
  com as tarifas em `VIKING_PRECO_GEMINI_*` — confira-as no painel do provedor, preço muda. Tokens
  de conteúdo em cache têm tarifa própria e não são modelados aqui; a conta continua estimativa.
"""

from dataclasses import dataclass, field

from lifeos.config import PRECO_GEMINI_ENTRADA, PRECO_GEMINI_SAIDA

# Nomes possíveis do campo de custo no `usage` do provedor; o primeiro encontrado vence.
_CHAVES_CUSTO = ("cost", "total_cost", "cost_usd")
_CHAVES_ENTRADA = ("prompt_tokens", "input_tokens")
_CHAVES_SAIDA = ("completion_tokens", "output_tokens")


def _primeiro(dados: dict, chaves) -> float:
    for chave in chaves:
        valor = dados.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return float(valor)
    return 0.0


def dinheiro(valor: float) -> str:
    """US$ com casas suficientes para não virar 0,00 em chamadas de fração de centavo."""
    if valor and valor < 0.01:
        return f"US$ {valor:.6f}".replace(".", ",")
    return f"US$ {valor:.2f}".replace(".", ",")


@dataclass
class Consumo:
    entrada: int = 0
    saida: int = 0
    custo: float = 0.0
    estimado: bool = False
    chamadas: int = 0

    def __add__(self, outro: "Consumo") -> "Consumo":
        return Consumo(
            entrada=self.entrada + outro.entrada,
            saida=self.saida + outro.saida,
            custo=self.custo + outro.custo,
            estimado=self.estimado or outro.estimado,
            chamadas=self.chamadas + outro.chamadas,
        )

    def resumo(self) -> str:
        tokens = f"{self.entrada + self.saida} tokens ({self.entrada} in / {self.saida} out)"
        prefixo = "~" if self.estimado else ""
        return f"{tokens} · {prefixo}{dinheiro(self.custo)}"


def do_gemini(usage_metadata) -> Consumo:
    """Converte o usage_metadata do google-genai. Custo é estimado a partir das tarifas.

    Entrada inclui `tool_use_prompt_token_count` (o schema das tools recontado a cada chamada de
    function-calling). Saída inclui `thoughts_token_count`: é raciocínio do modelo, mas é saída
    cobrada como tal — ignorá-lo subconta justamente os turnos mais caros.
    """
    if usage_metadata is None:
        return Consumo()
    m = usage_metadata
    entrada = (getattr(m, "prompt_token_count", 0) or 0) + (
        getattr(m, "tool_use_prompt_token_count", 0) or 0
    )
    saida = (getattr(m, "candidates_token_count", 0) or 0) + (
        getattr(m, "thoughts_token_count", 0) or 0
    )
    custo = (entrada * PRECO_GEMINI_ENTRADA + saida * PRECO_GEMINI_SAIDA) / 1_000_000
    return Consumo(entrada=entrada, saida=saida, custo=custo, estimado=True, chamadas=1)


def do_jev(usage: dict | None) -> Consumo:
    """Converte o `usage` agregado que o runner do Jev devolve.

    Se o provedor informou custo, ele é usado como valor real; caso contrário fica zerado e
    marcado como estimado, para não inventar número.
    """
    usage = usage or {}
    custo = _primeiro(usage, _CHAVES_CUSTO)
    return Consumo(
        entrada=int(_primeiro(usage, _CHAVES_ENTRADA)),
        saida=int(_primeiro(usage, _CHAVES_SAIDA)),
        custo=custo,
        estimado=custo == 0.0,
        chamadas=int(usage.get("chamadas", 0)),
    )


@dataclass
class Sessao:
    """Acumula o gasto da conversa inteira, e também o do turno corrente (uma mensagem do REPL)."""

    gemini: Consumo = field(default_factory=Consumo)
    navegador: Consumo = field(default_factory=Consumo)
    _turno: Consumo = field(default_factory=Consumo, repr=False)

    @property
    def total(self) -> float:
        return self.gemini.custo + self.navegador.custo

    def iniciar_turno(self) -> None:
        """Zera o acumulador do turno. Chame antes de cada `send_message`."""
        self._turno = Consumo()

    def registrar_gemini(self, consumo: Consumo) -> None:
        """Soma ao total da sessão E ao turno corrente. Chamado por `instrumentar()` a cada
        requisição real — inclusive as intermediárias do function-calling automático, que o
        `usage_metadata` da resposta final não inclui."""
        self.gemini = self.gemini + consumo
        self._turno = self._turno + consumo

    def turno(self) -> Consumo:
        """Consumo acumulado desde o último `iniciar_turno()` — inclui chamadas que já custaram
        mesmo que uma chamada posterior do mesmo turno tenha falhado."""
        return self._turno

    def total_formatado(self) -> str:
        linhas = [f"Gemini:    {self.gemini.resumo()}"]
        if self.navegador.chamadas:
            linhas.append(
                f"Navegador: {self.navegador.resumo()} em {self.navegador.chamadas} chamadas"
            )
        linhas.append(f"Total da sessão: ~{dinheiro(self.total)}")
        return "\n".join(linhas)


# Acumulador da sessão corrente. Global por simplicidade: o Viking é um CLI de um usuário só.
SESSAO = Sessao()


def instrumentar(client, *, sessao: "Sessao | None" = None, antes=None, depois=None) -> bool:
    """Conta cada requisição do function-calling automático (AFC), não só a última.

    Em google-genai 2.24.0, `Models.generate_content` roda um laço síncrono de AFC que
    *reatribui* `response` a cada volta e devolve apenas a resposta final — as chamadas
    intermediárias (que escolheram qual tool chamar) somem do `usage_metadata` visível no chat.
    Isso subconta justamente os turnos com ferramenta, porque o schema das 11 tools do Viking vai
    em CADA requisição.

    Interceptamos `client.models._generate_content` (o método de baixo nível, chamado sem `self`
    porque atribuímos uma função comum a um atributo de instância) e contabilizamos toda resposta
    que passa por ali, sozinha ou dentro do laço de AFC. É um acoplamento consciente a um atributo
    privado do SDK: se ele sumir numa versão futura, `instrumentar` vira no-op (devolve False) em
    vez de quebrar o assistente — e o teste de acoplamento avisa alto quando isso acontecer.

    `sessao` é injetável (o motor da nuvem usa uma por pedido; o chat do Mac, o `SESSAO` global).
    `antes()` roda antes de CADA chamada ao modelo e pode recusá-la levantando (o teto de gasto da
    nuvem: conferir antes, não depois, é o que impede a chamada que passaria do teto); `depois`
    recebe o `Consumo` de cada chamada.

    Devolve True se instrumentou agora, False se já estava instrumentado ou se o gancho não existe.
    """
    alvo = sessao if sessao is not None else SESSAO
    modelos = getattr(client, "models", None)
    original = getattr(modelos, "_generate_content", None)
    if original is None or getattr(modelos, "_viking_instrumentado", False):
        return False
    assert modelos is not None  # com `original`, `models` existe

    def contabilizado(**kwargs):
        if antes is not None:
            antes()
        resposta = original(**kwargs)
        consumo = do_gemini(getattr(resposta, "usage_metadata", None))
        alvo.registrar_gemini(consumo)
        if depois is not None:
            depois(consumo)
        return resposta

    modelos._generate_content = contabilizado
    modelos._viking_instrumentado = True
    return True


# --- o teto de gasto do chat da nuvem (Sessão 10b, D59) ---------------------------------------


@dataclass(frozen=True)
class Gasto:
    """O gasto estimado do Gemini no dia e no mês do dono, com os tetos."""

    dia: float
    mes: float
    teto_dia: float
    teto_mes: float

    @property
    def estourou(self) -> bool:
        return self.dia >= self.teto_dia or self.mes >= self.teto_mes

    def texto(self) -> str:
        return (
            f"hoje ~{dinheiro(self.dia)} de {dinheiro(self.teto_dia)} · no mês "
            f"~{dinheiro(self.mes)} de {dinheiro(self.teto_mes)} (estimativa pelas tarifas)"
        )

    def como_dict(self) -> dict:
        return {
            "dia": self.dia,
            "mes": self.mes,
            "teto_dia": self.teto_dia,
            "teto_mes": self.teto_mes,
            "estimado": True,
        }


class TetoAtingido(RuntimeError):
    """O teto do dia ou do mês foi atingido: a chamada ao modelo não sai."""

    def __init__(self, gasto: Gasto):
        super().__init__(f"teto de gasto do Gemini atingido: {gasto.texto()}")
        self.gasto = gasto


class Teto:
    """O teto do chat da nuvem, guardado no Firestore (`gastos/AAAA-MM`: o total do mês e um mapa
    dia → total), porque o motor sobe e desce instâncias: um contador em memória zeraria a cada
    partida. O dia e o mês são os do dono (o fuso do deploy), não os do UTC da nuvem.

    `conferir` roda antes de cada chamada ao modelo (pelo gancho de `instrumentar`); `somar`,
    depois. Duas instâncias somando juntas não perdem gasto: a soma é por comparar e trocar."""

    COLECAO = "gastos"

    def __init__(self, *, mes: float, dia: float, fuso):
        self.teto_mes, self.teto_dia, self.fuso = mes, dia, fuso

    def _chaves(self, agora=None) -> tuple[str, str]:
        from datetime import UTC, datetime

        local = (agora or datetime.now(UTC)).astimezone(self.fuso)
        return f"{local:%Y-%m}", f"{local:%Y-%m-%d}"

    def _ref(self, mes: str):
        from lifeos import firestore_comum

        return firestore_comum.cliente().collection(self.COLECAO).document(mes)

    def gasto(self, agora=None) -> Gasto:
        mes, dia = self._chaves(agora)
        snap = self._ref(mes).get()
        dados = snap.to_dict() if snap.exists else {}
        dados = dados or {}
        return Gasto(
            dia=float(dados.get("dias", {}).get(dia, 0.0)),
            mes=float(dados.get("total", 0.0)),
            teto_dia=self.teto_dia,
            teto_mes=self.teto_mes,
        )

    def conferir(self, agora=None) -> Gasto:
        gasto = self.gasto(agora)
        if gasto.estourou:
            raise TetoAtingido(gasto)
        return gasto

    def somar(self, custo: float, agora=None) -> None:
        from google.api_core.exceptions import AlreadyExists

        from lifeos import firestore_comum

        if custo <= 0:
            return
        mes, dia = self._chaves(agora)
        ref = self._ref(mes)
        try:
            ref.create({"total": 0.0, "dias": {}})
        except AlreadyExists:
            pass

        def decidir(snap):
            dados = snap.to_dict() or {}
            dias = dict(dados.get("dias", {}))
            dias[dia] = float(dias.get(dia, 0.0)) + custo
            return {"total": float(dados.get("total", 0.0)) + custo, "dias": dias}, None

        firestore_comum.trocar(ref, decidir)
