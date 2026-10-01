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
   o volume, e o chat da nuvem não tem e-mail.

Tudo que só o dono vê (o código, a lista de uma limpeza, o e-mail antes de sair, e as respostas
da barreira) volta no campo `ao_dono` da resposta (`lifeos/ao_dono.py`): nunca no texto do
modelo, no histórico ou no log. `interativo` (o que o terminal do Mac declarou) decide se uma
proposta com código pode nascer.

NÃO adicionar `from __future__ import annotations` aqui: `criar_lembrete` é tool do Gemini, e o
google-genai valida argumentos com `isinstance(valor, anotação)`.
"""

import re
from collections.abc import Callable
from typing import Any

from google.genai import types

from lifeos import ao_dono, config, confirmacao, custos, prazo, registro
from lifeos.assistant import agent
from lifeos.assistant import turno as turno_nucleo
from lifeos.browser._redacao import limpar_controles
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
    "Aviso: este lembrete mora na nuvem, e o aviso por e-mail dele ainda não existe (chega numa "
    "próxima etapa); o `viking lembretes --enviar` do Mac só envia os lembretes do Mac."
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
# As tools do chat do Mac que não vêm para a nuvem, e por quê. `tests/test_na_nuvem.py` exige que
# toda tool do Mac esteja numa das duas listas: uma tool nova tem de decidir onde mora.
SO_NO_MAC = {
    "saldos_das_contas": "as finanças seguem a D51",
    "gastos_do_periodo": "as finanças seguem a D51",
    "buscar_transacoes": "as finanças seguem a D51",
    "fatura_do_cartao": "as finanças seguem a D51",
}


def ferramentas() -> list[Callable[..., Any]]:
    """As tools deste motor: as da nuvem, sem as do Gmail quando o token dele não está aqui
    (`config.gmail_no_motor`, a mesma pergunta que o `/versao` responde)."""
    if config.gmail_no_motor():
        return list(FERRAMENTAS)
    return [f for f in FERRAMENTAS if f.__name__ not in _DO_GMAIL]


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


def _cliente() -> Any:
    from google import genai

    chave = config.gemini_chave()
    if not chave:
        raise RuntimeError("sem a chave do Gemini (o segredo do motor)")
    return genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=PRAZO_DO_GEMINI_MS))


def _config() -> types.GenerateContentConfig:
    presentes = ferramentas()
    return types.GenerateContentConfig(
        tools=[*presentes],
        system_instruction=turno_nucleo.instrucao(presentes, agent._hoje(), onde="nuvem"),
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
) -> dict[str, Any]:
    return {
        "ao_dono": list(so_ao_dono),
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
    historico_json, mensagem, nota, sessao, numero, interativo = _validar(dados)
    with ao_dono.coletar(interativo=interativo) as so_ao_dono, prazo.ate(PRAZO_DO_TURNO_S):
        return _turno(historico_json, mensagem, nota, sessao, numero, so_ao_dono)


def _antes_do_modelo(teto: custos.Teto) -> None:
    """Antes de CADA chamada ao Gemini: ela cabe no prazo do turno, e o teto de gasto deixa."""
    prazo.conferir(PRAZO_DO_GEMINI_MS / 1000, "a próxima chamada ao modelo")
    teto.conferir()


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

    local = barreira(mensagem)
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
    custos.instrumentar(
        cliente,
        sessao=consumo,
        antes=lambda: _antes_do_modelo(teto),
        depois=lambda c: teto.somar(c.custo),
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
            so_ao_dono=so_ao_dono,
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
    )
