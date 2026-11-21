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

### 2026-09-20 — reorganização do repo em torno do Viking

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
  `origin` aponta direto pro upstream `browser-use/jev-ultrafast`, sem remote próprio para o patch de
  fallback pra OpenRouter) — ver `docs/fontes/jev-typesafe.md`.
  > **Correção (2026-09-20):** esta linha dizia "os 3 commits locais, incluindo o patch". Era falso —
  > os 3 commits eram todos do upstream e o patch existia **apenas como modificação não commitada**.
  > O risco era portanto maior do que o registrado. Resolvido na sessão seguinte (ver abaixo).

### 2026-09-20 — MVP: calendário e navegador juntos na CLI

**MVP: calendário e navegador funcionando juntos no `viking chat`.** Até aqui a ferramenta de
navegador era um stub declarado (`browser_goal` abria uma aba e ignorava o objetivo). Agora o Viking
executa tarefas de verdade num Chrome real, via Jev.

- **Fork do Jev criado e patch protegido** (era a pendência mais urgente): `Zbreno11-git/jev-ultrafast`,
  branch `viking-openrouter`, commit `afbee69`. O clone local passou a ter `origin` = fork e
  `upstream` = `browser-use/jev-ultrafast`. Antes disso, o patch que troca o endpoint da TypeSafe pelo
  de decisões da OpenRouter — a única razão pela qual a chave disponível funciona — existia só como
  modificação não salva numa pasta gitignorada; qualquer `git checkout` o apagaria.
- **Decisão de arquitetura: subprocesso, não import.** O Viking chama o Jev com
  `uv run --directory <VIKING_JEV_DIR>`, no ambiente do próprio Jev, e lê um protocolo JSONL do
  stdout. Motivo: o Jev não tem timeout de wall-clock nem cancelamento (os limites internos levantam
  exceção e só dá pra parar entre passos), então in-process uma tarefa travada congelaria o REPL sem
  recuperação. Como processo separado, temos prazo e kill de verdade. De quebra, o pin
  `browser-harness==0.1.13` (que rebaixaria `websockets` 16.1.1→15.0.1) fica fora da venv do Viking, e
  o setup do Jev que já funciona no Mac é reaproveitado intacto.
- **Descoberta que mudou o desenho:** o Jev **não** usa MCP — ele fala CDP direto via `browser_harness`
  e sobe o próprio daemon. O caminho MCP que tínhamos (`browser/client.py` + `supervisor.py`, via
  `uvx browser-harness-mcp`) era redundante e, pior, competiria pelo mesmo daemon (`BU_NAME=default`) e
  pela mesma Chrome. Ambos os arquivos foram deletados.
- **Supervisão do daemon implementada** (`preparar_navegador()` em `_jev_subprocess.py`), atendendo ao
  incidente já registrado em `browser-automation-stack.md` §10-11 (`daemon vivo != navegador pronto`,
  `_IPCResponseTimeout` após 5s com 0 conexões ativas): probe CDP real via `page_info()` — que é o que
  reata a conexão —, depois tentativa de reattach, e no limite um `restart_daemon()`. Retentativas
  limitadas de propósito, sem laço infinito. O runner emite um evento `health` e o Viking avisa no
  terminal quando precisou reatar/reiniciar.
- **Novos módulos:** `browser/jev_runner.py` (spawn, prazo, kill em grupo de processo, trava de
  execução única, parsing do JSONL), `browser/_jev_subprocess.py` (roda sob o interpretador do Jev; só
  stdlib + `jev_ultrafast`), `browser/mensagens.py` (traduz os códigos de erro para português). Todo
  erro diz explicitamente que nada do que já foi feito na página foi desfeito; `timeout`,
  `step_budget` e afins avisam que a tarefa pode ter ficado pela metade, para que ninguém (nem o
  modelo) reexecute às cegas.
- **Novo subcomando `viking browser`** (`--url`, `--goal` repetível, `--timeout`, `--json`, `--quiet`,
  `--doctor`): executa o stack inteiro sem passar pelo Gemini, então uma falha ali é inequivocamente do
  navegador e não da ligação com o modelo. `--doctor` repassa o `browser-harness doctor` do próprio
  fornecedor.
- **Config:** `VIKING_JEV_DIR`, `VIKING_JEV_ENV_FILE`, `VIKING_UV_BIN`, `VIKING_BROWSER_TIMEOUT_S`
  (padrão 180s). As chaves do Jev continuam no `.env` **dele** — o Viking guarda só o ponteiro, para
  não duplicar a mesma chave OpenRouter em dois arquivos (armadilha de rotação).
- **Testes:** 47 passando, incluindo prazo que de fato mata o processo filho, parsing de saída
  corrompida, `uv`/pasta do Jev ausentes sem spawnar nada, e o evento de recuperação do daemon. Dois
  bugs reais foram achados pelos próprios testes: o timeout era mascarado como `runner_crash`, e um
  código de erro desconhecido engolia o detalhe técnico.
- **Pendente:** validar no Mac (ver checklist no plano). Nada disso foi executado contra uma Chrome de
  verdade — este ambiente é Linux sem tela, e o Browser Harness pede um clique humano em "Allow remote
  debugging" na primeira vez. O risco não verificado mais importante segue sendo o endpoint alpha de
  decisões da OpenRouter aceitar o corpo no formato TypeSafe.

### 2026-09-20 — endurecimento após o primeiro uso real no Mac

Primeira vez que o Viking rodou contra um Chrome de verdade, na máquina do dono. Tudo abaixo saiu de
falha observada em uso, não de revisão de código. Ordem cronológica dos consertos:

**Bring-up no Mac.** `pip` resolvia para o conda em vez do venv (conda base ativo junto), deixando o
`lifeos` fora do ambiente e o `pytest` falhando com `ModuleNotFoundError`. `python -m pip` resolveu.
Registrado porque vai acontecer de novo em qualquer máquina com conda.

**`from __future__ import annotations` quebrou todo function-calling.** Toda tool chamada *com
argumento* falhava com `isinstance() arg 2 must be a type...`. O future import transforma anotações
em strings e o google-genai valida argumentos com `isinstance(valor, anotação)`. Só chamadas sem
argumento escapavam, o que mascarou o problema (`listar_proximos_eventos` funcionava). Removido dos
três módulos que expõem tools, com comentário no topo de cada um e teste por tool que falha se
voltar. Foi regressão minha na migração do `calendar-bot`, que não tinha o import.

**`blocked` não é prova de fracasso.** Uma tarefa que funcionou (clicou o link, navegou para o
destino) voltou como `blocked`, porque na página nova não sobrava ação rumo à meta. A mensagem lia
como fracasso puro e teria feito o assistente reportar erro numa tarefa bem-sucedida.

**A aba sumia.** O Jev cria a aba em segundo plano e a fechava ao sair: "abre o YouTube pra mim"
abria e fechava. Fechar virou opt-in; por padrão a aba fica e é trazida para a frente
(`Target.activateTarget`).

**Exclusão de evento ganhou trava estrutural.** Apagar exigia só um termo e apagava o primeiro que
casasse, sem mostrar qual — com dois eventos de mesmo nome, o usuário não sabia qual sumiu. Agora
`apagar_evento_por_id` exige o ID (que só sai de `buscar_eventos_por_termo`) e confere o título
esperado contra o real, recusando se divergirem.

**Custos visíveis.** O Jev já guardava `usage` de toda chamada paga; agora isso é agregado e
mostrado. Números reais medidos: ~US$0,0008 por turno de chat; uma tarefa de navegador em site
simples ~US$0,0001; **uma no YouTube: 24.507 tokens em 6 chamadas (US$0,00096)** — muito mais que a
estimativa que eu vinha usando, porque o Jev manda até 6000 caracteres de texto de página ao modelo
de decisão a cada passo, e `example.com` tem uma fração disso. Em dólar segue barato (a rota do
modelo de decisão sai a ~US$0,04/milhão de tokens), mas **não** é "ordens de grandeza mais barato"
que o Gemini em sites complexos — naquele turno o navegador custou mais que o Gemini.

**Descrições das tools comprimidas: 1782 → 1305 tokens (-26,8%), medido.** A inspeção da
`FunctionDeclaration` mostrou que o bloco `Args:` inteiro entra como prosa na `description`, com os
parâmetros do schema ficando com `description=None` — ou seja, metade do texto era redundante com o
schema e cobrada em toda mensagem. Teste garante que as regras de comportamento sobreviveram ao
corte. `navegar_e_executar` continua sendo a mais cara sozinha (332 dos 1305).

**Três loops distintos do executor, três consertos.** Nenhum é pego pelo guard do próprio Jev, que
só detecta página que *não* muda:

1. *Objetivo-pergunta* ("abra X e me diga qual é o link principal"): nenhuma ação satisfaz a meta,
   27 ações em ping-pong. Conserto: a descrição da tool proíbe pergunta como objetivo e explica que
   o conteúdo da página volta no resultado.
2. *Ciclo período 3* (busca no YouTube reiniciando a cada tentativa de clicar resultado ainda não
   carregado). Meu detector só cobria período 2. Generalizado para 2–4, com assinatura `(url, ação)`
   em vez de só URL — digitar num campo não muda a URL.
3. *Loop estrutural* ("abre o **segundo** resultado"): cinco vídeos diferentes, nenhuma repetição
   literal. Conserto: assinatura ampla com URL normalizada (sem query) + tipo da ação, rodando em
   paralelo à exata. Teto próprio de 30 ações como rede final.

Causa raiz do caso 3, que **não** tem conserto na nossa camada: ordinais além do primeiro não
funcionam porque o Jev escolhe entre elementos da página, não conta posições. Virou regra na
descrição da tool. "Primeiro resultado" funciona; "segundo" não. Se isso virar necessidade real, o
caminho é uma ferramenta nossa que leia a lista de resultados e devolva as URLs.

**Também corrigido:** texto digitado passou a constar no histórico devolvido (sem ele o diagnóstico
do caso 3 dependia de adivinhação); `criar_lembrete` ganhou prazo (`quando`, ISO 8601) — antes "me
lembra amanhã de X" salvava sem o "amanhã"; REPL ignora entrada vazia, que gerava `Viking: None`; e
o Viking passou a saber a data de hoje, antes ele perguntava.

**Validado ao vivo, funcionando:** calendário (listar, criar, apagar com confirmação), lembretes com
prazo em SQLite (`data/viking.db`, criado na primeira gravação), navegador abrindo e mantendo aba,
busca+clique no primeiro resultado, Ctrl-C matando o subprocesso limpo, recuperação do daemon do
Browser Harness (o `doctor` reportou 0 conexões e a tarefa seguinte funcionou, reatando).

### 2026-09-20 — auditoria independente do Codex

- Auditoria somente leitura concluída sobre código, testes, configuração, documentação e os contratos
  consumidos do clone `jev-ultrafast`; nenhum código funcional foi alterado.
- Verificações: `111` testes passando, `ruff check` passando, `pip check` sem requisitos quebrados,
  CLI importável e servidor MCP iniciando em `stdio` com 10 tools descobertas. O format check apontou
  10 arquivos fora do formato, sem erro de sintaxe.
- Achados prioritários: trava de exclusão atravessável por título vazio/substrings; consulta de um dia
  abrangendo quase dois; fim inválido de evento de dia inteiro; reagendamento ambíguo pelo primeiro
  resultado; confirmação sensível apenas no prompt; egress de conteúdo autenticado do navegador para
  modelos externos; subcontagem de custo Gemini; e lacunas no ciclo de vida do subprocesso.
- Relatório/handoff detalhado criado em `auditoria_codex_1.md`, escrito como prompt para uma futura
  sessão do Claude confirmar, priorizar e só então implementar com autorização do usuário.

### 2026-09-20 — primeira rodada de correções da auditoria (calendário, custos, runner)

Antes de corrigir qualquer achado, medi em vez de confiar no relatório — mesma régua da sessão
anterior (custo do navegador). Confirmados com evidência reproduzida: `titulo_esperado=""` e
`"   "` apagavam qualquer evento (substring vazia casa com tudo); a janela de "um dia" ia até
`timeMax=2026-09-21T23:59:59Z` em UTC fixo; a doc do Google confirma que `end` é exclusivo, então
`end.date == start.date` no dia inteiro estava errado; `reagendar_evento` pegava `events[0]` sem
checar título; o SDK do Gemini (`google-genai` 2.24.0) reatribui `response` a cada volta do laço de
function-calling automático e só a última sobrevive no `usage_metadata` visível — um turno com
ferramenta subcontava todas as chamadas anteriores; `thoughts_token_count` existe no metadata e não
entrava na conta; `custos.py` lia as tarifas do `.env` antes do `load_dotenv` de `config.py` rodar,
então um override na raiz era ignorado sem aviso.

Dois achados do relatório eram menos graves do que descrito: o teste
`test_aceita_titulo_parcial` não cristalizava substring de verdade (só diferença de caixa,
`"dentista"` vs `"Dentista"`), e `navegar_e_executar` nunca esteve exposto no servidor MCP.

**Calendário.** `apagar_evento_por_id` e o novo `reagendar_evento_por_id` (substituiu
`reagendar_evento`, que escolhia por termo) exigem igualdade de título normalizada
(Unicode NFC + `casefold()` + espaços colapsados) em vez de substring, e recusam ID ou título
vazios. `listar_eventos_por_data` ganhou `_janela()`: monta os limites no fuso civil configurado
por `VIKING_TIMEZONE` (nova env; padrão = offset fixo da máquina, **não** acompanha horário de
verão) e `data_fim` passou a ser inclusiva de verdade, sem o dia extra. `criar_evento_dia_inteiro`
usa `end.date` no dia seguinte. `criar_evento` e o novo reagendamento validam fim > início antes de
chamar a API.

**Custos.** `PRECO_GEMINI_ENTRADA`/`_SAIDA` mudaram para `config.py` (onde o `.env` já é carregado)
— resolve a leitura tardia. `do_gemini()` agora soma `thoughts_token_count` (saída) e
`tool_use_prompt_token_count` (entrada). `custos.instrumentar(client)` intercepta
`client.models._generate_content` — o método de baixo nível chamado dentro do laço de AFC — e
contabiliza toda chamada real, não só a que o chat devolve; é acoplamento consciente a um atributo
privado do SDK, com teste dedicado que avisa se ele sumir numa versão futura. `Sessao` ganhou
`iniciar_turno()`/`turno()`, e a linha de custo no REPL foi para um `finally`: uma chamada que já
custou aparece mesmo se a chamada seguinte do mesmo turno falhar.

**Runner do navegador.** Em `_jev_subprocess.py`, checar `status in {"done","blocked"}` antes dos
guardas de limite/loop resolve o caso em que concluir exatamente na ação-limite virava
`step_budget` por engano. `usage` e `kept_open` passaram a ir em todo evento de erro
(`step_budget`, `loop_detected`, `timeout`, e o `except` final), não só nalguns — o custo
acontecia e sumia do resultado. Em `jev_runner.py`, um `on_progress` que levanta agora é engolido
(`_avisar`) em vez de escapar do laço e deixar o subprocesso órfão dirigindo a Chrome; todo o
trecho pós-`Popen` ganhou um `try/finally` que garante matar o processo em qualquer saída; um
`Popen` que falha vira `spawn_failed` em vez de propagar `OSError` — o contrato "devolve sempre um
`BrowserResult`" agora é verdadeiro de fato.

**Testes:** `tests/test_calendar_tools.py` substitui `test_calendar_apagar.py` (35 casos, incluindo
o buraco medido: `titulo_esperado="com"` contra "Reunião com o time"). `tests/test_custos.py` ganhou
os testes de `instrumentar()` com um `client.models` falso. `tests/test_jev_subprocess_main.py` é
novo: roda `_jev_subprocess.main()` de ponta a ponta injetando `jev_ultrafast` e
`browser_harness.{admin,helpers}` falsos via `sys.modules`, já que este ambiente não tem (nem deve
ter) o ambiente real do Jev instalado. 158 testes passando, `ruff check` limpo; `ruff format --check`
segue com os mesmos 10 arquivos pré-existentes que a auditoria encontrou (não mexidos agora, de
propósito, para não misturar formatação com correção de bug — vira Sessão 7 em `sessoes.md`).

**Docs:** corrigidos `docs/fontes/browser-harness.md` e `google-calendar-api.md` (não somos mais
cliente MCP; delete/reagendar são por ID), `.gitignore` (o `origin` do clone do Jev é o fork
pessoal, o upstream fica em `upstream`), `README.md`/`AGENTS.md` (`python -m pip`/`python -m
pytest`, hoje o próprio AGENTS.md se contradizia). O comentário do `from __future__ import
annotations` em `mcp_server/server.py` citava o google-genai por engano — testei ao vivo e o
FastMCP resolve esse future import sem problema (schema e chamada de tool com tipos reais), então a
regra não vale para esse arquivo hoje.

**Escopo restante da auditoria** (privacidade do navegador, confirmação em duas fases, lock
interprocesso, lockfile/CI etc.) foi organizado em `sessoes.md`, novo doc de planejamento — cada
sessão futura cabe em ~1h30, com o § correspondente da auditoria para rastrear.

**Não validado ao vivo** (VPS sem Chrome e sem as chaves): tudo acima passou em teste automatizado
offline; falta o dono confirmar no Mac que "o que eu tenho amanhã?" responde a data certa, que um
evento de dia inteiro ocupa só um dia no Google, e que a linha de custo do navegador aparece maior
e mais honesta que antes. **Atualização 2026-09-20:** confirmado ao vivo (calendário, custos,
runner) — ver "Validação ao vivo das Sessões 1-3" mais abaixo; só a checagem visual do evento de
dia inteiro no Google Calendar em si ficou pendente.

### 2026-09-20 — Sessão 2: config previsível + lembretes no fuso certo

Segunda rodada de correções da auditoria, seguindo `sessoes.md`. Antes de codar, investiguei o
código de verdade (não só o resumo do `sessoes.md`) e isso mudou o desenho em pontos concretos:

- **`Path("/base") / Path("/absoluto")`** em pathlib descarta o lado esquerdo quando o direito já
  é absoluto (comportamento documentado do operador `/`) — então `_path_env` podia virar um
  `.resolve()` único, sem precisar de um `if caminho.is_absolute()`.
- **Ordem importa: `expanduser()` tem que rodar antes do join com `REPO_ROOT`.** Testei os dois
  jeitos: `REPO_ROOT / Path("~/pasta")` (join primeiro) dá um caminho com `~` literal dentro,
  errado; `REPO_ROOT / Path("~/pasta").expanduser()` dá a pasta pessoal real, certo. Registrado em
  `AGENTS.md`.
- **`float("nan")` e `float("inf")` não levantam `ValueError`.** A auditoria (§9.2) já citava isso
  de passagem; testei o mecanismo exato — em `jev_runner.py`, `time.monotonic() + limite` com
  `limite=nan` faz `restante <= 0` devolver `False` para sempre, desligando o timeout que existe
  *especificamente* para matar uma tarefa de navegador travada.

**`config.py`:** `_path_env` agora ancora caminhos relativos em `REPO_ROOT` (medido:
`VIKING_DB_PATH=./x.db` rodado de `/tmp` antes apontava para `/tmp/x.db`; agora aponta para dentro
do repo). Duas funções novas, `_float_env`/`_int_env`, substituem `float()`/`int()` crus nas 4
variáveis numéricas (`VIKING_BROWSER_TIMEOUT_S`, `VIKING_BROWSER_MAX_ACOES`,
`VIKING_PRECO_GEMINI_ENTRADA`/`_SAIDA`) — mensagem de erro cita a variável, e NaN/infinito/valores
não-positivos são recusados antes de virarem configuração ativa.

**`reminders/store.py`:** `due_at` é normalizado para UTC na escrita (naive é tratado como estando
no `TIMEZONE` configurado — o mesmo que o calendário usa desde a Sessão 1) e convertido de volta ao
`TIMEZONE` na leitura. Fecha o achado §12.1: medido no sqlite que `"08:00+00:00"` (=08:00Z) ordenava
como texto antes de `"09:00+02:00"` (=07:00Z, o horário real mais cedo); com tudo normalizado pra
UTC na escrita, a ordenação textual passa a coincidir sempre com a cronológica. Migração automática
e idempotente via `PRAGMA user_version` (nativo do SQLite, não uma flag em memória do processo —
que vazaria entre bancos diferentes nos testes) normaliza registros gravados antes deste fix, sem
comando manual. Índice em `due_at` adicionado; efeito prático quase nulo no volume de dados de uma
pessoa só, incluído porque já estava no escopo.

Efeito colateral bom, de graça: um lembrete "só com data" (sem hora) virava meia-noite ingênua
(§12.2); agora vira meia-noite no `TIMEZONE` configurado — uma âncora real em vez de um vácuo.

**Testes:** `tests/test_config.py` é novo (18 testes: `_path_env`, `_float_env`/`_int_env`, e um
teste de integração via subprocesso provando que uma env inválida derruba o import com mensagem
clara). `tests/test_reminders_store.py` ganhou 6 testes (normalização, ordenação cross-fuso,
migração de registro legado, idempotência, índice). 182 testes passando, `ruff check` limpo.

**Docs:** `AGENTS.md` ganhou duas armadilhas novas (ordem do `expanduser()`; `nan`/`inf` em
`float()`/`int()`) e uma nota na seção de env vars sobre o ancoramento em `REPO_ROOT`.
`.env.example` passou a documentar `VIKING_DB_PATH`, `VIKING_BROWSER_MAX_ACOES` e os preços do
Gemini, que já existiam em `config.py` mas não apareciam lá.

**Não validado ao vivo:** mesma ressalva da sessão anterior — VPS sem Chrome/chaves, tudo abaixo é
teste automatizado offline. **Atualização 2026-09-20:** confirmado ao vivo (config e lembretes) —
ver "Validação ao vivo das Sessões 1-3" mais abaixo.

### 2026-09-20 — Sessão 3: paridade de lembretes no MCP + respostas estruturadas

Terceira rodada, seguindo `sessoes.md`. Escopo reduzido a lembretes (não calendário) por decisão
explícita, confirmada com o dono antes de codar — calendário fica para a Sessão 3b, porque
`calendar/tools.py` é compartilhado com o Gemini e não tem um objeto de domínio no meio (só string
formatada), tornando a mesma mudança mais arriscada ali.

- **§12.5 — CLI e MCP divergiram:** `viking_criar_lembrete` do MCP não aceitava `quando`/prazo,
  diferente de `criar_lembrete` do assistente de chat — a mesma lógica estava escrita duas vezes e
  só uma cópia foi atualizada. Extraído um serviço único, `reminders/service.py`
  (`criar_lembrete()`, exceção `QuandoInvalido`), consumido pelos dois adaptadores. As duas portas
  de entrada agora têm a mesma capacidade.
- **§14 — MCP retorna texto, não payload estável:** as 3 tools de lembrete do MCP passam a
  devolver `fastmcp.tools.ToolResult(content=..., structured_content=...)` — texto humano
  inalterado + um dict estável (id, título, prazo, etc.) para quem consumir programaticamente.
  Calendário fica de fora nesta sessão (Sessão 3b).
- **Erro estruturado de verdade:** `quando` inválido e ID de lembrete inexistente agora usam
  `is_error=True` no MCP — decisão confirmada com o dono, porque muda a experiência de quem chama
  (o protocolo sinaliza falha de execução, não só um aviso em texto).
- **Achado ao investigar antes de codar:** `ToolResult(is_error=True)` faz `Client.call_tool()` do
  FastMCP levantar `ToolError` por padrão, em vez de devolver um resultado inspecionável — testado
  ao vivo antes de decidir a semântica de erro com o dono. Registrado em `AGENTS.md` e
  `docs/fontes/fastmcp.md` (novo).
- **Primeiro teste de protocolo MCP real:** `fastmcp.Client(mcp)` conecta em memória (sem stdio nem
  subprocesso) e permite `list_tools()`/`call_tool()` de ponta a ponta; até esta sessão só
  conferíamos os schemas descobertos, nunca uma chamada de verdade. Não precisou de
  `pytest-asyncio`/`pytest-anyio` — `asyncio.run()` dentro de teste síncrono comum já basta,
  inclusive reusando o mesmo `mcp` (singleton do módulo) entre testes diferentes sem erro de loop.
- **Adiado por decisão de escopo:** structuredContent + paridade de serviço para calendário
  (Sessão 3b, criada em `sessoes.md`); teste preventivo de uma função virar tool do Gemini e do MCP
  ao mesmo tempo (backlog — não há bug real hoje, `mcp_server/server.py` não tem o future-import).

**Testes:** `tests/test_reminders_service.py` (novo, 5 testes) e `tests/test_mcp_server.py` (novo,
8 testes, primeiro cobrindo o protocolo MCP de verdade). `tests/test_assistant_tools.py` continuou
passando sem alteração — assinatura e docstring de `criar_lembrete` ficaram idênticas. 195 testes
passando, `ruff check` limpo.

**Não validado ao vivo:** mesma ressalva das sessões anteriores — VPS sem Chrome/chaves; além
disso, as tools de calendário do MCP não foram exercitadas nesta sessão (exigem OAuth, que também
não existe neste ambiente) — só as de lembrete, que são as tocadas aqui.

### 2026-09-20 — Validação ao vivo das Sessões 1-3, no Mac do dono

As ressalvas "não validado ao vivo" acima ficam resolvidas: o dono rodou o roteiro completo no Mac
(`git pull` até `ac2b84f`, `.venv` ativado corretamente) e confirmou, com saída real colada:

- **Sessão 2 — config:** `VIKING_DB_PATH=./x.db` rodado de `/tmp` resolveu para dentro do repo
  (`~/LifeOs/x.db`); `VIKING_BROWSER_TIMEOUT_S=nan` derrubou o import com
  `ValueError` citando a variável.
- **Sessão 2 — lembretes:** criados via `viking chat` (com e sem prazo) saíram de `list_open()` na
  ordem certa — prazo mais próximo primeiro, sem prazo por último.
- **Sessão 1 — calendário:** criar evento de dia inteiro e apagá-lo pediu confirmação explícita
  antes de executar, como desenhado; só apagou depois do "sim" do dono.
- **Sessão 1 — custos:** os 7 valores impressos por turno somaram **exatamente** os 34628 tokens
  do `/custos` final — confirma que a contabilidade por turno não perde nem duplica chamada
  nenhuma (o furo que a auditoria original tinha achado).
- **Sessão 1 — runner do navegador:** `viking browser --url ... --goal ...` completou, trouxe o
  texto da página e manteve a aba aberta (`kept_open`), sem travar.
- **Sessão 3 — MCP:** `viking_criar_lembrete` via `fastmcp.Client` aceitou `quando` e devolveu
  `structured_content` com `due_at` preenchido; `quando` inválido devolveu `is_error: True` com
  `{"erro": "quando_invalido", ...}`.

**Ainda não validado ao vivo:** as 7 tools de calendário do MCP (nunca exercitadas — ficam pra
quando a Sessão 3b mexer nelas) e o caso em que um evento de dia inteiro é conferido visualmente no
Google Calendar antes de ser apagado (o dono apagou o evento de teste na mesma conversa em que
criou; a lógica de data exclusiva já tem cobertura determinística em `test_calendar_tools.py`, mas
ninguém olhou a UI do Google ainda).

**Achado à parte, sem relação com o código:** o primeiro `python -m pytest` do dono falhou inteiro
com `ModuleNotFoundError: No module named 'lifeos'` porque o terminal estava com o conda `base`
ativo e o `.venv` do projeto nunca tinha sido ativado nessa sessão de shell — `which python`
apontava pro Python do conda, não pro do projeto. Resolvido com `source .venv/bin/activate` (já
documentado em `AGENTS.md`/`CLAUDE.md` como comportamento esperado do setup do Mac); não é um bug
desta base de código, só reforça que `.venv` precisa ser reativado a cada terminal novo antes de
`python -m pytest`/`python -m ruff`.

### 2026-09-26 — Sessão 4: privacidade e egress do navegador

Decisões do dono antes de codar: banco + e-mail bloqueados por padrão no navegador; e-mails
visíveis numa página **não** são redigidos (utilidade); proteger também o caminho do OpenRouter —
feito sem editar o fork do Jev. Nova regra permanente: toda sessão entrega testes offline de
código **e** de segurança.

**Achados medidos antes de codar (no código real, inclusive o clone do Jev):** o `snapshot.js` do
Jev já exclui `<input type="password">` das ações — o risco de texto digitado é em campos
`text`/`tel` (token, 2FA, cartão); o texto digitado nunca chegava ao Gemini (só ao `--json`);
título, URL e rótulos ficavam fora do aviso de não confiável e um `»` na página fechava o
delimitador; `imprimir_progresso` imprimia rótulo da página cru no terminal; `json.dumps(
ensure_ascii=False)` não escapa C1; o Jev chama `choose`/`field_context` como globais de
`jev_ultrafast.agent` e só captura `StalePage` no `tick` — o que torna o envelope possível e o
bloqueio impossível de ser engolido; o primeiro `choose` roda antes do primeiro `yield`, então a
checagem de domínio tinha que morar no envelope, não no laço de passos.

**Entregue:** `browser/_redacao.py` (stdlib, cópia única da regra); envelope
`instalar_protecao()` no subprocesso (redige e bloqueia antes de toda chamada remota; recusa
navegar se não encaixar); `_higienizar()` como ponto único em `jev_runner.result_from`;
`formatar()` com um só bloco delimitado e `«»` neutralizados; preflight de domínio em `run_jev`
(nem abre aba); `VIKING_BROWSER_BLOQUEADOS`/`_LIBERADOS`. Detalhe em
`docs/fontes/jev-typesafe.md`, "Egress e redação".

**Testes:** +97 (292 no total): `test_redacao.py` (unitário, adversarial — `usuario@host`,
sufixo parecido, porta, ponto final, URL sem esquema —, ReDoS), `test_browser_seguranca.py`
(integração: injeção dentro do bloco, `--json` sem C1, progresso limpo, preflight sem `Popen`) e,
em `test_jev_subprocess_main.py`, o envelope (zero chamada ao modelo num domínio bloqueado,
estado original intacto, fecha em falha) e um **teste de contrato** que lê o `agent.py` do clone
real com `ast`. Cada teste de segurança foi conferido por mutação: removendo `_neutralizar`,
`_higienizar` ou a limpeza do progresso, 3–5 testes falham; trocando o limite do bloco de chave
por `.*?`, o teste de ReDoS falha (10,5s contra 0,43s).

**Erros desta sessão (meus):**
1. Dimensionei o teste de ReDoS pequeno demais (5 mil blocos: 2,6s sem limite, perto do teto de
   2s — num Mac rápido a regressão passaria). Pego pela checagem de mutação; subi para 10 mil.
2. Deixei um `cat > arquivo` sem entrada no começo de um comando; ele esperou stdin e travou até o
   timeout. Refeito sem isso.
3. Escrevi `"\u202e"` em testes pela ferramenta de escrita, cujo parâmetro é JSON — o escape virou
   o caractere bidi **literal** no código-fonte (a própria técnica Trojan Source que o teste cobre).
   O `ruff` pegou (`PLE2502`); troquei por escape via script e registrei em `AGENTS.md`. Reincidi ao
   escrever este mesmo item no diário (o comando do terminal também é JSON); pego pela varredura
   de caracteres de controle em todos os arquivos alterados, que passa a rodar antes de cada commit.
4. Na conversa anterior afirmei que o "Jev" da TypeSafe "quase certamente não é o mesmo" do
   `jev-ultrafast`. Errado: o `.env` do Jev usa `TYPESAFE_MODEL=~typesafe/jev-latest` — é o
   modelo de decisão dele, e estava documentado aqui mesmo, em `jev-typesafe.md`. Afirmei sem
   conferir o repo.
5. Na Sessão 3 criei `docs/fontes/fastmcp.md` com bloco de código fora do padrão do `ruff format`
   (que também formata Python dentro de Markdown); só conferi os `.py`. Formatado agora.
6. Quase registrei em `AGENTS.md`, como "armadilha já paga", que redigir o valor dos campos faria o
   Jev repreencher em loop — é consequência direta do prompt dele, mas nunca observada. Movi para o
   doc do Jev marcada como não medida.

**Desvio do plano:** o item "não redigir `current_value`" saiu das armadilhas do `AGENTS.md` (erro
6). E formatar `browser/__init__.py` e `mensagens.py`, que esta sessão editou, levou junto a
formatação pré-existente deles (baseline de arquivos fora do `ruff format` caiu de 9 para 7).

**Não validado ao vivo:** bloqueio e redação no Chrome real do Mac. O venv do Jev neste VPS não
executa (`Permission denied` no Python dele), então nem o envelope no ambiente real do Jev pôde
rodar aqui — só o teste de contrato sobre o código-fonte.

### 2026-09-26 — Sessão 3b: calendário estruturado no MCP

Mesmo desenho da Sessão 3 (lembretes), aplicado às 7 tools de calendário. `calendar/service.py`
concentra lógica e travas com erros de domínio tipados (`entrada_invalida` com `campo`,
`nao_encontrado`, `titulo_divergente` com `titulo_real`, `falha_api`); `calendar/tools.py` ficou
só com o texto (`responder_*` → `Resposta(texto, dados, erro)`), e as tools do Gemini devolvem
esse texto. O MCP devolve o mesmo texto + dados estruturados, com `is_error` em recusa e falha.

**Como garanti que o Gemini não mudou:** retrato das 7 docstrings e assinaturas antes do refactor,
comparado caractere a caractere depois (idênticas); e os 30 testes de `test_calendar_tools.py`
passaram sem nenhuma asserção alterada — só o alvo do `monkeypatch` mudou de `tools` para
`service`. Por isso deixei o `ruff format` sem tocar as duas docstrings que ele queria reformatar
(`tools.py` segue na baseline de formatação pré-existente de propósito).

**Conserto de brinde (bug latente):** falha da API em criar, criar dia inteiro, reagendar e
listar subia como exceção crua pelo laço do Gemini; agora vira mensagem clara.

**Segurança dos próprios testes:** `tests/conftest.py` troca `get_calendar_service` por uma função
que falha alto em toda a suíte, e o fake entra por cima só onde o teste pede. No Mac o token OAuth
existe: sem isso, um teste que esquecesse o fake criaria evento na agenda real. Conferido com um
teste temporário sem fake (falhou alto, como deve).

**Testes:** +32 (324 no total): `test_calendar_service.py` (dados, códigos de erro, falha da API em
cada operação, título de convite com caractere de controle) e o calendário pelo protocolo MCP em
`test_mcp_server.py` — incluindo as travas da Sessão 1 valendo igual para um cliente MCP que chama
a tool destrutiva direto (§5.3). Mutação: voltar a trava de título para substring derruba 5
testes; tirar o `is_error` do MCP, 9; tirar o `_executar`, 9.

**Erros desta parte (meus):**
7. Na primeira versão, `_executar()` só envolvia o `.execute()`; a falha pode vir já ao montar a
   requisição (o fake levanta no `delete(...)`, a biblioteca real também levanta ali com parâmetro
   inválido). O teste antigo de falha no delete pegou; `_executar` passou a receber a montagem.

**Desvios do plano:** em vez de funções `formatar_*` + `mensagem_de_erro` soltas, uma `Resposta`
por operação (`responder_*`) — mesma meta (uma frase, um lugar), menos peças. O fake do Google
saiu de `test_calendar_tools.py` para o `conftest.py`, compartilhado por três arquivos. A trava
do `conftest` não estava no plano.

**Não validado ao vivo:** tools de calendário do MCP contra o Google real (continua exigindo o
OAuth do Mac); `viking chat` → "o que eu tenho amanhã?" no Mac confirma que o Gemini segue igual.

### 2026-09-26 — Validação ao vivo das Sessões 4 e 3b, no Mac do dono

Saída real colada pelo dono (`git pull` até `df109ad`, `which python` no `.venv`):

- **324 testes passando no Mac**, inclusive `test_contrato_com_o_jev_real` rodando contra o clone
  do Jev de lá (nenhum teste pulado em `test_jev_subprocess_main.py`).
- **Bloqueio:** `viking browser --url https://www.itau.com.br` recusado na hora, sem abrir aba nem
  subprocesso, com a mensagem de `dominio_bloqueado`.
- **Envelope no ambiente real do Jev:** `example.com` concluiu (0 ações, 1,1s). Concluir exige uma
  decisão do modelo, que passa pelo `choose` envolvido — então a proteção encaixou no Jev de
  verdade (senão teria saído `protecao_indisponivel`). Esta era a lacuna que o VPS não cobria.
- **Formato novo:** título, URL e trecho chegaram dentro do bloco `«…»` de conteúdo não confiável.

**Ainda não validado ao vivo:** tools de calendário do MCP contra o Google real; conferência
visual de um evento de dia inteiro no Google Calendar; redação com dado sensível numa página real.

### 2026-09-26 — Skills de trabalho instaladas e continuidade escrita no disco

**Feito.** As 11 skills que o dono trouxe (`skills-globais/`, vindas de outro projeto dele)
foram lidas e instaladas em `.claude/skills/`, sem as 6 menções ao nome do projeto de origem,
porque o repo é público (`gh repo view` → `PUBLIC`). Avaliação de maturidade pela
`software-build` (sondas rodadas nesta data: `324 passed in 3.78s`; `ruff check` limpo; 7 arquivos
pré-existentes fora do `ruff format`; nenhuma leitura de env fora de `config.py`; segredos
confirmados fora do git por `git check-ignore`). Documentos novos: `docs/decisoes.md` (17
decisões com gatilho de reabertura), `docs/erros.md` (meus erros em 6 classes, com índice),
`PROGRESSO.md` (bloco "retomar aqui"), `docs/barra-de-progresso.md` (estado para o dono) e o
bloco "▶️ Começar a próxima sessão por aqui" no `sessoes.md`. `HANDOFF.md` e
`auditoria_codex_1.md` foram para `docs/historico/`, com um README dizendo o que saiu e para onde.

**Decidido.** Todas pelo dono, via perguntas: skills commitadas sem o nome de origem; as quatro
mudanças de documentação; o freio de clique destrutivo vira a Sessão 4b, antes do Gmail; a
verificação automática no GitHub fica na Sessão 7, junto do lockfile. Não mexi em código: 2.860
linhas em `src/`, bem divididas, e a skill só autoriza refatorar com motivo concreto.

**Achado.** O freio de clique (§5.2) estava "para a Sessão 5" só no backlog; a seção da Sessão 5
não o tinha, então ele nunca chegaria lá. Parte das decisões do dono vivia só na memória local do
Claude neste VPS, que o Codex e o Mac não veem. E a frase "Não validado ao vivo" da Sessão 4 no
`sessoes.md` já era falsa desde a validação no Mac; corrigida.

**Erros desta sessão (meus).** Ao criar `docs/erros.md`, o escape bidi citado no item da classe 5
virou o caractere literal — a terceira ocorrência da mesma armadilha, desta vez dentro do texto que
a descreve. A varredura de caracteres de controle antes do commit pegou (1 achado em 37 arquivos);
trocado por script e registrado na classe 5.

**Não verificado.** Versões das dependências instaladas no Mac; status "Testing" do app OAuth.

**Próximo.** Sessão 4b — ver `PROGRESSO.md`.

### 2026-09-26 — Sessão 4b: o navegador não sai, não mexe na conta e não gasta dinheiro sozinho

**Feito.** Freio de cliques que agem sobre a conta (§5.2), encaixado no envelope da Sessão 4:
`choose_protegido` confere a ação que o modelo escolheu **antes** de o Jev executá-la — medido no
clone (`afbee69`): `act()` só executa `next(a for a in page["actions"] if a["id"] == selected)`,
com `selected = decision["choice"]`; não aperta Enter depois de digitar, mas no `select`
dispara `change`, que o site pode usar para enviar — então `click` e `select` são freados. A regra
(`_acoes_sensiveis.py`, stdlib pura) lê três sinais: rótulo normalizado, `href` de logout e o
texto do contêiner para botões genéricos. Recusa = `acao_sensivel`, aba aberta, botão nomeado na
mensagem, custo da decisão recusada contado. `scripts/mutacoes.py` com 16 mutações curadas.
Portões: `444 passed in 4.20s`; `ruff check` limpo; 7 arquivos antigos fora do `ruff format`
(igual antes); mutações `16 · mortas pelo teste esperado: 16` (rodada completa ~40 s, repetida
depois da última mudança na regra).

**Decidido.** Pelo dono: sair, mexer na conta e dinheiro (sem "publicar em seu nome"); para e
avisa; sem liberação até a Sessão 5 — escrito como primeiro item da seção dela. Meu: freio ligado
desde já (D19) e mutações à mão com âncoras conferidas pela suíte (D20).

**Achado.** A primeira rodada de mutação achou um teste fraco da Sessão 1: remover a trava de
título vazio deixava tudo verde, porque a comparação de títulos também recusa — exceto num evento
cujo título é só espaço, que normaliza igual a `""`. Esse caso não tinha teste; tem agora. O
teste de contrato novo foi conferido quebrando o Jev de três jeitos numa cópia (as três caíram).

**Erros desta sessão (meus).** (1) Âncora de mutação escrita de memória (`d` em vez de
`dominio`) — o script recusou antes de rodar; classe 2. (2) Três regras do freio desenhadas pelo
caso típico: `href` por substring barraria `/blog/como-sair-da-divida`; controle virando espaço
deixaria "Sa"+NUL+"ir" escapar; "Excluir" julgado por contexto de dinheiro recusaria apagar a
tarefa "comprar pão". Os dois primeiros pegos na releitura, o terceiro pelo teste de vizinho
legítimo; classe nova 7 em `docs/erros.md`. (3) Escrevi no plano que `select` não envia nada; o
`browser.py` que eu tinha lido dispara `change` — pego na segunda passada ("por onde mais se chega
lá?"); classe 2. (4) Rodei o formatador em `src`/`tests` inteiros e ele reescreveu 5 arquivos
antigos que eu não tinha tocado, inclusive duas docstrings do calendário que o Gemini lê — pego
no `git status`, restaurado pelo `git show HEAD:`; classe nova 8.

**Não verificado.** O freio numa página real, no Mac (roteiro em `PROGRESSO.md`).

**Próximo.** Validar a 4b no Mac; depois a Sessão Gmail.

### 2026-09-26 — Validação ao vivo da Sessão 4b, no Mac do dono

Saída real colada pelo dono (`git pull` até `86dd7e9`, `which python` →
`~/LifeOs/.venv/bin/python`):

- **`444 passed in 7.37s`**, nenhum pulado — inclusive os dois testes de contrato contra o clone
  do Jev de lá.
- **`mutações: 16 · mortas pelo teste esperado: 16`** no Python do Mac.
- **Freio na Chrome real:** página `data:` com `<button>Sair</button>` → `acao_sensivel`,
  "Botão recusado (sair), texto da página: «Sair»", aba aberta. Diálogo "Deseja excluir sua conta"
  com `<button>Excluir</button>` → recusado como **conta** — prova ao vivo da regra do contêiner
  (o rótulo sozinho, "Excluir", passaria).
- **Controle:** `<button>Buscar</button>` → concluído em 0,8 s com 1 ação; o freio não atrapalhou
  o clique comum.

**Ainda não validado ao vivo:** o freio num site real logado (as páginas de teste foram `data:`,
de propósito, para não tocar conta nenhuma).

### 2026-09-26 — Sessão Gmail: o Viking lê a caixa de e-mail (só leitura)

**Feito.** Gmail pela API oficial, só no `viking chat`: buscar (sintaxe do Gmail), ler um e-mail,
não lidos de hoje e um raio-x da caixa (quem manda o quê, quanto fica sem abrir, sinais de
newsletter e da aba Promoções). Login compartilhado com o calendário em `lifeos/google_auth.py`,
com token próprio do Gmail (`gmail.readonly`, permissão 600). O conteúdo passa pela redação das
páginas e vai no bloco de não confiável, agora cópia única em `lifeos/nao_confiavel.py`.
`viking gmail` valida tudo no Mac sem gastar Gemini. Portões: `528 passed`; `ruff check` limpo; 7
arquivos antigos fora do `ruff format`; mutações `26 · mortas pelo teste esperado: 26` na rodada
completa, mais a 27ª (token revogado) reprovada isolada depois do último conserto.

**Decidido.** Pelo dono: só chat, sem MCP; redação igual à das páginas (e-mails e códigos de
verificação visíveis); plano pago do Gemini; app OAuth conferido por ele (produção, externo, só
ele). Ele pediu também **limpar a caixa** — virou a Sessão Gmail 2, separada por decisão dele: só
arquivar, sempre com a lista exata aprovada. Meu: token próprio do Gmail (D24); D13 reavaliado
com o gatilho disparado, mantido.

**Achado.** O `has_scopes()` do `google-auth`, com o token carregado do jeito que o calendário
sempre carregou, compara com os escopos pedidos — daria sempre verdadeiro. Medido lendo a fonte
instalada antes de escrever; a conferência lê o campo `scopes` do arquivo. Conferido também que o
token do calendário tem esse campo, então o calendário não vai pedir login de novo (inferido da
cópia deste VPS; confirmar no Mac). Segunda passada de revisão ("o que a segunda execução
encontra?"): um token revogado no Google ficava no disco e toda tentativa, inclusive `--login`,
renovava o mesmo token morto — beco sem saída que o calendário já tinha desde o protótipo. Agora
a renovação recusada vira login novo, para os dois.

**Erros desta sessão (meus).** (1) O plano apoiava a conferência de escopo em `has_scopes` sem
ler a biblioteca — pego antes do código; classe 2. (2) Uma asserção com `or True` num teste —
pega na releitura; classe 4.

**Não verificado.** Login real (a tela de app não verificado), o formato real das mensagens do
dono contra o fake, a latência e os 429 do raio-x. Roteiro em `PROGRESSO.md`.

**Próximo.** Validar no Mac; depois a Sessão Gmail 2 (limpeza).

### 2026-09-26 — Validação ao vivo da Sessão Gmail, no Mac do dono

Saída real colada pelo dono (primeiro `git pull` falhou por rede e o roteiro seguiu sobre o código
antigo — erro meu de roteiro, classe 1; no segundo, `9841595`):

- **`528 passed in 6.01s`** no Mac.
- **Login:** `✅ Login do Gmail ok (só leitura)`, a conta certa; `google_token_gmail.json` criado
  com `-rw-------`; o token do calendário ficou intocado (mesma data de antes).
- **Não lidos de hoje e raio-x** na caixa real: o formato das mensagens bateu com o do fake
  (remetente, assunto, abas, `List-Unsubscribe`, entidades do `snippet`); o raio-x leu 200 e-mails
  de 91 remetentes em 30 dias e avisou que é piso. A redação não precisou agir nos trechos vistos
  (a chave de API citada num alerta já vinha mascarada pelo remetente).
- **Achado 1 — enchimento invisível:** vários trechos eram só caracteres de enchimento (ZWNJ, CGJ,
  espaço sem quebra) que newsletters põem na prévia. O fake não tinha isso; consertado no mesmo
  dia (trecho e corpo), com teste do caso e mutação.
- **Achado 2 — o app se chama "n8n":** o "Alerta de segurança: você permitiu que o app n8n…" chegou
  no mesmo minuto do token novo: é o nosso login. O app OAuth do Google Cloud usado pelo Viking
  tem esse nome — por isso o dono não o achava como "Viking". Renomear é na tela de marca do app
  (decisão dele).

**`viking chat`, validado em seguida (saída colada pelo dono):** "o que eu tenho amanhã?"
respondeu sem pedir login do calendário; "o que chegou de e-mail hoje?" e "quem mais me manda
e-mail que eu não abro?" chamaram as tools e responderam certo; "esses e-mails eu não abro nunca"
fez o Gemini dizer que não consegue bloquear nem descadastrar — a regra da descrição segurou a
promessa. Custo medido pelo `/custos` por mensagem: de ~2,6 mil a ~14,7 mil tokens (US$ 0,001 a
0,005), crescendo com o histórico da conversa. **Achado:** o Gemini mostrou 5 remetentes e repetiu
"outros 76" — eram 76 além dos 15 mandados; a linha agora diz "além destes 15 … (91 no total)".

**Não medido:** latência do raio-x (a saída não mede tempo).

### 2026-09-26 — Pluggy medido, e Sessão Gmail 2: limpar a caixa com aprovação por código

**Pluggy (medição, sem código).** Pelo MCP de documentação da Pluggy e pelo guia do Meu Pluggy: uso
pessoal é **gratuito** (até 5 conexões do mesmo titular) — responde a pergunta aberta de D5. Com as
credenciais que o dono pôs no `.env`: `/auth` → 200 e o conector MeuPluggy (id 200) disponível;
listar conexões → 403 (recurso desligado), então os IDs saem do Dashboard. A mesma chave alcança
PIX e apagar conexão: a sessão exige cliente só `GET`. Tudo em `docs/fontes/pluggy-open-finance.md`;
sessão escrita no `sessoes.md`, logo depois da Gmail 2 (decisão do dono).

**Gmail 2, feito.** O Gemini só **propõe** (`preparar_limpeza`): a lista exata e um código de 4
dígitos vão direto para o terminal; o dono digita `confirma NNNN`, que o laço do chat trata antes
do modelo; `desfaz NNNN` devolve por 7 dias. Seleção por remetente exato, proteções (estrela,
importante, anexo) na consulta **e** nos metadados, teto 1000, mais antigos primeiro; na
confirmação, só o que foi aprovado e ainda vale. `viking gmail --arquivar/--desfazer` para o Mac.
Portões: `607 passed`; `ruff check` limpo; 7 arquivos antigos fora do `ruff format`; mutações
`41 · mortas pelo teste esperado: 41` (13 novas) na rodada completa, rodada de novo depois das
correções da revisão; as 3 correções têm teste próprio.

**Decidido.** Pelo dono: teto 1000 (D28); seguir com `gmail.modify` sabendo, **medido** no
`gmail.v1.json`, que ele autoriza também enviar e lixeira (D29); Pluggy logo depois da Gmail 2.
Meu: aprovação no laço do chat, não numa tool (D30).

**Achado na revisão.** (1) Primeira passada: um e-mail que falhasse ao ser relido na confirmação
(ex.: 429) seria contado como "mudou desde a lista" — agora aparece como "não pôde ser conferido";
(2) a mensagem de erro do desfazer dizia "o código foi gasto", falso no desfazer; (3) duas chamadas
da tool no mesmo turno se anulam — a descrição pede uma só. Segunda passada ("o que ficou falso?"):
`AGENTS.md`, `gmail-api.md` e `sessoes.md` ainda diziam "só leitura".

**Erros desta sessão (meus).** (1) `\d` do Python casa dígitos Unicode, e eu afirmei que não —
pego pelo próprio teste; classe 2. (2) Texto da tela de consentimento escrito de memória no plano —
pego na releitura, conferido no `gmail.v1.json`; classe 2. (3) Asserção com `or` aceitando dois
caminhos — pega na segunda passada; classe 4, segunda vez.

**Não verificado.** Login novo com `gmail.modify` no Mac; arquivar e desfazer na caixa real;
latência e 429 dos metadados de 1000 e-mails. Roteiro em `PROGRESSO.md`.

### 2026-09-26 — Gmail 2 no Mac: a cota do Gmail estourou, e o conserto

**Medido no Mac (saída colada pelo dono).** `viking gmail --arquivar` num remetente de 207 e-mails:
proposta ok; na confirmação, `Arquivei 0`, "135 não puderam ser conferidos" e "72 NÃO foram
arquivados" com `403 ... Quota exceeded ... 'Units per minute per user'` (`rateLimitExceeded`).
O texto cru do erro trazia o número do projeto OAuth — não copiado para cá. Nada foi arquivado nem
perdido; o código foi gasto.

**Causa.** A documentação de cota do Google (lida depois, não antes — erro meu, classe 3): 6.000
unidades por minuto por usuário, `messages.get` = 20. A proposta leu 207 (≈ 4.100) e a confirmação
releu os mesmos 207 no mesmo minuto: passou de 6.000. O dono apontou o remédio ("tem que ter um
sleep entre elas").

**Feito.** Orçamento de 4.800/min por processo antes de cada chamada; espera crescente (2 → 64 s)
em qualquer recusa de cota, com aviso no terminal; a confirmação só faz buscas (as proteções
continuam em duas camadas, as duas por busca); o erro vira frase sem o corpo do Google. Teto
revisto pelo dono de 1000 para **250** (D28): cerca de 1 minuto de conferência. O fake do Gmail
passou a cobrar a mesma cota num relógio falso, e o caso do Mac (raio-x + 207 no mesmo minuto)
virou teste. Portões: `612 passed`; `ruff check` limpo; baseline 7; mutações
`46 · mortas pelo teste esperado: 46` (5 novas de cota).

### 2026-09-26 — Gmail 2 validada no chat do Mac (e dois defeitos do laço)

**Medido (saída colada pelo dono).** Depois do conserto da cota: no `viking chat`, "qual foi o
último e-mail?" → respondeu; "podemos arquivar [o remetente]" → a espera de cota apareceu uma vez
("pediu calma … em 2 s") e a lista foi impressa no terminal: 71 saem, 2 ficam (importantes), 3
assuntos de exemplo, o código e a validade; o Gemini não repetiu o código. `confirma NNNN` →
`Arquivei 71 e-mail(s)` com o prazo do desfazer, sem passar pelo Gemini. Custo por mensagem:
~3,2 mil a ~6,2 mil tokens (US$ 0,001 a 0,002).

**Defeitos vistos ali.** (1) O dono digitou primeiro "confirma" e depois só o número: o número
foi ao Gemini (classe 7). (2) "sair" logo depois da aprovação virou mensagem ao Gemini, porque a
nota era colada antes da checagem do `sair` (classe 6). Consertados no mesmo dia, com testes que
repetem a sequência do Mac e 3 mutações novas; o Gemini agora é instruído a falar com o dono em
segunda pessoa (tinha dito "o usuário precisa digitar"). Portões: `618 passed`; mutações
`49 · mortas pelo teste esperado: 49`.

**Ainda não visto no Mac:** o `desfaz` e a conferência no Gmail web.

**Mais tarde no mesmo dia (saída colada pelo dono).** Num `viking chat` novo, "desfaz 8768 do
gmail" e "você arquivou - desfaz o código é 8768" foram ao Gemini, que disse não haver função de
desfazer e negou o arquivamento. Consertado: qualquer frase com um número que seja código vivo
(proposta aberta, ou arquivamento dentro dos 7 dias) fica no Viking — com verbo age, sem verbo
ganha a instrução; número que não é código vivo segue para o Gemini. O Gemini passou a saber que
o desfazer existe e que não deve negar arquivamentos. Uma rodada de mutações travou num teste com
sorteio preso (laço infinito); matei só o `pytest` filho, o arquivo voltou (conferido), e o teste
passou a sortear códigos diferentes depois do primeiro. Portões: `631 passed`; mutações
`52 · mortas pelo teste esperado: 52`. **Falta:** o `desfaz` de verdade no Mac.

### 2026-09-26 — Gmail 2 fechada: validada no Mac

**Medido (saída colada pelo dono, `2316f25`).** `631 passed in 11.24s`. No `viking chat`: "desfaz
8768 do gmail" → "Devolvi 71 e-mail(s)", sem chamar o Gemini; "o que era o 8768 você lembra?" →
a instrução, sem chamar o Gemini (código vivo sem verbo); "confirma 8768" → "já foi usado"; busca
pelo remetente → 10 achados; "arquivar e-mails de [remetente]" → a espera de cota apareceu uma vez
e a lista (71 saem, 2 importantes ficam); "confirma 1737" → "Arquivei 71". O Gemini falou em
segunda pessoa e em nenhum momento recebeu um código.

**Observado, sem conserto agora:** "vamos arquivar esses e-mails", logo depois da busca, fez o
Gemini pedir o nome do remetente em vez de entender "esses" — a regra "só o que o usuário disser"
está mais estrita do que precisa; e a instrução para código vivo sem verbo não diz o que o código
foi. Os dois são de texto, não de segurança; anotados no backlog.

### 2026-09-27 — Pluggy: plano B para conectar (`viking financas --conectar`)

**Medido.** Os IDs de `meu.pluggy.ai/connections/...` que o dono mandou (Nubank e Itaú) dão
**404** para as credenciais da aplicação dele: são da aplicação do Meu Pluggy. O dono não achou
nada do MeuPluggy no Dashboard. `GET /connectors/200`: o MeuPluggy é OAuth, sem campos de
credencial. `connect_token` devolve `accessToken` (OpenAPI). O script do widget existe na CDN.

**Feito.** `lifeos/financas/`: cliente da Pluggy que recusa qualquer escrita fora de `/auth` e
`/connect_token` **antes** da rede (a chave alcança PIX), guarda a chave por 110 min e nunca põe
o segredo nem o corpo do erro numa mensagem; `viking financas --conectar` serve a janela oficial
da Pluggy numa página em `127.0.0.1` (caminho aleatório, token escapado dentro do `<script>`),
recebe o ID do `onSuccess`, confere na API e mostra a linha do `.env`; `viking financas` confere
as conexões (banco, estado, contas — sem saldo). Nenhum teste fala com a Pluggy (trava no
`conftest`). Portões: `668 passed`; mutações `58 · mortas pelo teste esperado: 58` (6 novas).

**Erro meu (classe 4).** Um teste de corrida passava por sorte e uma mutação era equivalente —
achados porque a rodada completa discordou da parcial. **Não medido:** o OAuth do widget numa
página em `127.0.0.1`.

**Validado no Mac (2026-09-27, saída colada pelo dono).** Duas rodadas de `viking financas
--conectar`, Nubank e Itaú: o login do Meu Pluggy voltou para a página em `127.0.0.1` (o risco
não medido), e cada uma mostrou o ID, `UPDATED` e as contas. Com os dois IDs no `.env`,
`viking financas` listou as duas conexões: 2 contas correntes e 2 cartões. IDs e nomes de conta
não entram no repo.


### 2026-09-27 — Sessão Pluggy: finanças no chat, só leitura (código pronto; falta o Mac)

**Decidido pelo dono na abertura.** Quatro perguntas (saldo, gastos do período, buscar transação,
fatura); valores e descrições podem ir ao Gemini; consultar toda vez, nada em disco; só no chat.
Viraram D31–D33; as minhas (sentido pela `type`, o que fica fora do gasto, a fatura só com
fatos) são D34 e D35.

**Medido nas conexões do dono (só estrutura e comparações, nenhum valor impresso).** O sinal do
`amount` muda entre conta e cartão; a fatura paga aparece nas duas contas; há 45 parcelas
pendentes até 2027. No meio da sessão, mais quatro coisas, que mudaram o código: vencimento e
fechamento de fatura vêm às `T00:00:00.000Z` (25 de 25) e convertidos cairiam um dia antes; o
`balance` do cartão é igual a limite − disponível (o limite usado, não a fatura); o
`balanceDueDate` é o vencimento da última fatura fechada, já passado; e a última fatura da
Pluggy tinha 33 e 39 dias. Cada compra diz a fatura dela em `creditCardMetadata.billId`.

**Feito.** `financas/service.py` (contas, transações com cursor e período cortado no fuso, gastos,
busca, fatura), `financas/tools.py` (o texto do Gemini, descrição redigida e dentro do bloco de
não confiável, rodapé com a última sincronização e aviso de conexão com erro ou velha), quatro
tools no `viking chat` com argumentos só em texto, e `viking financas --saldo | --gastos |
--buscar | --fatura` com o mesmo texto, sem o Gemini. A fatura não inventa "vence em": mostra a
última fechada, as compras sem fatura depois dela, as parcelas futuras e o limite usado.

**Portões.** `796 passed`; `ruff check` limpo; formatação no baseline de 7; mutações `71 ·
mortas pelo teste esperado: 71` (13 novas de finanças, rodada completa e parcial concordando).

**Erros meus** (em `docs/erros.md`): vencimento tratado como instante sem medir a hora, com um
teste que copiava o erro (classe 3); três falhas da Pluggy falsa — filtrava o lixo antes do
código, cópia rasa que vazou entre testes, e um teste que não conferia o que o nome dizia
(classe 4); o caractere bidi literal pela quarta vez, pego pelo `ruff` (classe 5).

**Não medido:** as respostas no Mac, com o Gemini de verdade e os números conferidos com o app do
banco (C7) — em especial se "compras sem fatura" bate com a fatura aberta no app.

**Primeiro teste no Mac (2026-09-27, saída colada pelo dono).** `797 passed`; `viking financas`,
`--saldo` e `--fatura` responderam, com o aviso de fatura atrasada nos dois cartões (32 e 38
dias). `--gastos` e `--buscar pix` deram `sem resposta da Pluggy (URLError)`, sem o motivo. Os
mesmos dois comandos, com as mesmas conexões, passaram no VPS (10 chamadas cada, todas abaixo de
0,5 s): falha de conexão do lado do Mac, causa não medida. Conserto: leitura (`GET`) com falha
de conexão é tentada mais duas vezes (1 s e 3 s), escrita nunca; a mensagem passa a trazer o
motivo e o número de tentativas. `801 passed`; mutações da Pluggy 5/5 (2 novas).

**Segunda rodada no Mac (2026-09-27).** Com a nova tentativa, `--gastos` e `--buscar pix`
responderam; o dono: "tudo certo". Lendo a saída, o "Pagamento de fatura" do Nubank estava no
gasto, em "Transferências": medido, os 33 do histórico vêm `Transfers`/`OUTROS` (erro meu,
classe 7). Reconhecido agora pela descrição exata; nos dados de setembro, internos 4 → 5 e
gastos contados 17 → 16 (contagens, no VPS). `804 passed`; mutações de finanças 16/16.

**Decisão do dono (2026-09-27): transferência para outra pessoa é gasto, numa linha própria.**
Separadas pela família `05…` da taxonomia da Pluggy (sem boleto, câmbio, mesma instituição e
cartão); de brinde, a família "mesma titularidade" inteira (`04…`, com PIX/TED/dinheiro) passou
a ser interna — antes só a categoria-mãe. Setembro do dono (contagens): 4 transferências, 12
compras e contas em 9 categorias. `807 passed`; mutações de finanças 18/18.

**Terceira rodada no Mac (2026-09-27, `0126535`).** `viking financas --gastos`: o pagamento de
fatura do Nubank saiu do gasto (o total caiu exatamente o valor dele) e entrou nos 5 movimentos
fora do total; as transferências para outras pessoas numa linha própria (4), com 9 categorias
de compra — o mesmo que as contagens do VPS. CLI validada. **Não visto:** as perguntas de
finanças no `viking chat` (o chat abriu nas duas rodadas, nenhuma pergunta colada).

**Chat no Mac (2026-09-27): Sessão Pluggy fechada.** Quatro perguntas no `viking chat`: gastos
(os números do `--gastos`, transferências à parte, sem somar o "fora do total"), fatura (os dois
cartões, com o aviso de conferir no app), "tenho dinheiro para a fatura?" e "não tem a de
setembro?". O dono: "tudo certo". Dois achados de texto: "cartão nubank" não achou o "gold"
(backlog), e o Gemini comparou o saldo com a fatura de **agosto**, já vencida — o texto dizia só
"vencimento". Consertado: "venceu em … — não é a fatura a pagar agora", as compras sem fatura
dizem que juntam a fatura já fechada e ainda não entregue, e a docstring proíbe comparar fatura
vencida com o saldo. A causa da fatura ausente está na documentação da Pluggy (só depois de
vencer, conforme o banco). `808 passed`; mutações de finanças 18/18.

### 2026-09-27 — Sessão 5, commit 1: registro de ações, desfazer e pedidos pelo MCP

**Decidido pelo dono (11 respostas na abertura):** as três partes em dois commits; no chat,
apagar/reagendar sem código ("exagero"), com `desfaz`; pelo MCP, só pedido, aprovado em
`viking aprovar` (1 h); registro por 30 dias, também no chat; liberar clique só de sair e conta,
refazendo só aquele clique (commit 2). Viraram D36 e D37; D30 com gatilho novo.

**Feito.** `confirmacao` com validade e substituição por proposta e número reservado entre ações;
`aprovacoes.py`; `aprovacao_local` para vários tipos (código do MCP digitado no chat aponta o
terminal); `registro.py` com estados feita/falhou/incerta, ligado a calendário, lembretes (novo
`service.concluir`), Gmail e navegador, e uma régua AST que reprova efeito externo sem registro;
"Não sei se apaguei…" na falha ambígua (antes dizia "NÃO apaguei" com o evento apagado — achado
pelo teste); `calendar/service.restaurar` e o `desfaz` sozinho no chat; aviso "Antes do erro, o
Viking já fez…" e a nota ao Gemini no turno seguinte; tool `acoes_recentes`; `viking registro`;
MCP `viking_apagar_evento`/`viking_reagendar_evento` só pedem, com limites, e `viking aprovar`
relê o evento (versão, título, início) antes de agir.

**Portões.** `894 passed`; `ruff check` limpo; formatação no baseline 7 (depois de restaurar dois
trechos); mutações `98 · mortas pelo teste esperado: 98` + 1 da revisão (1/1).

**Erros meus** (em `docs/erros.md`): reserva de código que desarmava "o código velho não aprova a
lista nova" e desfazer ambíguo que recriaria duas vezes (classe 6); prefixo de sessão com `LIKE`
(classe 7); `or` numa asserção pela terceira vez e dublê sem `id`/`end` (classe 4); as mesmas duas
docstrings reformatadas de novo (classe 8).

**Não medido:** restaurar evento pelo `patch status=confirmed`, a mescla do `patch` com `null` no
horário e o fluxo do MCP com um cliente de verdade — no Mac (C9).


### 2026-09-27 — Sessão 5, commit 2: liberar um clique do navegador, uma vez

**Decidido pelo dono (na abertura):** liberar só **sair** e **conta**, **dinheiro nunca**; com
código; refazer **só aquele clique**. Meu (D38): a liberação casa por uma digital (esquema+host,
categoria, rótulo normalizado) feita pelo subprocesso; o Viking reabre a URL **redigida** da recusa
(o plano dizia a bruta — mudei: URL com token ou código de login não vai ao banco nem é reaberta);
objetivo escrito pelo Viking ("clicar no botão «rótulo»", 5 ações, 60 s); sem reproposta.

**Feito.** `_acoes_sensiveis.sinais` julga cada categoria por conta própria ("Sair e pagar" era só
"sair" para o `motivo`) e dinheiro em qualquer lugar do botão veta; `digital`/`ler_liberacao`/
`esquema_host`. `_jev_subprocess`: `--liberar-uma=JSON` conferido antes de navegar (forma,
dinheiro, mesmo site do `--url`), o primeiro clique recusado passa se casar exato (evento
`liberado`), e a liberação se gasta ali; `allow_abbrev=False`. `jev_runner`: `--url=`/`--goal=`
colados, `BrowserResult.acao_sensivel`/`liberavel`/`liberado`. `scripts/pedido_mcp_de_teste.py` para o teste do
MCP no Mac. `browser/liberacao.py`: proposta só
com terminal interativo, código só no terminal, `clicar_aprovado`. Chat (`confirma NNNN`, só o
número, `desfaz` recusa) e `viking browser` (pede o código ali); `--json` não propõe. Registro diz
"clique liberado pelo dono".

**Portões.** `1003 passed` (contratos com o clone do Jev incluídos, zero pulados); `ruff check`
limpo; formatação no baseline 7; `python scripts/mutacoes.py` → saída 0 com 120 mutações (21
novas neste commit).

**Erros meus** (em `docs/erros.md`): script de edição rodado antes de ativar o venv, com um verde
de testes que não tinha nada a ver com a edição, e um heredoc dentro de outro que fez o bash
executar texto como comando, sem estrago (classe 5); nome `executar_aprovado` repetido, que
deixaria ambígua a régua do MCP (classe 6, pega pelo teste).

**Não medido:** a liberação numa Chrome de verdade (o Jev real achando o botão na reexecução) — no
Mac (C9), numa página `data:`.

### 2026-09-27 — Validação ao vivo da Sessão 5, no Mac do dono (e o evento às 15h)

**Medido no Mac (`21ab218`, `1003 passed`):** `viking browser` numa página `data:` com "Sair" →
recusa, 🔐 com código, código digitado → `✅ Cliquei em «Sair», uma vez.`; "Pagar" → recusa sem
proposta; no chat, criar/apagar o "Teste Viking" e `desfaz` → "voltou ao calendário" (o `patch`
de status restaura o mesmo evento — o gatilho da D37 não disparou); "o que você fez hoje?" listou
tudo, com "clique liberado pelo dono"; `scripts/pedido_mcp_de_teste.py` →
`aguardando_aprovacao`, `ainda no calendário: 1`, e o evento só saiu com o código em
`viking aprovar`. A Sessão 5 fecha.

**Achado:** "amanhã às 10h" virou `2026-09-28T10:00:00-08:00` — o Gemini inventou o fuso, e o
evento caiu às 15h de Brasília. Defeito antigo (a docstring dava um exemplo **com** fuso e o
serviço aceitava qualquer um). Consertado no mesmo dia (D39): as tools do Gemini (criar,
reagendar, prazo de lembrete) recusam fuso diferente do do dono, pelo fuso da **data** do
horário; o texto do sistema diz a hora com o fuso; o MCP fica como estava. Os testes do
calendário passaram a fixar Brasília no dublê. 5 mutações novas, 5 mortas; `1015 passed`.

**Não medido:** desfazer um reagendamento e evento com convidados — primeiro passo da Sessão 6.
**Erro meu:** a rodada de mutações do conserto foi com o `timeout` da ferramenta (classe 6,
segunda vez; terminou sem estrago).

### 2026-11-21 — Sessão 14b: a mini-auditoria e a manutenção (no ar; falta o Mac)

**Por quê:** 43 dias sem push. A mini-auditoria (`docs/auditorias/mini-auditoria-2026-11-21.md`,
18:23–18:35Z, só leitura) achou a nuvem verde (13 ✅, 34 ✅), mas com seis problemas:
- 20 vulnerabilidades em 8 pacotes da imagem;
- 2 testes vencidos por data;
- nenhuma auditoria agendada;
- nenhum alerta;
- Seattle no ar, com o dono já em SP;
- o `roles/editor` que o GCP dá à conta padrão do Compute.

**Feito (commits `93413a5` a `b56942f`; D69, D58 item 3 revisto):**
- **O lock inteiro atualizado (D45)**: o pip-audit foi de 20 a 0. O `google-genai` foi de 2.29 a
  3.6.1, uma versão maior, e as notas de versão mudam duas coisas:
  - **A API padrão virou `v1`.** Os dois clientes prendem `v1beta`, o medido no ar.
  - **O cliente HTTP virou o `httpx2`, que confia no repositório do sistema.** A base da imagem
    trazia três raízes emSign que a `certifi` nova tirou. A imagem passou a usar a `certifi` do
    lock (`SSL_CERT_FILE`; o build cai sem ela), e a base subiu de digest. A prova foi feita de
    dentro da imagem: um pedido sem chave ao Gemini deu 403 depois do aperto de mão.
- **As duas bombas de data:**
  - o `T0` do registro, achado pelo CI vermelho;
  - a tarifa do forte que dobra em 2027-01-01, achada rodando a suíte com o relógio adiantado em
    120 dias.

  Os dois testes estão verdes em +0, +120 e +400 dias.
- **O fuso:** o `.env` do VPS está em São Paulo, e o `deploy` agora prova o valor no ar. Antes, só
  o `.env` mudar não chegava ao motor.
- **Dois passos novos no `nuvem.py`:**
  - `editor`, executado com o ok do dono às 21:14Z. Antes, 0 usos da conta em 400 dias.
  - `alertas`: a métrica `viking_agendador_ok`, com o filtro medido no log do Scheduler, e o canal
    de e-mail, às 21:15Z. As políticas nascem depois de a métrica viver a janela de cada uma.
- **O CI toda segunda**, às 12:00Z.
- **O deploy às 21:17Z**, com o ok do dono: motor e finanças em `b56942f`, **36 ✅ e 0 ❌**, o fuso
  `America/Sao_Paulo` no ar, e nenhum minuto do envio de lembretes perdido.

**Medido:** suíte `3183 passed` (o `test_lock` tem 36 casos a menos: são 10 pacotes a menos no
lock). ruff, format, mypy e gitleaks limpos. CI do `b56942f` em `success`.

**Erros meus (`docs/erros.md`):**
- **Classe 8:** o `ruff --fix --select RUF100` apagou 47 `noqa` em 19 arquivos. Olhei só o diff de
  `tests/`, e foi o `ruff check` seguinte que mostrou o resto; restaurado do commit.
- **Classe 4:** as duas datas fixas.

**Falta:**
- **O Mac:** `uv sync` com o `google-genai` 3 no chat local, e a suíte.
- **A política do backup:** só pode nascer depois de ~2026-11-22 22:15Z, com
  `python scripts/nuvem.py --executar alertas`.
- **O repo público:** C8, por decisão do dono.

### 2026-10-09 — Sessão 14 fechada no Mac: os documentos (o dono manda um arquivo por tema, o Viking consulta e cita)

**A abertura** (03:08–03:12Z; tudo igual ao bloco de 02:16Z: `6e01b99`, `3020 passed`, 13 ✅, 34
✅): o lock com dnspython 2.9.0 e fastmcp/fastmcp-slim 4.1.0 (`edb4449`; o `beartype` bifurcado por
versão do Python obrigou a régua de `tests/test_lock.py` a ler nome e versão); os preços relidos
iguais a `custos.TARIFAS`; o `pypdf` medido (1 pacote sem dependências, 101 avisos de PDF
malformado) e o export do Docs lido (Markdown e texto puro). **9 respostas do dono (D68):** `.md`
ou `.txt`, pelo Mac, a 14 inteira, documento nunca vira fato, **busca por tema** escolhido pelo
modelo, até 5 trechos, até 1 MB, esquecer como os fatos com o texto no backup, o mesmo arquivo no
mesmo tema substitui.

**As medições do C1** (ok do dono, só texto inventado, ~US$ 0,047): recall@5 = MRR = 1,000 nos
dois temas; a distância não separa a pergunta de fora (ficou mais perto que várias certas), então
não há limiar de distância e a separação é o tema; o Flash-Lite consultou o tema certo em 6 de 7
perguntas do assunto e em nenhuma de 5 de fora; 5 de 5 respostas citaram o arquivo, e a ordem
plantada num trecho não virou chamada. O dono escolheu o limiar da avaliação fixa (recall@5 = 1,0
e MRR ≥ 0,95) e manteve a regra como medida.

**O que entrou** (D68; plano, checkpoints e medições no `PROGRESSO.md`):
- `documentos/cortes.py` (a régua do arquivo e o corte por parágrafo até 600 caracteres, com o
  caminho dos títulos e as linhas; linear em toda forma), `store.py` (as coleções `documentos` e
  `trechos`; aprender em duas fases, nada pela metade na busca; a consulta confere o documento de
  cada trecho; substituir, esquecer e devolver com a cadeia), `consulta.py` (a tool só de leitura,
  o trecho no bloco de não confiável, a linha 📄 do que ela achou), `servico.py` e `terminal.py`;
- as rotas `/documentos*` (só o `cli@`), `viking documentos`, o `--reindexar` com os trechos, o
  resumo de segunda com os documentos, o backup versão 4 (1 a 3 ainda se leem);
- o índice vetorial composto de `trechos` e as TTLs `documentos.apagar_em`/`trechos.apagar_em` no
  `nuvem.py`, e a fumaça da memória exercendo a consulta dos trechos.
- **O conserto no caminho** (`3dc67a3`): o CI do C0 caiu num teste antigo porque a redação de
  páginas trocava por "[cartão]" um pedaço de ~1 em mil UUIDs no registro; o vizinho era o id do
  Gmail na busca. Os dois consertados, no ar junto.

**No ar, com os oks do dono no chat:** o índice e as TTLs criados às 14:45–14:47Z ("Ok, cria"),
prontos às 14:53Z (13 ✅); o deploy de `56f0807` às 14:53–14:55Z ("Ok, publica quando pronto") →
34 ✅ e 0 ❌, e a leitura de 14:56Z com 0 commits desde.

**O reinício do VPS** (do dono, depois dos portões): nada estava rodando; o bloco de retomada e
o checkpoint `56f0807` levaram o estado pelo compact.

**No Mac (2026-10-09, devolvido às 16:39Z):**
- a suíte: `2732 passed, 468 skipped`;
- o `--aprender` de um `.txt` inventado (1 trecho), a lista, a pergunta do tema citando o arquivo
  com a linha 📄 (~US$ 0,0039: duas chamadas ao modelo e o embedding da pergunta), o "oi" sem 📄
  e sem anotação (~US$ 0,002), e a limpeza ("Nenhum documento ativo").

**Portões:**
- a suíte: `3200 passed`, 0 pulados (emulador exigido);
- ruff, format, mypy, gitleaks, `uv lock --check` e `docker build` verdes;
- mutações: **492 de 492** (as 468 de antes, 3 da redação e 21 dos documentos).

**O resto que o dono aceitou** (D68): dois `--aprender` do mesmo arquivo no mesmo tema ao mesmo
tempo podem marcar um ao outro como trocado; o documento sai da busca e `--desfazer` o devolve.

**Em linguagem simples:** agora você manda um arquivo de texto ao Viking com um assunto
(`viking documentos --aprender arquivo.md --tema treino`), e no chat da nuvem ele consulta só
aquele assunto quando a pergunta é dele, responde citando o arquivo e mostra numa linha própria o
que consultou. O que está escrito num documento nunca vira ordem nem anotação sobre você.

**Erros desta sessão (meus; em `docs/erros.md`):**
- a hora do bloco de retomada escrita antes do `date -u`, duas vezes, pega antes do commit
  (classe 2);
- o histórico com uma chamada de tool montada à mão, sem a `thought_signature` (400; classe 3);
- a contagem de «» do teste da consulta que esquecia o cabeçalho (classe 4);
- três âncoras de mutação quebradas, uma por fase (classe 6), e o vizinho da redação (o id do
  Gmail) achado só depois do conserto do registro (classe 6);
- a regra do cartão, de 2026-09-20, lendo dígitos dentro de um id (classe 7).

### 2026-10-09 — Sessão 13b fechada no Mac: as receitas (o dono ensina, o Viking reusa sem permissão nova)

**A abertura** (2026-10-08, depois do compact; leitura e conferências batendo com o bloco: `16379ea`,
`2892 passed`, 13 ✅, 34 ✅): o lock com google-api-core 2.42.0, google-cloud-firestore 2.34.1 e
pydantic 2.14.0 (`44024ba`, a suíte igual antes e depois); os preços relidos iguais a
`custos.TARIFAS`; **7 respostas do dono (D67):** a receita nasce proposta pelo Viking e só se
guarda com `guarda receita`; roda pelo nome; pode ter passos que enviam, com a aprovação de
sempre; a 13b inteira; no `viking memoria`, marcada; até 8 passos; no resumo de segunda. A soma
delas (um e-mail colado vira proposta) foi mostrada ao dono com o que a fecha: os passos à vista,
o aviso do endereço, o código do envio e o resumo.

**As medições do C1** (oks do dono, só texto inventado, US$ 0,0351 no pior caso): o extrator com o
campo `receita` separou bem as receitas (14 de 14 em JSON válido); a regra do chat que só proibia
deixou o modelo dizer "receita anotada" em 5 de 7 e executar os passos em 1; a que diz o que
responder deu a frase certa em 6 de 7. Lidas as 16 respostas inteiras.

**O que entrou** (D67; plano, checkpoints e medições no `PROGRESSO.md`):
- `memoria/receitas.py` (a coleção `receitas`, sem vetor, só marcas; a proposta morre em 1 dia
  pela TTL) e `regras.recusa_receita` (o filtro próprio: a forma de ordem dos fatos recusaria
  toda receita);
- o extrator propõe a receita na mesma chamada; `na_nuvem` lê `guarda receita` e `roda NOME`
  antes do modelo, manda os nomes no bloco e a regra `_RECEITAS` medida; o `roda` não anota;
- `viking memoria` com 📋 e `--receitas`; esquecer e desfazer nas duas coleções; o resumo de
  segunda e o backup versão 3 com as receitas; a TTL `receitas.apagar_em` e as provas no
  `nuvem.py`;
- a 2ª passada achou o desfazer de uma cadeia de trocas (A→B→C), também nos fatos da 13:
  consertado nos dois (`fa53068`).

**No ar, com os oks do dono no chat:** a TTL criada às 23:46Z ("Ok, cria"); o deploy de
`2c78d8b` às ~00:39Z ("Ok, publica quando pronto") → 34 ✅ e 0 ❌ (00:42Z).

**O reinício do VPS** (pedido do dono, ~23:50Z): a 1ª rodada inteira de mutações morreu no meio
(23:54Z) e deixou `agent.py` com uma mutação e a trava; restaurado do HEAD (o hash conferido), a
trava apagada (o processo dono não existia) e a rodada refeita. Nada chegou a commit.

**No Mac (2026-10-09, 01:07–01:09Z; ainda 08/10 em Seattle):**
- a suíte: `2630 passed, 390 skipped`;
- o roteiro: a proposta 📋 com os passos nas palavras do dono; `guardar receita` guardou; `roda
  checagem de teste` mandou os passos; `viking memoria` e `--receitas`; a limpeza (esquecida,
  "Nenhuma receita guardada"); ~US$ 0,004 por turno;
- a 1ª tentativa do `viking chat --nuvem` deu "a nuvem não respondeu": o log do motor não tem
  pedido nenhum antes das 01:07:21Z (a falha foi do lado do Mac, antes do Cloud Run);
- no ensinar, o modelo listou os lembretes na hora (a leitura medida no C1): o dono escolheu
  "aceitar e vigiar" (D67, com gatilho).

**Portões:**
- a suíte: `3020 passed`, 0 pulados (emulador exigido);
- ruff, format, mypy (53), gitleaks, `uv lock --check` e `docker build` verdes;
- mutações: **468 de 468** (as 451 de antes, 15 das receitas e 2 da cadeia).

**Em linguagem simples:** agora você ensina um procedimento ao Viking uma vez ("quando eu pedir
X, faz isso e aquilo"), ele mostra a receita inteira e só guarda se você digitar `guarda receita`.
Depois, `roda` e o nome fazem tudo de novo, sempre pedindo as mesmas aprovações de antes: uma
receita nunca dá permissão nova.

**Erros desta sessão (meus; em `docs/erros.md`):**
- a hora da TTL escrita de cabeça na mensagem do `2c78d8b` ("~23:31Z"; o certo é 23:46Z), e duas
  horas e uma contagem no `PROGRESSO.md` pegas antes do commit (classe 2);
- dois testes do C3 escritos sobre o que eu supunha (a barreira pega "confirma 4821" antes; as
  tools chegam como funções), caídos na primeira rodada (classe 2);
- o desfazer desenhado para uma troca só, da 13, copiado nas receitas (classe 7);
- fora do catálogo: a 1ª regra das receitas escrita como a regra velha da 13, que só proibia,
  quando a 13 já tinha medido que a que diz o que responder funciona (custou a remedição,
  US$ 0,014).

### 2026-10-08 — Sessão 13 fechada no Mac: a memória de fatos, que aprende sozinha só do dono

**A abertura** (depois do compact; leitura e conferências batendo com o bloco):
- o lock com o platformdirs 4.12.4 e o pycparser 3.1 (`0cae0a7`);
- relidos no dia: o `gemini-embedding-2` (US$ 0,20 por 1M, sem `task_type`, a tarefa no prefixo
  do texto) e a busca vetorial do Firestore (até 2048 dimensões, só `flat`, índice obrigatório);
  medido de graça: o emulador aceita `find_nearest` com filtro, sem índice.
- **8 respostas do dono (D66):** a memória na nuvem, só no chat da nuvem; a 13 com os fatos e o
  resumo, as receitas na 13b (nova; a barra passou a 33); o extrator em toda mensagem; embeddings
  agora; nunca anotar valores das finanças, dados de outras pessoas nem planos com data; o
  esquecer some na hora e apaga em 30 dias; até 8 fatos por resposta; o resumo na segunda às 9h.
- **As medições do C1** (ok do dono, ~US$ 0,002): o extrator custa ~US$ 0,00015 por mensagem, em
  0,6–1,0 s; a resposta do embedding não traz contagem de tokens (o teto cobra pelos bytes); uma
  lista de strings dá um vetor só (erro meu, abaixo); o conjunto de ouro: recall@8 = MRR = 1,000.

**O que entrou** (D66; plano, checkpoints e medições no `PROGRESSO.md`):
- `memoria/`: `regras` (o filtro, com 26 vizinhos legítimos e 43 disfarces), `store` (a coleção
  `memoria`, só se acrescenta, a TTL no esquecido), `vetores` (cada texto num `types.Content`),
  `extrator` (a chamada separada que lê só a `mensagem`), `resumo`, `servico` e `terminal`;
- `na_nuvem`: os 8 parecidos no texto de sistema, no bloco de não confiável; a anotação numa
  thread com cliente próprio; o "esquece isso" antes da barreira; o campo `memoria`;
- o motor: as rotas `/memoria*` (só o `cli@`), o resumo na rodada dos lembretes, a
  `/fumaca/memoria`; o backup versão 2; `viking memoria`;
- `scripts/nuvem.py`: o índice vetorial e a TTL `memoria.apagar_em` (criados com o ok do dono) e as
  provas.

**No ar, com os oks do dono no chat:** o deploy de `a8107d6` → 34 ✅ e 0 ❌ (19:41Z); o de `a964aff`
(os consertos do fechamento) → 34 ✅ e 0 ❌ (20:32Z), com o log limpo nos dois serviços.

**No Mac (2026-10-08):**
- a suíte: `1 failed, 2551 passed, 338 skipped` na primeira (o teste de tempo, abaixo); depois do
  conserto, verde ("funcionou", o dono);
- o roteiro: 3 fatos com o 📝; "esquece isso" sem passar pelo modelo; a lembrança numa conversa
  nova; a troca com "no lugar de"; `viking memoria`, `--todos` e `--semana` com o esperado; a
  limpeza, todos esquecidos;
- ~US$ 0,0018 por mensagem com a anotação e o embedding; o teste, ~US$ 0,009.

**O fechamento achou três coisas, consertadas com o ok do dono:**
- **o 429 do serviço de finanças** (19:05Z): o Cloud Run abortou o pedido sem instância livre
  (`--max-instances=1`, da 11d); o motor repete só o 429, até 2 vezes, no prazo do turno
  (`70da02f`);
- **o teste de tempo que caiu no Mac** (2,09 s contra 2 s, escrito na 4): os três testes de "texto
  gigante" medem o crescimento (4× a entrada, ~4× o tempo; o quadrático dá ~16×), e um teste prova a
  régua dos dois lados (`208c7e0`);
- **o "anotado" do modelo**, contra a regra: medido com frases inventadas (~US$ 0,043), a regra
  velha confirmou em 3 de 8 e a nova em 0 de 7 fatos simples, mas ainda em ~2 de 4 trocas e em 1
  de 3 recusados; a abertura diz "vale só a linha 📝" (`a964aff`; D66).

**Portões:**
- a suíte: `2892 passed`, 0 pulados (emulador exigido);
- ruff, format, mypy (52), gitleaks e `uv lock --check` verdes;
- mutações: 448 de 448 (a rodada inteira deu 446, e as 2 vivas eram verdade, consertadas) mais 3
  de 3 do 429 (451).

**Em linguagem simples:** o Viking da nuvem agora lembra o que você conta sobre você, sem pedir
"sim" toda hora, e avisa cada anotação numa linha própria. Ele só aprende do que você digita:
nada de um e-mail, de uma página ou de uma busca vira lembrança. Dá para esquecer na hora, corrigir
pelo `viking memoria`, e toda segunda chega um resumo do que ele aprendeu.

**Erros desta sessão (meus; em `docs/erros.md`):**
- a lista de textos ao `gemini-embedding-2` sem ler a página (um vetor agregado; classe 3); o
  dono, na hora: "lembra se nao souber algo - pesquisa docs e repo";
- o serviço de finanças com uma instância e nenhuma repetição, desenhado na 11d (classe 3);
- a hora do bloco escrita de cabeça (classe 2);
- três testes que passavam por outro motivo, e o limite fixo de 2 s que dependia da máquina, com
  um controle que eu mesmo errei ao desenhar a régua nova (classe 4);
- três âncoras de mutação, o `conferir` do backup e o nome `desfazer` na régua da D26 (classe 6);
- a régua de palavras da medição do "anotado", que não pegou "mudei" nem "Cadastrado!" (classe 7);
- fora do catálogo: a emenda do `{hoje}` saiu ao contrário do comentário (pega ao reler) e um
  `scripts/nuvem.py --executar` sem o nome do passo (o argparse recusou; nada rodou).

### 2026-10-08 — Sessão 12 fechada no Mac: o agente geral (busca com fontes, Flash-Lite, o forte quando precisa)

**A abertura** (2026-10-07, depois do compact; leitura e conferências batendo com o bloco):
- o lock com o google-auth 2.61.0 e o google-genai 2.29.0 (`15e7dd9`);
- as páginas do Gemini relidas no dia:
  - o 2.5 restrito a quem já usava;
  - o 3.5 Flash-Lite indicado para projeto novo, no mesmo preço;
  - o 3.8 Flash, que dobra em 2027-01-01;
  - a busca dos modelos 3 cobrada por consulta, 5.000 por mês grátis;
  - a combinação busca + tools só em preview, na Interactions API;
  - os termos mandando mostrar a resposta da busca igual, com as sugestões, sem guardar.
- **8 respostas do dono (D65):**
  - o Flash-Lite no dia a dia; o 3.8 Flash como forte, pedido pelo próprio Viking;
  - a busca e o forte só na nuvem;
  - os tetos: US$ 0,30 por dia no forte e 30 buscas por dia;
  - o tom caloroso e direto;
  - a busca mostrada igual, com as fontes à parte.
- **As medições** (ok do dono, ~US$ 0,005):
  - o schema das tools custa +2,8% no Flash-Lite;
  - a busca leva ~2 s, com fontes por redirecionamento;
  - o 3.8 continua a conversa do Flash-Lite, o que permitiu o plano A.

**O que entrou** (D65; plano, checkpoints e medições no `PROGRESSO.md`):
- `custos`:
  - a tarifa do modelo que respondeu e do dia (`TARIFAS`; fora da tabela, a mais cara);
  - o modelo em cada consumo;
  - o gancho que escolhe o modelo da chamada;
  - as cotas do dia (`cotas/AAAA-MM-DD`), fora do backup.
- `turno`: o `gemini-3.5-flash-lite` nos dois chats; o tom novo (o resto do texto de sistema
  igual byte a byte); as seções da busca e do forte.
- `na_nuvem`:
  - `usar_modelo_forte` liga a marca do turno, e as chamadas seguintes do mesmo turno vão ao
    `gemini-3.8-flash` enquanto a cota deixa; acabou no meio, o resto volta ao barato;
  - `SO_NA_NUVEM`;
  - o `/custos` com as cotas do dia.
- `assistant/busca.py`:
  - uma chamada separada, só com o `google_search`, sem as nossas tools nem a conversa;
  - as fontes só do `grounding_metadata`;
  - o dono vê a resposta igual, no campo `busca`;
  - o modelo a recebe no bloco de não confiável.
- **Motor e script:** o `/versao` diz a busca e os modelos; `scripts/nuvem.py` ganhou a prova
  disso, grátis.
- **Dívida achada e consertada:** um teste do backup (11c) que caía entre 00:00 e 01:00 UTC.

**No ar, com os oks do dono no chat:**
- o deploy de `f1b47b0` → 33 ✅ e 0 ❌;
- o de `ed92a0c` (o `/custos`) → 33 ✅ e 0 ❌, com o log limpo nos dois serviços.

**No Mac (2026-10-08):**
- a suíte: `2439 passed, 245 skipped` (2684);
- a pergunta factual: o bloco 🔎 igual, com 3 fontes e as 2 consultas, e o comentário à parte;
- a conta dos voos: o Viking pediu o forte sozinho, e o 💸 mostrou o Flash-Lite e o
  `gemini-3.8-flash` (~US$ 0,0053 no forte);
- a agenda: no Flash-Lite;
- o `viking chat` do Mac: o tom novo, no Flash-Lite;
- o `/custos`: "o modelo forte ~US$ 0,005348 de US$ 0,30 · buscas na web 2 de 30";
- gasto do dia: ~US$ 0,03.

**Portões:**
- a suíte: `2685 passed`, 0 pulados (emulador exigido);
- ruff, format (168), mypy (44), gitleaks e `uv lock --check` verdes;
- mutações: **419 de 419** na rodada inteira, mais 1 de 1 do `/custos` (401 → 420 na sessão).

**Em linguagem simples:** o Viking da nuvem agora busca na internet e mostra a resposta com as
fontes, do jeito que o Google exige. Ele usa um modelo novo e barato no dia a dia e, quando a
pergunta pede mais raciocínio, chama sozinho um modelo mais forte. Cada um tem um limite por dia,
para que um e-mail mal-intencionado não gaste por você. E conversa de um jeito mais caloroso.

**Erros desta sessão (meus; em `docs/erros.md`):**
- o "/custos por modelo" dado por feito sem abrir o `/custos` da nuvem (classe 2);
- um teste que assumia o texto de sistema numa linha só, e o teste do backup da 11c que caía à
  meia-noite UTC (classe 4);
- duas âncoras de mutação quebradas pelas minhas mudanças, pegas pelo teste das âncoras antes da
  rodada (classe 6).

### 2026-10-07 — Sessão 11d fechada no Mac: as finanças no chat da nuvem, por um serviço isolado

**A abertura** (depois do compact; leitura e conferências batendo com o bloco): o lock com o
iniconfig 2.3.1 (`050b46e`); a D51 medida de novo com o ok do dono às 18:46:45Z, igual a
2026-10-06 (403 `PAYMENT_INITIATION_NOT_ALLOWED`; 200 com 0 pedidos); 6 respostas do dono (D64):
serviço isolado, as 4 tools do Mac, o chat do Mac igual, o segredo subido do Mac, as provas
automáticas sem a Pluggy. A leitura do código mostrou que o "só nos GET da lista fechada" do
`sessoes.md` não era verdade (o cliente aceita qualquer GET): o serviço responde 5 perguntas
fechadas com texto pronto.

**O que entrou** (D64; plano, checkpoints e medições no `PROGRESSO.md`):
- `nuvem/financas.py`, o 2º serviço do Cloud Run: a mesma imagem do motor com outro comando, a
  conta `viking-financas@` (a única que lê o segredo `viking-pluggy`), só o `viking-motor@` entra;
  `/responder` (uma das 5 perguntas → o texto do Mac) e `/saude` (sem rede). Na nuvem, a Pluggy só
  aceita o `/auth`.
- `nuvem/identidade.py`: a verificação do token tirada do motor, a mesma para os dois serviços.
- `financas/pergunta.py` (o formato fechado) e `financas/remoto.py` (o motor pergunta, com o token
  do servidor de metadados e dentro do prazo do turno); cada `tools.responder_*` pergunta ao
  serviço no motor. O motor nunca tem a chave: um teste faz `pluggy.cliente` levantar fora do
  serviço.
- O texto de sistema e a abertura do chat da nuvem montados das capacidades (os textos de antes,
  iguais byte a byte; as 8 combinações testadas).
- Motor: `/financas` e `/fumaca/financas` (só o `cli@`), `/versao.financas`; `viking financas
  --nuvem`.
- `scripts/nuvem.py`: o passo `financas`, o segredo `viking-pluggy` subido do `.env` do Mac, o
  deploy do serviço antes do motor, 11 provas do serviço (nenhuma chama a Pluggy) e a
  `prova-financas`. Todo `add-iam-policy-binding` agora espera a propagação de uma conta
  recém-criada (o 1º `--executar financas` caiu nisso).

**No ar, com os oks do dono no chat:** o passo `financas` (a conta, o segredo vazio, a leitura;
13 ✅); o segredo subido do Mac (`viking-pluggy: 1 versão`); o deploy de `dda075f` (os dois
serviços), todas as provas ✅ menos o "log sem erro" do motor, que pegou o 502 da 1ª tentativa
da própria `/fumaca/financas` durante a propagação do `run.invoker` do `motor@` (15 s depois
passou: `credenciais: True, conexoes: 2`); a `prova-financas` às 22:02Z → HTTP 200 em 1,3 s, as
duas conexões `UPDATED`. O `deploy` só-leitura às 22:32:04Z, com o 502 fora da janela de 30 min:
**32 ✅, 0 ❌**, o log limpo nos dois serviços.

**No Mac (2026-10-07):** `2421 passed, 217 skipped` (2638); `viking financas --saldo`, `--gastos`
e `--fatura` contra o mesmo com `--nuvem`: **iguais nos três** (`cmp`); `viking financas --nuvem`
→ as duas conexões; `viking chat --nuvem` abriu com "finanças, só leitura" e respondeu o gasto do
mês e o de ontem pelo serviço (~US$ 0,004 por turno).

**Portões:** a suíte `2638 passed`, 0 pulados (emulador exigido); ruff; format (164); mypy (44);
gitleaks; `docker build` e o contêiner local recusando sem token; mutações **400 de 400** na
rodada inteira e a do conserto do IAM, 1 de 1 (374 → 401 na sessão: 27 novas, e uma reescrita).

**Em linguagem simples:** o chat da nuvem agora responde saldo, gastos, busca e fatura, igual ao
do Mac. A chave da Pluggy, que alcança PIX, fica num serviço separado que só sabe responder essas
perguntas; a parte da nuvem que conversa com o modelo e lê e-mails nunca a vê.

**Erros desta sessão (meus; em `docs/erros.md`):** a "lista fechada de GET" escrita na 11c sem
abrir o cliente (classe 2); o dublê das provas que dava o mesmo token ao `cli@` e ao dono, e uma
exclusão que escondia a prova da `/fumaca/financas` (classe 4); três âncoras de mutação quebradas
pelas minhas mudanças e a conta recém-criada sem esperar o IAM (classe 6); a espera do CI com o
SHA digitado errado, que nunca terminaria (classe 5).

### 2026-10-07 — Sessão 11c fechada no Mac: o backup no Drive que restaura num banco vazio, e a D51 medida

**O que entrou** (D63; plano e medições no `PROGRESSO.md`):
- `backup/`: o arquivo versionado (lembretes no formato da migração, o registro de ações dos 30
  dias, os gastos do teto; contagens e a impressão de cada lembrete, conferidos na leitura); o
  Drive com o escopo `drive.file`, que **só cria, lista e baixa** (uma régua lê o código); a rodada
  da nuvem (`POST /tarefas/backup`, só o `viking-agendador@`, todo dia às 09:00 UTC);
  `viking backup --conferir` (restaura num `viking.db` temporário e compara com a nuvem) e
  `--restaurar ARQUIVO` (o desastre, sem sobrescrever nada); o aviso de 48 h na abertura do chat.
- **Um arquivo novo só quando algo mudou** (resposta do dono no meio do fechamento: "ainda não
  estou usando o Viking ativamente"): a rodada baixa o mais novo do Drive, o lê de volta e só
  sobe outro se o conteúdo mudou, se não há arquivo ou se ele não se lê.
- As recusas sem terminal do Gmail falam com o dono e citam `viking chat --nuvem`.
- **A D51 medida (2026-10-06):** pagamento sem o dono → 403 `PAYMENT_INITIATION_NOT_ALLOWED`;
  todo PIX exige a autorização dele no banco. As finanças na nuvem viraram a **Sessão 11d**.

**No ar, com os oks do dono no chat:**
- o segredo `viking-drive` (vazio, depois com o token subido do Mac);
- dois deploys: `a41cfa9` e `3a38d07`, 19 provas ✅ cada, o 2º com `'drive': True` e `backup: True`;
- a tarefa `viking-backup`, cujo 1º backup foi às 18:03:07Z (HTTP 200 em 5,4 s);
- `python scripts/nuvem.py` → 12 ✅.

**A medição de 24 h do agendador:** 163 leituras e 1.481 gravações do Firestore, 1.491 pedidos 2xx
e 26 4xx (todos das provas do deploy). A conta da D61 tinha posto as ~1,5 mil nas leituras.

**No Mac (2026-10-07):** `2279 passed, 210 skipped` (2489); o login do Drive; o token subiu; `viking
backup` → "conferido em 2026-10-07T18:03:07…"; **`viking backup --conferir` → 7 de 7 lembretes e 8
de 8 ações restaurados num banco vazio, 7 iguais à nuvem, "✅ O backup restaura inteiro e bate com
a nuvem.", saída 0**; `viking chat --nuvem` abriu sem aviso de backup.

**Um defeito achado no Mac e consertado na hora:** com o Gmail e o navegador na nuvem, a abertura
dizia "…ligado lá).  e finanças: `viking chat`." (a lista com um item só). `_em_lista`, dois testes,
uma mutação morta. Não precisa de deploy: é texto do terminal do Mac, e chega com o `git pull`.

**Em linguagem simples:** os seus lembretes, o que o Viking fez e o que ele gastou ganham uma
cópia no seu Drive, conferida todo dia, sem o Mac ligado; e foi provado no seu Mac que essa cópia
volta inteira num banco vazio.

**Erros desta sessão (meus; em `docs/erros.md`):** horários escritos no `PROGRESSO.md` sem olhar o
relógio, antes e depois do compact (classe 2); a conta de leituras da D61 que eram gravações
(classe 3); o teste da abertura sem a combinação que está no ar (classe 4).

### 2026-10-06 — Sessões 10c e 11 fechadas no Mac: o Gmail na nuvem, as mãos e os lembretes com uma fonte só

**O portão e o que subiu** (com os oks do dono no chat, nesta ordem):
- 10c C6: a prova passou (`viking gmail --login` no Mac sem abrir o navegador, depois de
  2026-10-04, com o token de 2026-09-26); o token subiu do Mac (`viking-gmail: 1 versão`).
- 10c C7: o motor `66cf7d9` com os 3 segredos como volume, 17 provas ✅; `prova-chat` "quantos
  e-mails não lidos chegaram hoje?" → HTTP 200 em 6,1 s, 9.969 tokens, ~US$ 0,0034; o log da
  revisão sem a pergunta, a resposta ou um código.
- 11: o passo `agendador` (a API do Cloud Scheduler, o `viking-agendador@`, a tarefa de 1 em 1
  min em `southamerica-east1`, aceita); 4 min depois, `envio_de_lembretes: True`.
- **A prova do lembrete com o Mac fechado:** criado pelo chat da nuvem às 16:59:22Z (09:59
  Seattle) para 17:02:00Z (10:02); o motor enviou às 17:02:02.9Z (Firestore, `enviado`), e o
  e-mail apareceu na caixa às 10:02. Três segundos depois do prazo.
- **A migração de verdade, no Mac:** "✅ Migrado: 5 copiado(s), todos conferidos"; `viking
  lembretes` lista da nuvem; o estado do envio veio junto (o "Testar o Viking" continua
  `enviado` desde 29/09).

**O C9 da 10c no Mac (2026-10-06):** `2207 passed, 173 skipped`; pelo chat da nuvem: os não
lidos, o raio-x, a limpeza de 194 e-mails de um remetente com o código só no quadro do terminal,
`confirma` → arquivados, `desfaz` → de volta, o envio para a própria conta; um "confimar 1616"
com erro de digitação não foi ao modelo; sem terminal, a limpeza recusa antes de criar o código;
no chat local, "confirma o 4821 da nuvem" barrado.

**Um defeito achado no C9 e consertado na hora (`bbcba1a`, no ar):** `echo "o que chegou hoje no
meu e-mail?" | viking chat --nuvem` voltou "🤖 Viking: " calado (3.884 tokens de entrada, 0 de
saída). O núcleo do turno, dos dois chats, devolvia `resposta.text or ""`: uma resposta do Gemini
sem texto virava silêncio e escondia o aviso do que uma tool já tinha feito; o limite de chamadas
de tool do turno caía no mesmo vazio. Agora é `turno.SemResposta`, com o motivo, pelo caminho de
erro (aviso, nota, fora do histórico). 6 testes que caíam antes, 4 mutações mortas, `2386
passed`; o motor `bbcba1a` com as 17 provas ✅; no Mac, a mesma pergunta pelo `echo` respondeu.
**Não medido:** por que o Gemini voltou vazio naquela vez (agora o motivo aparece na tela).

**Em linguagem simples:** o Viking na nuvem lê, arquiva (com o seu código) e manda e-mail; o
lembrete chega por e-mail com o Mac fechado; os lembretes moram num lugar só; e o navegador do
Mac atende o chat da nuvem enquanto o `viking maos` está aberto.

**Erros desta sessão (meus; em `docs/erros.md`):** na 11, um `monkeypatch` dentro de um contexto
que se desfazia (classe 4), mutações em primeiro plano pela terceira sessão seguida (classe 5),
"10 ✅" escrito no bloco sem medir (classe 2), a espera da propagação do IAM só para o `cli@`
(classe 6); na 10c, o teste de corrida que pegava em 1 de 10 (classe 4) e quatro escorregões de
ferramenta (classe 5); hoje, `<o mesmo remetente>` dentro de um comando para colar (classe 1) e o
`prova-chat --mensagem` do plano (classe 2).

**Fica para a 11c (primeiro passo):** medir as leituras do Firestore e os pedidos do Cloud Run
com 24 h de agendador ligado (a partir de 2026-10-07 ~17:00Z), contra a conta da D61 (~1,5 mil
leituras por dia; o gatilho é passar de metade das 50 mil grátis). E o texto da recusa sem
terminal, que o modelo repete como se fosse para ele ("peça ao usuário…"), no próximo deploy.

### 2026-10-06 — o Browser Use Cloud estudado e recusado (D62); o lock da 11

- O lock subiu 19 versões num commit próprio (`53dda98`): `2380 passed` antes e depois, ruff,
  format, mypy e gitleaks limpos, CI `success` pelo SHA.
- O dono saiu da lista de espera do Browser Use Cloud e perguntou se o navegador deveria migrar.
  Pesquisa só de leitura (`docs/fontes/pesquisa-roteiro.md`, seção 2b): a conta liberada é a
  normal; o agente deles não usa o Jev e custa, no dado de produção publicado, ~US$ 0,70–1,64 por
  tarefa; não alcança a Chrome do dono sem subir cookies; os termos dão licença perpétua sobre o
  conteúdo. Os ~7 s anunciados são do Jev local, o mesmo que já roda no Mac.
- **Decidido (D62):** o navegador fica no Mac; pergunta factual vai à busca do Gemini (S12); um
  navegador na nuvem sem login só como terceira rota medida na S12, com o nosso Jev e as nossas
  travas. A 11b ganha um item: conferir as correções do Jev para campos com o mesmo rótulo.

### 2026-09-30 — Sessão 10b fechada no Mac

Saída colada pelo dono:
- **Instalação e testes:** `git pull` até `3a7ce21`; o `uv sync` só reinstalou o `lifeos`;
  `2048 passed, 64 skipped` (2112 no total, e os pulados são as peças da nuvem, que o Mac não
  instala).
- **`viking chat --nuvem`:**
  - "tenho algo para amanha" → nenhum evento em 30/09, com 3.982 tokens e ~US$ 0,0015;
  - o lembrete "teste viking" foi criado com o aviso do e-mail (4.297 tokens);
  - `confirma 1234` → o texto de "ainda não há o que aprovar", sem linha de consumo: não foi ao
    modelo;
  - `/custos` → hoje ~US$ 0,004590. É a soma da `prova-chat` do VPS com os dois turnos do Mac:
    o teto no Firestore é um só;
  - o lembrete foi concluído (7.184 tokens);
  - ao sair, ~US$ 0,007029 no dia.
- **`viking lembretes --nuvem`:** a marca do e-mail, e "Nenhum lembrete pendente".
- **`viking chat` local:** a mesma pergunta respondeu igual, com 9.019 tokens. Na nuvem o turno
  equivalente usou 3.982, porque o modelo recebe só as 11 tools da nuvem.

Barra: 17 de 30, sem parciais.

### 2026-09-30 — Sessão 10b: o chat na nuvem (feita no VPS e no ar; falta o Mac)

Dividida na abertura pelo dono: o Gmail e o código de aprovação pela rede foram para a 10c, que
só abre depois de 2026-10-03 (a prova do token do Gmail). Plano e medições no `PROGRESSO.md` até
o fechamento; decisões na D59.

O que mudou:
- **O chat roda no motor.** `viking chat --nuvem` (Mac) manda a conversa inteira a cada turno
  para `POST /chat`; o motor roda o Gemini com as 11 tools da nuvem (7 da agenda, 3 dos
  lembretes, `acoes_recentes`) e devolve a conversa nova. A nuvem não guarda a conversa. O
  `viking chat` local continua igual: o texto de sistema dele saiu do núcleo novo igual ao de
  antes, byte a byte.
- **Um núcleo do turno** (`assistant/turno.py`) para os dois chats, com o texto de sistema por
  seção, conforme as tools presentes; `SO_NO_MAC` lista as 12 tools que ficam no Mac, com o
  motivo, e um teste exige que toda tool esteja numa das duas listas.
- **O registro de ações no Firestore**, atrás de `registro_interface.Registro`: o mesmo contrato
  nos dois stores (19 testes em cada), ids crescentes (`time_ns` + `create()`), TTL de 30 dias
  em `expira_em` e o corte dos 30 dias também na leitura. `banco.conectar` recusa no modo nuvem.
- **O teto do Gemini**: US$ 10 por mês e US$ 1 por dia, no fuso do dono, conferido antes de cada
  chamada ao modelo (`gastos/AAAA-MM`, comparar e trocar).
- **A barreira de aprovação**: na nuvem, uma linha com cara de aprovação nunca vai ao modelo nem
  entra no histórico; na 10b a resposta é "ainda não há o que aprovar na nuvem".
- **Os segredos** (a chave do Gemini e o token da agenda) no Secret Manager, montados como volume
  e lidos só pelo `config`; o token da agenda renova em memória e o login nunca abre na nuvem.
- **`scripts/nuvem.py`**: os passos `segredos` e `ttl`, os subcomandos `segredo NOME` e
  `prova-chat`, a prova "segredos só como volume" e as fumaças `/fumaca/registro` e
  `/fumaca/segredos`. Dois consertos da segunda vida do script: com uma API nova desligada, a
  lista dizia "criar" para o que existia; e o passo dos índices recriava um índice existente.
- **Desvio declarado (C3):** as rotas do motor ficaram `async`, com o trabalho que bloqueia em
  `run_in_threadpool` (uma rota `def` do Starlette não lê o corpo).

Evidência:
- **C0 (2026-09-30 ~04:10Z, VPS, ok do dono):** 5 turnos reais levaram de 0,9 a 3,0 s, com 2 ou 3
  chamadas ao Gemini, 13.224 tokens e ~US$ 0,0062 no total; o histórico chegou a 7 KB.
- **Infraestrutura (05:17Z):** `python scripts/nuvem.py` → 10 ✅ (índices prontos, TTL `ACTIVE`,
  os dois segredos com 1 versão).
- **Deploy (05:19:42Z–05:20:59Z, `36fcd13`, ok do dono):** 12 provas ✅. Entre elas, a imagem no
  ar é a esperada, os segredos estão só como volume, `/fumaca/registro` responde 200 e
  `/fumaca/segredos` responde `{'gemini': True, 'agenda': True}`. O log não tem erro.
- **Turno real no ar (05:21Z, `prova-chat`, ok do dono):** "o que tenho amanhã na agenda?" →
  `HTTP 200 em 4.9 s`, 3.986 tokens, ~US$ 0,0015. O teto gravou o gasto, e a resposta usou o
  "amanhã" do fuso do dono (30/09; pelo relógio do motor, em UTC, seria 01/10). Nas 28 entradas
  do log desde o deploy, nada da pergunta, da resposta ou do histórico.
- **Portões:** suíte `2112 passed`; `ruff`, formatação e `mypy` limpos; mutações 251/251 mortas pelo teste esperado (05:25–05:41Z).

Divergência na retomada depois do compact: o CI do checkpoint `573d553` falhou num teste da
Sessão 5 que procurava o código falso `7391` dentro dos horários (`…147391`). Não houve
vazamento; o teste agora olha só os campos de texto.

Decisões: D59.

Erros desta sessão (em `docs/erros.md`):
- classe 4:
  - duas mutações não caíram pelo teste que eu dizia (o corte dos 30 dias; o segredo no
    ambiente);
  - o teste instável da Sessão 5;
- classe 5:
  - a emenda do `registro.py` cortou na docstring;
  - uma mutação rodou em primeiro plano;
  - um valor falso com cara de chave foi barrado pelo gitleaks;
- classe 7: o script da nuvem foi desenhado só para a primeira execução.

### 2026-09-30 — Sessão 10 fechada no Mac

Saída colada pelo dono: `git pull` até `736fd1a`; o `uv sync` trouxe as 7 versões do C1;
`1966 passed, 31 skipped` (no VPS, sem o jar do emulador nem o gitleaks no cache, deu os mesmos
1966/31: 19 do contrato no Firestore, 7 do gitleaks, 5 do store do Firestore); `viking gmail
--login` ok sem abrir o navegador (o google-auth-oauthlib 1.5.0 entra; não é a prova dos 7
dias); o `gcloud` já estava instalado; `gcloud auth application-default login` guardou como
projeto de cota **outro projeto do dono**, e `viking lembretes --nuvem` respondeu ("Nenhum
lembrete pendente") porque o cliente troca a cota pela do Viking (`with_quota_project`, com
mutação); `curl` sem token → `403`. Provas no ar de novo em 2026-09-30 03:01Z: 9 ✅.

### 2026-09-29/30 — Sessão 10: o motor na nuvem (feita no VPS; falta o Mac)

O que mudou:
- **Repo privado** (2026-09-29 22:28Z, com o ok do dono) depois do **gitleaks** no CI (histórico
  inteiro, 106 commits limpos) e no commit do VPS; 3 achados antigos eram dados falsos do teste
  da redação, dispensados um por um pela impressão digital.
- **Projeto só do Viking em São Paulo** (o ID fica no `.env`), criado por `scripts/nuvem.py` (8 passos, cada um
  medido; nada muda sem `--executar`). O faturamento bateu no limite de 9 projetos da conta; o
  dono escolheu desligar o do `dbt-project`. Orçamento de 105 BRL (US$ 20 na PTAX de 5,2204).
- **Firestore pelo contrato** do SQLite, no emulador (obrigatório no CI). A reserva é comparar e
  trocar: a transação dava lock timeout com execuções juntas (5 de 10 rodadas; 0 de 40 depois).
- **O motor** (Starlette no Cloud Run, 0 instâncias mínimas): verifica a assinatura, a audience e
  o e-mail do token na primeira instrução de toda rota. **O cliente**: `viking lembretes --nuvem`.
- 1ª execução de verdade: cinco consertos do script, cada um com teste (listar sem projeto, conta
  de faturamento na saída, ID curto, índice além de 300 s, "Cannot find service"); e duas
  descobertas do Cloud Run (a URL da audience está na anotação; a permissão levou <1 min).

Evidência (2026-09-30 00:56Z, `python scripts/nuvem.py deploy`): 9 provas ✅ — imagem no ar =
`b7a0635`; só o `viking-cli@` invoca; sem token → 403 do Google; o token pessoal do dono passou
pelo IAM e o motor devolveu 401; o `viking-cli@` → 200 em `/versao`, `/lembretes` e
`/fumaca/vencidos` (o índice composto funciona na produção); 0 erros no log. `viking lembretes
--nuvem` do VPS, com o login do dono → "Nenhum lembrete pendente". Mutações 228/228. Suíte:
`1997 passed` no VPS.

Decisões: D47 revista (o deploy usa o login do gcloud do VPS, decisão do dono) e D58.

Erros desta sessão (em `docs/erros.md`): a premissa "VPS sem credencial" sem abrir
`~/.config/gcloud` (e o `.env` com as chaves do Gemini e da Pluggy, que o `CLAUDE.md` negava);
a corrida de threads que passava com 7 threads explodindo; a promessa do docstring sem teste; dois
números sem medida; o "não existe" do gcloud pelo caso típico.

### 2026-09-29 — Sessão 9 fechada no Mac

Saída colada pelo dono:
- `1884 passed`, e o `shasum` do `data/viking.db` igual antes e depois da suíte;
- o primeiro `viking lembretes` migrou e criou `viking.db.antes-da-migracao-1` (69.632 bytes, o
  tamanho do banco de antes; o migrado ficou com 81.920);
- a lista saiu sem `#`;
- a limpeza achou 8 de 12 e apagou os 8: um por `pytest` rodado no Mac desde 2026-09-27;
- "me lembra de testar o viking daqui a 2 minutos" virou um lembrete;
- o `--enviar` mandou 1 e listou 3 atrasados; o dono confirmou que o e-mail chegou;
- a 2ª rodada deu 0 enviados e saída `0`;
- o `viking registro --dias 1` tem uma linha do envio e as ações de antes da migração, intactas.

Barra: 15 de 28, sem parciais.

### 2026-09-29 — Sessão 9: fundação de dados (migrations, UUID, envio de lembrete)

**Abertura, conferida contra o disco (04:30 UTC).** HEAD `5d0ace4` = origin, limpo, sem trava,
`1804 passed`, CI `success` pelo SHA inteiro, `uv lock --upgrade --dry-run` sem nada novo. Uma
divergência com o bloco: ao abrir o `data/viking.db` do VPS para medir, 132 lembretes, **todos**
"Pagar conta" concluídos em ≤ 0,014 s: a suíte gravava um no banco real a cada `pytest` desde a
Sessão 5 (o `conftest` isolava `confirmacao` e `registro`, e não o store dos lembretes; erros,
classe 6). No Mac, um por rodada, no banco do dono.

**Respostas do dono:** a checagem de tipos só no que a 9 toca; as tabelas de memória para a S13;
um e-mail por lembrete (assunto = título); só os vencidos das últimas 24 h (os mais velhos
listados); apagar o lixo de teste do Mac com o critério exato; o chat sem o `#12`.

**C1.** `lifeos/banco.py` é o único que abre o SQLite; o `conftest` troca um nome só, por teste,
e a `VIKING_DB_PATH` antes de importar o `lifeos`. Um teste por camada; o hash do
`data/viking.db` igual antes e depois da suíte.

**C2.** `mypy` no lock e no CI, com a lista de arquivos no `pyproject` e um teste que deriva do
código quem importa `banco`. Os 3 erros eram `None` possíveis que viravam objeto em silêncio:
agora erram alto.

**C3, as migrations.** Uma lista só para o arquivo, ledger com checksum; as 1–4 recriam o formato
de `5d0ace4`. Duas medições decidiram o desenho: o `executescript` **comita sozinho** a
transação aberta, e o `backup` pela mesma conexão com `BEGIN IMMEDIATE` **trava para sempre**
(por outra conexão funciona e copia só o comitado). Testes contra um banco no formato antigo com
dados (DDL literal, conferido contra o banco que o próprio código de `5d0ace4` cria): migra sem
perder linha, duas vezes não muda nada, falha no meio deixa o despejo idêntico, 4 processos
juntos, banco mais novo não abre, checksum editado não abre, backup uma vez. A cópia do banco do
VPS migrou com as 133 linhas.

**C4.** Migração 5: lembretes com UUID (reconstrução), colunas da reserva, instantes em UTC de
largura fixa. `reminders/interface.py` e o contrato parametrizado; o contrato achou um defeito de
hoje: concluir de novo mudava a hora. O store só grava instantes; o fuso do dono entra e sai na
borda. Testes de fuso com o dono em Seattle: no VPS em UTC, "14h" passaria por acaso.

**C5.** `viking lembretes [--enviar]`: reserva no banco antes de mandar (4 processos de verdade
mandam cada lembrete uma vez); "pode ter saído" marca `incerto` e não reenvia; recusa e limite
soltam. **Incidente meu:** rodei o `--enviar` no VPS esperando "sem login"; o VPS tem o cliente
OAuth do Google (desde 2026-09-20), o login abriu, o VS Code do dono abriu a aba, ele aprovou, e
um e-mail de teste saiu para a caixa dele. Token do Gmail apagado do VPS por decisão dele; o
`CLAUDE.md` agora diz o que o VPS tem (erros, classe 2).

**C6.** `scripts/limpar_lembretes_de_teste.py` (sem `--aplicar` só conta): na cópia do banco do
VPS achou 132 de 133 (o 133º é o do meu teste vermelho do C1, outro título). 17 mutações novas.
D56 (fundação de dados) e D57 (o que mora onde).

**Erros desta sessão:** o isolamento dos testes da Sessão 5 (classe 6, achado na abertura); o
envio de verdade pelo VPS (classe 2); e a revisão pegou a CLI dizendo "Nada ficou reservado"
quando o login caía no meio com e-mails já enviados.

### 2026-09-29 — Sessão 8b fechada no Mac; as parciais 4 e 3b também

Saída colada pelo dono:
- **e-mail:** "manda pra mim um e-mail apresentando quem você é…" saiu sem código, e "o email
  chegou bem sim - tudo certo" (formatado);
- **CPF (parcial 4):** a Wikipédia em `#Formato` terminou com "🔒 Escondi dos modelos, antes de
  enviar a página: 2 CPF.", o número esperado pela medição com `curl`, e o trecho mostrou `[CPF]`
  nos dois lugares. O Jev concluiu em 0 ações (0,5 s): a contagem veio do primeiro `choose`;
- **3b:** criar pelo MCP ok (dia inteiro), listar e buscar acharam 1 (lista completa), o apagar
  ficou `aguardando_aprovacao`, o `viking aprovar` apagou com o código e o `--conferir` deu 0.

A linha final do `pytest` no Mac não foi colada (a demora que ele citou era a do CI); o código
novo estava no Mac, porque o contador só existe nele. Barra: 14 de 28, sem parciais.

### 2026-09-29 — Sessão 8b: e-mail formatado, agenda paginada, contador de redação (falta o Mac)

**Abertura, conferida contra o disco (00:48 UTC).** HEAD `70f25ab` = origin, limpo, sem trava,
`1688 passed`, CI `success` pelo SHA inteiro, `uv lock --upgrade --dry-run` sem nada novo. Nenhuma
divergência com o bloco de retomada.

**Respostas do dono:** o plano do e-mail formatado confirmado (reabre a D46 no "só texto"); a
linha do Viking em cinza e menor; as validações ao vivo 4 e 3b no roteiro do Mac. No meio da
sessão ele pediu **formulários** ("ele teria que saber meu cpf e etc"): virou a **Sessão 11b**,
depois da 11, com a D55 — cofre local no Mac, só dados pessoais, os modelos veem só apelidos, e
o Viking **só preenche**: quem clica em "Enviar" é ele.

**C1, o e-mail formatado.** `gmail/formato.py` (só stdlib) divide o texto cru em blocos e trechos
e escapa cada trecho antes de escrever as nossas tags; o e-mail sai em `multipart/alternative`
(texto puro sem os `**` + HTML), as duas partes do texto que o dono aprovou. A régua principal
não depende da lista de ataques: tiradas as tags que nós escrevemos (lista à mão no teste), não
sobra `<` no HTML, e as palavras batem com a parte texto. 5 mutações mortas.

**C2, a agenda.** `buscar` e `por_data` liam só a 1ª página (250): agora seguem o
`nextPageToken` até 500 e dizem "há mais" (texto e MCP, `completa`). Achado na 1ª passada de
revisão: a referência do Google diz que uma página pode vir "none at all, even if there are
more events" — o laço contava só eventos e giraria para sempre; o teste novo travou até o
`timeout`, e o conserto é um teto de 10 páginas, que também diz "incompleta".

**C3, o contador de redação.** A saída do Viking é redigida de novo na volta, então um `[CPF]`
no fim não prova que o modelo não viu o número. O envelope agora conta o que escondeu (antes ×
depois, por tipo) e o texto termina com "🔒 Escondi dos modelos…". Medido no clone do Jev: ele
só lê o texto **visível na tela** (`snapshot.js`), e no artigo da Wikipédia o CPF de exemplo está
longe do topo — o roteiro abre direto em `#Formato`, onde aparecem `12345678909` e
`123.456.789-09` (medido pelo `curl` do artigo).

**C4.** `scripts/calendario_mcp_ao_vivo.py`: o roteiro da 3b pelo MCP em memória, sem imprimir ID.

**Fechamento:** `1804 passed`; `ruff` limpo; bateria inteira de mutações `198 · mortas pelo
teste esperado: 198`, `recusadas: 0`.

**Erros meus registrados:**
- classe 3: desenhei a paginação sem ler a referência do `events.list` (a página vazia com mais
  por vir); pego na revisão, antes do commit do fechamento;
- classe 5: um `ruff check` falhou no meio de uma cadeia `&&` e as mutações da agenda não foram
  gravadas — o verde das âncoras que veio depois era das antigas; e criei um arquivo de teste com
  `cat >`, contra o antídoto escrito.

**Não verificado aqui:** o HTML no Gmail do dono; o contador numa página real; a 3b contra o
Google. Tudo isso é o roteiro do Mac.

### 2026-09-28 — Depois da 8: o "eu" confirmado no Mac, o nome de usuário fora do repo, o markdown medido

- **"manda pra mim" no Mac:** o dono testou e saiu direto, sem perguntar o endereço. O 1º passo
  da 8b fechou.
- **Nome de usuário do Mac:** a pedido do dono, saiu das 3 linhas do repo público (`.env.example`
  e duas do diário, trocado por `~` e `<seu-usuario>`). `tests/test_repo_publico.py` reprova um
  `/Users/<nome>` que não seja de exemplo; conferido que cai sem o conserto. O histórico do git
  ainda tem 3 commits com ele; reescrever exigiria force push, e isso fica para o repo privado na
  Sessão 10.
- **E-mail com markdown cru:** a captura de tela do dono mostrou `**negrito**` e listas `- `
  como texto no Gmail, porque o Viking manda só `text/plain`. Medido no VPS: a stdlib monta
  `multipart/alternative` (texto + HTML) sem parte de anexo. O plano, com um conversor nosso que
  escapa tudo antes e só depois formata um subconjunto, está como primeiro passo da 8b em
  `sessoes.md`.

### 2026-09-28 — Sessão 8 fechada no Mac; o "manda pra mim" que perguntava o endereço

**Mac (saída colada pelo dono, horários no fuso dele):**
- `view-source:` do banco e `file:///etc/hosts` recusados sem abrir aba, com o texto novo;
- um e-mail para ele saiu sem código;
- a carta para a noiva:
  - apareceu no quadro "E-mail para aprovar";
  - um pedido de mudança gerou uma versão nova, com outro código (o velho morreu);
  - o código errado (`8306`) não enviou nada; o certo enviou;
- ela recebeu, ele também;
- o registro, pedido dentro do chat, listou as duas linhas, sem código.

O dono disse "tudo certo" para a suíte e o `viking gmail --login` (oauthlib 4), sem colar essas
duas saídas.

**Defeito achado pelo teste:** em "manda pra mim…" o Gemini respondeu "Para qual endereço?" e,
depois de "o meu", disse que precisava do endereço completo. A tool dizia "para o próprio
usuário sai na hora", mas o modelo não tinha como nomear o usuário: é o "uma ausência no contexto"
da skill `integracoes` §4.
- Conserto: `para="eu"` (ou "mim") é a conta do `getProfile`, e a docstring manda usar `eu` sem
  perguntar.
- O endereço do dono continua sem ir ao modelo.
- 7 testes e uma mutação novos; as 9 do envio mortas.
- A conferência ao vivo é o 1º passo da 8b.
- Também saiu a frase que o Gemini repetia torta ("me diga o e-mail novamente").

**Portões depois do conserto:** `1686 passed`; mutações do envio 9/9, status 0.

### 2026-09-28 — Sessão 8: o Viking manda e-mail; o furo do bloqueio fechado (falta o Mac)

**Abertura, conferida contra o disco.** HEAD `7f1145f` = origin, árvore limpa, `1553 passed`, CI
`success` pelo SHA inteiro. Duas divergências com o bloco de retomada:
- **Versões:** o `uv lock --upgrade --dry-run` mostrou 4 atualizações, não 2 (entraram `pyjwt` e
  `sse-starlette`, que vêm do MCP). Na hora do upgrade eram 5: o `google-auth` 2.59.0 saiu às
  21:49Z.
- **Login em "Testing":** o dono já tinha conferido em 2026-09-26 ("em produção, externo, só ele
  de usuário"). O "nunca conferido" que escrevi na revisão estava errado (`docs/erros.md`, classe
  2). O passo do Console saiu do plano; a prova de que o token não vence em 7 dias foi para o 1º
  passo da Sessão 10.

**Respostas do dono:**
- "você" no envio livre é a própria conta do Gmail;
- até 20 por dia;
- a resposta não cita a original;
- a linha visível "Escrito pelo Viking (Assistente AI)", com uma logo "bem depois" (backlog).

Ele também descreveu o teste que quer fazer: um e-mail polido para a noiva, mostrado antes e
enviado só se ele aceitar. O endereço dela não entra no repo, que é público.

**C1, o furo do bloqueio (D8).**
- Teste vermelho primeiro: 17 de 20 disfarces passavam — `view-source:`, `blob:`, `filesystem:`,
  `https:banco`, barra invertida, `%69tau`, largura dupla, hífen invisível, ponto ideográfico.
- O host agora é lido pela regra de URL que o Chrome segue (WHATWG; não medido no Chrome), num
  ponto só (`_redacao`), dos dois lados.
- O endereço inicial só aceita `http`/`https`/`data:`/`about:blank`: `file:` levaria um arquivo
  do Mac aos modelos.
- 11 mutações novas, mortas.

**C2.** `uv lock --upgrade` com 5 pacotes, em commit próprio, com os changelogs lidos; a suíte
passou antes e depois.

**C3–C4, o envio (D46).**
- `gmail/envio.py`: uma regra para e-mail novo e resposta. Todos os destinatários são a conta → sai
  na hora, até 20 em 24 h (janela móvel, sem fuso). Qualquer outro → o e-mail inteiro e o código
  vão só ao terminal, com terminal interativo.
- `service.enviar` é o único `send`, dentro de `registro.acao`; 5xx é `incerta`, sem nova
  tentativa.
- Responder não tem parâmetro de destinatário: `Reply-To`, senão `From`; se quem escreveu foi o
  dono, o `To` dela, como no Gmail. Achado na 1ª passada de revisão: antes disso, responder ao que
  ele mandou ia para ele mesmo.
- Texto com controle, bidi ou invisível é recusado, não limpo. Os emojis com ZWJ passam.
- `X-Viking` em todo envio; lido de volta, vira a etiqueta "[enviado pelo Viking]" dentro do bloco
  de não confiável (D53).
- A régua do `send` mudou de forma: permitido uma vez, em `service.enviar`; lixeira, importar e
  apagar continuam proibidos.
- Achado nos testes: um código que não existe, com um e-mail aberto, recebia o texto da limpeza
  ("digite o código da lista"). Agora a resposta é a da proposta aberta mais recente.

**Portões (2026-09-28, VPS):** `1679 passed`; `ruff check` limpo; formatação zero; mutações
**183/183** mortas pelo teste esperado (17 novas nesta sessão: 9 do bloqueio, 8 do envio).

**Erros meus registrados:**
- classe 2: "Testing nunca conferido";
- classe 5: um hífen invisível escrito direto no plano, e o veredito das mutações cortado por um
  `tail`;
- classe 7: o bloqueio desenhado pelo caso típico.

**Não verificado aqui:**
- o envio de verdade;
- se o Gmail mantém o `From` explícito;
- o `view-source:` no Chrome real;
- o `oauthlib` 4 no login do Mac.

Tudo isso é o teste do dono.

### 2026-09-28 — Roteiro 8–21, e a revisão sênior com pesquisa antes da Sessão 8

**Roteiro (`0cec657`).** Planejado com o dono em várias rodadas de perguntas: Sessões 8–21 em
`sessoes.md` e as decisões D46–D52. Faltou esta entrada no diário naquele commit; entra aqui.

**Revisão sênior + pesquisa (pedido do dono).** Cinco pesquisas na web, com todas as fontes
acessadas em 2026-09-28, estão em `docs/fontes/pesquisa-roteiro.md`: assistentes "Jarvis" e o Jev,
memória de agente, Gemini/Claude/Google, GCP barato e app/Garmin/skills. Cada sessão 8–21 ganhou
"Escolhas de arquitetura previstas" e "Libs/repos a reaproveitar", e a arquitetura-alvo entrou na
§11 do doc principal. As regras e as recusas são a D53.

**Medido.**
- O bloqueio de banco e e-mail deixa passar endereço embrulhado: `blob:`, `view-source:` e
  `filesystem:` de um domínio bloqueado devolvem `None`. É dívida; o conserto é o primeiro passo da
  Sessão 8.
- `EmailMessage` do Python 3.12.3 recusa CR/LF num cabeçalho.
- O secret scanning e o push protection estão ligados no repo (API do GitHub). A documentação diz
  que eles somem num repo privado de conta pessoal.
- `uv lock --upgrade --dry-run`: `oauthlib` 3.3.1 → 4.0.0 (publicada hoje) e `platformdirs` →
  4.12.1. Fica para a abertura da 8, em commit próprio.

**Pesquisado, não medido.**
- Nenhum framework de memória respeita a D48.
- Um "sim" solto é forjável por um documento (ataque publicado contra a memória do Gemini).
- Busca e tools na mesma chamada, só nos modelos 3.x.
- O acesso ao Gemini 2.5 está sendo limitado, e o 3.8 Flash dobra de preço em 2027.
- A nuvem sai quase de graça com o Firestore.
- A API da Garmin é "only for business use".
- O passkey do iPhone aceita o código do aparelho no lugar do Face ID.

**Docs corrigidos:** a §6 da arquitetura dizia "nenhum código de finanças existe"; o README dizia
só Python 3.12 e não listava `gmail/` e `financas/`.

**Perguntas ao dono** (as que tocam decisões dele): o "sim" da memória, quando o repo vira privado,
a credencial do deploy e o plano B da Garmin. Respondidas no mesmo dia:
- memória: primeiro "sim" só como resposta ao Viking; logo depois o dono reabriu a D48 ("tenho medo
  de ter que ficar respondendo sim toda hora"), e agora o Viking aprende sozinho só do que o dono
  escreve, avisando numa linha; de e-mail, página e documento, nunca sozinho;
- o repo privado no começo da 10 (D50);
- nenhuma credencial fixa no VPS (D47);
- o relógio direto pelo Strava, sem pedir à Garmin (D54).

### 2026-09-28 — Sessão 7 fechada: 2º teste no Mac

**Medido no Mac (`069fe2a`).**
- `uv sync --locked --extra dev` terminou ("Prepared 20 packages in 4m 00s"), com 20 trocas de
  versão e nenhuma remoção. O cryptography 50.0.1, compilado antes pelo `pip`, ficou.
- Versões: `cryptography 50.0.1`, `google-genai 2.25.0`, `ruff 0.16.9`, Python 3.13.5; o
  `which python` foi igual antes e depois.
- `1553 passed in 37.35s`. O `--doctor` e o `viking financas` ficaram como antes, e o chat leu a
  agenda de amanhã (login do Google com as bibliotecas novas).
- A contagem de pacotes ficou em 99: meu "esperado" dizia que cairia (erros, classe 2).
- No GitHub, o CI do `069fe2a` passou nos dois Pythons, e os 3 alertas do Dependabot ficaram
  `fixed` sozinhos.

**Portões no fechamento.**
- `1553 passed`, `ruff` limpo, formatação zero, `uv lock --check` ok, `pip-audit` sem falhas.
- Mutações: `162 · mortas pelo teste esperado: 162` na rodada completa da entrega 1; as do CI,
  isoladas, 4/4. Depois dela não houve mudança em `src/`: o `git diff be47ab4 -- src` está vazio.

**Erros meus da sessão** (`docs/erros.md`, classe 2, cinco):
- o plano afirmou que as alternativas tinham todas 1 item;
- um número escrito antes do último caso;
- `no-build` provado num `uv` só;
- "seu Mac já está na 48", uma premissa errada numa pergunta ao dono;
- "a contagem cai".

O maior foi o quarto: uma decisão do dono foi tomada sobre uma premissa que eu não tinha medido, e
teve de ser refeita.

### 2026-09-28 — Sessão 7, teste no Mac: o `uv sync` recusou, e o Mac já tinha o cryptography 50

**Medido no Mac (`23a2a79`).**
- **`uv sync --locked --extra dev` falhou:** "Distribution `lifeos==0.1.0 @ editable+.` can't be
  installed because it is marked as `--no-build`". O uv do Mac é o 0.11.24; o do VPS e o do CI,
  o 0.12.10.
- **O resto rodou no ambiente antigo:** `1158 passed`, `cryptography 50.0.1`, `google-genai
  2.24.0`, Python **3.13.5**.
- O `--doctor` e o `viking financas` ficaram como antes. O chat leu a agenda de amanhã, o que
  testa o login do Google, mas com as bibliotecas antigas.

**O que muda.**
- O `no-build` saiu. No lugar, `tests/test_lock.py` lê o lock e exige wheel de todo pacote para
  Mac Intel (macOS ≤ 13) e Linux x86_64, nos Pythons 3.12 e 3.13.
- As plataformas saem dos marcadores do próprio lock (um pacote só do Windows não conta).
  Resultado: 396 casos. Num lock sem a trava, o teste cai exatamente no `cryptography 50.0.1`
  para Mac, nos dois Pythons.
- O CI passa a rodar nos dois Pythons, com um teste que amarra essa lista à do lock. No VPS, com
  Python 3.13 pelo lock: `1553 passed, 2 skipped`.

**A premissa errada, e a decisão refeita.**
- Eu tinha dito ao dono que o Mac já estava na 48 "sem saber". Estava na 50.0.1: o `dist-info`
  diz `Generator: maturin` e `Tag: cp313-abi3-macosx_10_12_x86_64`, uma compilação local feita
  pelo `pip`, e o Mac tem Rust em `~/.cargo/bin`.
- Com esse dado, o dono escolheu a 50 em todo lugar, e o Mac a compila. A trava `cryptography<49`
  e os 3 `--ignore-vuln` saíram.
- `tests/test_lock.py` ganhou a exceção `COMPILA = {("cryptography", "darwin")}`, que reprova
  sozinha se voltar a existir wheel (conferido: com um pacote que tem wheel na lista, cai).
- `pip-audit` do lock: nenhuma falha. `1553 passed` no VPS, já na 50.0.1 pelo lock. Mutações do
  CI: 4/4, uma delas nova (o scanner ignorando uma falha).

### 2026-09-28 — Sessão 7, entrega 2: versões travadas, CI e alertas de dependência (falta o Mac)

**Lock (`uv.lock`, 103 pacotes).**
- Instalar agora é `uv sync --locked --extra dev`, no Mac, no VPS e no CI. O `.venv` do VPS já
  foi sincronizado: `1158 passed`.
- A venv do `uv` não tem `pip`: a doc passou a `uv pip` (`AGENTS.md`, `CLAUDE.md`, `README.md`).

**O achado do lock: cryptography sem wheel para Mac Intel.**
- A primeira resolução pegou o cryptography 50.0.1, que não publica wheel para Mac Intel: medido
  no PyPI, a partir da 49.0.0 só há wheel arm64. No Mac do dono, o `uv sync` teria de compilar do
  código-fonte, com Rust.
- `required-environments` sozinho não resolveu, porque o código-fonte conta como "compatível".
  Com `no-build = true` o `uv` dividiu o lock em dois (48.0.1 no Mac, 50.0.1 no Linux).
- A saída foi `constraint-dependencies = ["cryptography<49"]`: a mesma versão em toda máquina,
  para o CI testar o que roda no Mac.

**Scanner.**
- O `pip-audit` do lock acusou 3 falhas no 48.0.1: PKCS#7 e o verificador de cadeia X.509.
- Pelo `grep` no que está instalado, nada as chama além do próprio cryptography, e o HTTPS usa o
  `ssl` do Python.
- O dono escolheu 48.0.1 em todo lugar, com os 3 IDs ignorados no CI e escritos na D45.
  `test_a_isencao_acaba_quando_o_cryptography_sair_da_48` reprova quando o lock sair da 48.
- Alertas do Dependabot ligados com o ok do dono (`vulnerability-alerts` → 204), sem PRs
  automáticos.

**CI (`.github/workflows/testes.yml`).**
- A cada push roda testes, `ruff check`, `ruff format --check` e o `pip-audit`.
- Permissão só de leitura, sem nenhum segredo, checkout sem guardar a credencial.
- Actions fixadas por SHA, conferidos por `gh api`: checkout v7.0.1, setup-uv v10.2.0.
- `tests/test_ci_workflow.py` lê o workflow e prende tudo isso, inclusive que o CI rode os
  mesmos `python -m …` do "Comandos" do `AGENTS.md`. 3 mutações novas, isoladas: 3/3.

**Portões.** `1158 passed`; `ruff` limpo; formatação zero; `uv lock --check` ok; mutações: a
rodada completa de 162/162 da entrega 1 (sem mudança em `src/` desde então) + as 3 do CI, isoladas.

**Erros desta entrega** (`docs/erros.md`, classe 2): escrevi `1148 passed` no diário e no bloco
depois de acrescentar um caso, sem recontar; a suíte dizia 1149. Pego ao rodar os portões antes do
commit.

### 2026-09-28 — Sessão 7, entrega 1: formatação sem baseline e três consertos pequenos

Plano aprovado pelo dono (`5dd06a7`, no `PROGRESSO.md`): lock, CI, alertas de dependência,
formatação e os pequenos, em 2 entregas. A checagem de tipos foi medida e foi para o backlog, por
decisão do dono (67 erros em 15 arquivos com o `mypy` 2.3.1; nos ~12 que li, nenhum defeito real).

**Medido antes de construir (C1, 2026-09-28).**
- A suíte num `git archive HEAD`, sem `.env` e sem o clone do Jev: `1116 passed, 2 skipped`. Ela
  não depende das chaves do VPS; os 2 são os contratos com o clone.
- Uma instalação limpa de hoje pega 18 pacotes em versão diferente da venv do VPS (google-genai
  2.25.0 contra 2.24.0, fastmcp, ruff…). É o §15.1 medido.
- `pip-audit`: nenhuma falha conhecida.
- Venv criada pelo `uv` não tem `pip`.

**Formatação (`dd7d4c8`, commit só disso).**
- Os 6 `.py` atrasados foram formatados, nomeados um a um, e os `.md` saíram do `ruff format`: o
  único apontado cita o patch do Jev, e citação fica como veio (D45).
- As descrições das tools que o Gemini lê mudaram só no fim: 3 perderam um `\n    ` final, com as
  palavras idênticas às de `b894956` (comparado pela AST).
- O "de propósito" de 2026-09-20, que deixava duas delas fora do formato, era para provar que
  aquele refactor não mudava o texto. Não era regra que continua valendo.

**google-genai (§15.2).**
- O teste de schema usava a função privada com `VERTEX_AI`, mas o chat fala com a API de
  desenvolvedor. Agora usa `FunctionDeclaration.from_callable_with_api_option(..., "GEMINI_API")`,
  que é o caminho que o SDK percorre com as nossas tools.
- A função pública tem um conversor de reserva, por JSON schema, que aceita quase tudo. O teste
  exige o estrito (`parameters_json_schema is None`) e todos os parâmetros da assinatura. A mutação
  com `tuple[int, str]`, que só a reserva aceita, prova isso.

**Regras das descrições.**
- A de `navegar_e_executar` era uma lista de alternativas: "AÇÃO" bastava sem "nunca uma
  pergunta".
- Agora as 33 regras são obrigatórias, uma por caso, sem `or` na asserção.

**`inicio` na aprovação do MCP.**
- O início guardado no pedido e o relido na aprovação eram comparados como texto. Os dois saem de
  `no_fuso_do_dono`, mas em processos diferentes.
- Com o fuso do dono diferente entre o servidor MCP e o `viking aprovar`, o mesmo instante vinha
  escrito noutro fuso, e o pedido válido era recusado com "o evento mudou".
- Agora é `_mesmo_instante`, e o `_mesmo_horario` do desfazer, que já comparava instantes sobre o
  `start` cru, passou a usar a mesma regra (uma fonte só). Vazio e texto que não é horário nunca
  contam como "o mesmo", nos dois usos.

**Portões.** `1149 passed`; `ruff check` limpo; `ruff format --check .` → zero a formatar;
`python scripts/mutacoes.py` → `162 · mortas pelo teste esperado: 162` (5 novas).

**Erros desta entrega** (`docs/erros.md`, classe 2): escrevi no plano que todas as listas de
alternativas tinham um item, lendo só a linha da asserção; a primeira tinha dois. Pego ao abrir o
dicionário para editar.

### 2026-09-28 — Sessão 6 fechada

O dono autorizou fechar ("pode fechar a sessão") sem a conferência das datas das finanças, porque
não tinha o app do banco à mão; ela é o primeiro passo da Sessão 7 (`sessoes.md`) e a 6 conta como
parcial na barra até lá. Entregue: D40–D44 e a D39 revista. **Atualização (2026-09-28, mais
tarde):** o dono conferiu `viking financas --gastos` contra o app do banco — "tudo certo". A 6 conta
como fechada. Portões no fechamento: `1118 passed`,
`ruff` limpo, baseline 7, mutações 157/157. Erros meus da sessão, em `docs/erros.md`: classes 1, 2
(três, e a maior: presumir Brasília), 4 (duas), 6 (duas) e 7.

### 2026-09-28 — Sessão 6: três fusos medidos, e o dono não está em Brasília

**Medido no Mac (`b52b3b8`, `1102 passed`).** `date +%z` → `-0800` (AKDT); o fuso do Viking →
`AKDT …-08:00`; `VIKING_TIMEZONE` no `.env`: 0; o registro mostra os eventos da agenda com
`-03:00`. O dono disse que **não** está no fuso de Brasília. A hipótese de ontem se confirmou e
cresceu: "10h" foi 10:00 do relógio do Mac, que a agenda (em São Paulo) mostra como 15:00; o Gemini
repetiu "15:00" porque recebia o horário no fuso da agenda. Eu presumia Brasília desde a Sessão 1
(erro meu, classe 2).

**Consertado (D42 revista, D44).** Horário lido da agenda chega no fuso do dono (`_evento_de`);
dia de transação da Pluggy no fuso do banco (Brasília), porque no do dono toda transação sem hora
caía um dia antes do extrato; o aviso de fuso renova o token em silêncio (no Mac ficou mudo: token
vencido) e só aparece quando o Viking adivinhou o fuso, sem sugerir o da agenda. A cidade do dono
não entra no repositório (público).

**YouTube.** Desta vez "abrir o primeiro resultado" concluiu em 5 ações (`done`). O rastro real
(`--json`: passo, tipo, URL, rótulo) virou teste de vizinho legítimo — a regra de volta não pode
cortar uma tarefa que conclui. O loop de 30 não se repetiu ao vivo: o conserto da D43 segue provado
pelo rastro reconstruído, não por uma rodada no Mac.

**Portões.** `1118 passed`; `ruff` limpo; baseline 7; mutações 157/157.

**Conferido no Mac depois (`4d5e48b`).** Com `VIKING_TIMEZONE` no `.env` do dono: "amanhã às 10h"
caiu às 10:00 dele (14:00 na agenda, que está em São Paulo); a reunião das 13:00 da agenda veio às
09:00 na listagem; com a variável vazia só num comando, o aviso de fuso apareceu. Uma listagem
intermediária ainda dizia "14:00" — era o Mac um commit atrás, não o código.

### 2026-09-28 — Sessão 6, teste no Mac: chaves e trava ok; o YouTube em loop e o fuso da máquina

**Medido no Mac (`ba860fa`, `1078 passed`).** `HOME` 1/1 e `GEMINI_API_KEY` 1 → 0 no ambiente do
daemon depois do `pkill`; o `--doctor` mostrou ramo, commit, nada não salvo e o patch presente; o
segundo `--doctor`, com o YouTube rodando, recusou dizendo "pelo terminal (viking browser) desde
15:49 (tarefa: «abrir o primeiro resultado»)". O `desfaz` de um reagendamento voltou o horário
(15:00 → 11:00 → 15:00, confirmado pela busca seguinte).

**Achado 1 — YouTube até o teto de 30 ações.** "Abrir o primeiro resultado" já na busca: clicou o
vídeo na 1ª ação e ficou em vídeo → pesquisar → "lofi" → vídeo, com 3 a 5 ações por volta. O
detector não viu por dois motivos, lidos no rastro e no código do Jev: contava estados, e o Jev
devolve um estado sem ação nova quando a página muda antes do clique (`StalePage`); e o ciclo não
tinha período fixo. Consertado (D43): conta por ação e `_revisitando` corta na 3ª volta à mesma
ação na mesma página — no rastro, na ação 8. O rastro do teste tem a ordem e os rótulos medidos e
as URLs reconstruídas; das oito reconstruções, só as com "lofi" como clique fazem o detector antigo
passar os 30 passos sem ver nada, como no Mac.

**Achado 2 — o evento às 15h de novo.** Criado "às 10:00" (a frase do Gemini), achado às 15:00 pela
busca. Não havia outro "Teste Viking" (o dono conferiu). Hipótese forte: sem `VIKING_TIMEZONE`, o
Viking usa o fuso do relógio do Mac, e ele estaria em -08:00 — um lembrete do Mac de 2026-09-20 saiu
com `…-08:00`, e no VPS, com `TZ=America/Anchorage`, "10:00" vira `10:00-08:00` (15:00 em Brasília)
e a D39 não recusa `-08:00`. Então a D39 partiu de um diagnóstico errado (erro meu, classe 2). **A
medir no Mac.** Feito já (D42): a abertura do chat compara o fuso do Viking com o da agenda do
Google e avisa, sem renovar token nem abrir login.

**Achados rodando a CLI aqui.** O texto de "ocupado" falava com o Gemini ("diga ao usuário…") e
aparecia assim no terminal — ficou neutro; num pipe, o bloco "Jev em …" do `--doctor` saía depois
da saída do harness — `flush` antes; e um teste de finanças com corrida (verde 37 em 40) — `join`.

**Portões.** `1102 passed` antes das últimas docs; `ruff` limpo; baseline 7; mutações 153/153 (7
novas; uma sobreviveu na 1ª rodada e mostrou um teste que passava pelos dois caminhos — refeito,
morta).

### 2026-09-27 — Sessão 6, commit 2: o Jev não recebe as chaves do Viking, e o Viking diz qual Jev roda

**Feito.** `jev_runner.ambiente_do_jev(nonce)`: o Jev, o `--doctor` e o `git` da versão recebem só
uma lista (sistema, `uv`, harness, rede, tela do Linux, o nonce); `GEMINI_*`, `PLUGGY_*`,
`GOOGLE_*`, `VIKING_*`, as chaves do próprio Jev, `VIRTUAL_ENV`, `CONDA_*` e `PYTHON*` ficam de
fora. O `--doctor` monta o `uv run` pelo mesmo trecho da tarefa (`_uv_run`) e passa a mandar o
`--env-file` do Jev. `browser/versao_jev.py`: ramo, commit, mudanças não salvas e o patch
OpenRouter pelo **conteúdo** do `model.py`; o `--doctor` mostra, cada tarefa avisa uma linha no
stderr (o Gemini não vê), e nada disso levanta. D41.

**Medido (VPS, 2026-09-27).** O harness também lê `BROWSER_USE_*` (navegador na nuvem; fica fora)
e monta o socket do daemon com a pasta temporária (`TMPDIR` passa). Com o uv 0.12.10: um
`UV_ENV_FILE` herdado é lido quando não há `--env-file`, e `UV_NO_ENV_FILE` desliga o `.env` do
Jev — os dois viraram exceção dentro de `UV_*`. O clone do Jev daqui: `viking-openrouter`,
`afbee69`, nada fora de commit, patch presente; o `.gitignore` do fork cobre `.env` e `.venv/`.

**Revisão.** 1ª passada (*o que ainda chega ao Jev e ao daemon? quem mais abre subprocesso?*):
achou o `UV_ENV_FILE` e confirmou que os três pontos que abrem o Jev passam pela lista; e um clone
sem `.git` dentro do repo do Viking responderia com o ramo do Viking — `conferir` compara o
`--show-toplevel`. 2ª passada (*o que isto tornou falso?*): no roteiro do Mac, `ps eww` não mostra o
ambiente no macOS e daria "0" por outro motivo; virou `ps -wwE` com `HOME=` como controle.

**Erros meus** (em `docs/erros.md`): o prefixo `UV_` inteiro na lista do plano (classe 7); o
roteiro do C7 medindo antes do `git pull` (classe 1); e a URL sem aspas do commit 1, que o diário
dizia registrada e não estava (classe 1, registrada agora).

**Não medido:** o Jev e o daemon de verdade com o ambiente novo — o `.venv` do clone é do Mac (C7).

### 2026-09-27 — Sessão 6, commit 1: um navegador por vez, e só a saída desta execução vale

**Decidido pelo dono (7 respostas na abertura):** recusar na hora dizendo quem usa, desde quando e
a tarefa (curta, marcada não confiável); o `--doctor` também respeita; allowlist de ambiente; versão
do Jev só avisa; teste adiado só com o reagendamento; os 4 itens em 2 commits. Viram D40 (este
commit) e D41 (o próximo).

**Medido na abertura** (lendo o clone e o `uv` daqui): o ambiente do pai **vence** o `--env-file`;
o daemon do Browser Harness herda o ambiente da primeira tarefa e sobrevive a ela; no caminho do
runner nada escreve no stdout além do `emit`.

**Feito.** `browser/trava.py`: `flock` em `data/navegador.lock`, sem espera, dono escrito no arquivo
(pid, origem, desde, objetivo redigido ≤60), arquivo nunca apagado, `Indisponivel` quando não abre.
`run_jev` e `viking browser --doctor` pegam a trava; `busy` mostra quem usa (neutralizado) e
`trava_indisponivel` recusa navegar. Protocolo: nonce por execução em `VIKING_JEV_NONCE` (ambiente,
não argv), `parse_event(linha, nonce)` exige `schema` 1, nonce, `type` conhecido e `status`/`code`.
O texto do clique aprovado distingue "a tarefa nem começou" de "não achou o botão".

**Portões.** `1047 passed`; `ruff check` limpo; formatação no baseline 7; mutações
`135 · mortas pelo teste esperado: 135` (10 novas) + 1 da revisão.

**Erros meus** (em `docs/erros.md`): um teste que esperava por si mesmo sob a mutação "espera" —
a rodada ficou 1 h parada (classe 6); a trava nova deixava um `OSError` escapar do `run_jev`, pego
na revisão (classe 6); o roteiro do Mac no plano tinha uma URL com `?` sem aspas, pego antes de
entregar (classe 1).

**Não medido:** dois `viking` de verdade disputando o Chrome no Mac (C7).

