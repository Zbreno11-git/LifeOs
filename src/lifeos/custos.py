"""Contabilidade de uso dos modelos, para o usuário ver o que cada mensagem custou.

Duas fontes, com confiabilidade diferente:

- **Jev/OpenRouter**: o próprio provedor devolve `usage` em cada chamada, e quando vem um campo de
  custo ele é usado como valor real. É exato.
- **Gemini**: a API devolve contagem de tokens, não preço. O custo aqui é *estimativa*, calculada
  com as tarifas em `VIKING_PRECO_GEMINI_*` — confira-as no painel do provedor, preço muda.
"""

import os
from dataclasses import dataclass, field

# US$ por 1 milhão de tokens. Ajuste por env se a tabela do provedor mudar.
PRECO_GEMINI_ENTRADA = float(os.getenv("VIKING_PRECO_GEMINI_ENTRADA", "0.30"))
PRECO_GEMINI_SAIDA = float(os.getenv("VIKING_PRECO_GEMINI_SAIDA", "2.50"))

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
    """Converte o usage_metadata do google-genai. Custo é estimado a partir das tarifas."""
    if usage_metadata is None:
        return Consumo()
    entrada = getattr(usage_metadata, "prompt_token_count", 0) or 0
    saida = getattr(usage_metadata, "candidates_token_count", 0) or 0
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
    """Acumula o gasto da conversa inteira."""

    gemini: Consumo = field(default_factory=Consumo)
    navegador: Consumo = field(default_factory=Consumo)

    @property
    def total(self) -> float:
        return self.gemini.custo + self.navegador.custo

    def total_formatado(self) -> str:
        linhas = [f"Gemini:    {self.gemini.resumo()}"]
        if self.navegador.chamadas:
            linhas.append(f"Navegador: {self.navegador.resumo()} em {self.navegador.chamadas} chamadas")
        linhas.append(f"Total da sessão: ~{dinheiro(self.total)}")
        return "\n".join(linhas)


# Acumulador da sessão corrente. Global por simplicidade: o Viking é um CLI de um usuário só.
SESSAO = Sessao()
