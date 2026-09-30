"""O turno do chat quando ele roda no motor da nuvem (Sessão 10b, D59).

O `viking chat --nuvem` do Mac manda a conversa inteira a cada turno (`historico`) e recebe de
volta a conversa nova: o motor não guarda a conversa (decisão do dono, 2026-09-30). Aqui:

1. **a barreira de aprovação**, antes de tudo: uma linha com cara de aprovação (`confirma NNNN`,
   só o número, a palavra sozinha, verbo e número numa frase) nunca vai ao Gemini nem entra no
   histórico. Na 10b a nuvem ainda não aprova nada (a aprovação pela rede é da 10c), e o risco é
   o dono digitar aqui um código que o chat do Mac mostrou. O `desfaz` sozinho desfaz a última
   exclusão ou reagendamento da agenda desta conversa, como no Mac;
2. **o teto de gasto** (`custos.Teto`), conferido antes do turno e antes de cada chamada ao modelo;
3. **o turno**, pelo mesmo núcleo do chat do Mac (`turno.py`), só com as tools que moram na nuvem
   (`FERRAMENTAS`; o que fica no Mac está em `SO_NO_MAC`, com o motivo). O Gemini tem prazo por
   chamada e um limite de chamadas de tool por turno.

NÃO adicionar `from __future__ import annotations` aqui: `criar_lembrete` é tool do Gemini, e o
google-genai valida argumentos com `isinstance(valor, anotação)`.
"""

import re
from collections.abc import Callable
from typing import Any

from google.genai import types

from lifeos import config, confirmacao, custos, registro
from lifeos.assistant import agent
from lifeos.assistant import turno as turno_nucleo
from lifeos.browser._redacao import limpar_controles
from lifeos.registro_texto import acoes_recentes

PRAZO_DO_GEMINI_MS = 60_000  # por chamada; o turno medido levou até 3 s (2026-09-30)
MAX_CHAMADAS_DE_TOOL = 10  # por turno: o turno medido usou até 2 (2026-09-30)
MAX_MENSAGEM = 8_000  # caracteres
MAX_NOTA = 20_000
_SESSAO = re.compile(r"[A-Za-z0-9-]{1,40}")

AVISO_SEM_EMAIL = (
    "Aviso: este lembrete mora na nuvem, e o aviso por e-mail dele ainda não existe (chega numa "
    "próxima etapa); o `viking lembretes --enviar` do Mac só envia os lembretes do Mac."
)
AINDA_NAO_APROVA = (
    "Na nuvem ainda não há o que aprovar com código: isso chega ao chat da nuvem numa próxima "
    "etapa. Se o código é de uma ação do Mac (Gmail, navegador), digite-o no `viking chat` do Mac. "
    "Nada foi enviado ao modelo."
)
NADA_A_DESFAZER = (
    "Não achei nesta conversa uma exclusão ou um reagendamento na agenda para desfazer. Nada mudou."
)


def criar_lembrete(titulo: str, corpo: str = "", tags: str = "", quando: str = "") -> str:
    texto = agent.criar_lembrete(titulo, corpo, tags, quando)
    if texto.startswith("✅"):
        texto = f"{texto} {AVISO_SEM_EMAIL}"
    return texto


criar_lembrete.__doc__ = agent.criar_lembrete.__doc__

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
]
# As tools do chat do Mac que não vêm para a nuvem, e por quê. `tests/test_na_nuvem.py` exige que
# toda tool do Mac esteja numa das duas listas: uma tool nova tem de decidir onde mora.
SO_NO_MAC = {
    "navegar_e_executar": "o navegador é o do Mac até a S11 (as mãos)",
    "buscar_emails": "o Gmail na nuvem é da 10c",
    "emails_nao_lidos_de_hoje": "o Gmail na nuvem é da 10c",
    "ler_email": "o Gmail na nuvem é da 10c",
    "raio_x_da_caixa": "o Gmail na nuvem é da 10c",
    "preparar_limpeza": "o Gmail na nuvem é da 10c (e aprova com código)",
    "enviar_email": "o Gmail na nuvem é da 10c (e aprova com código)",
    "responder_email": "o Gmail na nuvem é da 10c (e aprova com código)",
    "saldos_das_contas": "as finanças seguem a D51",
    "gastos_do_periodo": "as finanças seguem a D51",
    "buscar_transacoes": "as finanças seguem a D51",
    "fatura_do_cartao": "as finanças seguem a D51",
}


def barreira(linha: str) -> tuple[str, str] | None:
    """(texto para o dono, nota para o Gemini) se a linha não pode ir ao modelo; senão `None`.

    As mesmas formas que o laço do Mac reconhece (`agent.aprovacao_local`), mais uma: verbo e um
    número de 4 dígitos na mesma frase, mesmo sem código vivo aqui (os códigos vivos estão no Mac,
    e a nuvem não os vê)."""
    linha = linha or ""
    palavra = agent._SO_PALAVRA.match(linha)
    if palavra:
        if palavra.group(1).lower().startswith("desfa"):
            desfeito = agent._desfazer_no_calendario()
            return desfeito if desfeito is not None else (NADA_A_DESFAZER, "")
        return AINDA_NAO_APROVA, ""
    if agent._APROVACAO.match(linha):
        return AINDA_NAO_APROVA, ""
    so_numero = agent._SO_NUMERO.match(linha)
    if so_numero and len("".join(so_numero.group(1).split())) == confirmacao.DIGITOS:
        return AINDA_NAO_APROVA, ""
    if agent._VERBO.search(linha) and agent._NUMERO_DE_CODIGO.search(linha):
        return AINDA_NAO_APROVA, ""
    return None


def _validar(dados: Any) -> tuple[list[Any], str, str, str, int]:
    """Os campos do pedido, conferidos; `ValueError` (o motor responde 400) sem ecoar conteúdo."""
    if not isinstance(dados, dict):
        raise ValueError("o pedido tem de ser um objeto JSON")  # noqa: TRY004 - o motor: 400
    mensagem, nota = dados.get("mensagem"), dados.get("nota", "")
    sessao, numero = dados.get("sessao"), dados.get("numero")
    historico = dados.get("historico", [])
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
    return historico, mensagem.strip(), nota, sessao, numero


def _teto() -> custos.Teto:
    return custos.Teto(mes=config.TETO_GEMINI_MES, dia=config.TETO_GEMINI_DIA, fuso=config.TIMEZONE)


def _cliente() -> Any:
    from google import genai

    chave = config.gemini_chave()
    if not chave:
        raise RuntimeError("sem a chave do Gemini (o segredo do motor)")
    return genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=PRAZO_DO_GEMINI_MS))


def _config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tools=[*FERRAMENTAS],
        system_instruction=turno_nucleo.instrucao(FERRAMENTAS, agent._hoje()),
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
) -> dict[str, Any]:
    return {
        "resposta": resposta,
        "erro": erro,
        "aviso": aviso,
        "nota": nota,
        "historico": historico,
        "gasto": teto.gasto().como_dict(),
        "consumo": consumo,
    }


def turno(dados: Any) -> dict[str, Any]:
    """Um turno do chat da nuvem, do pedido à resposta (tudo JSON)."""
    historico_json, mensagem, nota, sessao, numero = _validar(dados)
    turno_id = f"{sessao}:{numero}"
    registro.ORIGEM.set("nuvem")
    registro.TURNO.set(turno_id)
    teto = _teto()

    local = barreira(mensagem)
    if local is not None:  # nunca ao modelo, nunca no histórico
        texto, nota_nova = local
        juntas = turno_nucleo.juntar(nota, nota_nova)
        return _resposta(historico=historico_json, nota=juntas, teto=teto, resposta=texto)
    try:
        teto.conferir()
    except custos.TetoAtingido as exc:
        erro = f"Não mandei ao modelo: o teto de gasto foi atingido ({exc.gasto.texto()})."
        return _resposta(historico=historico_json, nota=nota, teto=teto, erro=erro)

    historico = turno_nucleo.historico_de_json(historico_json)
    cliente = _cliente()
    consumo = custos.Sessao()
    custos.instrumentar(
        cliente, sessao=consumo, antes=teto.conferir, depois=lambda c: teto.somar(c.custo)
    )
    chat = cliente.chats.create(model=turno_nucleo.MODELO, config=_config(), history=historico)
    prompt = f"{nota}\n\n{mensagem}" if nota else mensagem
    resultado = turno_nucleo.executar(chat, prompt, turno_id)
    gasto_do_turno = consumo.turno().resumo() if consumo.turno().chamadas else ""
    if resultado.erro is None:
        return _resposta(
            historico=turno_nucleo.historico_para_json(chat.get_history()),
            nota="",
            teto=teto,
            resposta=resultado.texto,
            consumo=gasto_do_turno,
        )
    if isinstance(resultado.erro, custos.TetoAtingido):
        erro = f"Parei no meio: o teto de gasto foi atingido ({resultado.erro.gasto.texto()})."
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
    )
