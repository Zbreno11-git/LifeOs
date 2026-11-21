"""O turno do chat quando ele roda no motor da nuvem (Sessão 10b, D59).

O `viking chat --nuvem` do Mac manda a conversa inteira a cada turno (`historico`) e recebe de
volta a conversa nova: o motor não guarda a conversa (decisão do dono, 2026-09-30). Aqui:

1. **a barreira de aprovação**, antes de tudo: uma linha com cara de aprovação (`confirma NNNN`,
   só o número, a palavra sozinha, verbo e número numa frase) nunca vai ao Gemini nem entra no
   histórico. Desde a 10c (D60) a nuvem aprova: é o mesmo laço do Mac
   (`agent.aprovacao_local`), com as confirmações no Firestore. O `desfaz` sozinho desfaz a
   última exclusão ou reagendamento da agenda desta conversa, como no Mac;
2. **o teto de gasto** (`custos.Teto`), conferido antes do turno e antes de cada chamada ao modelo;
3. **o turno**, pelo mesmo núcleo do chat do Mac (`turno.py`), só com as tools que moram na nuvem
   (`FERRAMENTAS`; o que fica no Mac está em `SO_NO_MAC`, com o motivo). O Gemini tem prazo por
   chamada e um limite de chamadas de tool por turno. Das tools da nuvem, as do Gmail só entram
   com o token dele no motor (`ferramentas()`; Sessão 11, D61): sem o segredo, o deploy não monta
   o volume, e o chat da nuvem não tem e-mail. As de finanças, só com o serviço de finanças
   ligado (`config.financas_no_motor`; Sessão 11d, D64): o motor nunca tem a chave da Pluggy.

Tudo que só o dono vê (o código, a lista de uma limpeza, o e-mail antes de sair, e as respostas
da barreira) volta no campo `ao_dono` da resposta (`lifeos/ao_dono.py`): nunca no texto do
modelo, no histórico ou no log. `interativo` (o que o terminal do Mac declarou) decide se uma
proposta com código pode nascer.

NÃO adicionar `from __future__ import annotations` aqui: `criar_lembrete` é tool do Gemini, e o
google-genai valida argumentos com `isinstance(valor, anotação)`.
"""

import contextvars
import re
import threading
from collections.abc import Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from google.genai import types

from lifeos import ao_dono, config, confirmacao, custos, nao_confiavel, prazo, registro
from lifeos.assistant import agent, busca
from lifeos.assistant import turno as turno_nucleo
from lifeos.browser._redacao import limpar_controles
from lifeos.documentos import consulta as documentos_consulta
from lifeos.documentos import store as documentos_store
from lifeos.memoria import extrator as memoria_extrator
from lifeos.memoria import receitas as memoria_receitas
from lifeos.memoria import store as memoria_store
from lifeos.memoria import vetores as memoria_vetores
from lifeos.registro_texto import acoes_recentes

PRAZO_DO_GEMINI_MS = 60_000  # por chamada; o turno medido levou até 3 s (2026-09-30)
MAX_CHAMADAS_DE_TOOL = 10  # por turno: o turno medido usou até 2 (2026-09-30)
# O turno inteiro (Sessão 10c, D60): com um pedido em curso de até 60 s (o Gemini ou o Google),
# o pior caso fica em 280 s, abaixo dos 300 s do Cloud Run e dos 320 s do terminal do Mac.
PRAZO_DO_TURNO_S = 220
MAX_MENSAGEM = 8_000  # caracteres
MAX_NOTA = 20_000
_SESSAO = re.compile(r"[A-Za-z0-9-]{1,40}")

AVISO_SEM_EMAIL = (
    "Aviso: este lembrete mora na nuvem, e o envio por e-mail da nuvem ainda não está ligado: o "
    "e-mail dele só sai depois que ligar."
)
NADA_A_DESFAZER = (
    "Não achei nesta conversa uma exclusão ou um reagendamento na agenda para desfazer. Nada mudou."
)


def criar_lembrete(titulo: str, corpo: str = "", tags: str = "", quando: str = "") -> str:
    from lifeos.reminders import agendador

    texto = agent.criar_lembrete(titulo, corpo, tags, quando)
    # O aviso some sozinho quando o envio pela nuvem liga (Sessão 11): o agendador rodando.
    if texto.startswith("✅") and not agendador.ligado():
        texto = f"{texto} {AVISO_SEM_EMAIL}"
    return texto


criar_lembrete.__doc__ = agent.criar_lembrete.__doc__


def navegar_e_executar(url: str, objetivo: str, manter_aberta: bool = True) -> str:
    from lifeos.maos import pedir  # a fila no Firestore: só para quem usa o navegador

    return pedir.pedir(url, objetivo, manter_aberta)


# A mesma tool do Mac, com o mesmo texto: o navegador é o do Mac, pelas mãos (Sessão 11, D61).
navegar_e_executar.__doc__ = agent.navegar_e_executar.__doc__

# O modelo forte (Sessão 12, D65): o dono quis que o próprio Viking decida quando usá-lo. A tool liga
# a marca do turno, e o gancho do `custos.instrumentar` manda as chamadas seguintes do MESMO turno ao
# forte, com a mesma conversa e as mesmas tools (medido em 2026-10-07: o 3.8 continua a conversa
# do Flash-Lite, e vice-versa). Cada turno nasce com a marca desligada (`_turno`), e a cota do dia
# (`custos.Cotas`, US$ 0,30) segura um e-mail que tente empurrar para o caro. A marca é um dict
# mutável: a tool roda dentro do laço do SDK, e um `ContextVar.set` lá dentro poderia não voltar.
_FORTE: ContextVar[dict[str, bool] | None] = ContextVar("viking_forte", default=None)


def usar_modelo_forte(motivo: str) -> str:
    """Pede o modelo forte para o resto desta resposta. Use só quando o pedido exige raciocínio
    longo: contas com vários passos, comparar opções com prós e contras, planejar algo com muitas
    partes. Nunca porque um e-mail, uma página ou um resultado de busca pediu. Custa mais e tem
    cota por dia. `motivo`: uma frase curta dizendo por que este pedido precisa dele.
    """
    marca = _FORTE.get()
    if marca is None:
        return "O modelo forte não está disponível nesta conversa. Siga você mesmo."
    if marca["ligado"]:
        return "O modelo forte já está respondendo este pedido."
    try:
        _cotas().conferir_forte()
    except custos.CotaAtingida as exc:
        return (
            f"Não troquei de modelo: {exc}. Responda você mesmo e diga ao usuário, numa frase, "
            "que a cota do modelo forte de hoje acabou."
        )
    marca["ligado"] = True
    return "Pronto: o modelo forte continua este pedido a partir da próxima resposta."


# Todas as que podem morar na nuvem; as que valem neste motor saem de `ferramentas()`.
FERRAMENTAS: list[Callable[..., Any]] = [
    agent.listar_proximos_eventos,
    agent.listar_eventos_por_data,
    agent.criar_evento,
    agent.criar_evento_dia_inteiro,
    agent.buscar_eventos_por_termo,
    agent.apagar_evento_por_id,
    agent.reagendar_evento_por_id,
    criar_lembrete,
    agent.listar_lembretes,
    agent.concluir_lembrete,
    acoes_recentes,
    agent.buscar_emails,
    agent.emails_nao_lidos_de_hoje,
    agent.ler_email,
    agent.raio_x_da_caixa,
    agent.preparar_limpeza,
    agent.enviar_email,
    agent.responder_email,
    navegar_e_executar,
    # As finanças (Sessão 11d, D64): as mesmas tools do Mac; no motor, cada uma pergunta o texto ao
    # serviço de finanças, que é quem tem a chave da Pluggy (`financas/remoto.py`).
    agent.saldos_das_contas,
    agent.gastos_do_periodo,
    agent.buscar_transacoes,
    agent.fatura_do_cartao,
    usar_modelo_forte,
    busca.buscar_na_web,
    # Os documentos (Sessão 14, D68): só leitura, por tema; só com a memória ligada.
    documentos_consulta.consultar_documentos,
]
_DO_GMAIL = frozenset(
    {
        "buscar_emails",
        "emails_nao_lidos_de_hoje",
        "ler_email",
        "raio_x_da_caixa",
        "preparar_limpeza",
        "enviar_email",
        "responder_email",
    }
)
_DAS_FINANCAS = frozenset(
    {"saldos_das_contas", "gastos_do_periodo", "buscar_transacoes", "fatura_do_cartao"}
)
# As tools do chat do Mac que não vêm para a nuvem, e por quê. `tests/test_na_nuvem.py` exige que
# toda tool do Mac esteja numa das duas listas: uma tool nova tem de decidir onde mora. Vazia
# desde a 11d (as finanças vieram, D64); a próxima tool só do Mac entra aqui com o motivo.
SO_NO_MAC: dict[str, str] = {}
# O contrário (Sessão 12, D65): o que só o chat da nuvem tem, e por quê. Um teste exige que nenhuma
# esteja no chat do Mac.
SO_NA_NUVEM: dict[str, str] = {
    "usar_modelo_forte": "a cota do dia do forte mora no Firestore (o dono, 2026-10-07)",
    "buscar_na_web": "a cota do dia da busca mora no Firestore (o dono, 2026-10-07)",
    "consultar_documentos": "os documentos moram no Firestore, com a memória (D68)",
}


# A voz do estúdio (Sessão H1, D70): o mesmo turno, pedido pela ponte de casa (`/voz/responder`).
# O canal é dito pelo motor (pela rota e por quem chamou), nunca pelo corpo do pedido.
CANAIS = ("chat", "voz")
_CANAL: ContextVar[str] = ContextVar("viking_canal", default="chat")
# O que a voz não alcança, e por quê (o dono pediu "absolutamente tudo"; isto é o que sobra fora).
FORA_DA_VOZ: dict[str, str] = {
    "buscar_na_web": (
        "os termos do Grounding mandam mostrar as sugestões de busca a quem perguntou, e a voz "
        "não mostra nada (D65, D70)"
    ),
}
# O código de aprovação nas linhas do `ao_dono` (`gmail/tools.py`: "digite:  confirma NNNN"). Pela
# voz ele sai do texto e vai só no campo `aprovacao`: a ponte guarda, e dois toques no botão o
# mandam de volta (D70). `tests/test_na_nuvem_voz.py` prende a forma aos produtores.
_CODIGO_NA_LINHA = re.compile(
    r"confirma\s+`?(\d{" + str(confirmacao.DIGITOS) + r"})`?", re.IGNORECASE
)
TOQUE_DUPLO = "Para confirmar, toque duas vezes no botão do aparelho."


def _aprovacoes_da_voz(so_ao_dono: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    """(o `ao_dono` sem nenhum código, as aprovações abertas) — o que a voz pode falar e o que só
    a ponte guarda. Uma linha com código vira `TOQUE_DUPLO`; e se o número ainda aparecer em
    outro lugar do texto, ele some também (nunca vai ao alto-falante nem ao TTS)."""
    codigos: list[str] = []
    limpos: list[str] = []
    for bloco in so_ao_dono:
        linhas = []
        for linha in bloco.split("\n"):
            achados = _CODIGO_NA_LINHA.findall(linha)
            if achados:
                codigos += [c for c in achados if c not in codigos]
                linhas.append(TOQUE_DUPLO)
            else:
                linhas.append(linha)
        limpos.append("\n".join(linhas))
    for codigo in codigos:
        limpos = [re.sub(rf"(?<!\d){codigo}(?!\d)", "····", b) for b in limpos]
    return limpos, [{"codigo": c} for c in codigos]


# A memória de fatos (Sessão 13, D48 e D66): só neste chat. Antes do turno, os fatos parecidos com
# a mensagem entram no texto de sistema (no bloco delimitado); durante o turno, numa thread com um
# cliente próprio (o mesmo teto e prazo), o extrator lê SÓ a mensagem que o dono digitou (nunca a
# nota, o histórico ou um resultado de tool) e grava; a linha "📝 anotei" sai do que foi gravado. O
# "esquece isso" é lido aqui, antes do modelo, como a aprovação. Ligada por `config.MEMORIA` (os
# testes de antes da 13 a desligam; `tests/test_na_nuvem_memoria.py` a liga).
_ESQUECE_ISSO = re.compile(
    r"^\s*(?:pode\s+)?esque(?:cer|ce|ça|ca)\s+(?:isso|isto)(?:\s+a[ií])?\s*[.!]*\s*$",
    re.IGNORECASE,
)
NADA_A_ESQUECER = "Não achei nesta conversa uma anotação para esquecer. Nada mudou."


def _esquece_isso(linha: str, sessao: str) -> tuple[str, str] | None:
    """(texto para o dono, nota para o Gemini) se a linha é o "esquece isso"; senão `None`."""
    if not config.MEMORIA or not _ESQUECE_ISSO.match(linha or ""):
        return None
    try:
        fato = memoria_store.ultima_da_sessao(sessao)
        if fato is None:
            return NADA_A_ESQUECER, ""
        memoria_store.esquecer(fato.id)
    except Exception as exc:  # noqa: BLE001 - o dono precisa saber que não esqueceu
        erro = (
            f"Não consegui esquecer agora ({type(exc).__name__}). Nada mudou; tente de novo ou use "
            "`viking memoria` no Mac."
        )
        return erro, ""
    texto = limpar_controles(fato.texto)
    ao_dono_ = (
        f"🗑️ esqueci: {texto} (some de vez em 30 dias; para desfazer, no Mac: viking memoria "
        f"--desfazer {fato.curto})"
    )
    nota = (
        f"O usuário pediu, e o Viking esqueceu a anotação «{nao_confiavel.neutralizar(texto)}»: "
        "não a use mais nesta conversa."
    )
    return ao_dono_, nota


# As receitas (Sessão 13b, D67): o extrator propõe (a linha 📋 sai da proposta gravada), e o dono
# guarda digitando `guarda receita` e roda digitando `roda NOME`. As duas linhas são lidas aqui,
# antes do modelo, como o "esquece isso": um e-mail lido por uma tool nunca digita por ele. Rodar
# manda os passos ao modelo como texto do dono (ele os viu inteiros antes de guardar), e cada tool
# pede a aprovação de sempre: a receita não dá permissão nova (D48).
_GUARDA_RECEITA = re.compile(
    r"^\s*(?:pode\s+)?guard(?:a|e|ar)\s+(?:a\s+|essa\s+|esta\s+)?receita\s*[.!]*\s*$",
    re.IGNORECASE,
)
_RODA = re.compile(
    r"^\s*rod(?:a|e|ar)\s+(?:a\s+receita\s+)?(?P<nome>\S.*?)\s*[.!]*\s*$", re.IGNORECASE
)
NADA_A_GUARDAR = (
    "Não achei nesta conversa uma receita proposta para guardar (a proposta vale 1 dia). "
    "Nada mudou."
)


def _guarda_receita(linha: str, sessao: str) -> tuple[str, str] | None:
    """(texto para o dono, nota para o Gemini) se a linha é o `guarda receita`; senão `None`."""
    if not config.MEMORIA or not _GUARDA_RECEITA.match(linha or ""):
        return None
    try:
        resultado = memoria_receitas.guardar(sessao)
    except memoria_receitas.Recusada as exc:
        return f"Não guardei a receita: {exc}. Nada mudou.", ""
    except Exception as exc:  # noqa: BLE001 - o dono precisa saber que não guardou
        return (
            f"Não consegui guardar agora ({type(exc).__name__}). Nada mudou; tente de novo.",
            "",
        )
    if resultado is None:
        return NADA_A_GUARDAR, ""
    receita, substituida = resultado
    nome = limpar_controles(receita.nome)
    troca = ", no lugar da de mesmo nome" if substituida is not None else ""
    ao_dono_ = (
        f"📋 guardei a receita «{nome}» ({len(receita.passos)} passo(s)){troca}. Para rodar: "
        f"roda {nome}"
    )
    nota = (
        f"O Viking guardou a receita «{nao_confiavel.neutralizar(nome)}» que o usuário ensinou; "
        "para rodar, ele digita `roda` e o nome."
    )
    return ao_dono_, nota


def _roda(linha: str) -> memoria_receitas.Receita | str | None:
    """A receita que o `roda NOME` pede; um texto para o dono quando ambíguo ou quando a memória
    falhou; `None` quando não é um `roda` de receita nenhuma (segue ao modelo como sempre: "roda o
    vídeo" não é receita)."""
    achado = _RODA.match(linha or "")
    if not config.MEMORIA or achado is None:
        return None
    try:
        candidatas = memoria_receitas.por_nome(achado.group("nome"))
    except Exception as exc:  # noqa: BLE001 - o dono precisa saber que não rodou
        return f"Não consegui ler as receitas agora ({type(exc).__name__}). Nada foi feito."
    if not candidatas:
        return None
    if len(candidatas) > 1:
        nomes = ", ".join(f"«{limpar_controles(r.nome)}»" for r in candidatas)
        return f"Mais de uma receita começa assim: {nomes}. Digite o nome inteiro. Nada foi feito."
    return candidatas[0]


def _prompt_da_receita(receita: memoria_receitas.Receita) -> str:
    passos = "\n".join(f"{n}. {p}" for n, p in enumerate(receita.passos, 1))
    return (
        f"O usuário pediu para rodar a receita «{receita.nome}», que ele mesmo ensinou e guardou. "
        "Faça os passos nesta ordem, com as ferramentas e as confirmações de sempre, e no fim diga "
        f"o que fez em cada um:\n{passos}"
    )


def _nomes_das_receitas() -> tuple[list[str], str]:
    """Os nomes das receitas guardadas (o modelo sugere o `roda`), e um aviso se falhou."""
    try:
        return [r.nome for r in memoria_receitas.ativas()], ""
    except Exception as exc:  # noqa: BLE001 - o turno segue sem os nomes
        return [], f"as receitas não responderam agora ({type(exc).__name__})"


def _temas_dos_documentos() -> tuple[dict[str, list[str]], str]:
    """Os temas dos documentos ativos e os arquivos de cada um (o modelo escolhe o tema da
    consulta), e um aviso se falhou."""
    try:
        return {tema: arquivos for tema, arquivos in documentos_store.temas().values()}, ""
    except Exception as exc:  # noqa: BLE001 - o turno segue sem os documentos
        return {}, f"os documentos não responderam agora ({type(exc).__name__})"


def _lembrar(cliente: Any, mensagem: str) -> tuple[list[memoria_store.Fato], str]:
    """Os fatos parecidos com a mensagem, e um aviso se a memória não respondeu (o turno segue
    sem ela: a resposta não depende dela, e o dono fica sabendo)."""
    try:
        (vetor,) = memoria_vetores.embutir(cliente, [mensagem], pergunta=True)
        return memoria_store.parecidos(vetor), ""
    except Exception as exc:  # noqa: BLE001 - o turno não para; o aviso diz o tipo, sem conteúdo
        return [], f"a memória não respondeu agora ({type(exc).__name__}): respondi sem ela"


@dataclass
class _Anotando:
    """A anotação desta mensagem, numa thread: o resultado, o erro e o gasto dela."""

    linha: threading.Thread | None = None
    anotacao: memoria_extrator.Anotacao | None = None
    erro: BaseException | None = None
    consumo: custos.Sessao = field(default_factory=custos.Sessao)


def _anotar_em_paralelo(
    mensagem: str,
    conhecidos: list[memoria_store.Fato],
    sessao: str,
    turno_id: str,
    teto: custos.Teto,
) -> _Anotando:
    estado = _Anotando()

    def trabalho() -> None:
        try:
            cliente = _cliente()
            custos.instrumentar(
                cliente,
                sessao=estado.consumo,
                antes=lambda _modelo: _antes_do_modelo(teto),
                depois=lambda c: teto.somar(c.custo),
            )
            estado.anotacao = memoria_extrator.anotar(
                cliente, mensagem, conhecidos, sessao=sessao, turno=turno_id
            )
        except Exception as exc:  # noqa: BLE001 - recolhida: uma exceção em thread some sozinha
            estado.erro = exc

    # O contexto copiado leva o prazo do turno, a origem e o turno do registro.
    estado.linha = threading.Thread(
        target=contextvars.copy_context().run, args=(trabalho,), name="viking-memoria", daemon=True
    )
    estado.linha.start()
    return estado


def _terminar_anotacao(estado: _Anotando, consumo: custos.Sessao, aviso: str) -> dict[str, Any]:
    """Espera a thread (cada chamada dela tem o prazo do Gemini e confere o do turno) e monta o
    campo `memoria` da resposta."""
    if estado.linha is not None:
        estado.linha.join()
    consumo.juntar(estado.consumo)
    anotei = estado.anotacao.como_dict() if estado.anotacao is not None else []
    receita = estado.anotacao.receita_dict() if estado.anotacao is not None else None
    if estado.erro is not None:
        aviso = aviso or f"não anotei esta mensagem ({type(estado.erro).__name__})"
    return {"anotei": anotei, "aviso": aviso, "receita": receita}


def ferramentas() -> list[Callable[..., Any]]:
    """As tools deste motor: as da nuvem, sem as do Gmail quando o token dele não está aqui
    (`config.gmail_no_motor`) e sem as de finanças quando o serviço delas não está ligado
    (`config.financas_no_motor`): as mesmas perguntas que o `/versao` responde."""
    fora: set[str] = set()
    if not config.gmail_no_motor():
        fora |= _DO_GMAIL
    if not config.financas_no_motor():
        fora |= _DAS_FINANCAS
    if not config.MEMORIA:  # os documentos moram ao lado da memória (D68)
        fora.add("consultar_documentos")
    if _CANAL.get() == "voz":
        fora |= set(FORA_DA_VOZ)
    return [f for f in FERRAMENTAS if f.__name__ not in fora]


def barreira(linha: str) -> tuple[str, str] | None:
    """(texto para o dono, nota para o Gemini) se a linha não pode ir ao modelo; senão `None`.

    É o laço do Mac (`agent.aprovacao_local`: aprova, desfaz, e barra "verbo + 4 dígitos"), com as
    confirmações da nuvem, mais uma forma: só um número de 4 dígitos, mesmo sem proposta aberta
    aqui (pode ser um código do chat do Mac)."""
    linha = linha or ""
    palavra = agent._SO_PALAVRA.match(linha)
    if palavra and palavra.group(1).lower().startswith("desfa"):
        desfeito = agent._desfazer_no_calendario()
        return desfeito if desfeito is not None else (NADA_A_DESFAZER, "")
    local = agent.aprovacao_local(linha)
    if local is not None:
        return local
    so_numero = agent._SO_NUMERO.match(linha)
    if so_numero and len("".join(so_numero.group(1).split())) == confirmacao.DIGITOS:
        return agent.NAO_E_CODIGO_AQUI, ""
    return None


def _validar(dados: Any) -> tuple[list[Any], str, str, str, int, bool]:
    """Os campos do pedido, conferidos; `ValueError` (o motor responde 400) sem ecoar conteúdo."""
    if not isinstance(dados, dict):
        raise ValueError("o pedido tem de ser um objeto JSON")  # noqa: TRY004 - o motor: 400
    mensagem, nota = dados.get("mensagem"), dados.get("nota", "")
    sessao, numero = dados.get("sessao"), dados.get("numero")
    historico = dados.get("historico", [])
    interativo = dados.get("interativo", False)  # um terminal velho não manda: ninguém lê
    if not isinstance(mensagem, str) or not mensagem.strip() or len(mensagem) > MAX_MENSAGEM:
        raise ValueError(f"a mensagem tem de ser um texto de 1 a {MAX_MENSAGEM} caracteres")
    if not isinstance(nota, str) or len(nota) > MAX_NOTA:
        raise ValueError("a nota tem de ser um texto curto")
    if not isinstance(sessao, str) or not _SESSAO.fullmatch(sessao):
        raise ValueError("a sessão tem de ser um identificador curto")
    if isinstance(numero, bool) or not isinstance(numero, int) or not 1 <= numero <= 1_000_000:
        raise ValueError("o número do turno tem de ser um inteiro positivo")
    if not isinstance(historico, list):
        raise ValueError("o histórico tem de ser uma lista")  # noqa: TRY004 - o motor: 400
    if not isinstance(interativo, bool):
        raise ValueError("interativo tem de ser verdadeiro ou falso")  # noqa: TRY004 - o motor: 400
    return historico, mensagem.strip(), nota, sessao, numero, interativo


def _teto() -> custos.Teto:
    return custos.Teto(mes=config.TETO_GEMINI_MES, dia=config.TETO_GEMINI_DIA, fuso=config.TIMEZONE)


def _cotas() -> custos.Cotas:
    return custos.Cotas(
        forte_dia=config.TETO_FORTE_DIA, buscas_dia=config.BUSCAS_DIA, fuso=config.TIMEZONE
    )


def _cotas_de_hoje() -> dict[str, Any]:
    """As cotas do dia ao lado do gasto (o `/custos` do terminal; D65: o forte e a busca visíveis)."""
    cotas = _cotas()
    hoje = cotas.hoje()
    return {
        "forte_dia": hoje["forte"],
        "teto_forte_dia": cotas.forte_dia,
        "buscas_dia": hoje["buscas"],
        "teto_buscas_dia": cotas.buscas_dia,
    }


def _cliente() -> Any:
    from google import genai

    chave = config.gemini_chave()
    if not chave:
        raise RuntimeError("sem a chave do Gemini (o segredo do motor)")
    opcoes = types.HttpOptions(timeout=PRAZO_DO_GEMINI_MS, api_version=turno_nucleo.VERSAO_DA_API)
    return genai.Client(api_key=chave, http_options=opcoes)


def _config(
    memoria: list[str] | None = None,
    receitas: list[str] | None = None,
    documentos: dict[str, list[str]] | None = None,
) -> types.GenerateContentConfig:
    presentes = ferramentas()
    return types.GenerateContentConfig(
        tools=[*presentes],
        system_instruction=turno_nucleo.instrucao(
            presentes,
            agent._hoje(),
            onde="nuvem",
            memoria=memoria,
            receitas=receitas,
            documentos=documentos,
            voz=_CANAL.get() == "voz",
        ),
        temperature=turno_nucleo.TEMPERATURA,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=MAX_CHAMADAS_DE_TOOL
        ),
    )


def _resposta(
    *,
    historico: list[Any],
    nota: str,
    teto: custos.Teto,
    resposta: str | None = None,
    erro: str = "",
    aviso: str = "",
    consumo: str = "",
    so_ao_dono: list[str],
    buscas: Sequence[busca.Busca] = (),
    memoria: dict[str, Any] | None = None,
    consultas: Sequence[documentos_consulta.Consulta] = (),
) -> dict[str, Any]:
    return {
        "ao_dono": list(so_ao_dono),
        "busca": [b.como_dict() for b in buscas],
        "documentos": [c.como_dict() for c in consultas],
        "memoria": memoria or {"anotei": [], "aviso": "", "receita": None},
        "resposta": resposta,
        "erro": erro,
        "aviso": aviso,
        "nota": nota,
        "historico": historico,
        "gasto": teto.gasto().como_dict() | _cotas_de_hoje(),
        "consumo": consumo,
    }


def turno(dados: Any, canal: str = "chat") -> dict[str, Any]:
    """Um turno do chat da nuvem, do pedido à resposta (tudo JSON). `canal` é dito pelo motor:
    "voz" (a ponte de casa, D70) tira o que a voz não alcança, pede resposta curta, liga o
    `interativo` (os dois toques no botão são o canal de aprovação; o corpo não decide) e tira o
    código do `ao_dono` para o campo `aprovacao`."""
    if canal not in CANAIS:
        raise ValueError(f"canal={canal!r}: use {CANAIS}")
    historico_json, mensagem, nota, sessao, numero, interativo = _validar(dados)
    if canal == "voz":
        interativo = True
    marca = _FORTE.set({"ligado": False})  # todo turno começa no modelo do dia a dia
    marca_do_canal = _CANAL.set(canal)
    try:
        with ao_dono.coletar(interativo=interativo) as so_ao_dono, prazo.ate(PRAZO_DO_TURNO_S):
            resposta = _turno(historico_json, mensagem, nota, sessao, numero, so_ao_dono)
    finally:
        _CANAL.reset(marca_do_canal)
        _FORTE.reset(marca)
    if canal == "voz":
        resposta["ao_dono"], resposta["aprovacao"] = _aprovacoes_da_voz(resposta["ao_dono"])
    return resposta


def _antes_do_modelo(teto: custos.Teto) -> None:
    """Antes de CADA chamada ao Gemini: ela cabe no prazo do turno, e o teto de gasto deixa."""
    prazo.conferir(PRAZO_DO_GEMINI_MS / 1000, "a próxima chamada ao modelo")
    teto.conferir()


def _escolher(cotas: custos.Cotas) -> Callable[[str], str]:
    """O modelo de cada chamada: o forte depois que a tool ligou a marca e enquanto a cota do dia
    deixa; acabou no meio do turno, o resto volta ao do dia a dia (o 💸 mostra cada um)."""

    def escolher(modelo: str) -> str:
        marca = _FORTE.get()
        if not (marca and marca["ligado"]) or busca.em_curso():  # a busca é sempre a do dia a dia
            return modelo
        try:
            cotas.conferir_forte()
        except custos.CotaAtingida:
            marca["ligado"] = False
            return modelo
        return turno_nucleo.MODELO_FORTE

    return escolher


def _depois_do_modelo(teto: custos.Teto, cotas: custos.Cotas, consumo: custos.Consumo) -> None:
    teto.somar(consumo.custo)
    if consumo.modelo == turno_nucleo.MODELO_FORTE:
        cotas.somar_forte(consumo.custo)


def _turno(
    historico_json: list[Any],
    mensagem: str,
    nota: str,
    sessao: str,
    numero: int,
    so_ao_dono: list[str],
) -> dict[str, Any]:
    turno_id = f"{sessao}:{numero}"
    registro.ORIGEM.set("nuvem")
    registro.TURNO.set(turno_id)
    teto = _teto()

    local = _esquece_isso(mensagem, sessao) or _guarda_receita(mensagem, sessao)
    local = local or barreira(mensagem)
    achado = _roda(mensagem) if local is None else None
    rodar: memoria_receitas.Receita | None = None
    if isinstance(achado, str):
        local = (achado, "")
    else:
        rodar = achado
    if local is not None:  # nunca ao modelo, nunca no histórico; a resposta, só ao dono
        texto, nota_nova = local
        ao_dono.mostrar(texto)
        juntas = turno_nucleo.juntar(nota, nota_nova)
        return _resposta(historico=historico_json, nota=juntas, teto=teto, so_ao_dono=so_ao_dono)
    try:
        teto.conferir()
    except custos.TetoAtingido as exc:
        erro = f"Não mandei ao modelo: o teto de gasto foi atingido ({exc.gasto.texto()})."
        return _resposta(
            historico=historico_json, nota=nota, teto=teto, erro=erro, so_ao_dono=so_ao_dono
        )

    historico = turno_nucleo.historico_de_json(historico_json)
    cliente = _cliente()
    consumo = custos.Sessao()
    cotas = _cotas()
    custos.instrumentar(
        cliente,
        sessao=consumo,
        escolher=_escolher(cotas),
        antes=lambda _modelo: _antes_do_modelo(teto),
        depois=lambda c: _depois_do_modelo(teto, cotas, c),
    )
    com_memoria = config.MEMORIA  # lida uma vez: o turno inteiro com ela ou sem ela
    # Um `roda NOME`: os passos guardados vão ao modelo no lugar da linha digitada (13b).
    pedido = _prompt_da_receita(rodar) if rodar is not None else mensagem
    if rodar is not None:
        ao_dono.mostrar(
            f"📋 rodando a receita «{limpar_controles(rodar.nome)}» ({len(rodar.passos)} passo(s))"
        )
    lembrados, aviso_da_memoria = _lembrar(cliente, pedido) if com_memoria else ([], "")
    fatos = [f.texto for f in lembrados] if com_memoria else None
    nomes, aviso_das_receitas = _nomes_das_receitas() if com_memoria else ([], "")
    temas, aviso_dos_documentos = _temas_dos_documentos() if com_memoria else ({}, "")
    aviso_da_memoria = aviso_da_memoria or aviso_das_receitas or aviso_dos_documentos
    chat = cliente.chats.create(
        model=turno_nucleo.MODELO,
        config=_config(fatos, nomes if com_memoria else None, temas if com_memoria else None),
        history=historico,
    )
    prompt = f"{nota}\n\n{pedido}" if nota else pedido
    # Só a mensagem digitada vai a quem anota: nunca o `prompt` (a nota do Viking vem junto). Num
    # `roda`, ninguém anota: os passos já foram revistos pelo dono ao guardar.
    anotando = (
        _anotar_em_paralelo(mensagem, lembrados, sessao, turno_id, teto)
        if com_memoria and rodar is None
        else None
    )
    with (
        busca.no_turno(cliente, cotas) as buscas,
        documentos_consulta.no_turno(cliente) as consultas,
    ):
        resultado = turno_nucleo.executar(chat, prompt, turno_id)
    if anotando is not None:
        memoria = _terminar_anotacao(anotando, consumo, aviso_da_memoria)
    elif com_memoria:
        memoria = {"anotei": [], "aviso": aviso_da_memoria, "receita": None}
    else:
        memoria = None
    gasto_do_turno = consumo.resumo_do_turno() if consumo.turno().chamadas else ""
    if resultado.erro is None:
        return _resposta(
            historico=turno_nucleo.historico_para_json(chat.get_history()),
            nota="",
            teto=teto,
            resposta=resultado.texto,
            consumo=gasto_do_turno,
            so_ao_dono=so_ao_dono,
            buscas=buscas,
            memoria=memoria,
            consultas=consultas,
        )
    if isinstance(resultado.erro, custos.TetoAtingido):
        erro = f"Parei no meio: o teto de gasto foi atingido ({resultado.erro.gasto.texto()})."
    elif isinstance(resultado.erro, prazo.TempoEsgotado):
        erro = (
            f"Parei no meio: {resultado.erro} (o turno na nuvem tem {PRAZO_DO_TURNO_S} s). "
            "O que já foi feito está no aviso abaixo; peça o resto num turno novo."
        )
    else:
        erro = f"Erro ao processar a resposta: {limpar_controles(str(resultado.erro))[:300]}"
    # O turno não entrou no histórico: a nota que ia com ele continua pendente, somada à nova.
    return _resposta(
        historico=historico_json,
        nota=turno_nucleo.juntar(nota, resultado.nota),
        teto=teto,
        erro=erro,
        aviso=resultado.aviso,
        consumo=gasto_do_turno,
        so_ao_dono=so_ao_dono,
        buscas=buscas,  # o que já apareceu numa busca antes do erro continua do dono
        consultas=consultas,
        memoria=memoria,  # a mensagem é do dono mesmo com o turno falhando: o que anotou, aparece
    )
