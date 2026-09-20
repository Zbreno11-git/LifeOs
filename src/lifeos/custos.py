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
            linhas.append(f"Navegador: {self.navegador.resumo()} em {self.navegador.chamadas} chamadas")
        linhas.append(f"Total da sessão: ~{dinheiro(self.total)}")
        return "\n".join(linhas)


# Acumulador da sessão corrente. Global por simplicidade: o Viking é um CLI de um usuário só.
SESSAO = Sessao()


def instrumentar(client, *, sessao: "Sessao | None" = None) -> bool:
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

    `sessao` é injetável para teste; em produção usa sempre o `SESSAO` global do módulo.

    Devolve True se instrumentou agora, False se já estava instrumentado ou se o gancho não existe.
    """
    alvo = sessao if sessao is not None else SESSAO
    modelos = getattr(client, "models", None)
    original = getattr(modelos, "_generate_content", None)
    if original is None or getattr(modelos, "_viking_instrumentado", False):
        return False

    def contabilizado(**kwargs):
        resposta = original(**kwargs)
        alvo.registrar_gemini(do_gemini(getattr(resposta, "usage_metadata", None)))
        return resposta

    modelos._generate_content = contabilizado
    modelos._viking_instrumentado = True
    return True
