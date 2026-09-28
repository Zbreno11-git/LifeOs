"""Ponto de entrada `viking` — assistente de chat, navegador e servidor MCP.

Ver docs/arquitetura/viking-visao-e-arquitetura.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict


def _doctor() -> int:
    """Diagnóstico do Browser Harness, usando a ferramenta do próprio fornecedor. Respeita a
    trava do navegador: o doctor pode reiniciar o daemon, e derrubaria a tarefa de outro terminal."""
    from lifeos.browser import jev_runner, trava, versao_jev
    from lifeos.browser._redacao import limpar_controles
    from lifeos.config import UV_BIN

    try:
        with trava.ocupar("diagnóstico (viking browser --doctor)") as ocupado:
            if ocupado is not None:
                descricao = limpar_controles(trava.descrever(ocupado))
                print(f"❌ Não rodei o diagnóstico: {descricao}. Espere terminar.", file=sys.stderr)
                return 2
            # Antes do harness, que escreve direto no terminal: num pipe, o print ficaria no buffer
            # e sairia depois da saída dele.
            print(versao_jev.texto(versao_jev.conferir()), flush=True)
            cmd = jev_runner.comando_doctor()
            print(f"$ {' '.join(cmd)}", file=sys.stderr)
            try:
                # O doctor pode subir o daemon, que guarda este ambiente: o mesmo da tarefa (D41).
                return subprocess.call(cmd, env=jev_runner.ambiente_do_jev())
            except FileNotFoundError:
                print(f"❌ Não encontrei o executável '{UV_BIN}' no PATH.", file=sys.stderr)
                return 2
    except trava.Indisponivel as exc:
        print(f"❌ Não rodei o diagnóstico: {limpar_controles(str(exc))}.", file=sys.stderr)
        return 2


def _browser(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.doctor:
        return _doctor()
    if not args.url or not args.goals:
        parser.error("--url e --goal são obrigatórios (ou use --doctor)")

    from lifeos.browser import formatar, imprimir_progresso, run_jev, versao_jev
    from lifeos.browser.jev_runner import BrowserResult

    versao_jev.avisar()
    resultado: BrowserResult = run_jev(
        args.url,
        args.goals,
        timeout_s=args.timeout,
        fechar=args.fechar,
        on_progress=None if args.quiet else imprimir_progresso,
    )

    if args.json:
        print(json.dumps(asdict(resultado), ensure_ascii=False, indent=2))
        return _saida_do_navegador(resultado)
    print(formatar(resultado))
    return _liberar_clique(resultado, on_progress=None if args.quiet else imprimir_progresso)


def _saida_do_navegador(resultado) -> int:
    return {"done": 0, "blocked": 1}.get(resultado.status, 2)


def _liberar_clique(resultado, *, on_progress) -> int:
    """O freio recusou um clique de sair ou de mexer na conta: propõe liberar só esse clique e pede
    o código aqui mesmo (como `--arquivar`). Sem terminal interativo, nem propõe."""
    from lifeos import confirmacao
    from lifeos.browser import liberacao

    proposta = liberacao.propor(resultado) if liberacao.terminal_interativo() else None
    if proposta is None:
        return _saida_do_navegador(resultado)
    print(liberacao.texto_da_proposta(proposta, no_chat=False))
    digitado = input("Código (Enter cancela): ").strip()
    if not digitado:
        print("Cancelado: nada foi clicado.")
        return _saida_do_navegador(resultado)
    try:
        texto, novo = liberacao.clicar_aprovado(digitado, on_progress=on_progress)
    except (confirmacao.ErroConfirmacao, ValueError) as exc:
        print(f"❌ Não cliquei: {exc}.", file=sys.stderr)
        return 2
    print(texto)
    return 0 if novo.liberado else 2


def _arquivar(remetentes: str) -> int:
    """A limpeza sem o Gemini: mostra a proposta e pede o código aqui mesmo."""
    from lifeos import confirmacao
    from lifeos.gmail import limpeza, service, tools

    try:
        proposta = limpeza.preparar(remetentes)
    except (service.ErroGmail, confirmacao.ErroConfirmacao) as exc:
        erro = tools.mensagem_de_erro(exc) if isinstance(exc, service.ErroGmail) else str(exc)
        print(f"❌ {erro}", file=sys.stderr)
        return 2
    print(tools.texto_da_proposta(proposta))
    if not proposta.codigo:
        return 0
    digitado = input("Digite o código para arquivar (Enter cancela): ").strip()
    if not digitado:
        print("Cancelado: nada foi arquivado.")
        return 1
    try:
        print(tools.texto_da_execucao(limpeza.confirmar(digitado)))
    except (service.ErroGmail, confirmacao.ErroConfirmacao) as exc:
        print(f"❌ {tools.mensagem_de_aprovacao(exc)}", file=sys.stderr)
        return 2
    return 0


def _desfazer(codigo: str) -> int:
    from lifeos import confirmacao
    from lifeos.gmail import limpeza, service, tools

    try:
        print(tools.texto_do_desfeito(limpeza.desfazer(codigo)))
    except (service.ErroGmail, confirmacao.ErroConfirmacao) as exc:
        print(f"❌ {tools.mensagem_de_aprovacao(exc, desfazendo=True)}", file=sys.stderr)
        return 2
    return 0


def _gmail(args: argparse.Namespace) -> int:
    """Gmail sem passar pelo Gemini: o texto impresso é o mesmo que o chat entrega ao modelo."""
    from lifeos.gmail import service, tools

    if args.arquivar is not None:
        return _arquivar(args.arquivar)
    if args.desfazer is not None:
        return _desfazer(args.desfazer)
    if args.login:
        try:
            endereco, total = service.perfil()
        except service.ErroGmail as exc:
            print(f"❌ {tools.mensagem_de_erro(exc)}", file=sys.stderr)
            return 2
        print(f"✅ Login do Gmail ok (ler e arquivar): {endereco}, {total} mensagens na conta.")
        return 0
    if args.buscar is not None:
        print(tools.buscar_emails(args.buscar, args.max))
    elif args.ler:
        print(tools.ler_email(args.ler))
    elif args.raio_x is not None:
        print(tools.raio_x_da_caixa(args.raio_x))
    else:
        print(tools.emails_nao_lidos_de_hoje())
    return 0


def _financas_consulta(args: argparse.Namespace) -> int | None:
    """Saldo, gastos, busca e fatura: o mesmo texto que o chat recebe, sem o Gemini."""
    from lifeos.financas import pluggy, tools

    buscar = args.buscar is not None or bool(args.valor)
    if not (args.saldo or args.gastos or buscar or args.fatura):
        return None
    desde, ate = args.desde or "", args.ate or ""
    try:
        if args.saldo:
            texto = tools.responder_saldo(levantar=True)
        elif args.gastos:
            texto = tools.responder_gastos(desde, ate, levantar=True)
        elif buscar:
            texto = tools.responder_buscar(
                args.buscar or "", desde, ate, args.valor or "", levantar=True
            )
        else:
            texto = tools.responder_fatura(levantar=True)
    except pluggy.ErroPluggy as exc:
        print(f"❌ {tools.mensagem_de_erro(exc)}", file=sys.stderr)
        return 2
    print(texto)
    return 0


def _financas(args: argparse.Namespace) -> int:
    """Conectar, conferir as conexões e (com --saldo/--gastos/--buscar/--fatura) consultar."""
    import webbrowser

    from lifeos.config import PLUGGY_ITEM_IDS
    from lifeos.financas import conectar, pluggy

    consulta = _financas_consulta(args)
    if consulta is not None:
        return consulta

    try:
        cliente = pluggy.cliente()
    except pluggy.ErroPluggy as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    def descrever(item_id: str) -> str:
        item = cliente.conexao(item_id)
        contas = cliente.get("/accounts", itemId=item_id).get("results") or []
        tipos = ", ".join(
            f"{c.get('name') or '?'} ({c.get('type')}/{c.get('subtype')})" for c in contas
        )
        conector = (item.get("connector") or {}).get("name") or "?"
        return (
            f"{conector}: {item.get('status')} · atualizado {item.get('lastUpdatedAt') or '?'} · "
            f"{len(contas)} conta(s){': ' + tipos if tipos else ''}"
        )

    if args.conectar:
        try:
            token = cliente.token_de_conexao()
        except pluggy.ErroPluggy as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 2

        def abrir(url: str) -> None:
            print(f"Abrindo o navegador em {url} (se não abrir, cole o endereço).")
            print("Dentro da janela da Pluggy: entre no Meu Pluggy e autorize UM banco.")
            webbrowser.open(url)

        resultado = conectar.servir(token, abrir=abrir)
        if resultado.item_id:
            try:
                print(f"✅ Conectado: {descrever(resultado.item_id)}")
            except pluggy.ErroPluggy as exc:
                print(f"⚠️ Conectado, mas não consegui conferir agora: {exc}")
            ids = ",".join(dict.fromkeys([*PLUGGY_ITEM_IDS, resultado.item_id]))
            print("Coloque (ou troque) esta linha no .env da raiz:")
            print(f"PLUGGY_ITEM_IDS={ids}")
            return 0
        if resultado.erro:
            print(f"❌ A Pluggy devolveu um erro: {resultado.erro}", file=sys.stderr)
            return 2
        if resultado.fechou:
            print("A janela foi fechada sem conectar nenhum banco.")
        else:
            print("Tempo esgotado sem resposta da janela da Pluggy.")
        return 1

    if not PLUGGY_ITEM_IDS:
        print("Nenhuma conexão no .env (PLUGGY_ITEM_IDS). Rode `viking financas --conectar`.")
        return 1
    falhou = False
    for item_id in PLUGGY_ITEM_IDS:
        try:
            print(f"- {descrever(item_id)}")
        except pluggy.ErroPluggy as exc:
            falhou = True
            print(f"- ❌ {item_id[:8]}…: {exc}")
    return 2 if falhou else 0


def _aprovar() -> int:
    """Os pedidos que vieram de outro app (MCP), um por um, com os dados exatos; o dono digita o
    código de cada um para aprovar. Só num terminal interativo (D36): um app que roda comandos
    (um agente com terminal) leria o código de uma saída que não é tela de gente."""
    from lifeos import aprovacoes, confirmacao
    from lifeos.browser._redacao import limpar_controles
    from lifeos.calendar import service as calendario_service
    from lifeos.config import TIMEZONE

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print(
            "❌ `viking aprovar` só roda num terminal interativo, digitado por você.",
            file=sys.stderr,
        )
        return 2
    pedidos = [
        (tipo, proposta)
        for tipo in aprovacoes.TIPOS
        if not tipo.no_chat
        for proposta in confirmacao.abertas(tipo.acao)
    ]
    if not pedidos:
        print("Nenhum pedido esperando aprovação.")
        return 0
    falhou = False
    for tipo, proposta in pedidos:
        descricao = limpar_controles(str(proposta.dados.get("descricao") or tipo.acao))
        quando = proposta.expira.astimezone(TIMEZONE).strftime("%H:%M")
        print(f"\nPedido de outro app (MCP): {descricao}. Vale até as {quando}.")
        print(f"Para aprovar, digite o código {proposta.codigo} (Enter pula).")
        resposta = input("Código: ").strip()
        if not resposta:
            print("Pulado: nada mudou.")
            continue
        try:
            evento = calendario_service.executar_aprovado(tipo.acao, resposta)
        except (confirmacao.ErroConfirmacao, calendario_service.ErroCalendario) as exc:
            falhou = True
            print(f"❌ Não fiz: {limpar_controles(str(exc))}.", file=sys.stderr)
            continue
        feito = "apagado" if tipo.acao == aprovacoes.CALENDARIO_APAGAR else "reagendado"
        print(f"✅ Evento '{evento.titulo}' {feito}. Para desfazer: `viking registro --ids`.")
    return 2 if falhou else 0


def _registro(args: argparse.Namespace) -> int:
    """O que o Viking fez (30 dias) e, com --desfazer ID, desfaz uma ação de calendário."""
    from lifeos import registro_texto
    from lifeos.browser._redacao import limpar_controles
    from lifeos.calendar import service as calendario_service

    if args.desfazer is None:
        print(registro_texto.texto_das_recentes(args.dias, com_id=args.ids))
        if not args.ids:
            print("(`viking registro --ids` mostra o número de cada ação, para --desfazer ID.)")
        return 0
    try:
        feito = calendario_service.restaurar(args.desfazer)
    except calendario_service.ErroCalendario as exc:
        print(f"❌ Não desfiz: {limpar_controles(str(exc))}. Nada mudou.", file=sys.stderr)
        return 2
    print(f"↩️ Desfeito: '{feito.titulo}' ({feito.como}).")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="viking")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "chat",
        help="Inicia o assistente de chat (calendário, navegador, lembretes, e-mail, finanças)",
    )
    subparsers.add_parser(
        "mcp-server", help="Inicia o servidor MCP do Viking (calendário + lembretes)"
    )
    navegador = subparsers.add_parser(
        "browser", help="Executa um objetivo num navegador real (executor Jev)"
    )
    navegador.add_argument("--url", help="URL inicial (obrigatório, exceto com --doctor)")
    navegador.add_argument(
        "--goal",
        action="append",
        dest="goals",
        metavar="OBJETIVO",
        help="Objetivo em linguagem natural; repita para uma lista ordenada",
    )
    navegador.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Segundos até interromper (padrão: VIKING_BROWSER_TIMEOUT_S, 180)",
    )
    navegador.add_argument(
        "--fechar", action="store_true", help="Fecha a aba ao terminar (padrão: deixa aberta)"
    )
    navegador.add_argument("--json", action="store_true", help="Imprime o resultado bruto em JSON")
    navegador.add_argument(
        "--quiet", action="store_true", help="Não imprime o progresso passo a passo"
    )
    navegador.add_argument(
        "--doctor",
        action="store_true",
        help="Mostra a versão do Jev, diagnostica o Browser Harness e sai",
    )

    gmail = subparsers.add_parser(
        "gmail", help="Lê o Gmail pela API, sem o Gemini (padrão: não lidos de hoje)"
    )
    acao = gmail.add_mutually_exclusive_group()
    acao.add_argument("--login", action="store_true", help="Faz/confere o login do Gmail e sai")
    acao.add_argument("--buscar", metavar="CONSULTA", help='Busca do Gmail, ex.: "is:unread"')
    acao.add_argument("--ler", metavar="ID", help="Lê um e-mail pelo ID de uma busca")
    acao.add_argument(
        "--raio-x", type=int, nargs="?", const=30, metavar="DIAS", help="Raio-x da caixa"
    )
    acao.add_argument(
        "--arquivar",
        metavar="ENDERECOS",
        help="Propõe arquivar tudo destes remetentes (vírgula) e pede o código",
    )
    acao.add_argument("--desfazer", metavar="CODIGO", help="Desfaz uma limpeza (até 7 dias)")
    gmail.add_argument("--max", type=int, default=10, help="Máximo de resultados da busca")

    financas = subparsers.add_parser(
        "financas",
        help="Pluggy: conecta um banco, confere as conexões (padrão) ou consulta, só leitura",
    )
    o_que = financas.add_mutually_exclusive_group()
    o_que.add_argument(
        "--conectar",
        action="store_true",
        help="Abre a janela oficial da Pluggy no navegador e mostra o ID da conexão criada",
    )
    o_que.add_argument("--saldo", action="store_true", help="Saldo das contas e limite do cartão")
    o_que.add_argument(
        "--gastos", action="store_true", help="Gastos do período (padrão: o mês até hoje)"
    )
    o_que.add_argument("--buscar", metavar="TEXTO", help="Transações com esse pedaço na descrição")
    o_que.add_argument("--fatura", action="store_true", help="Faturas e limite dos cartões")
    financas.add_argument("--valor", help="Com --buscar (ou sozinho): valor, ex.: 1500 ou 89,90")
    financas.add_argument("--desde", metavar="AAAA-MM-DD", help="Início do período")
    financas.add_argument("--ate", metavar="AAAA-MM-DD", help="Fim do período (padrão: hoje)")

    subparsers.add_parser(
        "aprovar", help="Aprova (com código) pedidos que outros apps fizeram pelo MCP"
    )
    registro_cli = subparsers.add_parser(
        "registro", help="O que o Viking fez (até 30 dias) e desfazer no calendário"
    )
    registro_cli.add_argument("--dias", type=int, default=7, help="Quantos dias mostrar (1 a 30)")
    registro_cli.add_argument(
        "--desfazer", type=int, metavar="ID", help="Desfaz uma exclusão ou reagendamento"
    )
    registro_cli.add_argument("--ids", action="store_true", help="Mostra o número de cada ação")

    args = parser.parse_args()

    from lifeos import registro

    # Quem pede, para o registro de ações: o chat e o MCP marcam a própria origem por cima.
    registro.ORIGEM.set("cli")

    if args.command == "chat":
        from lifeos.assistant.agent import iniciar_assistente

        iniciar_assistente()
    elif args.command == "mcp-server":
        from lifeos.mcp_server.server import main as run_server

        run_server()
    elif args.command == "browser":
        sys.exit(_browser(args, navegador))
    elif args.command == "gmail":
        sys.exit(_gmail(args))
    elif args.command == "financas":
        sys.exit(_financas(args))
    elif args.command == "registro":
        sys.exit(_registro(args))
    elif args.command == "aprovar":
        sys.exit(_aprovar())


if __name__ == "__main__":
    main()
