# Windows-MCP

- **Upstream:** https://github.com/CursorTouch/Windows-MCP (Python, MIT, 7k+ estrelas, Windows 7–11)
- **Fork usado neste projeto:** https://github.com/Zbreno11-git/Windows-MCP
- **Local no repo:** `windows-mcp/` (clone externo, gitignored, próprio `.git` com remotes
  `origin`/`upstream` — não faz parte do histórico deste repositório)
- **O que é:** servidor MCP (stdio/SSE/streamable-HTTP) expondo ~20 tools de automação do Windows
  (Click/Type/Scroll via árvore de UI Automation, `PowerShell`, `Registry`, `FileSystem`, `Process`,
  `Clipboard`) — sem dependência de visão computacional.
- **Papel no projeto:** era a peça de controle local de PC do Windows Agent (trilha de hardware). Ver
  `docs/arquitetura/wristband-hardware-pausado.md`.
- **Status:** pausado — a automação de navegador (Jev + Browser Harness) é hoje o mecanismo padrão de
  execução, ver `browser-harness.md` e `jev-typesafe.md`. Pode voltar a ser relevante se/quando a trilha
  de hardware for retomada.
- **Cuidado:** o próprio README do projeto documenta "full system access with no sandboxing" —
  recomendado rodar em VM/ambiente isolado; a allow-list de ações deve ser aplicada pelo Windows Agent,
  não pelo servidor MCP cru.
