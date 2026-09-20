# Browser Harness

- **Projeto:** https://github.com/browser-use/browser-harness
- **O que é:** CLI + daemon local que controla um Chrome real via Chrome DevTools Protocol (CDP); expõe
  primitivas (`page_info()`, `new_tab()`, `js()`, `wait_for_load()`) e também roda como servidor MCP
  próprio (`browser-harness-mcp`).
- **Versão validada:** 0.1.13 (ver `docs/arquitetura/browser-automation-stack.md` para o relatório
  completo de validação, feito em 2026-09-19).
- **Papel no projeto:** é a camada de execução de baixo nível das "mãos" do Viking. O Viking **não**
  fala com ele por MCP (esse caminho existiu e foi removido) — hoje é subprocesso → Jev
  (`jev_ultrafast.Agent`) → `browser_harness` (CDP direto) → Chrome. Ver
  `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 4.2.
- **Achado crítico de confiabilidade:** o daemon pode reportar "vivo" com zero conexões ativas de
  navegador (`daemon alive != browser ready`). Health checks precisam verificar daemon vivo + conexão
  ativa + probe CDP bem-sucedido, não só o processo rodando. `browser-harness --doctor` expõe isso.
- **Boas práticas herdadas da validação:** perfil de Chrome dedicado + endpoint CDP fixo para uso não
  supervisionado (evitar depender do Chrome pessoal do usuário); cada tarefa cria sua própria
  aba/target, nunca reaproveita "a aba ativa atual".
- **Custo/licença:** não verificado neste repo além do necessário para os testes já feitos — conferir
  antes de uso em produção.

## Supervisão de saúde (implementada)

O achado de `daemon vivo != navegador pronto` está implementado em
`src/lifeos/browser/_jev_subprocess.py` (`preparar_navegador()`), que roda **antes** de qualquer
`Agent`, dentro do ambiente do Jev onde `browser_harness` é importável:

1. `ensure_daemon()`;
2. probe CDP real via `helpers.page_info()` — essa chamada é a que **reata** a conexão quando o
   daemon está de pé mas solto;
3. se falhar, checa `admin.daemon_browser_ready()` e faz um segundo probe (tentativa de reattach);
4. se ainda falhar, `admin.restart_daemon()` + `ensure_daemon()` + probe final;
5. se ainda assim falhar, levanta `browser-not-ready` → o usuário recebe uma mensagem clara em vez
   de um `_IPCResponseTimeout` cru.

Retentativas são **limitadas de propósito** (no máximo um reattach e um restart, sem laço infinito),
como o próprio relatório de validação recomenda. O runner emite um evento `health` com o estado
(`ok` / `reatado` / `reiniciado`); quando não é `ok`, o Viking avisa no terminal — assim uma partida
lenta tem explicação visível.

`_IPCResponseTimeout` herda de `TimeoutError`, então falhas de IPC no meio da tarefa (não no
preflight) caem no código de erro `harness_ipc`.
