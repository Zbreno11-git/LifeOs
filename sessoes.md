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

- **Sessão:** nenhuma numerada na fila — a 7 (manutenção) fechou no Mac em 2026-09-28. A próxima
  sai do "Backlog sem sessão marcada" abaixo (ex.: checagem de tipos, com o número medido;
  paginação e recorrência no calendário; notas buscáveis; RAG) ou da validação ao vivo que falta
  nas parciais 4 e 3b. **Quem escolhe é o dono.**
- **Primeiro passo:** perguntar ao dono qual assunto, e abrir pela skill `software-build`.
- **Ao abrir qualquer sessão (D45, desde a 7):** `uv lock --upgrade --dry-run` — há versão nova?
  Se houver, `uv lock --upgrade` num commit próprio, com a suíte antes e depois; e conferir o CI do
  último commit pelo SHA (`gh run list --commit <sha>`). Alerta do Dependabot aberto = atualizar
  aquele pacote primeiro.
- **Ler antes:** `AGENTS.md`, `PROGRESSO.md`, `docs/erros.md`, `docs/decisoes.md` (D39–D45), a
  seção da Sessão 7 abaixo, e a memória do Claude sobre o fuso do dono.
- **Depende do dono:** a escolha da próxima sessão.

> **Notas de ordem.** 2026-09-26: Sessão 4b criada e posta antes da Sessão Gmail, por decisão do
> dono — o freio de clique era o maior risco aberto e estava sem sessão. 2026-09-26: Sessão
> Pluggy logo depois da Gmail 2 e antes da Sessão 5, por decisão do dono ("bem importante").

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

## ✅ Sessão Gmail — leitura via API (feita e validada em 2026-09-26)

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
Perguntas no `viking chat` também validadas. Não medida: a latência do raio-x.

## ✅ Sessão Gmail 2 — limpar a caixa (feita e validada no Mac em 2026-09-26)

**Entregue:** `viking chat` → "arquiva tudo do X" → a tool `preparar_limpeza` imprime no terminal
a lista exata e um código de 4 dígitos (nunca devolvido ao Gemini) → o dono digita
`confirma NNNN`, lido pelo laço do chat antes do modelo → arquiva; `desfaz NNNN` devolve por 7
dias. `viking gmail --arquivar/--desfazer` faz o mesmo sem o Gemini. Teto 250 (D28, revista depois do 403 de cota no Mac); escopo
`gmail.modify` com teste que proíbe enviar/lixeira/apagar (D29); confirmação mecânica genérica
em `lifeos/confirmacao.py`, pronta para a Sessão 5. Plano e checkpoints em `PROGRESSO.md`.

O que era a abertura:

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
- **Respostas do dono na abertura (2026-09-26, antes do compact):**
  - Escolha **por remetente** (a partir do raio-x), não por regra do Gmail.
  - Do remetente escolhido saem **todos** os e-mails da caixa de entrada, lidos ou não.
  - **Nunca** arquivar: com estrela, marcados como importantes, com anexo. Somado: o Gmail às
    vezes marca newsletter como importante, então parte de um remetente escolhido fica — a lista
    tem de dizer quantos ficaram e por quê ("3 protegidos: importantes").
  - Aprovação **digitando um código** que o Viking mostra direto no terminal, sem passar pelo
    Gemini ("confirma 4821"): um e-mail malicioso não consegue fazer o Gemini aprovar sozinho.
  - **Desfazer por 7 dias:** o Viking guarda quais e-mails arquivou e devolve exatamente esses.
- **Desenho técnico proposto (meu, ainda não apresentado ao dono como plano):**
  - Escopo `gmail.modify` no lugar de `gmail.readonly`, no mesmo `google_token_gmail.json`: a
    conferência de escopo de `google_auth` já força o login novo (uma vez, no Mac).
  - Seleção: `from:<endereço> in:inbox -is:starred -is:important -has:attachment`; a contagem dos
    protegidos sai da consulta complementar.
  - Confirmação mecânica reaproveitável pela Sessão 5 (ex.: `lifeos/confirmacao.py`, SQLite em
    `data/viking.db`): código curto aleatório ligado à ação, ao conjunto exato de IDs e a uma
    expiração; consumido uma vez. O código vai para o terminal do dono, não para o Gemini.
  - Na confirmação, refazer a seleção e **intersectar** com os IDs aprovados: o que ganhou estrela
    depois sai; e-mail novo não entra.
  - Execução por `users.messages.batchModify` (até 1000 IDs por chamada) tirando `INBOX`;
    desfazer = recolocar `INBOX` nos mesmos IDs; registro local do que foi pedido, aprovado e
    executado (cobre parte do §7 da Sessão 5).
  - Só no `viking chat` (como a leitura) + `viking gmail --arquivar` para validar no Mac.
  - Em aberto (perguntar ao dono no plano): teto de e-mails por aprovação.
- **Base medida (raio-x real, 2026-09-26):** 200 e-mails (piso) de 91 remetentes nos últimos 30
  dias; nos 15 maiores, praticamente tudo sem abrir, e a maioria com sinal de newsletter. Nomes de
  remetente não entram neste repo (é público).

## Sessão Pluggy — finanças, só leitura (feita em 2026-09-27, validada no Mac)

**Feita e validada no Mac em 2026-09-27** (diário, mesma data): saldo, gastos, busca e fatura no
`viking chat` e em `viking financas --saldo/--gastos/--buscar/--fatura`; decisões D31–D35. Três
rodadas no Mac trouxeram três consertos (conexão, pagamento de fatura do Nubank, linha própria das
transferências). A medição e o plano de abertura, como estavam:

Pedida pelo dono como "bem importante". Medição completa, com fontes e datas:
`docs/fontes/pluggy-open-finance.md`. O essencial:

- **Custo:** uso pessoal é **gratuito** pelo Meu Pluggy (até 5 conexões do mesmo titular). A
  pergunta aberta de D5 está respondida.
- **Credenciais:** `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` já estão no `.env` da raiz; `/auth`
  respondeu 200 e o conector MeuPluggy (id 200) está disponível. Falta o **ID de cada conexão**
  (a listagem vem desligada: 403) — sai do Dashboard.
- **Primeiro passo: feito em 2026-09-27.** `viking financas --conectar` (feito antes da sessão
  porque o Dashboard não mostrou o MeuPluggy ao dono) conectou Nubank e Itaú; os IDs estão no
  `.env` do Mac, e `viking financas` confere as duas: 2 contas correntes e 2 cartões.
- **Entrega proposta (1 sessão de ~1h30–2h):** `lifeos/financas/` com cliente **só `GET`** por
  construção (a mesma chave alcança PIX e apagar item — ver a fonte), chave de 2 h em cache,
  contas e transações por período (`/v2/transactions`, cursor); tools no chat para saldo, gastos
  do período por categoria e busca de transação; `viking financas` para validar no Mac sem o
  Gemini; descrição de transação como **não confiável** (quem manda um PIX escreve a descrição) e
  redigida; toda resposta diz de quando é o dado (sincroniza a cada 24 h, sem atualização
  manual).
- **Perguntas ao dono na abertura:** quais bancos/cartões; só no chat ou também no MCP; o que
  pode ir ao Gemini (valores e descrições são necessários para responder); consultar ao vivo ou
  guardar cópia local (pesa para RAG depois, mas deixa dado financeiro em disco).
- **Fica para depois:** categorização/recorrências pela Enrichment API, alertas de gasto, cópia
  local para RAG. Webhook não serve (o Viking não tem servidor público).

## Sessão 5 — confirmação mecânica (feita e testada no Mac em 2026-09-27)

**Commit 1 (2026-09-27):** registro de ações (D37), `desfaz` do calendário no chat, pedidos pelo
MCP aprovados em `viking aprovar` (D36).
**Commit 2 (2026-09-27):** liberar, com código e uma vez, um clique de sair ou de mexer na conta
que o freio recusou; dinheiro nunca (D38, D18 reescrita).
**Mac (2026-09-27):** as quatro partes funcionaram (liberar "Sair", recusar "Pagar", `desfaz`
restaurando o mesmo evento, pedido do MCP aprovado em `viking aprovar`). O teste achou um defeito
antigo — o Gemini inventou fuso e o evento foi às 15h em vez das 10h — consertado no mesmo dia
(D39). Não medido: desfazer um reagendamento; evento com convidados. O que estava escrito na
abertura:


- **Primeiro passo (adiado da 4b por decisão do dono, 2026-09-26):** a liberação do freio de
  cliques (`_acoes_sensiveis`) passa por esta mesma confirmação — o dono aprova **aquele** clique
  (site, botão, categoria), uma vez; não existe chave que desligue uma categoria inteira.
- §3.5/§5: o fluxo de confirmação em duas fases que ficou de fora da Sessão 1 —
  `preparar_exclusao(event_id)` devolve um token curto ligado a ID+título+data+expiração,
  `confirmar_exclusao(token)` consome uma vez. Valendo igual para Gemini e MCP.
- §7: idempotency key por intenção mutável + log de auditoria local (o que foi pedido, o que foi
  confirmado, o que rodou, o resultado) — cobre o caso de uma tool funcionar e a chamada seguinte
  ao Gemini falhar, hoje sem rastro de que a mutação já aconteceu.

## Sessão 6 — runner em concorrência (feita em 2026-09-27/28, testada no Mac)

**Commit 1 (2026-09-27):** um navegador por vez entre processos, recusando na hora e dizendo quem
usa; o `--doctor` também; protocolo com nonce por execução (D40).
**Commit 2 (2026-09-27):** o Jev recebe do ambiente só uma lista (as chaves do Viking não chegam a
ele nem ao daemon); o `--doctor` mostra a versão do Jev e cada tarefa avisa se destoa (D41).
**Mac (2026-09-27/28):** chave fora do daemon (1 → 0, com `HOME` de controle), versão no doctor,
"ocupado" com o YouTube rodando, `desfaz` de reagendamento. O teste achou: o YouTube em loop até o
teto (detector por ação e regra de volta, D43) e **três fusos** — o dono não está em Brasília, a
agenda está em São Paulo, o relógio do Mac em -08:00 (D39 revista, D42, D44; conferido criar,
listar e o aviso). Rodando a CLI no VPS: o "ocupado" falava com o Gemini no terminal, a ordem do
`--doctor` num pipe, e um teste com corrida. A data das finanças o dono conferiu em 2026-09-28: bateu.


- **Primeiro passo (adiado da 5, 2026-09-27):** no Mac, medir o que o teste da 5 não alcançou —
  reagendar o "Teste Viking" pelo chat e `desfaz` (o `patch` com `{"date": null}`/`dateTime` volta
  o horário exato?) e, se o dono topar, um evento de teste com um convidado dele mesmo (o `desfaz`
  não manda aviso?). Roteiro: o do C9 da Sessão 5 no `PROGRESSO.md`/diário.
- §10.7: lock hoje é só `threading.Lock` (intraprocesso) — dois `viking` separados disputam o
  mesmo daemon/Chrome. Lock em arquivo, com timeout de aquisição e mensagem de quem é o dono.
- §10.10: `parse_event` aceita qualquer dict com `"type"` no stdout — um schema mais estrito (ou
  canal dedicado) evita falso terminal se alguma dependência imprimir JSON parecido.
- §11.1: o subprocesso do Jev herda todo o ambiente do Viking, inclusive `GEMINI_API_KEY` — trocar
  por um ambiente allowlisted (só o que o Jev precisa).
- §11.2: nada confere se o clone do Jev está no commit/branch esperado com o patch OpenRouter —
  `viking browser --doctor` podia mostrar branch/commit/dirty status.

## Sessão 7 — manutenção (feita e testada no Mac em 2026-09-28)

- ~~Adiado da 6: conferir as datas de `viking financas --gastos` no app do banco~~ — feito pelo dono
  em 2026-09-28, bateu (D44).
- ~~§15.1: sem lockfile no projeto principal~~ — feito em 2026-09-28: `uv.lock`, instalado com
  `uv sync --locked --extra dev`; `tests/test_lock.py` exige wheel para Mac Intel e Linux nos
  Pythons 3.12 e 3.13, menos o cryptography no Mac, que se compila lá (decisão do dono, D45).
- ~~§15.3: sem CI, sem scanner de dependências~~ — feito em 2026-09-28: `.github/workflows/testes.yml`
  (testes, `ruff`, `pip-audit` do lock) e alertas do Dependabot ligados (D45). A checagem de tipos
  foi para o backlog, por decisão do dono, com o número medido (67 erros).
- ~~§15.4: `ruff format --check` ainda aponta arquivos pré-existentes~~ — feito em 2026-09-28
  (`dd7d4c8`, commit só de formatação; `.md` fora do `ruff format`, D45): zero a formatar.
- ~~§15.2: `test_assistant_tools.py` usa `_automatic_function_calling_util`, API privada do
  google-genai~~ — feito em 2026-09-28: o teste usa a função pública
  (`FunctionDeclaration.from_callable_with_api_option`, com `GEMINI_API`, a API que o chat usa; a
  privada conferia contra o Vertex AI) e exige o conversor estrito.

## Só se o Bosgame voltar (trilha de hardware reativada)

- §10.1: `jev_runner._matar()` não mata a árvore de processos no Windows (só
  `terminate()`/`kill()`, sem `CTRL_BREAK_EVENT`/Job Object). Não vale investir sem o Bosgame
  ativo — ver `AGENTS.md`, "Não sugerir de novo".
- §16: trilha de hardware arquivada — caminho padrão errado em `serial_mcp_bridge.py`
  (`parents[2]` aponta para `archive/windows-mcp`, deveria ser `parents[3]` ou config explícita) e
  docs que afirmam sucesso não comprovado no Bosgame.

## Backlog sem sessão marcada

- **Checagem de tipos como portão do CI** (§15.3, adiada pelo dono em 2026-09-28, Sessão 7):
  `uvx mypy==2.3.1 --python-executable .venv/bin/python src` → `Found 67 errors in 15 files
  (checked 41 source files)`. 34 são um padrão só em `browser/jev_runner.py` (`**dict` num
  dataclass), 9 são imports do ambiente do Jev e 3 são pacotes do Google sem tipos; nos ~12 que li,
  nenhum defeito real. Para virar portão: consertar os 67, ignorar os imports do ambiente do Jev
  (`_jev_subprocess.py` roda noutro Python) e pôr o `mypy` fixado no CI.

Paginação e eventos recorrentes no calendário (§4.5); notas recuperáveis/buscáveis, não só
criáveis (§12.4); migrations de schema formais (§12.6); decidir se o Viking é só-checkout ou
pacote instalável de verdade (§9.3); RAG/busca semântica sobre notas e
calendário; teste preventivo para o caso de uma função virar tool do Gemini e do MCP ao mesmo
tempo (armadilha do future-import) — sem bug real hoje (conferido na Sessão 3), só rede de
segurança para um cenário hipotético. Residuais da Sessão 4: o objetivo, os rótulos/valores
de campos e o histórico de ações ainda vão ao OpenRouter sem redação (ver
`docs/fontes/jev-typesafe.md`, "Egress e redação"); domínio em punycode/IDN não é normalizado;
o clique destrutivo num site não bloqueado (§5.2) foi feito na Sessão 4b; ficou de fora, por
decisão do dono, "publicar em seu nome" (postar, enviar mensagem).

Da Sessão 5 (planejamento, 2026-09-27): aprovação fora do terminal (elicitation do MCP, web) —
hoje `viking aprovar` exige terminal interativo; idempotência automática de criar (devolver o já
criado) cortada: exige reler o Google para não mostrar evento fantasma.

Da Pluggy (vistos no Mac, 2026-09-27, sem conserto agora): "cartão nubank" não achou o cartão,
que o banco chama de "gold" (a docstring já avisa; agrupar contas por conexão resolveria); a
fatura que fechou e ainda não venceu está dentro de "compras sem fatura" — dá para separar pelo
dia de fechamento do mês anterior, como estimativa rotulada; o Gemini não citou a data da
sincronização na resposta de gastos (a regra está no prompt); nomes de conta longos ("Nu
Pagamentos S.A. - Instituição de Pagamento (Conta Pré-paga)").

Da Gmail 2 (vistos no Mac, 2026-09-26, só texto): "vamos arquivar esses e-mails" depois de uma
busca faz o Gemini pedir o remetente de novo; a instrução para um código vivo digitado sem verbo
podia dizer o que aquele código foi (limpeza de quando, quantos e-mails).
