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
  (`/Users/luanabreno/LifeOs/x.db`); `VIKING_BROWSER_TIMEOUT_S=nan` derrubou o import com
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
