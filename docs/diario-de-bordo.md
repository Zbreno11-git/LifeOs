# Diário de bordo — Life OS de Pulso

> Manter atualizado a cada sessão de trabalho. Registrar data, o que mudou, evidência e decisão — sem presumir que este arquivo atualiza sozinho a memória do assistente (ver seção final do documento de referência).

Referência de produto/arquitetura: `Life OS de Pulso Visao e Arquitetura.docx` (v1.0, 19/09/2026,
arquivado em `docs/arquitetura/viking-visao-e-arquitetura-v1-pulso.docx`). O documento original propõe
o Mac como executor de ações locais; essa parte foi substituída pelo Bosgame (Windows 11) — ver decisão
em 2026-09-19 abaixo. O resto da arquitetura (fluxo pulseira → API → STT → roteamento → execução)
continua válido, mas essa trilha inteira foi **pausada** em 2026-09-20 — ver log abaixo e
`docs/arquitetura/wristband-hardware-pausado.md`.

> **Nota (2026-09-20):** a partir de hoje, a referência de produto/arquitetura corrente do projeto é
> `docs/arquitetura/viking-visao-e-arquitetura.md` (marca **Viking**, codinome técnico **Life OS**). As
> seções abaixo (Resumo do produto, Componentes, Roadmap de validação, Perguntas em aberto) descrevem
> especificamente a trilha do dispositivo de pulso, hoje pausada — mantidas como estavam, não reescritas.

## Resumo do produto

Assistente de pulso acionado por botão/gesto: captura pensamentos, executa comandos, responde por voz.
Fluxo proposto: botão/gesto → captura no ESP32 → HTTPS → API Life OS → STT → roteamento de intenção →
execução (nuvem / PC Windows / firmware local) → resposta estruturada → TTS → reprodução na pulseira.

## Componentes (estado atual)

| Componente | Papel | Estado |
|---|---|---|
| Arduino Uno R3 + botão + Serial | Validação física de acionamento, comando local sem áudio/nuvem | **Fail test em andamento** |
| XIAO ESP32-S3 + INMP441 + MAX98357A + alto-falante | Captura/reprodução de áudio (I2S), Wi-Fi, energia | Hardware selecionado; integração pendente |
| VL53L0X + botões | Gatilho por proximidade e controles físicos | Fase posterior |
| FastAPI + dados do usuário | Recebe áudio/comandos, autentica dispositivos, roteia intenções, persiste notas/tarefas | Arquitetura proposta |
| STT, modelo, TTS | Transcrição, interpretação de intenção, síntese de fala | Fornecedores e desempenho a validar |
| Life OS Windows Agent (Bosgame) | Conexão de saída com backend, valida comandos, executa ferramentas locais via MCP | **Novo componente a construir** (substitui o "Life OS Mac Agent" do documento original) |
| Windows-MCP (externo) | Servidor MCP em Python, 7k+ estrelas, ferramentas nativas do Windows via stdio (UI Automation, PowerShell, etc.) | Projeto externo — https://github.com/CursorTouch/Windows-MCP · fork: https://github.com/Zbreno11-git/Windows-MCP |

**mac-control-mcp foi descartado como caminho ativo** (não é mais um componente do projeto): o
`Package.swift` do projeto fixa `.macOS(.v14)` como plataforma mínima — trava tanto o binário pré-compilado
quanto qualquer build local. O Mac disponível é um Ventura 13 (Intel, 2017), e macOS Sonoma (14) não é
oferecido para a maioria dos Macs Intel de 2017. Sem caminho de upgrade de SO, não há como rodar esse
servidor nessa máquina. O fork antigo (`Zbreno11-git/mac-control-mcp`) e o clone local foram removidos do
fluxo de trabalho — ver log de 2026-09-19.

Decisão registrada no documento original sobre o mac-control-mcp ("um fork só seria considerado se houvesse
necessidade comprovada de alterar o componente") fica sem efeito prático — o componente inteiro saiu do
projeto, não foi modificado. O mesmo princípio se aplica ao fork do Windows-MCP: ele existe para *consumir*
o servidor (rodar via `uv run windows-mcp serve`), não para alterar seu código-fonte, a menos que surja
necessidade comprovada.

## Roadmap de validação

1. **Fase 1 — Fail test**: Arduino R3 + botão → Serial → script Python no Bosgame → comando MCP local
   (`PowerShell`, alternando mute). Critério de saída: botão aciona uma vez; erro e sucesso observáveis.
2. **MVP 0.5 — Canal remoto**: ESP32 → API autenticada → Windows Agent (Bosgame) → MCP local → play/pause.
3. **MVP 1 — Áudio de entrada**: XIAO + INMP441 → upload Wi-Fi → STT → nota/ação.
4. **MVP 2 — Resposta e ergonomia**: ToF, MAX98357A, alto-falante, botões, TTS.
5. **Produto**: case, pareamento, atualizações, observabilidade, catálogo de ações.

## Perguntas em aberto (do documento original, adaptadas)

- Qual rede dará acesso à pulseira fora do Wi-Fi conhecido (hotspot, telefone como ponte, conectividade própria)?
- Quais comandos são seguros para execução direta vs. exigem confirmação?
- Como provisionar/atualizar o Windows Agent no Bosgame e recuperar uma conexão interrompida? (O documento
  original falava em permissões TCC do macOS — no Windows o equivalente é UAC/permissões de automação; ainda
  não avaliado.)
- Quais metas mensuráveis (autonomia, latência, precisão STT, custo por pedido) justificam o produto?
- Notas/lembretes ou controle do PC primeiro? MVP 0.5 prova integração técnica, não valor de uso diário.

---

## Log de progresso

### 2026-09-19

- Lido e resumido o documento `Life OS de Pulso Visao e Arquitetura.docx` (v1.0).
- Confirmado que o repositório citado no documento (`[1]`) e no README do fail test era o mesmo:
  https://github.com/AdelElo13/mac-control-mcp (Swift, MIT, 153 ferramentas, apenas stdio, sem chamadas de rede).
- Criado `requirements.txt` com as dependências da Fase 1 (fail test): `mcp`, `pyserial`. Instaladas no
  `.venv` do projeto.
- Criado este diário de bordo em `docs/` e o `CLAUDE.md` na raiz.
- Fork criado e clonado: `Zbreno11-git/mac-control-mcp` (upstream `AdelElo13/mac-control-mcp`), com
  `LifeOS Arduino Fail Test/` copiada para dentro dele como `lifeos-failtest/`.
- **Bloqueio descoberto**: o usuário informou que o Mac disponível é um Ventura 13 (Intel, 2017).
  `Package.swift` do mac-control-mcp fixa `platforms: [.macOS(.v14)]` — requisito rígido de build e de
  runtime, não apenas recomendação. macOS Sonoma (14) não é oferecido para a maioria dos Macs Intel de 2017.
  Bloqueio confirmado como real, sem contorno viável nessa máquina.
- Usuário informou ter um mini PC **Bosgame com Windows 11** disponível. Pesquisa no GitHub por
  alternativas de controle de PC via MCP; comparados por estrelas/atividade/licença: `CursorTouch/Windows-MCP`
  (7k★, MIT, Python, roda em Windows 7–11 sem trava de versão) venceu com folga sobre `winremote-mcp`,
  `mcp-windows-desktop-automation`, `MCPControl`, `mcp-windows`, `windows-mcp-server`, `mcp-windows-automation`.
- Fork criado e clonado: https://github.com/Zbreno11-git/Windows-MCP (upstream `CursorTouch/Windows-MCP`),
  em `windows-mcp/` na raiz deste repo (gitignored — repo Git próprio, remotes `origin`/`upstream`).
- **Removido o caminho Mac**: apagado o clone local `mac-control-mcp/` e sua cópia `lifeos-failtest/`
  (conteúdo desatualizado após o pivô). Removida a entrada `mac-control-mcp/` do `.gitignore`. Usuário
  confirmou apagar o fork no GitHub; `gh repo delete Zbreno11-git/mac-control-mcp --yes` executado após
  `gh auth refresh -s delete_repo` (token não tinha esse escopo até então). Fork removido — confirmado 404
  na API. Não sobra nenhum artefato do caminho mac-control-mcp neste projeto.
- Migrado o fail test para o Bosgame: pasta `LifeOS Arduino Fail Test/mac/` renomeada para `pc/`;
  `serial_mcp_bridge.py` reescrito para chamar a ferramenta MCP `PowerShell` do Windows-MCP (via
  `uv run windows-mcp serve`, stdio) alternando o mute do sistema (`keybd_event`/`VK_VOLUME_MUTE`) em vez do
  `set_volume` do mac-control-mcp. README do fail test reescrito para Windows (portas `COM*`, `uv`,
  PowerShell em vez de Xcode/Swift).
- Pendente: rodar de fato no Bosgame (clonar o fork lá, `uv run windows-mcp serve`, testar com o Arduino) —
  não é possível validar isso neste ambiente Linux.

### 2026-09-20

**Brainstorm de produto e reorganização completa do repositório**, feito interativamente com o usuário
(perguntas e respostas registradas na sessão) para reconciliar peças que tinham surgido em paralelo sem
documentação: `calendar-bot/` (protótipo de assistente de calendário via Gemini), `jev-ultrafast/` +
`life_os_browser_stack.md` (automação de navegador via MCP, já validada em testes reais), e as ideias
fundadoras nunca documentadas neste repo — **Viking** (marca do assistente pessoal unificado, com RAG) e
**finanças** (administração via dados confiáveis, não entrada manual).

**Decisões do brainstorm:**
- Viking = marca do produto inteiro. Life OS = codinome técnico interno; pacote continua `lifeos`.
- Trilha de hardware (pulso/Arduino/Windows-MCP) **pausada e arquivada** — não descontinuada.
- Automação de navegador (Jev + Browser Harness) substitui o Windows-MCP como mecanismo principal de
  execução ("mãos" do assistente) daqui pra frente.
- Finanças continuam core do Life OS a longo prazo, mas via **Pluggy** (open finance brasileiro, conta já
  conectada) — não entrada manual, considerada não confiável o suficiente. Fase futura, sem código ainda.
- Próximo milestone: assistente de chat **CLI-first** unificando Google Calendar (portado do
  `calendar-bot/`), automação de navegador (cliente MCP do Browser Harness) e lembretes gerais
  (armazenamento estruturado "RAG-ready", sem embeddings de verdade ainda).
- Viking expõe seu próprio servidor MCP (calendário + lembretes como tools), além de ser cliente MCP do
  Browser Harness.
- `AGENTS.md` novo como fonte canônica de instruções (Codex vai trabalhar neste repo também);
  `CLAUDE.md` vira um arquivo enxuto que importa `AGENTS.md` (`@AGENTS.md`), evitando duas fontes de
  verdade divergentes.

**Execução (mesma sessão):**
- **Segurança primeiro**: `calendar-bot/credentials.json` e `calendar-bot/token.json` (segredos OAuth
  reais) não eram cobertos por nenhuma regra de `.gitignore` — só `.env` era, incidentalmente. Corrigido
  antes de qualquer outra mudança; verificado com `git check-ignore -v`.
- Criada taxonomia `docs/arquitetura/` (visão/arquitetura) e `docs/fontes/` (6 páginas de referência
  técnica: Windows-MCP, Browser Harness, Jev/TypeSafe, Google Calendar API, Pluggy, o dead-end do
  mac-control-mcp consolidado num só lugar).
- `life_os_browser_stack.md` movido para `docs/arquitetura/browser-automation-stack.md` (com nota
  histórica sobre as referências a `mac-mcp`, escritas antes do pivô para Windows). `.docx` original
  movido para `docs/arquitetura/viking-visao-e-arquitetura-v1-pulso.docx`. Novo doc-bandeira criado:
  `docs/arquitetura/viking-visao-e-arquitetura.md` (v2.0).
- `LifeOS Arduino Fail Test/` movida para `archive/wristband-fail-test/` (com banner de status
  pausado); `wristband-hardware-pausado.md` criado condensando a arquitetura/roadmap de hardware que
  antes vivia inline no `CLAUDE.md`.
- **`calendar-bot/` portado para `src/lifeos/`**: novos módulos `calendar/` (OAuth + tools, com os
  caminhos de credenciais corrigidos para usar `lifeos.config` em vez dos relativos fixos do
  protótipo — só funcionavam por acidente), `browser/` (cliente MCP do Browser Harness + supervisor de
  saúde, "daemon vivo != navegador pronto"), `reminders/` (schema + SQLite, campos genéricos
  `type`/`source`/`external_id`/`metadata` pensados para acomodar dados do Pluggy depois),
  `assistant/agent.py` (generalização do REPL do calendar-bot, agora com as três capacidades),
  `mcp_server/` (servidor MCP próprio do Viking), `cli.py` (`viking chat` / `viking mcp-server`).
  Segredos reais copiados para `secrets/` (`google_credentials.json`, `google_token.json`) e `.env` da
  raiz; `calendar-bot/` removido após validar que os imports funcionam de fora dele.
- `pyproject.toml` atualizado com as dependências reais (derivadas dos imports, não copiadas do
  `requirements.txt` do protótipo, que citava `mcp` sem uso e omitia `google-auth-oauthlib`), extra
  `hardware` (`pyserial`) e o script `viking`. `requirements.txt` da raiz removido — consolidado em
  `pyproject.toml` (`mcp` é dependency core, `pyserial` é o extra `hardware`), evitando duas fontes de
  dependências.
- `AGENTS.md` criado; `CLAUDE.md` reescrito como arquivo enxuto (`@AGENTS.md`); `README.md` atualizado.
- Verificação: `pytest` (2 passed) e `ruff check .` (all checks passed) depois da migração;
  `python -c "from lifeos.calendar import tools"` e `viking --help` confirmados funcionando a partir da
  raiz do repo, sem depender da pasta `calendar-bot/` original.
- Pendente/recomendado, não feito nesta sessão: criar um fork pessoal de `jev-ultrafast` (hoje o
  `origin` aponta direto pro upstream `browser-use/jev-ultrafast`, sem remote próprio para os 3 commits
  locais, incluindo o patch de fallback pra OpenRouter) — ver `docs/fontes/jev-typesafe.md`.
