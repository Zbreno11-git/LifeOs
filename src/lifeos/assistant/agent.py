"""Assistente de chat unificado do Viking — calendário, navegador, lembretes, e-mail e finanças.

Generalizado a partir do protótipo `calendar-bot/agent.py` (Gemini function-calling), que só
registrava ferramentas de calendário.
"""

# NÃO adicionar `from __future__ import annotations` aqui: o google-genai valida os argumentos
# das tools com isinstance(valor, anotação), e o future import transforma as anotações em strings,
# quebrando toda chamada que passe argumento (`isinstance() arg 2 must be a type...`).
import re
import secrets
import sys
from datetime import datetime, timedelta

from google import genai
from google.genai import types

from lifeos import aprovacoes, config, confirmacao, custos, registro
from lifeos.assistant import turno as turno_nucleo
from lifeos.browser import executar_no_navegador, imprimir_progresso, liberacao
from lifeos.browser._redacao import limpar_controles
from lifeos.calendar import (
    apagar_evento_por_id,
    buscar_eventos_por_termo,
    criar_evento,
    criar_evento_dia_inteiro,
    listar_eventos_por_data,
    listar_proximos_eventos,
    reagendar_evento_por_id,
)
from lifeos.calendar import service as calendario_service
from lifeos.calendar.tools import aviso_de_fuso, recusa_de_fuso
from lifeos.config import GEMINI_API_KEY, TIMEZONE
from lifeos.financas.tools import (
    buscar_transacoes,
    fatura_do_cartao,
    gastos_do_periodo,
    saldos_das_contas,
)
from lifeos.gmail import envio, limpeza
from lifeos.gmail import tools as gmail_tools
from lifeos.gmail.tools import (
    buscar_emails,
    emails_nao_lidos_de_hoje,
    enviar_email,
    ler_email,
    preparar_limpeza,
    raio_x_da_caixa,
    responder_email,
)
from lifeos.registro_texto import acoes_recentes
from lifeos.reminders import service as reminders_service


def navegar_e_executar(url: str, objetivo: str, manter_aberta: bool = True) -> str:
    """Executa cliques e digitação num navegador real do usuário. Leva de segundos a minutos.

    `objetivo` é sempre uma AÇÃO ("abrir X", "buscar Y e abrir o primeiro resultado"), nunca uma
    pergunta: o executor só clica, digita, rola e espera, e um objetivo que só uma resposta
    satisfaria o faz rodar em círculo. Para responder algo sobre uma página, mande só abri-la — o
    conteúdo dela volta no resultado e você interpreta.

    Ordinais além do primeiro ("o segundo resultado") não funcionam: o executor escolhe entre
    elementos da página, não conta posições — ele tenta um, outro, outro, sem parar. Peça o
    primeiro, ou identifique o alvo pelo nome.

    Prefira uma URL que já leve ao estado desejado em vez de mandar digitar e clicar: para buscas,
    monte a URL de resultados do site (ex.: youtube.com/results?search_query=termo+aqui). Digitar e
    submeter é a parte mais frágil, porque a página pode ainda não ter trocado quando o executor
    clicar.

    Cliques que saem da conta, mexem nela (excluir, cancelar assinatura, trocar senha) ou gastam
    dinheiro (comprar, pagar, transferir) são recusados antes de acontecer: não mande o navegador
    fazer isso nem repita a tarefa. Sair e mexer na conta o usuário pode liberar uma vez, com o
    código que o Viking mostra só a ele; dinheiro nunca — esse clique é dele.

    Após erro, timeout ou parada sem concluir, não repita sem confirmar com o usuário: o que já
    foi executado não é desfeito. `manter_aberta` deixa a aba aberta e em foco (padrão); use False
    quando a página interessar só a você.
    """
    return executar_no_navegador(url, objetivo, manter_aberta=manter_aberta)


def criar_lembrete(titulo: str, corpo: str = "", tags: str = "", quando: str = "") -> str:
    """Cria um lembrete ou nota. Não é evento de calendário: use isto para coisas a fazer, e o
    calendário para compromissos com hora marcada. `tags` separadas por vírgula. `quando` é o
    prazo opcional em ISO 8601 ('2026-09-25' ou '2026-09-25T14:00') — resolva "amanhã" você mesmo.
    Sem fuso: o Viking aplica o do usuário.
    """
    recusa = recusa_de_fuso("NÃO criei o lembrete", quando)
    if recusa:
        return recusa
    try:
        reminder = reminders_service.criar_lembrete(
            titulo, corpo, tags, quando, source="viking-cli"
        )
    except reminders_service.QuandoInvalido:
        return f"Não entendi a data '{quando}'. Use ISO 8601, ex.: 2026-09-25 ou 2026-09-25T14:00."
    return f"✅ Lembrete criado: '{titulo}'{_prazo_do_dono(reminder)} [id: {reminder.id}]."


def _prazo_do_dono(reminder) -> str:
    """O prazo no fuso do dono (o store devolve UTC): a conversão é da borda."""
    if reminder.due_at is None:
        return ""
    return f" (para {reminder.due_at.astimezone(config.TIMEZONE):%Y-%m-%d %H:%M})"


def listar_lembretes() -> str:
    """Lista os lembretes não concluídos, prazo mais próximo primeiro. O `[id: …]` de cada linha é
    só para você chamar `concluir_lembrete`: ao dono, mostre título e prazo, nunca o id."""
    reminders = reminders_service.pendentes()
    if not reminders:
        return "Nenhum lembrete pendente."
    return "\n".join(f"- {r.title}{_prazo_do_dono(r)} [id: {r.id}]" for r in reminders)


def concluir_lembrete(reminder_id: str) -> str:
    """Marca um lembrete como concluído. `reminder_id` é o `[id: …]` da listagem, copiado inteiro;
    se o dono disser qual pelo título, liste antes para achar o id."""
    reminder = reminders_service.concluir(reminder_id.strip())
    if not reminder:
        return "Não encontrei esse lembrete: liste de novo e use o id que aparece lá."
    return f"✅ Lembrete concluído: '{reminder.title}'."


_DIAS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def _hoje() -> str:
    """Data corrente para o system_instruction: sem isso o modelo não resolve 'amanhã'."""
    agora = datetime.now(TIMEZONE)
    fuso = calendario_service._offset(agora)
    return f"{agora:%Y-%m-%d} ({_DIAS[agora.weekday()]}, {agora:%H:%M}, fuso {fuso})"


def _build_client() -> genai.Client:
    if not GEMINI_API_KEY:
        print("❌ ERRO: GEMINI_API_KEY não encontrada no .env!")
        sys.exit(1)
    return genai.Client(api_key=GEMINI_API_KEY)


# Registradas no Gemini como function-calling. Constante no módulo para que os testes possam
# verificar as assinaturas sem subir o assistente.
FERRAMENTAS = [
    listar_proximos_eventos,
    listar_eventos_por_data,
    criar_evento,
    criar_evento_dia_inteiro,
    buscar_eventos_por_termo,
    apagar_evento_por_id,
    reagendar_evento_por_id,
    navegar_e_executar,
    criar_lembrete,
    listar_lembretes,
    concluir_lembrete,
    buscar_emails,
    emails_nao_lidos_de_hoje,
    ler_email,
    raio_x_da_caixa,
    preparar_limpeza,
    enviar_email,
    responder_email,
    saldos_das_contas,
    gastos_do_periodo,
    buscar_transacoes,
    fatura_do_cartao,
    acoes_recentes,
]


# A aprovação mora aqui, e não numa tool: nenhuma chamada do Gemini chega a arquivar. A linha
# que casa com isto é tratada pelo Viking e NUNCA vai ao modelo (nem o código, nem o resultado
# cru); o Gemini só recebe uma nota sem o código no turno seguinte. Exige o número depois da
# palavra para não roubar frases como "confirma a reunião de amanhã?".
_APROVACAO = re.compile(
    r"^\s*(confirma|confirmo|confirmar|desfaz|desfazer)\s*[:\-]?\s*([\d\s]+?)\s*[.!]?\s*$",
    re.IGNORECASE,
)
# Só o número, ou só a palavra: foi o que o dono digitou na primeira vez no Mac (2026-09-26), e o
# número sozinho foi parar no Gemini. Com uma proposta aberta, um número do tamanho do código é
# tratado como a aprovação; a palavra sozinha ganha a instrução aqui mesmo.
_SO_NUMERO = re.compile(r"^\s*([\d\s]+?)\s*[.!]?\s*$")
_SO_PALAVRA = re.compile(
    r"^\s*(confirma|confirmo|confirmar|desfaz|desfazer)\s*[.!]?\s*$", re.IGNORECASE
)
# Frase livre ("desfaz 8768 do gmail", "você arquivou, desfaz, o código é 8768"): foi o que o dono
# escreveu no Mac, e ia ao Gemini. Um número de 4 dígitos que é código VIVO nunca sai daqui: com
# verbo, age; sem verbo, ganha a instrução. Número que não é código vivo segue para o Gemini —
# "confirma se a reunião é às 1530" não é roubado.
_VERBO = re.compile(
    r"\b(confirma|confirmo|confirmar|confirme|desfaz|desfazer|desfaça|desfaca|desfazê)\b",
    re.IGNORECASE,
)
_NUMERO_DE_CODIGO = re.compile(rf"(?<![0-9])[0-9]{{{confirmacao.DIGITOS}}}(?![0-9])")
_COMO_APROVAR = (
    "Para aprovar, digite `confirma` e o código de 4 números que o Viking mostrou (ou só o "
    "código). Para desfazer uma limpeza do Gmail: `desfaz` e o código."
)
# "Verbo + 4 dígitos" com um número que NÃO é código vivo aqui também não vai ao Gemini (dono,
# 2026-09-30, D60): desde a 10c há códigos vivos em dois lugares (o chat do Mac e o da nuvem), e
# um código de um lado, digitado numa frase no outro, chegaria ao modelo. Uma frase rara como
# "confirma se a reunião é às 1530" paga isso: a resposta ensina a escrever 15:30.
NAO_E_CODIGO_AQUI = (
    "Não mandei essa linha ao modelo: ela tem cara de aprovação (um verbo como “confirma” e um "
    "número de 4 dígitos), mas esse número não é um código vivo neste chat. Se é um código do "
    "outro chat (o `viking chat` do Mac ou o `viking chat --nuvem`), digite-o lá. Se é outra "
    "coisa, escreva o número de outro jeito (um horário como 15:30, por exemplo). Nada foi feito."
)
_SO_NO_TERMINAL = (
    "Esse código é de um pedido que veio de outro app (pelo servidor MCP): ele se aprova só no "
    "terminal, com `viking aprovar`. Nada foi feito."
)


def _vivos(linha: str) -> set[tuple[aprovacoes.Tipo, str]]:
    """(tipo, código) de cada número da linha que é código vivo de alguma ação."""
    return {
        (tipo, c)
        for c in _NUMERO_DE_CODIGO.findall(linha)
        for tipo in aprovacoes.TIPOS
        if confirmacao.vivo(tipo.acao, c, janela=tipo.janela)
    }


def _tipo_do_codigo(codigo: str) -> aprovacoes.Tipo | None:
    acao = confirmacao.acao_do_codigo(codigo)
    return next((t for t in aprovacoes.TIPOS if t.acao == acao), None)


def _tipo_aberto() -> aprovacoes.Tipo | None:
    """De que ação é a proposta aberta mais recente do chat: um código que não existe ("confirma
    0001") ganha a resposta do que o dono está vendo na tela, não a da limpeza."""
    abertas = [(p.id, t) for t in aprovacoes.do_chat() for p in confirmacao.abertas(t.acao)]
    return max(abertas, key=lambda par: par[0])[1] if abertas else None


def aprovacao_local(linha: str) -> tuple[str, str] | None:
    """(texto para o dono, nota para o Gemini) se a linha é uma aprovação; senão `None`. A nota
    vem vazia quando não há nada a contar ao Gemini."""
    linha = linha or ""
    palavra_sozinha = _SO_PALAVRA.match(linha)
    if palavra_sozinha:
        if palavra_sozinha.group(1).lower().startswith("desfa"):
            desfeito = _desfazer_no_calendario()
            if desfeito is not None:
                return desfeito
        return _COMO_APROVAR, ""
    achado = _APROVACAO.match(linha)
    so_numero = _SO_NUMERO.match(linha)
    if achado:
        verbo, codigo = achado.group(1).lower(), achado.group(2)
    elif (
        so_numero
        and len("".join(so_numero.group(1).split())) == confirmacao.DIGITOS
        and any(confirmacao.aberta(t.acao) for t in aprovacoes.do_chat())
    ):
        verbo, codigo = "confirma", so_numero.group(1)
    else:
        vivos = _vivos(linha)
        if not vivos:
            if _VERBO.search(linha) and _NUMERO_DE_CODIGO.search(linha):
                return NAO_E_CODIGO_AQUI, ""
            return None
        if any(not tipo.no_chat for tipo, _c in vivos):
            return _SO_NO_TERMINAL, ""
        palavra = _VERBO.search(linha)
        codigos = {c for _tipo, c in vivos}
        if not palavra or len(codigos) != 1:
            return _COMO_APROVAR, ""
        verbo, codigo = palavra.group(1).lower(), codigos.pop()
    tipo = _tipo_do_codigo(codigo) or _tipo_aberto()
    if tipo is not None and not tipo.no_chat:
        return _SO_NO_TERMINAL, ""
    if tipo is not None and tipo.acao == aprovacoes.NAVEGADOR_CLIQUE:
        return _aprovar_clique(verbo, codigo)
    if tipo is not None and tipo.acao == aprovacoes.GMAIL_ENVIAR:
        return _aprovar_envio(verbo, codigo)
    return _aprovar_limpeza(verbo, codigo)


DESFAZER_CALENDARIO_POR = timedelta(days=7)


def _desfazer_no_calendario() -> tuple[str, str] | None:
    """`desfaz` sozinho: a última ação de calendário (apagar ou reagendar) DESTA sessão do chat.
    Tratado aqui, e não por uma tool: um e-mail com injeção não consegue induzir o Gemini a
    desfazer nada. O desfazer do Gmail continua pedindo o código (`desfaz NNNN`)."""
    turno = registro.TURNO.get()
    if ":" not in turno:
        return None
    acao = registro.ultima_desfazivel(
        calendario_service.OPERACOES_DESFAZIVEIS,
        prefixo_turno=turno.rsplit(":", 1)[0] + ":",
        janela=DESFAZER_CALENDARIO_POR,
    )
    if acao is None:
        return None
    try:
        feito = calendario_service.restaurar(acao.id)
    except calendario_service.ErroCalendario as exc:
        if getattr(exc, "incerta", False):
            texto = (
                f"Não sei se desfiz: o Google Calendar não respondeu direito "
                f"({limpar_controles(str(exc))}). Confira no calendário antes de tentar de novo."
            )
            return texto, _nota("o usuário tentou desfazer no calendário; pode ter sido feito")
        texto = f"Não desfiz: {limpar_controles(str(exc))}. Nada mudou no calendário."
        return texto, _nota("o usuário tentou desfazer uma ação no calendário, e nada mudou")
    texto = {
        "restaurado": f"↩️ O evento '{feito.titulo}' voltou ao calendário.",
        "recriado": (
            f"↩️ Recriei o evento '{feito.titulo}' (é um evento novo, sem os convidados: ninguém "
            "recebeu aviso)."
        ),
        "horario": f"↩️ O evento '{feito.titulo}' voltou ao horário de antes.",
        "ja_estava": f"O evento '{feito.titulo}' já estava no calendário: não mexi.",
    }[feito.como]
    return texto, _nota(f"o usuário desfez no calendário: {texto}")


def _nota(conteudo: str) -> str:
    return f"[Nota do Viking, não do usuário: fora de você, {conteudo}.]"


def _aprovar_limpeza(verbo: str, codigo: str) -> tuple[str, str]:
    desfazendo = verbo.startswith("desfa")
    try:
        if desfazendo:
            desfeito = limpeza.desfazer(codigo)
            texto = gmail_tools.texto_do_desfeito(desfeito)
            nota = (
                f"o usuário desfez uma limpeza: {len(desfeito.modificacao.feitos)} e-mail(s) "
                "voltaram à caixa de entrada"
            )
        else:
            execucao = limpeza.confirmar(codigo)
            texto = gmail_tools.texto_da_execucao(execucao)
            nota = (
                f"o usuário aprovou a limpeza: {len(execucao.modificacao.feitos)} e-mail(s) "
                "foram arquivados"
            )
    except (confirmacao.ErroConfirmacao, limpeza.service.ErroGmail) as exc:
        texto = gmail_tools.mensagem_de_aprovacao(exc, desfazendo=desfazendo)
        nota = "o usuário tentou aprovar ou desfazer uma limpeza, e nada foi feito"
    return texto, _nota(nota)


def _aprovar_clique(verbo: str, codigo: str) -> tuple[str, str]:
    """Um clique que o freio do navegador recusou, liberado uma vez (D38). Não se desfaz."""
    if verbo.startswith("desfa"):
        texto = "Um clique no navegador não se desfaz pelo Viking: esse código é de uma liberação."
        return f"{texto} Nada mudou.", ""
    try:
        texto, resultado = liberacao.clicar_aprovado(codigo, on_progress=imprimir_progresso)
    except (confirmacao.ErroConfirmacao, ValueError) as exc:
        texto = f"Não cliquei: {limpar_controles(str(exc))}. Nada mudou."
        return texto, _nota("o usuário tentou liberar um clique no navegador, e nada foi feito")
    return texto, _nota(liberacao.nota_do_clique(resultado))


def _aprovar_envio(verbo: str, codigo: str) -> tuple[str, str]:
    """Um e-mail para outra pessoa, aprovado com o código (D46). Não se desfaz."""
    if verbo.startswith("desfa"):
        return "Um e-mail enviado não se desfaz: esse código é de um envio. Nada mudou.", ""
    try:
        confirmado = envio.confirmar(codigo)
    except (confirmacao.ErroConfirmacao, envio.service.ErroGmail) as exc:
        texto = gmail_tools.mensagem_de_envio_aprovado(exc)
        incerta = getattr(exc, "incerta", False)
        nota = (
            "o usuário aprovou um e-mail, e o Gmail não respondeu direito: pode ter saído"
            if incerta
            else "o usuário tentou aprovar um e-mail, e nada foi enviado"
        )
        return texto, _nota(nota)
    r = confirmado.rascunho
    nota = f"o usuário aprovou e o Viking enviou o e-mail “{r.assunto}” para {', '.join(r.para)}"
    return gmail_tools.texto_do_confirmado(confirmado), _nota(nota)


_juntar = turno_nucleo.juntar


def iniciar_assistente() -> None:
    client = _build_client()
    custos.instrumentar(client)

    config = types.GenerateContentConfig(
        tools=FERRAMENTAS,
        system_instruction=turno_nucleo.instrucao(FERRAMENTAS, _hoje(), onde="mac"),
        temperature=turno_nucleo.TEMPERATURA,
    )

    chat = client.chats.create(model=turno_nucleo.MODELO, config=config)

    print("🤖 Viking iniciado! (calendário, navegador, lembretes, e-mail e finanças)")
    fuso = aviso_de_fuso()
    if fuso:
        print(fuso)
    print("Digite 'sair' para encerrar.\n")

    nota_pendente = ""
    # Origem e turno das ações (registro): o `desfaz` sozinho só alcança ações desta sessão, e o
    # aviso depois de um erro lista as do turno que falhou.
    registro.ORIGEM.set("chat")
    sessao = secrets.token_hex(4)
    numero = 0
    while True:
        prompt = input("Você: ").strip()
        if not prompt:
            continue
        numero += 1
        turno = f"{sessao}:{numero}"
        registro.TURNO.set(turno)
        local = aprovacao_local(prompt)
        if local is not None:
            texto, nota = local
            nota_pendente = _juntar(nota_pendente, nota)
            print(f"🤖 Viking: {texto}\n")
            continue
        if prompt.lower() in ["sair", "exit", "quit"]:
            print("🤖 Viking: Até logo!")
            print(custos.SESSAO.total_formatado())
            break
        if prompt.lower() in ["/custos", "custos"]:
            print(custos.SESSAO.total_formatado())
            continue

        # A nota entra só aqui, depois de "sair" e "/custos": colada antes, o "sair" logo depois de
        # uma aprovação virou mensagem ao Gemini (visto no Mac, 2026-09-26).
        if nota_pendente:
            prompt, nota_pendente = f"{nota_pendente}\n\n{prompt}", ""
        print("⏳ Pensando...")
        custos.SESSAO.iniciar_turno()
        # O núcleo (`turno.py`, o mesmo do motor da nuvem) manda ao Gemini e, se uma tool agiu
        # antes de um erro (o §7 da auditoria), diz o que já foi feito; o Gemini recebe no turno
        # seguinte a mesma lista, para não repetir.
        resultado = turno_nucleo.executar(chat, prompt, turno)
        if resultado.erro is None:
            print(f"🤖 Viking: {resultado.texto}\n")
        else:
            print(f"❌ Erro ao processar a resposta: {resultado.erro}\n")
            if resultado.aviso:
                print(f"{resultado.aviso}\n")
                nota_pendente = _juntar(nota_pendente, resultado.nota)
        # Também depois de um erro: se uma chamada já custou e uma chamada POSTERIOR do mesmo
        # turno falhou, o custo da primeira ainda deve aparecer — não some com o erro.
        consumo = custos.SESSAO.turno()
        if consumo.chamadas:
            print(f"   💸 gemini: {consumo.resumo()}", file=sys.stderr)


if __name__ == "__main__":
    iniciar_assistente()
