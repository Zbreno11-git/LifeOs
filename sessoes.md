# Sessões — planejamento de trabalho

Doc vivo para organizar o que vem depois de `docs/historico/auditoria_codex_1.md` (auditoria do
Codex, 2026-09-20). Cada sessão de trabalho aqui cabe em ~1h30: revisão → implementação → teste →
commit → push, no mesmo formato da Sessão 1. O que não coube numa sessão vira o começo da
próxima — nada fica perdido, só adiado.

Como usar: ao abrir uma sessão nova, pega o primeiro item não riscado da fila, confirma escopo e
decisões de produto com o dono se a auditoria deixou isso em aberto (seção 23 dela), implementa,
testa, atualiza `docs/diario-de-bordo.md`, e marca aqui o que ficou feito e o que precisou ser
adiado por tempo.

Adiar algo = escrever a etapa **na seção da sessão que a recebe**, como primeiro passo dela. Um
item que só diz "fica para a sessão N" no backlog, sem estar na seção N, não chega lá (aconteceu
com o freio de clique destrutivo — ver Sessão 4b).

## ▶️ Começar a próxima sessão por aqui

- **Antes dela:** validar a Sessão Gmail (leitura) no Mac — roteiro em `PROGRESSO.md`.
- **Sessão:** Gmail 2 — limpar a caixa (só arquivar, lista aprovada).
- **Primeiro passo:** o da seção da Sessão Gmail 2 abaixo (escopo `gmail.modify`).
- **Ler antes:** `AGENTS.md`, `PROGRESSO.md`, `docs/erros.md`, `docs/fontes/google-calendar-api.md`,
  skills `integracoes` e `seguranca` (conteúdo de e-mail é dado de terceiro).
- **Depende do dono:** sim — a saída do roteiro do Mac, e o raio-x real, que é de onde sai a
  primeira lista de limpeza.

> **Notas de ordem.** 2026-09-26: Sessão 4b criada e posta antes da Sessão Gmail, por decisão do
> dono — o freio de clique era o maior risco aberto e estava sem sessão.

## Sessão 1 — correção, custos e runner (feita em 2026-09-20)

Medi os achados P0/P1 da auditoria antes de corrigir (não tomei o relatório como fato). Entregue:

- **Calendário:** `apagar_evento_por_id` e o novo `reagendar_evento_por_id` exigem igualdade de
  título normalizada (NFC + casefold + espaços colapsados) em vez de substring — fecha o buraco
  onde `titulo_esperado=""` apagava qualquer evento. `listar_eventos_por_data` monta a janela no
  fuso civil configurado (`VIKING_TIMEZONE`, padrão = offset da máquina) e não inclui mais um dia
  extra. `criar_evento_dia_inteiro` usa `end.date` exclusivo (dia seguinte), como a API exige.
- **Custos:** `.env` de preços do Gemini agora é lido de verdade (morava em `custos.py`, que
  importava antes do `load_dotenv` de `config.py`); `thoughts_token_count` e
  `tool_use_prompt_token_count` entram na conta; `instrumentar(client)` contabiliza TODA chamada
  do function-calling automático, não só a última (o SDK reatribui `response` no laço de AFC); o
  custo de um turno aparece mesmo se uma chamada posterior do mesmo turno falhar.
- **Runner do navegador:** estado terminal (`done`/`blocked`) agora vence os guardas de
  limite/loop — concluir exatamente na ação-limite não vira mais `step_budget` por engano;
  `usage` e `kept_open` chegam em todo evento de erro, não só em alguns; um callback de progresso
  que levanta não deixa mais o subprocesso órfão; `Popen` que falha vira `spawn_failed` em vez de
  exceção crua.
- Testes novos: `tests/test_calendar_tools.py` (substituiu `test_calendar_apagar.py`),
  `tests/test_jev_subprocess_main.py` (novo — `main()` de ponta a ponta com `jev_ultrafast` e
  `browser_harness` falsos via `sys.modules`), extensões em `test_custos.py` e
  `test_browser_jev_runner.py`. 158 testes passando, `ruff check` limpo.
- Docs corrigidos: `browser-harness.md` (não somos mais cliente MCP), `google-calendar-api.md`
  (delete/reagendar são por ID, não por termo), `.gitignore` (origin do Jev é o fork pessoal),
  `README.md`/`AGENTS.md` (`python -m pip`/`python -m pytest`), comentário do future-import em
  `mcp_server/server.py` (testei ao vivo: FastMCP tolera `from __future__ import annotations`,
  diferente do google-genai — a regra antiga citava o motivo errado).

Decisões do dono que valem para as sessões seguintes: fuso vem de `VIKING_TIMEZONE` (padrão =
fuso da máquina, sem tratar DST); exclusão por igualdade normalizada, sem token de confirmação em
duas fases por enquanto; a Chrome pessoal continua sendo a que o Viking dirige — privacidade do
navegador é decisão adiada, não recusada.

## Sessão 2 — config previsível + lembretes com instante correto (feita em 2026-09-20)

Entregue:

- §9.1: `config._path_env()` ancora caminho relativo de env em `REPO_ROOT`, não no `cwd` — medido
  antes e depois (`VIKING_DB_PATH=./x.db` de `/tmp` apontava pra `/tmp/x.db`, agora aponta pra
  dentro do repo). Achado extra na investigação: `expanduser()` precisa rodar antes do join com
  `REPO_ROOT`, senão `~` vira caractere literal no caminho — registrado em `AGENTS.md`.
- §9.2: `config._float_env()`/`_int_env()` substituem `float()`/`int()` crus nas 4 variáveis
  numéricas — mensagem de erro cita a variável, e NaN/infinito/valores não-positivos são
  recusados. Achado extra: `float("nan")`/`float("inf")` não levantam erro no Python puro, e um
  timeout `nan` desliga silenciosamente o próprio deadline do navegador (comparação com NaN nunca
  é verdadeira) — registrado em `AGENTS.md`.
- `.env.example` agora documenta `VIKING_DB_PATH`, `VIKING_BROWSER_MAX_ACOES` e os preços do
  Gemini.
- §12.1: `due_at` é normalizado para UTC na escrita (`reminders/store.py`) e convertido de volta
  ao `TIMEZONE` configurado na leitura — fecha a ordenação por texto que misturava fusos. Migração
  automática e idempotente via `PRAGMA user_version`, sem comando manual. §12.2: efeito colateral
  bom — lembrete sem hora agora vira meia-noite no fuso configurado, não mais meia-noite ingênua.
- Índice em `due_at` adicionado (efeito prático quase nulo no volume de uma pessoa só, incluído
  porque já estava no escopo).
- Testes: `tests/test_config.py` novo (18 testes); `tests/test_reminders_store.py` +6 testes.
  182 testes passando, `ruff check` limpo.

## Sessão 3 — paridade MCP e resultados estruturados (feita em 2026-09-20, escopo: só lembretes)

Escopo reduzido a lembretes por decisão do dono (`AskUserQuestion`), confirmada antes de codar —
calendário compartilha código com o Gemini e não tem objeto de domínio no meio, mais arriscado de
mexer no tempo de uma sessão. Vira Sessão 3b. Entregue:

- §12.5: novo `reminders/service.py` (`criar_lembrete()`, exceção `QuandoInvalido`) — serviço único
  usado por `assistant/agent.py` e `mcp_server/server.py`, fechando a divergência (`quando` agora
  funciona nos dois lados).
- §14 (parcial, só lembretes): as 3 tools de lembrete do MCP devolvem
  `fastmcp.tools.ToolResult(content=..., structured_content=...)` — texto humano inalterado + dict
  estável (id, título, prazo etc.). `quando` inválido e ID inexistente usam `is_error=True`
  (decisão do dono: erro estruturado de verdade, não só aviso em texto).
- Primeiro teste chamando o MCP pelo protocolo de verdade: `fastmcp.Client(mcp)` em memória (sem
  stdio/subprocesso), sem precisar de `pytest-asyncio`. Achado registrado em `AGENTS.md` e
  `docs/fontes/fastmcp.md` (novo): `ToolResult(is_error=True)` faz `Client.call_tool()` levantar
  `ToolError` por padrão.
- Teste do future-import dos dois lados: adiado para o backlog (não há bug real hoje — conferido).
- Testes novos: `tests/test_reminders_service.py`, `tests/test_mcp_server.py`. 195 testes passando,
  `ruff check` limpo.

## Sessão 3b — MCP: calendário estruturado (feita em 2026-09-26)

- `calendar/service.py` (novo): lógica e travas do calendário com erros de domínio tipados
  (`codigo` + `dados`); `calendar/tools.py` virou adaptador de texto (`responder_*` →
  `Resposta`), com as 7 docstrings/assinaturas do Gemini idênticas às de antes.
- As 7 tools de calendário do MCP devolvem `ToolResult` (mesmo texto + dados estruturados);
  travas e falhas da API viram `is_error`. Conserto de brinde: falha da API em criar, reagendar e
  listar agora vira mensagem clara em vez de exceção crua.
- Testes: `test_calendar_service.py` (novo), calendário pelo protocolo MCP em `test_mcp_server.py`
  (fecha "tools de calendário do MCP nunca exercitadas"), e `tests/conftest.py` com o fake
  compartilhado + trava que impede qualquer teste de tocar o Google de verdade.
- Ficou para decidir: um `output_schema` formal (hoje `ToolResult` genérico não anuncia schema —
  ver `docs/fontes/fastmcp.md`).

## Sessão 4 — privacidade e egress do navegador (feita em 2026-09-26)

Decisões do dono: banco + e-mail bloqueados por padrão; e-mails na página não são redigidos;
proteger também o caminho do OpenRouter (feito sem editar o fork). Entregue:

- `browser/_redacao.py` (stdlib pura, cópia única da regra, usada dos dois lados do subprocesso):
  CPF/CNPJ/cartão só com dígito verificador (telefone não vira CPF), SSN, tokens por prefixo,
  chave privada, parâmetros sensíveis de URL (query e fragmento), texto digitado em campo sensível,
  limpeza de C0/C1/bidi.
- Caminho OpenRouter: `_jev_subprocess.instalar_protecao()` envolve `jev_ultrafast.agent.choose`
  e `field_context` — página redigida e domínio bloqueado recusado **antes** de qualquer chamada
  remota, inclusive redirecionamento na página inicial. Fecha em falha (`protecao_indisponivel`).
- Caminho Gemini/terminal/`--json`: `jev_runner._higienizar()` como ponto único em `result_from`;
  `imprimir_progresso` limpo; `formatar()` põe título, URL, rótulos e trecho num único bloco
  `«…»` não confiável e neutraliza `«»` vindos da página (antes a página fechava o bloco).
- Bloqueio de domínio: preflight em `run_jev` (nem abre aba) + `--bloquear` no subprocesso;
  `VIKING_BROWSER_BLOQUEADOS`/`VIKING_BROWSER_LIBERADOS`.
- Testes: `test_redacao.py` (unitário + adversarial + ReDoS), `test_browser_seguranca.py`
  (integração), envelope e contrato com o Jev real em `test_jev_subprocess_main.py`. Cada teste de
  segurança conferido por mutação (tirar a proteção faz o teste certo falhar).

Validado no Mac do dono em 2026-09-26 (saída colada por ele): 324 testes, inclusive o de contrato
com o clone do Jev; Itaú recusado sem abrir aba; `example.com` concluído passando pelo envelope
real. Ainda não validado ao vivo: redação numa página real com CPF/cartão/token visível.

## Sessão 4b — freio de cliques que agem sobre a conta + mutações curadas (feita em 2026-09-26)

Decisões do dono: recusar **sair**, **mexer na conta** e **dinheiro** ("publicar em seu nome"
ficou de fora); a tarefa para e avisa; nenhuma liberação até a Sessão 5. Entregue:

- `browser/_acoes_sensiveis.py` (stdlib pura): rótulo normalizado contra disfarce, `href` de
  logout por trecho inteiro, texto do contêiner para botões genéricos ("Excluir", "Confirmar").
- Freio no envelope (`choose_protegido`): confere a decisão **antes** de o Jev executá-la; recusa
  = `acao_sensivel`, aba aberta, botão nomeado, custo da decisão recusada contado. Formato do Jev
  diferente → `protecao_indisponivel`. Frase nova na tool do Gemini para ele nem tentar.
- `scripts/mutacoes.py`: 16 mutações curadas (calendário, MCP, bloqueio, envelope, freio,
  delimitador, redação, timeout); todas mortas pelo teste esperado. A primeira rodada achou um
  teste fraco da Sessão 1 (título vazio contra evento de título em branco) — teste novo.
  `tests/test_mutacoes_ancoras.py` reprova no mesmo dia uma âncora que apodreceu.
- `select` também é freado: o Jev dispara `change` ao escolher a opção, e o site pode enviar
  nesse evento (achado na segunda passada de revisão).
- Contrato novo com o Jev real: `agent.py` executa só `decision["choice"]`; `guard` do
  `snapshot.js` com `href`/contêiner nas posições 12/13. Conferido que cai em 3 quebras.

Validado no Mac do dono em 2026-09-26: 444 testes, 16/16 mutações, "Sair" e o "Excluir" de um
diálogo de excluir conta recusados na Chrome real, "Buscar" concluído. Não testado num site real
logado (as páginas de teste foram `data:` de propósito).

## Sessão Gmail — leitura via API (feita em 2026-09-26)

Decisões do dono (2026-09-26): só no `viking chat`, não pelo MCP (sem autenticação ainda);
redação igual à das páginas (CPF/CNPJ/cartão/chaves/links com token somem; e-mails e códigos de
verificação ficam); ferramentas buscar, ler, não lidos de hoje e um raio-x da caixa que **só lê**;
plano do Gemini é o pago. App OAuth conferido pelo dono: **em produção, externo, só ele de
usuário** — o login não vence em 7 dias; o Gmail é escopo restrito, então o login mostra "app não
verificado" (esperado, não bloqueia). Entregue:

- `lifeos/google_auth.py`: login compartilhado com o calendário, token próprio do Gmail (600),
  escopo conferido no arquivo do token e permissão desmarcada falhando alto.
- `lifeos/gmail/`: buscar, ler, não lidos de hoje e raio-x (lotes, teto de 200 = piso, falhas
  contadas); 4 tools no chat, nenhuma no MCP; `viking gmail --login/--buscar/--ler/--raio-x`.
- `lifeos/nao_confiavel.py`: o delimitador virou cópia única (navegador e Gmail).
- 27 mutações curadas (11 novas: Gmail e login), todas mortas.
- Login revogado no Google agora vira login novo — antes, calendário incluso, o token morto
  ficava no disco e só apagando o arquivo à mão (achado na segunda passada de revisão).

Validado no Mac do dono em 2026-09-26: 528 testes, login real (token 600), não lidos e raio-x
na caixa real (formato bateu com o fake; achado e consertado o enchimento invisível das prévias).
Ainda não: as perguntas no `viking chat` e a latência do raio-x.

## Sessão Gmail 2 — limpar a caixa (próxima depois da leitura)

Pedida pelo dono em 2026-09-26 ("recebo anúncio e jornal que não abro nunca"); separada da
leitura por decisão dele, para o Viking nunca ter mais permissão do que usa.

- **Primeiro passo:** trocar o escopo do login do Gmail de `gmail.readonly` para `gmail.modify`
  (o dono refaz o login uma vez no Mac).
- **Ação:** só **arquivar** (tirar da caixa de entrada; continua em "Todos os e-mails"). Lixeira,
  marcar como lido e descadastrar ficaram de fora por decisão do dono.
- **Aprovação:** o Viking mostra a lista exata (ex.: "47 e-mails de 6 remetentes", a partir do
  raio-x) e só arquiva depois do ok do dono, **naquela lista**; e-mail que chegar depois não entra
  sem nova aprovação. É o primeiro uso real da confirmação em duas etapas (Sessão 5) — desenhar
  para ser reaproveitado lá.
- **Base medida (raio-x real, 2026-09-26):** 200 e-mails (piso) de 91 remetentes nos últimos 30
  dias; nos 15 maiores, praticamente tudo sem abrir, e a maioria com sinal de newsletter. Nomes de
  remetente não entram neste repo (é público).

## Sessão 5 — confirmação mecânica

- **Primeiro passo (adiado da 4b por decisão do dono, 2026-09-26):** a liberação do freio de
  cliques (`_acoes_sensiveis`) passa por esta mesma confirmação — o dono aprova **aquele** clique
  (site, botão, categoria), uma vez; não existe chave que desligue uma categoria inteira.
- §3.5/§5: o fluxo de confirmação em duas fases que ficou de fora da Sessão 1 —
  `preparar_exclusao(event_id)` devolve um token curto ligado a ID+título+data+expiração,
  `confirmar_exclusao(token)` consome uma vez. Valendo igual para Gemini e MCP.
- §7: idempotency key por intenção mutável + log de auditoria local (o que foi pedido, o que foi
  confirmado, o que rodou, o resultado) — cobre o caso de uma tool funcionar e a chamada seguinte
  ao Gemini falhar, hoje sem rastro de que a mutação já aconteceu.

## Sessão 6 — runner em concorrência

- §10.7: lock hoje é só `threading.Lock` (intraprocesso) — dois `viking` separados disputam o
  mesmo daemon/Chrome. Lock em arquivo, com timeout de aquisição e mensagem de quem é o dono.
- §10.10: `parse_event` aceita qualquer dict com `"type"` no stdout — um schema mais estrito (ou
  canal dedicado) evita falso terminal se alguma dependência imprimir JSON parecido.
- §11.1: o subprocesso do Jev herda todo o ambiente do Viking, inclusive `GEMINI_API_KEY` — trocar
  por um ambiente allowlisted (só o que o Jev precisa).
- §11.2: nada confere se o clone do Jev está no commit/branch esperado com o patch OpenRouter —
  `viking browser --doctor` podia mostrar branch/commit/dirty status.

## Sessão 7 — manutenção

- §15.1: sem lockfile no projeto principal (`uv.lock` ou equivalente).
- §15.3: sem CI, sem scanner de dependências, sem type checking.
- §15.4: `ruff format --check` ainda aponta arquivos pré-existentes (de antes da auditoria) —
  eram 10 na auditoria, 7 em 2026-09-26 (`python -m ruff format --check .`); cada sessão formata
  só os arquivos que já está editando, então o número cai aos poucos.
- §15.2: `test_assistant_tools.py` usa `_automatic_function_calling_util`, API privada do
  google-genai — acoplamento intencional, mas vale um teste público adicional que não dependa
  disso.

## Só se o Bosgame voltar (trilha de hardware reativada)

- §10.1: `jev_runner._matar()` não mata a árvore de processos no Windows (só
  `terminate()`/`kill()`, sem `CTRL_BREAK_EVENT`/Job Object). Não vale investir sem o Bosgame
  ativo — ver `AGENTS.md`, "Não sugerir de novo".
- §16: trilha de hardware arquivada — caminho padrão errado em `serial_mcp_bridge.py`
  (`parents[2]` aponta para `archive/windows-mcp`, deveria ser `parents[3]` ou config explícita) e
  docs que afirmam sucesso não comprovado no Bosgame.

## Backlog sem sessão marcada

Paginação e eventos recorrentes no calendário (§4.5); notas recuperáveis/buscáveis, não só
criáveis (§12.4); migrations de schema formais (§12.6); decidir se o Viking é só-checkout ou
pacote instalável de verdade (§9.3); Pluggy (finanças); RAG/busca semântica sobre notas e
calendário; teste preventivo para o caso de uma função virar tool do Gemini e do MCP ao mesmo
tempo (armadilha do future-import) — sem bug real hoje (conferido na Sessão 3), só rede de
segurança para um cenário hipotético. Residuais da Sessão 4: o objetivo, os rótulos/valores
de campos e o histórico de ações ainda vão ao OpenRouter sem redação (ver
`docs/fontes/jev-typesafe.md`, "Egress e redação"); domínio em punycode/IDN não é normalizado;
o clique destrutivo num site não bloqueado (§5.2) foi feito na Sessão 4b; ficou de fora, por
decisão do dono, "publicar em seu nome" (postar, enviar mensagem).
