# mac-control-mcp — dead end (registro histórico)

> **Não sugerir usar `mac-control-mcp` novamente neste projeto.** Este documento consolida a pesquisa
> que levou a essa decisão, antes espalhada entre `CLAUDE.md` e `docs/diario-de-bordo.md`.

- **Projeto:** https://github.com/AdelElo13/mac-control-mcp — servidor MCP em Swift, MIT, declarava 153
  tools (acessibilidade, input, janelas, apps, volume), comunicação via stdio, sem chamadas de rede.
- **Era a escolha original** (v1.0 do doc de visão) para o "Life OS Mac Agent" — controle local do Mac.
- **Bloqueio confirmado, não contornável:** o `Package.swift` do projeto fixa
  `platforms: [.macOS(.v14)]` (Sonoma) como requisito de build **e** runtime. O Mac disponível para o
  projeto é um 2017 Intel rodando Ventura 13, sem caminho de upgrade para Sonoma na maioria dos Macs
  Intel de 2017.
- **Decisão (2026-09-19):** abandonar totalmente a trilha Mac. Fork local (`Zbreno11-git/mac-control-mcp`)
  e clone deletados; fork no GitHub deletado (`gh repo delete Zbreno11-git/mac-control-mcp --yes`,
  confirmado via 404 da API que nenhum artefato resta no projeto).
- **Substituto escolhido:** um Windows 11 mini PC ("Bosgame") ficou disponível. Pesquisa comparou
  alternativas de controle de PC via MCP por estrelas/atividade/licença: `CursorTouch/Windows-MCP`
  (7k★, MIT, Python, Windows 7–11, sem lock de versão) venceu decisivamente sobre `winremote-mcp`,
  `mcp-windows-desktop-automation`, `MCPControl`, `mcp-windows`, `windows-mcp-server` e
  `mcp-windows-automation`. Ver `docs/fontes/windows-mcp.md`.
- **Status desta trilha inteira (Windows-MCP incluso):** hoje pausada — ver
  `docs/arquitetura/wristband-hardware-pausado.md`. A automação de navegador (Jev + Browser Harness)
  assumiu o papel de mecanismo principal de execução.
