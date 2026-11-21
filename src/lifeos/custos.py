"""Contabilidade de uso dos modelos, para o usuário ver o que cada mensagem custou.

Duas fontes, com confiabilidade diferente:

- **Jev/OpenRouter**: o próprio provedor devolve `usage` em cada chamada, e quando vem um campo de
  custo ele é usado como valor real. É exato.
- **Gemini**: a API devolve contagem de tokens, não preço. O custo aqui é *estimativa*, calculada
  com a tarifa **do modelo que respondeu** (`TARIFAS`, desde a Sessão 12: o dia a dia e o forte
  custam diferente) — confira-as no painel do provedor, preço muda. Tokens de conteúdo em cache
  têm tarifa própria e não são modelados aqui; a conta continua estimativa.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from lifeos.config import PRECO_GEMINI_ENTRADA, PRECO_GEMINI_SAIDA

# US$ por 1M de tokens (entrada, saída), por modelo e a partir de que dia (UTC), lidos em
# 2026-10-07 em https://ai.google.dev/gemini-api/docs/pricing (D65). O modelo do dia a dia
# (`turno.MODELO`) usa as `VIKING_PRECO_GEMINI_*` do `.env`, que valem 0,30/2,50 sem elas. O 3.8
# Flash dobra em 2027-01-01 ("$1.50 starting January 1, 2027"): a tabela já cobra o preço novo.
_SEMPRE = date.min
TARIFAS: dict[str, tuple[tuple[date, float, float], ...]] = {
    "gemini-3.5-flash-lite": ((_SEMPRE, PRECO_GEMINI_ENTRADA, PRECO_GEMINI_SAIDA),),
    "gemini-3.8-flash": ((_SEMPRE, 0.75, 3.75), (date(2027, 1, 1), 1.50, 7.50)),
    "gemini-2.5-flash": ((_SEMPRE, 0.30, 2.50),),
    # A memória (Sessão 13, D66): lido em 2026-10-08, "$0.20" por 1M de tokens de texto. A resposta
    # do embedding não traz contagem de tokens (medido em 2026-10-08): a entrada é contada em bytes
    # do texto, um limite de cima (um token nunca tem menos de um byte), e o teto erra para parar.
    "gemini-embedding-2": ((_SEMPRE, 0.20, 0.0),),
    # A fala da voz do estúdio (Sessão H1, D70): lido em 2026-11-21 na página de preços, US$ 0,50
    # por 1M de texto de entrada e US$ 6,00 por 1M de áudio de saída até 2026-12-31, e o dobro
    # depois. A transcrição usa o modelo do dia a dia (o áudio de entrada na mesma tarifa).
    "gemini-3.8-flash-lite-tts": ((_SEMPRE, 0.50, 6.00), (date(2027, 1, 1), 1.00, 12.00)),
}
# Os modelos cuja entrada é contada em bytes (o limite de cima), não em tokens.
POR_BYTES = frozenset({"gemini-embedding-2"})


def tarifa(modelo: str, quando: date | None = None) -> tuple[float, float]:
    """(entrada, saída) do modelo naquele dia. Um modelo fora da tabela custa a entrada mais cara
    e a saída mais cara dela, cada uma (desde a H1: o TTS tem a saída mais cara e uma entrada
    barata, e a maior soma subcontaria a entrada): o teto erra para o lado de parar."""
    dia = quando or datetime.now(UTC).date()
    faixas = TARIFAS.get(modelo.removeprefix("models/"))
    if faixas is None:
        todas = [(e, s) for f in TARIFAS.values() for _d, e, s in f]
        return max(e for e, _s in todas), max(s for _e, s in todas)
    vigentes = [(e, s) for desde, e, s in faixas if desde <= dia]
    return vigentes[-1]


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
    modelo: str = ""  # quem respondeu (só o Gemini); somas de modelos diferentes ficam sem nome

    def __add__(self, outro: "Consumo") -> "Consumo":
        modelos = {m for m in (self.modelo, outro.modelo) if m}
        return Consumo(
            entrada=self.entrada + outro.entrada,
            saida=self.saida + outro.saida,
            custo=self.custo + outro.custo,
            estimado=self.estimado or outro.estimado,
            chamadas=self.chamadas + outro.chamadas,
            modelo=modelos.pop() if len(modelos) == 1 else "",
        )

    def resumo(self) -> str:
        if self.modelo in POR_BYTES:  # sem contagem de tokens na resposta: o limite de cima
            return f"≤{self.entrada} tokens (bytes do texto) · ~{dinheiro(self.custo)}"
        tokens = f"{self.entrada + self.saida} tokens ({self.entrada} in / {self.saida} out)"
        prefixo = "~" if self.estimado else ""
        return f"{tokens} · {prefixo}{dinheiro(self.custo)}"


def do_gemini(usage_metadata, modelo: str, quando: date | None = None) -> Consumo:
    """Converte o usage_metadata do google-genai. Custo é estimado pela tarifa do `modelo`.

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
    preco_entrada, preco_saida = tarifa(modelo, quando)
    custo = (entrada * preco_entrada + saida * preco_saida) / 1_000_000
    modelo = modelo.removeprefix("models/")
    return Consumo(
        entrada=entrada, saida=saida, custo=custo, estimado=True, chamadas=1, modelo=modelo
    )


def _bytes_do_texto(contents) -> int:
    """Os bytes UTF-8 do texto de um pedido de embedding (strings, `Content` ou `Part`). Outra
    forma erra alto: contar zero seria subcontar o teto."""
    itens = contents if isinstance(contents, list | tuple) else [contents]
    total = 0
    for item in itens:
        if isinstance(item, str):
            total += len(item.encode())
            continue
        partes = getattr(item, "parts", None)
        for parte in partes if partes is not None else [item]:
            texto = getattr(parte, "text", None)
            if not isinstance(texto, str):
                raise TypeError(f"pedido de embedding numa forma que não sei contar: {type(item)}")
            total += len(texto.encode())
    return total


def do_embedding(contents, modelo: str, quando: date | None = None) -> Consumo:
    """O custo de um pedido de embedding pelos bytes do texto (o limite de cima: `POR_BYTES`)."""
    entrada = _bytes_do_texto(contents)
    preco_entrada, _saida = tarifa(modelo, quando)
    modelo = modelo.removeprefix("models/")
    return Consumo(
        entrada=entrada,
        custo=entrada * preco_entrada / 1_000_000,
        estimado=True,
        chamadas=1,
        modelo=modelo,
    )


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
    por_modelo: dict[str, Consumo] = field(default_factory=dict)
    _turno: Consumo = field(default_factory=Consumo, repr=False)
    _turno_por_modelo: dict[str, Consumo] = field(default_factory=dict, repr=False)

    @property
    def total(self) -> float:
        return self.gemini.custo + self.navegador.custo

    def iniciar_turno(self) -> None:
        """Zera o acumulador do turno. Chame antes de cada `send_message`."""
        self._turno = Consumo()
        self._turno_por_modelo = {}

    def registrar_gemini(self, consumo: Consumo) -> None:
        """Soma ao total da sessão E ao turno corrente. Chamado por `instrumentar()` a cada
        requisição real — inclusive as intermediárias do function-calling automático, que o
        `usage_metadata` da resposta final não inclui."""
        self.gemini = self.gemini + consumo
        self._turno = self._turno + consumo
        for contas in (self.por_modelo, self._turno_por_modelo):
            contas[consumo.modelo] = contas.get(consumo.modelo, Consumo()) + consumo

    def juntar(self, outra: "Sessao") -> None:
        """Soma o turno de outra sessão a esta, modelo a modelo (a anotação da memória roda numa
        thread com a sua, e o 💸 do turno mostra as duas; Sessão 13)."""
        for consumo in outra._turno_por_modelo.values():
            self.registrar_gemini(consumo)

    def turno(self) -> Consumo:
        """Consumo acumulado desde o último `iniciar_turno()` — inclui chamadas que já custaram
        mesmo que uma chamada posterior do mesmo turno tenha falhado."""
        return self._turno

    def resumo_do_turno(self) -> str:
        """O gasto do turno com o modelo que respondeu (Sessão 12: o forte aparece pelo nome)."""
        return _por_modelo(self._turno_por_modelo)

    def total_formatado(self) -> str:
        linhas = [f"Gemini:    {self.gemini.resumo()}"]
        if len(self.por_modelo) > 1:
            linhas += [f"  {m}: {c.resumo()}" for m, c in sorted(self.por_modelo.items())]
        if self.navegador.chamadas:
            linhas.append(
                f"Navegador: {self.navegador.resumo()} em {self.navegador.chamadas} chamadas"
            )
        linhas.append(f"Total da sessão: ~{dinheiro(self.total)}")
        return "\n".join(linhas)


def _por_modelo(contas: dict[str, Consumo]) -> str:
    return "; ".join(f"{m or '?'}: {c.resumo()}" for m, c in sorted(contas.items()))


# Acumulador da sessão corrente. Global por simplicidade: o Viking é um CLI de um usuário só.
SESSAO = Sessao()


def instrumentar(
    client, *, sessao: "Sessao | None" = None, antes=None, depois=None, escolher=None
) -> bool:
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
    `escolher(modelo)` devolve o modelo desta chamada (o forte no meio do turno, Sessão 12);
    `antes(modelo)` roda antes de CADA chamada ao modelo e pode recusá-la levantando (o teto de
    gasto da nuvem: conferir antes, não depois, é o que impede a chamada que passaria do teto);
    `depois` recebe o `Consumo` de cada chamada, com o modelo que respondeu.

    Devolve True se instrumentou agora, False se já estava instrumentado ou se o gancho não existe.
    """
    alvo = sessao if sessao is not None else SESSAO
    modelos = getattr(client, "models", None)
    original = getattr(modelos, "_generate_content", None)
    if original is None or getattr(modelos, "_viking_instrumentado", False):
        return False
    assert modelos is not None  # com `original`, `models` existe

    def contabilizado(**kwargs):
        if escolher is not None:
            kwargs["model"] = escolher(kwargs.get("model") or "")
        modelo = str(kwargs.get("model") or "")
        if antes is not None:
            antes(modelo)
        resposta = original(**kwargs)
        consumo = do_gemini(getattr(resposta, "usage_metadata", None), modelo)
        alvo.registrar_gemini(consumo)
        if depois is not None:
            depois(consumo)
        return resposta

    modelos._generate_content = contabilizado

    # O embedding da memória (Sessão 13): o mesmo teto antes e a mesma conta depois.
    original_embed = getattr(modelos, "_embed_content", None)
    if original_embed is not None:

        def embutido(**kwargs):
            modelo = str(kwargs.get("model") or "")
            if antes is not None:
                antes(modelo)
            consumo = do_embedding(kwargs.get("contents"), modelo)
            resposta = original_embed(**kwargs)
            alvo.registrar_gemini(consumo)
            if depois is not None:
                depois(consumo)
            return resposta

        modelos._embed_content = embutido
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


# --- as cotas do dia: o modelo forte e a busca (Sessão 12, D65) -------------------------------


class CotaAtingida(RuntimeError):
    """A cota do dia do modelo forte ou da busca acabou: o pedido não sai (o texto diz qual)."""


class Cotas:
    """O que o dono limitou por dia além do teto (D65, 2026-10-07): o gasto do modelo forte (US$)
    e as consultas de busca. Um documento por dia do dono (`cotas/AAAA-MM-DD`), fora do backup
    (um contador de um dia não se restaura) e fora de `gastos/` (o formato fechado do backup e o
    `Teto.somar`, que reescreve o mês inteiro). Cada campo muda sozinho, por comparar e trocar:
    duas instâncias somando juntas não perdem nada, e a 31ª reserva de busca não passa."""

    COLECAO = "cotas"

    def __init__(self, *, forte_dia: float, buscas_dia: int, fuso):
        self.forte_dia, self.buscas_dia, self.fuso = forte_dia, buscas_dia, fuso

    def _dia(self, agora=None) -> str:
        return f"{(agora or datetime.now(UTC)).astimezone(self.fuso):%Y-%m-%d}"

    def _ref(self, agora=None):
        from lifeos import firestore_comum

        return firestore_comum.cliente().collection(self.COLECAO).document(self._dia(agora))

    def hoje(self, agora=None) -> dict:
        snap = self._ref(agora).get()
        dados = (snap.to_dict() if snap.exists else None) or {}
        return {"forte": float(dados.get("forte", 0.0)), "buscas": int(dados.get("buscas", 0))}

    def conferir_forte(self, agora=None) -> None:
        gasto = self.hoje(agora)["forte"]
        if gasto >= self.forte_dia:
            raise CotaAtingida(
                f"o modelo forte já gastou ~{dinheiro(gasto)} hoje, e a cota do dia é "
                f"{dinheiro(self.forte_dia)}"
            )

    def _criar(self, agora=None):
        from google.api_core.exceptions import AlreadyExists

        ref = self._ref(agora)
        try:
            ref.create({"forte": 0.0, "buscas": 0})
        except AlreadyExists:
            pass
        return ref

    def _somar(self, campo: str, valor: float, agora=None) -> None:
        from lifeos import firestore_comum

        def decidir(snap):
            dados = snap.to_dict() or {}
            return {campo: dados.get(campo, 0) + valor}, None

        firestore_comum.trocar(self._criar(agora), decidir)

    def somar_forte(self, custo: float, agora=None) -> None:
        if custo > 0:
            self._somar("forte", float(custo), agora)

    def reservar_busca(self, agora=None) -> None:
        """Uma consulta, antes de buscar; `CotaAtingida` sem gastar nada se o dia acabou."""
        from lifeos import firestore_comum

        def decidir(snap):
            feitas = int((snap.to_dict() or {}).get("buscas", 0))
            if feitas >= self.buscas_dia:
                return None, False
            return {"buscas": feitas + 1}, True

        if not firestore_comum.trocar(self._criar(agora), decidir):
            raise CotaAtingida(
                f"já foram {self.buscas_dia} buscas na web hoje, a cota do dia; amanhã volta"
            )

    def somar_buscas(self, consultas: int, agora=None) -> None:
        """As consultas a mais que o modelo fez numa busca (a primeira já foi reservada)."""
        if consultas > 0:
            self._somar("buscas", int(consultas), agora)


def exportar_gastos() -> list[dict]:
    """Os gastos do teto, um por mês (`gastos/AAAA-MM`), para o backup (Sessão 11c, D63)."""
    from lifeos import firestore_comum

    copias = []
    for snap in firestore_comum.cliente().collection(Teto.COLECAO).stream():
        dados = snap.to_dict() or {}
        copias.append(
            {
                "mes": snap.id,
                "total": float(dados.get("total", 0.0)),
                "dias": {dia: float(v) for dia, v in dict(dados.get("dias", {})).items()},
            }
        )
    return sorted(copias, key=lambda c: c["mes"])


def importar_gasto(copia: dict) -> str:
    """Grava o mês só se ele não existe (`criado`); se existe, nada muda (`igual`/`diferente`):
    um mês que voltou a gastar depois do backup tem o total mais novo, e ele fica."""
    from google.api_core.exceptions import AlreadyExists

    from lifeos import firestore_comum

    ref = firestore_comum.cliente().collection(Teto.COLECAO).document(copia["mes"])
    try:
        ref.create({"total": float(copia["total"]), "dias": dict(copia["dias"])})
    except AlreadyExists:
        atual = ref.get().to_dict() or {}
        mesmo = {
            "mes": copia["mes"],
            "total": float(atual.get("total", 0.0)),
            "dias": {dia: float(v) for dia, v in dict(atual.get("dias", {})).items()},
        } == copia
        return "igual" if mesmo else "diferente"
    return "criado"
