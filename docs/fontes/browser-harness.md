# Browser Harness

- **Projeto:** https://github.com/browser-use/browser-harness
- **O que é:** CLI + daemon local que controla um Chrome real via Chrome DevTools Protocol (CDP); expõe
  primitivas (`page_info()`, `new_tab()`, `js()`, `wait_for_load()`) e também roda como servidor MCP
  próprio (`browser-harness-mcp`).
- **Versão validada:** 0.1.13 (ver `docs/arquitetura/browser-automation-stack.md` para o relatório
  completo de validação, feito em 2026-09-19).
- **Papel no projeto:** é a camada de execução de baixo nível das "mãos" do Viking — o Viking é cliente
  MCP deste servidor. Ver `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 4.2.
- **Achado crítico de confiabilidade:** o daemon pode reportar "vivo" com zero conexões ativas de
  navegador (`daemon alive != browser ready`). Health checks precisam verificar daemon vivo + conexão
  ativa + probe CDP bem-sucedido, não só o processo rodando. `browser-harness --doctor` expõe isso.
- **Boas práticas herdadas da validação:** perfil de Chrome dedicado + endpoint CDP fixo para uso não
  supervisionado (evitar depender do Chrome pessoal do usuário); cada tarefa cria sua própria
  aba/target, nunca reaproveita "a aba ativa atual".
- **Custo/licença:** não verificado neste repo além do necessário para os testes já feitos — conferir
  antes de uso em produção.
