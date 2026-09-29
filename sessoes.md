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

- **Sessão:** 8b — pequenos (a 8, e-mail que sai, fechou no Mac em 2026-09-28).
- **Revisão sênior e pesquisa do roteiro: feitas em 2026-09-28** (pedido do dono).
  - Fontes em `docs/fontes/pesquisa-roteiro.md`; as escolhas, na seção de cada sessão abaixo;
    regras e recusas na D53.
  - As 4 perguntas que tocavam decisões do dono foram respondidas no mesmo dia e já estão nas
    seções: a memória, que aprende sozinha só do dono (13, D48), o repo privado no começo da 10 (D50), o deploy sem
    credencial fixa (10, D47) e o relógio pelo Strava (21, D54).
- **Agora:** abrir e planejar a 8b pela skill `software-build` (primeiros passos já escritos na
  seção dela).
- **Ao abrir qualquer sessão (D45, desde a 7):** `uv lock --upgrade --dry-run` — há versão nova?
  Se houver, `uv lock --upgrade` num commit próprio, com a suíte antes e depois; e conferir o CI do
  último commit pelo SHA (`gh run list --commit <sha>`). Alerta do Dependabot aberto = atualizar
  aquele pacote primeiro.
- **Ler antes:** `AGENTS.md`, `PROGRESSO.md`, `docs/erros.md`, `docs/decisoes.md` (D45–D52), o
  roteiro de 2026-09-28 abaixo, e a memória do Claude (fuso e visão do dono).
- **Depende do dono:** as perguntas da abertura da 8b.

> **Notas de ordem.** 2026-09-26: Sessão 4b criada e posta antes da Sessão Gmail, por decisão do
> dono — o freio de clique era o maior risco aberto e estava sem sessão. 2026-09-26: Sessão
> Pluggy logo depois da Gmail 2 e antes da Sessão 5, por decisão do dono ("bem importante"). 2026-09-28:
> roteiro das Sessões 8–21, com a **nuvem cedo** (S10–11, antes das features), por decisão do dono
> ("o meu Mac vai atrasar o dev"); documentos antes do coach, porque o material do NotebookLM dele
> é o que faz o coach "não ser genérico".

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

## O roteiro de 2026-09-28: do terminal a um agente geral na nuvem (Sessões 8–21)

Planejado com o dono em 2026-09-28, depois da Sessão 7. A "versão de sucesso final" dele:
- um agente geral, que conversa de verdade e busca na web;
- um profissional em alguns assuntos, a começar por **personal trainer/coach** a partir dos
  treinos dele;
- aprende coisas novas;
- se diagnostica e propõe consertos, com o código passando pelo dono;
- ganha um segundo agente (Claude);
- tem app no iPhone, no navegador e por voz;
- mora na nuvem (GCP), com o Mac como "mãos" do navegador.

As decisões estão na D46–D52 (`docs/decisoes.md`). Cada sessão abre e planeja do jeito de
sempre (skill `software-build`): a entrega abaixo é o alvo, e o tamanho sai da medição da
abertura. Dividir uma sessão em duas é decisão do dono; a 10, a 13 e a 17 são as candidatas.

**Regras que valem para todas, decididas agora:**
- **Nunca código de aprovação por e-mail**, nem por nenhum canal que uma tool leia: o Viking lê o
  Gmail (D22), e leria o próprio código.
- **Memória (D48, revista pelo dono em 2026-09-28):** o Viking anota sozinho só o que **o dono
  escreve**, avisando numa linha; o que vem de e-mail, página ou documento nunca entra sozinho;
  receita continua com pergunta. O modelo do chat não tem tool de gravar memória.
- **O Claude nunca vê** e-mail, finanças nem páginas (D49).
- Tudo que custa dinheiro é medido antes, e o teto de ~US$ 20/mês fica no próprio app
  (`custos.py`), porque o alerta do GCP só avisa, não para o gasto.
- A nuvem roda em UTC: `VIKING_TIMEZONE` explícito, sempre. Os logs dela não guardam prompt nem
  conteúdo.

**Da revisão sênior + pesquisa de 2026-09-28** (fontes datadas em `docs/fontes/pesquisa-roteiro.md`;
tudo lá é "não medido" até a sessão que usa medir):
- **E-mail que o próprio Viking mandou é conteúdo de terceiro** quando ele o lê de volta, mesmo com
  o remetente sendo o dono. Sem isso, um e-mail injetado faria o Gemini mandar ao dono (caminho
  livre da D46) um texto com instruções, que voltaria depois "assinado" por ele. O mesmo vale
  para o texto de um lembrete enviado por e-mail.
- **Toda lib nova** passa pela árvore e pelas wheels antes de entrar (`tests/test_lock.py`), e as
  da nuvem entram só onde rodam: o Mac é cliente e "mãos", não instala Firestore nem gRPC.
- **Skills e plugins de terceiros** não se instalam: o texto útil se copia para `.claude/skills/`,
  com o commit de origem anotado. `/security-review` e `/code-review`, que a pesquisa diz virem no Claude Code
  (na 8 não estavam entre as skills que eu podia chamar: não conferidos), entram no fechamento de toda sessão em que estiverem disponíveis.
- **Formato por sessão abaixo:** "Escolhas de arquitetura previstas" (o que eu já recomendo, com o
  gatilho que reabre) e "Libs/repos a reaproveitar". São a proposta de partida; o plano de cada
  sessão confirma ou derruba na abertura, com o dono.

## Sessão 8 — e-mail que sai (feita e testada no Mac em 2026-09-28)

**Feito em 2026-09-28** (plano e checkpoints em `PROGRESSO.md`):
- o furo do bloqueio de banco/e-mail fechado, e o endereço inicial só `http`/`https`/`data:`/
  `about:blank` (D8);
- o lock atualizado em commit próprio (5 pacotes);
- o envio: `gmail/envio.py`, as tools `enviar_email`/`responder_email`, `confirma NNNN` no chat e
  `viking gmail --enviar/--responder` (D46 com as respostas do dono).

Os comandos de revisão do Claude Code (D53): **não conferidos** nesta sessão. A lista de skills
que esta sessão podia chamar não trazia `/security-review` nem `/code-review`, e um comando
embutido do terminal eu não consigo chamar. Fica para o dono rodar, se quiser, ou para uma sessão
em que apareçam.

**Mac (2026-09-28, no fuso do dono):**
- os dois endereços recusados sem abrir aba (`view-source:` do banco e `file:///etc/hosts`);
- um e-mail para ele, sem código;
- a carta para a noiva só depois do código: uma versão nova substituiu a anterior, e o código
  errado não enviou nada;
- as duas linhas no registro, sem código;
- o dono disse "tudo certo" para a suíte e o login, sem colar a saída desses dois.

O teste achou um defeito: o Gemini não sabia o endereço do dono e perguntou duas vezes antes de
um "manda pra mim". Consertado no mesmo dia: `para="eu"` é a própria conta, com teste e mutação.
A conferência ao vivo disso é o primeiro passo da 8b.

O que estava escrito na abertura:

- **Entrega:** um e-mail para o próprio dono sai sem código; uma resposta a outra pessoa só sai
  depois do código dele, com a linha no `registro`.
- **Decidido (D46):**
  - para ele, livre, com o endereço vindo da config (o repo é público) e um limite de envios por
    dia;
  - para outros, com código, e-mail novo e resposta na conversa certa, sem anexo por construção.
- **Travas:**
  - o código liga destinatários, assunto, corpo e conversa;
  - CRLF nos cabeçalhos é recusado, e a resposta nunca acrescenta Cc/Cco;
  - o teste que hoje proíbe enviar (`test_codigo_do_gmail_nunca_chama_enviar_lixeira_ou_apagar`)
    vira um que permite `send` em **uma** função, dentro de `registro.acao`. Lixeira e apagar
    continuam proibidos.
- **Medido:** o `gmail.modify` já autoriza enviar (D29), então não precisa de login novo para isso.
- ~~**Primeiro passo:** conferir com o dono se o app OAuth está em "Testing"~~ — **já estava
  conferido:** o dono viu em 2026-09-26, na Sessão Gmail, "em produção, externo, só ele de
  usuário" (`docs/fontes/gmail-api.md`). O "D11 nunca conferiu" escrito aqui na revisão de
  2026-09-28 era erro meu (`docs/erros.md`, classe 2). O que falta medir, a prova de que o token
  não vence em 7 dias, foi para o primeiro passo da Sessão 10.
- **Lembretes:** até a nuvem, o disparo por e-mail é manual (`viking lembretes --enviar`); o
  automático vem na 11.
- **Primeiros passos, antes do e-mail (dívida achada na revisão de 2026-09-28):**
  1. **Furo no bloqueio de banco e e-mail (D8), medido em 2026-09-28:** um endereço embrulhado
     passa. `_redacao.dominio_bloqueado("blob:https://<banco>/…")`, `view-source:https://<banco>/`
     e `filesystem:https://<banco>/…` devolvem `None`, e `https://<banco>/x` é bloqueado.
     - Conserto: o runner e o subprocesso aceitam só `http`/`https` (mais o `about:blank` e o
       `data:` de que os testes e a D38 precisam, a conferir). O host dos esquemas que embrulham
       outro endereço sai do endereço de dentro. O teste é a lista acima, com mutação.
     - Não medido: se o Chrome abre `view-source:` por CDP com os cookies do dono.
  2. **Rotina da D45:** o `uv lock --upgrade --dry-run` de 2026-09-28 mostrou `oauthlib` 3.3.1 →
     **4.0.0**, publicada no mesmo dia, e `platformdirs` 4.12.0 → 4.12.1.
     - O changelog da 4.0.0 só quebra o lado **provedor** (revogação com JSONP e validação do
       `grant_type`). O Viking é cliente, pelo `requests-oauthlib`.
     - Commit próprio, com a suíte antes e depois, e o dono confere o login no Mac
       (`viking gmail --login`).
  3. ~~**Login que vence em 7 dias**~~ — o app já está "em produção" desde antes de 2026-09-26
     (conferido pelo dono). O prazo de 7 dias é do modo "Testing"
     (https://developers.google.com/identity/protocols/oauth2); que ele não vale para o nosso
     escopo restrito em produção sem verificação se mede na Sessão 10 (primeiro passo lá).
- **Escolhas de arquitetura previstas:**
  - **Mensagem montada com `email.message.EmailMessage`**, que recusa CR/LF num cabeçalho
    (medido: `ValueError` no Python 3.12.3). A nossa trava continua, e o teste cobre os dois
    Pythons.
  - **Resposta na conversa certa:** `threadId` mais `In-Reply-To`/`References` copiados da
    mensagem original, e o `Subject` igual. O destinatário da resposta sai **do cabeçalho da
    original**, nunca do texto do Gemini, e o código liga esse destinatário.
  - **O caminho livre** (só para o dono) confere o destinatário contra a config, depois de
    normalizar. Um "dono@…" com outro domínio, ou com `+tag`, não é o dono.
  - **Todo e-mail enviado leva uma marca** (cabeçalho próprio). Ao ser lido de volta, vai no bloco
    de não confiável como qualquer outro, e fica gravado no `registro` com o id da mensagem.
  - **Um token só com `gmail.send`?** O `gmail.send` é sensível e o `modify` é restrito, mas o
    `modify` que já temos também envia. Separar só reduz o raio se o `modify` sair de onde o envio
    roda: decisão da S10 (o que vai para a nuvem).
    - Gatilho: a medição do "In production" acima.
- **Libs/repos a reaproveitar:** nenhuma nova. A stdlib `email` e o `googleapiclient` que já temos
  bastam.

## Sessão 8b — pequenos (curta, planejada em 2026-09-28)

- **Primeiros passos (adiados da 8, 2026-09-28):**
  1. No Mac, `manda pra mim um e-mail…` sai direto, sem o Gemini perguntar o endereço (o
     conserto do "eu", feito depois do teste da 8).
  2. Perguntar ao dono: o nome de usuário do Mac aparece em 3 linhas antigas do repo público
     (`.env.example:20` e duas no diário). Tirar, ou deixar até o repo virar privado na 10?

- **Entrega:** uma série semanal de 300 ocorrências aparece inteira na busca; os testes ao vivo
  que faltam nas parciais 4 (redação de CPF/cartão numa página real) e 3b (tools de calendário
  do MCP contra o Google real, evento de dia inteiro conferido no Google Calendar) estão feitos.
- **Medido:** `calendar/service.buscar()` não tem `timeMax` e usa `singleEvents=True`. Lê só a
  1ª página (até 250 resultados), e uma série pode enchê-la em silêncio (§4.5).
- **Escolha de arquitetura prevista:** seguir o `nextPageToken` até um teto declarado. Quem bate no
  teto diz que a lista está incompleta, e quantos vieram (skill `falha-ruidosa` §2: um teto
  silencioso é uma interrupção). Janela com `timeMax` quando a pergunta tem prazo. Nenhuma lib
  nova.

## Sessão 9 — fundação de dados (planejada em 2026-09-28)

- **Entrega:**
  - migrations numeradas em todos os módulos que usam o `viking.db`, e um banco no formato antigo
    migra (§12.6);
  - uma interface de store com UUID e UTC;
  - "o que mora onde" escrito numa decisão;
  - lembrete com `enviado_em`: `viking lembretes --enviar` rodado duas vezes manda uma.
- **Por que antes da nuvem:** texto em tabelas normais é a fonte, e o índice vetorial é
  descartável. A troca de banco vira reconstruir um índice, não migrar dados. É também a defesa
  estrutural contra a deriva de contexto.
- **O que mora onde, proposto:** no Mac ficam o navegador, a trava, a liberação de clique (D38) e
  o Chrome logado. Na nuvem ficam o cérebro, os lembretes, a memória, os treinos e os documentos.
  A aprovação mora onde a ação roda.
- **Pergunta na abertura:** a checagem de tipos (backlog, 67 erros) antes desta refatoração?
- **Escolhas de arquitetura previstas:**
  - **A interface de store tem de servir ao SQLite (Mac, testes) e ao Firestore (nuvem, S10).**
    - Operações pequenas e explícitas: buscar por id, listar por índice, gravar numa transação e
      "reservar para enviar".
    - Nada de SQL solto fora dela.
    - O `enviado_em` vira uma **reserva com prazo** (quem pegou e até quando), porque o Scheduler
      entrega "at least once" e pode chamar duas vezes. Fonte:
      https://docs.cloud.google.com/scheduler/docs/overview
    - Gatilho: a S10 escolher Cloud SQL, e aí a interface pode encolher para SQL.
  - **"O que mora onde" também diz o que cada credencial alcança:**
    - na nuvem: tokens do Google (com o raio do `gmail.modify`, que envia), Gemini e Claude;
    - no Mac: a Chrome logada, o Jev e as chaves dele (D7);
    - a Pluggy segue a D51.
  - **Tabelas de memória com cara de registro,** já agora, mesmo sem uso até a S13: só se
    acrescenta linha; um fato substituído ganha `invalida_em` e aponta para o que o substituiu
    (ideia do Graphiti); a origem e a mensagem de onde veio ficam gravadas.
- **Libs/repos a reaproveitar:** nenhuma lib de migrations. A régua numerada é pequena e é nossa:
  Alembic traria o SQLAlchemy só para isso.

## Sessão 10 — nuvem 1: o motor (planejada em 2026-09-28)

- **Primeiro passo (decisão do dono, 2026-09-28):** o repo vira **privado antes de qualquer
  infraestrutura**. Antes da troca entra um scanner de segredos nosso no CI e no commit, porque o
  secret scanning do GitHub some em repo privado (detalhe na Sessão 11, onde isto estava).
  Nenhum ID de projeto, URL ou conta de serviço chega a um repo público.
- **Primeiro passo (adiado da 8, 2026-09-28):** provar que o login do Google não vence em 7 dias
  (o app está "em produção" sem verificação, com o escopo restrito `gmail.modify`). O token do
  Gmail foi feito em 2026-09-26: `viking gmail --login` no Mac **depois de 2026-10-03**, sem abrir
  o navegador, é a prova. Se pedir login de novo, a nuvem precisa de outra saída antes de guardar
  token (a verificação do Google, ou um escopo menor).
- **Entrega:**
  - projeto GCP (criado pelo dono, com o faturamento dele) com a infraestrutura em script;
  - o `describe` mostra a imagem do commit;
  - um pedido sem login responde 401;
  - `viking chat` no Mac conversa com a nuvem, e o código de aprovação aparece só no terminal, por
    um canal que o modelo não vê;
  - alerta de faturamento ligado.
- **Decidido (D47):**
  - Cloud Run com mínimo de 0 instâncias, Cloud Scheduler e Secret Manager;
  - sem load balancer nem IAP (~US$ 18/mês, fora do orçamento);
  - o deploy sou eu, do VPS, com uma conta de serviço limitada ao projeto e o ok do dono a cada
    deploy; o script mostra o que muda antes.
- **Banco:** escolhido na abertura pelo custo medido: Firestore com busca vetorial, Cloud SQL +
  pgvector (~US$ 9–10+/mês) ou Chroma numa VM gratuita. Na nuvem o Chroma instala; no Mac Intel
  não, porque o `onnxruntime` só publicou até a 1.23.2 (medido em 2026-09-28).
- **Escolhas de arquitetura previstas** (fontes na seção 5 de `docs/fontes/pesquisa-roteiro.md`):
  - **Banco: Firestore (modo nativo), recomendado.**
    - A cota grátis cobre um usuário: 50 mil leituras e 20 mil gravações por dia, e vetor de até
      2048 dimensões.
    - O Cloud SQL `db-f1-micro` custaria ~US$ 9,4/mês, quase metade do orçamento, fora do SLA.
    - **Recusados:** SQLite num volume do Cloud Storage, porque a própria documentação diz "no
      file locking… last write wins"; e Chroma, porque exige servidor ou VM.
    - Gatilho: uma consulta que o Firestore não faz sem índice caro, ou a cota estourar.
  - **Duas portas, não uma: o "motor" fica fechado para sempre.**
    - Serviço `motor` com IAM (`run.invoker`): só contas de serviço entram, e pedido recusado nem
      chega ao nosso código nem cobra.
    - O app da S17 será um **segundo** serviço, público, com o passkey, que chama o motor pela
      conta de serviço dele.
    - Assim, abrir o app não abre as rotas do motor, e o "401 sem login" da entrega vale para
      sempre.
    - Gatilho: o custo ou a latência de dois serviços medidos na S17.
  - **Quem chama o motor, sem chave em disco:**
    - o terminal do Mac e o `viking maos` se fazem passar por contas de serviço estreitas (`cli@`,
      `maos@`), com o papel `serviceAccountTokenCreator` só nelas;
    - o token sai com audience. O token de usuário do `gcloud` não tem audience e é "susceptible
      to replay";
    - o Mac passa a precisar do `gcloud` (ou do `google-auth` com as credenciais do dono).
    - Fonte: https://docs.cloud.google.com/run/docs/authenticating/developers
  - **O código de aprovação passa a atravessar a rede:**
    - limite de tentativas erradas por proposta, porque hoje não há: o TTY era a barreira;
    - o código viaja num campo próprio do protocolo, nunca no texto que o modelo escreve;
    - a linha "confirma NNNN" é lida pelo laço **antes** do modelo, como hoje, e não entra no
      histórico.
  - **Dependências da nuvem num grupo só dela,** com marcador de Linux. O `tests/test_lock.py`
    aprende que esse grupo não vai para o Mac, e continua exigindo wheel no Linux.
  - **Custos no ar:**
    - teto no `custos.py` antes de gastar, porque o alerta do GCP só avisa;
    - desligar o faturamento por Pub/Sub foi **recusado**: "resources might be irretrievably
      deleted";
    - logs: nada de conteúdo na URL nem no stdout, e um filtro de exclusão;
    - se o corpo da requisição fica fora do log: **não conferido**, medir.
  - **Deploy sem credencial fixa no VPS (decisão do dono, 2026-09-28).**
    - A cada deploy, o dono roda um comando no Mac que gera um token de 1 h, por impersonação da
      conta de serviço `deployer@`, e o envia ao VPS. Nunca pela conversa.
    - A documentação do Google manda evitar chave de conta de serviço.
    - **Não conferido:** o mecanismo exato (o `gcloud` com access token num arquivo, e a validade
      de 1 h). Medir na abertura.
    - O Mac precisa do `gcloud`.
- **Libs/repos a reaproveitar:**
  - `google-cloud-firestore` 2.32.0, só na nuvem;
  - `google-auth`, que já está no lock, para a impersonação no Mac;
  - o modelo de "script de deploy que só lê sem flag", da skill `nuvem-e-deploy` §6.

## Sessão 11 — nuvem 2: vida própria (planejada em 2026-09-28)

- **Entrega:**
  - os dados do Mac migrados;
  - lembrete por e-mail em ±2 min com o Mac desligado;
  - `viking maos` liga o navegador do Mac à nuvem;
  - backup no Drive (`drive.file`) que restaura num banco novo;
  - (o repo privado passou para o começo da Sessão 10, por decisão do dono em 2026-09-28).
- **O navegador (mãos no Mac):** o Mac **puxa** as tarefas, numa saída autenticada e sem porta
  aberta. A tarefa expira, e todas as travas do navegador continuam rodando no Mac. Só funciona
  enquanto o dono deixa `viking maos` ligado: ele recusou processo em segundo plano.
- **Finanças (D51):** vão para a nuvem só se a medição, feita só lendo, disser que é seguro:
  - o produto de pagamentos está desligado na aplicação Pluggy dele?
  - a documentação oficial diz que o PIX exige autorização no banco?

  Se sim, a chave vai para um serviço isolado de leitura. Se não, fica no Mac até ele pedir à
  Pluggy que desligue os pagamentos.
- **Escolhas de arquitetura previstas:**
  - **As "mãos" são um nó que pergunta, não uma porta.**
    - `viking maos` chama o motor a cada 5–10 s, em pedidos curtos, só enquanto está ligado.
    - Long-poll e WebSocket ficam fora: no Cloud Run, conexão aberta é cobrada o tempo todo, e 8
      h/dia dariam ~US$ 16/mês (estimativa). Fonte:
      https://docs.cloud.google.com/run/docs/triggering/websockets
    - O padrão é o do nó local do OpenClaw (https://docs.openclaw.ai/nodes/node-host): pareado uma
      vez e com lista fixa de comandos. O `maos@` só pega uma tarefa de navegador e devolve o
      resultado; não lê a memória, a agenda nem o e-mail.
    - A tarefa tem prazo (vencida não roda) e é pega uma vez (reserva, como o lembrete).
    - O freio, a trava, a redação e a liberação por código (D38, no TTY do Mac) continuam rodando
      **no Mac**.
    - Gatilho: a latência de 5–10 s atrapalhar o uso.
  - **Nunca a porta CDP do Mac na nuvem,** nem o `profile-sync` do Browser Harness, que sobe
    cookies. O Jev fica no Mac com a Chrome local.
  - **Repo privado perde o secret scanning e o push protection,** ligados hoje (medido em
    2026-09-28 pela API). A documentação do GitHub diz que eles não existem em repo privado de
    conta pessoal no plano gratuito
    (https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning).
    - Antes de mudar, entra um scanner no CI e no commit: `detect-secrets` (Python, Apache-2.0)
      ou `gitleaks` (binário, MIT), a medir. O CI ganha uma cota de 2.000 min/mês.
    - Os alertas do Dependabot continuam grátis.
    - **Quando:** no começo da Sessão 10, antes de qualquer infraestrutura (decisão do dono,
      2026-09-28). Este item fica aqui como registro das consequências.
  - **Backup:** exportar do Firestore para um arquivo e subir no Drive com `drive.file`, que não é
    sensível (https://developers.google.com/workspace/drive/api/guides/api-specific-auth). O
    teste restaura num banco novo, vazio.
- **Libs/repos a reaproveitar:**
  - só o `googleapiclient`, para o Drive, que já está no lock;
  - o scanner de segredos, escolhido na abertura.

## Sessão 12 — agente geral (planejada em 2026-09-28)

- **Entrega:**
  - uma pergunta factual responde com fontes;
  - o tom é conversador e caloroso;
  - Flash no dia a dia e Pro quando precisa, visível no `/custos`;
  - o teto diário recusa com clareza.
- **Travas:**
  - o resultado da busca vai no bloco de conteúdo não confiável;
  - as fontes saem dos metadados da busca (`grounding_metadata`), não do texto do modelo;
  - um e-mail injetado não força o modelo caro, porque há teto.
- **A medir:** se a busca do Gemini combina com function calling na mesma chamada. Se não,
  vira uma tool que faz uma chamada separada.
  - Pesquisado em 2026-09-28: a combinação é "Preview and supported for Gemini 3 models only"
    (https://ai.google.dev/gemini-api/docs/tool-combination).
  - Com o `gemini-2.5-flash` de hoje, então, é uma tool `buscar_na_web` com chamada separada.
- **Pergunta na abertura, de dinheiro: o modelo mudou de preço e de oferta.** Pesquisado em
  2026-09-28 (https://ai.google.dev/gemini-api/docs/deprecations e /pricing):
  - o acesso ao 2.5 está sendo limitado a quem já usa, e os substitutos indicados são o 3.5
    Flash-Lite (US$ 0,30/2,50, o preço do 2.5 Flash) e o 3.8 Flash (US$ 0,75/3,75, **o dobro a
    partir de 2027-01-01**);
  - o Pro 3.x só existe em preview.

  O "barato no dia a dia, forte quando precisa" vira, provavelmente, 3.5 Flash-Lite no dia a dia
  e 3.8 Flash no difícil. Trocar de modelo refaz a medição de tokens das tools e o teste das
  regras das docstrings.
- **Escolhas de arquitetura previstas:**
  - **As fontes vêm do `groundingMetadata`** (`groundingChunks`/`groundingSupports`), e o texto do
    resultado vai no bloco de não confiável.
  - **Os termos exigem mostrar as "Search Suggestions"** (um HTML) a quem perguntou
    (https://ai.google.dev/gemini-api/terms). No terminal, mostrar as consultas e os links; no app,
    o HTML. Conferir na abertura se isso cumpre os termos.
  - **Resultado de busca não vai para o Claude:** os termos proíbem "syndicate" (inferência).
  - **Teto por dia antes de chamar:** modelo forte e busca, no `custos.py`. A busca é quase de
    graça para um usuário (1.500 prompts por dia grátis no 2.5), mas um e-mail injetado não pode
    forçar volume.
  - **Menos tools por pedido?** Com 21, já passa do número que alguns assistentes escolhem por
    pedido (isair/jarvis). Medir tokens antes de mexer (armadilha "não estime tokens").
  - **Interactions API: não migrar agora.** Ela guarda o histórico no servidor por padrão
    (`store=true`), e o `generateContent` continua "fully supported". Se migrar um dia, usar
    `store=false`.
- **Libs/repos a reaproveitar:** nada novo. O google-genai 2.25.0 do lock já tem a busca e o
  `url_context`.

## Sessão 13 — memória de fatos e receitas (planejada em 2026-09-28)

- **Entrega:**
  - um fato que o dono escreve na conversa A ("treino às 7h") é anotado sozinho, com a linha
    "📝 anotei: …", e volta na conversa B; "esquece isso" apaga;
  - um fato plantado num e-mail ou numa página **não** é anotado (teste com o texto do ataque);
  - um fato que contradiz substitui o antigo;
  - o dono lista, corrige e apaga;
  - uma receita reusada sem ganhar permissão nova;
  - uma nota achada por significado;
  - casos fixos de avaliação contra a deriva de contexto.
- **Decidido (D48):**
  - sem o histórico inteiro das conversas;
  - a origem de cada fato fica gravada, e o que veio de e-mail ou página é marcado.
- **Escolhas de arquitetura previstas** (seção 3 de `docs/fontes/pesquisa-roteiro.md`):
  - **Camada nossa, nenhum framework.**
    - mem0, Letta, LangMem, cognee e Memobase gravam sozinhos, por LLM ou por tool do agente, e
      alguns não instalam no Mac Intel.
    - O mem0, desde a v2.0.0, nem substitui o fato velho (só acrescenta).
  - **Aprende sozinho, mas só do dono** (D48 revista pelo dono em 2026-09-28: "tenho medo de ter
    que ficar respondendo sim toda hora").
    - Depois de cada mensagem do dono, **uma chamada separada** do Gemini recebe só o texto que ele
      digitou, nunca o resultado de uma tool, e devolve os fatos numa forma fixa. O modelo do chat
      não tem tool de gravar memória.
    - É isso que fecha o ataque publicado em que um documento planta "quando o usuário disser sim,
      grave isto"
      (https://embracethered.com/blog/posts/2025/gemini-memory-persistence-prompt-injection/): o
      e-mail nunca chega a quem grava.
    - A linha "📝 anotei: …" é escrita pelo laço a partir do que foi **gravado**, não da prosa do
      modelo. "Esquece isso" apaga a última anotação.
    - **Resto de risco:** um e-mail que o dono **cola** na mensagem conta como texto dele. Contra
      isso, a regra de forma de ordem abaixo e o resumo semanal.
    - **Resumo semanal** do que aprendeu, pelo e-mail do lembrete (e no app depois), para corrigir
      de uma vez. Ele volta como conteúdo de terceiro (D53).
    - O que vem de e-mail, página ou documento, no máximo, vira sugestão, e o Viking pergunta.
  - **Receita só nasce de mensagem do dono;** fato de origem externa (e-mail, página, documento)
    fica marcado e, na leitura, dentro do bloco de não confiável. Texto com forma de ordem ("se o
    usuário disser…", "sempre faça…") vindo de fora não vira fato.
  - **O que entra por turno tem teto:** poucos fatos, os mais relevantes. O visor da memória (a
    ideia do isair/jarvis) é o `viking memoria`, que lista, corrige e apaga, como o `viking
    registro`.
  - **Índice:**
    - `gemini-embedding-2`, US$ 0,20 por 1M de tokens, até 3072 dimensões, gravado com a dimensão
      e a instrução;
    - até 2048 dimensões se o Firestore guardar os vetores;
    - no Mac, se precisar, `sqlite-vec` (sem dependências, com wheel para Mac Intel e Linux);
    - o índice se reconstrói do texto, e o teste confere o mesmo top-k.
  - **Avaliação à mão no pytest:** perguntas de ouro, recall@k e MRR, com vetores gravados como
    fixture. O ragas (92 pacotes) e o deepeval (66, com telemetria) ficam recusados.
  - Gatilho: a avaliação fixa cair, ou o dono pedir histórico.
- **Libs/repos a reaproveitar:**
  - `sqlite-vec` 0.1.9, se houver busca no Mac. Conferir antes se o Python 3.13 de lá tem
    `sqlite3.enable_load_extension`;
  - as ideias do Graphiti (`invalida_em`) e do Leon (camadas: preferências, contexto do dia,
    conversa recente).

## Sessão 14 — documentos (planejada em 2026-09-28)

- **Entrega:** "aprende este PDF", um arquivo por vez. A resposta cita o arquivo e o trecho, e a
  avaliação fixa atinge um limiar medido e combinado.
- **O dono:** vai montar um NotebookLM com material de coach e mandar os arquivos um por um.
  Primeiro passo: confirmar se o NotebookLM tem API para conta pessoal (provável que não).
- **Ponto técnico:** o seletor do Drive é um componente de página web. Até o app, os arquivos são
  locais ou abertos por uma página local, como a da Pluggy.
- **NotebookLM, pesquisado em 2026-09-28:**
  - a API só existe no NotebookLM **Enterprise**, e sem conta pessoal: pede Cloud Identity ou outro
    provedor de identidade
    (https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/overview);
  - na conta pessoal, hoje chamada "Gemini Notebook", dá para exportar as **notas** para um Google
    Doc (https://support.google.com/notebooklm/answer/16262519).

  Então o caminho é: o dono exporta as notas para o Docs, e o Viking lê o Doc escolhido
  (`drive.file`) ou o arquivo baixado. A pergunta do primeiro passo está respondida; falta ele
  confirmar que é esse o material.
- **Escolhas de arquitetura previstas:**
  - **O documento é conteúdo de terceiro:** trecho citado vai no bloco de não confiável, e uma
    instrução dentro de um PDF não vira fato nem receita (a mesma regra da 13).
  - **Cortes com o arquivo e a posição gravados,** para a resposta citar arquivo e trecho.
  - **O limiar da avaliação é do dono,** medido antes de combinado.
- **Libs/repos a reaproveitar:** medir na abertura um leitor de PDF só com wheel (a árvore e o Mac
  Intel, se ler lá). Nenhum candidato aprovado ainda.

## Sessão 15 — coach 1: registrar (planejada em 2026-09-28)

- **Entrega:** "supino 4x8 80kg" fica guardado estruturado (exercício, séries, repetições,
  carga, unidade); recordes e volume por semana.
- **Escolhas de arquitetura previstas:**
  - **O modelo aponta, a regra decide:** o Gemini só extrai os campos do texto do dono. Volume,
    recorde e progresso são contas do código, com teste (skill `integracoes` §4).
  - **Registrar treino é uma escrita do dono, não uma memória:** não precisa do "sim" da D48, mas
    tem o `desfaz` e a linha no `registro`, como o calendário.
  - **Unidade explícita** (kg/lb), sem converter em silêncio.
  - **Nomes de exercício normalizados** num catálogo pequeno, que o dono corrige. "Supino" e
    "bench press" são um só.
- **Libs/repos a reaproveitar:** nenhuma. São tabelas e contas.

## Sessão 16 — coach 2: planejar e cobrar (planejada em 2026-09-28)

- **Entrega:**
  - o plano é ajustado pelos logs e pelo material do dono, que é citado;
  - dor relatada muda o plano e sugere fisioterapeuta ou médico se persistir, sem nunca
    diagnosticar;
  - "faz 5 dias sem treinar" chega por e-mail.
- **Escolhas de arquitetura previstas:**
  - **A cobrança é uma "pergunta agendada":** o Scheduler dispara, o motor lê os treinos e manda o
    e-mail (padrão das automações do Khoj e do resumo matinal do OpenJarvis).
    - Idempotente pela mesma reserva do lembrete (S9).
    - O texto enviado leva a marca do Viking e volta como conteúdo de terceiro (regra de
      2026-09-28).
  - **O material do dono é citado** (arquivo e trecho, da 14); sem citação, a resposta diz que é
    conhecimento geral.
  - **Dor e lesão:** uma regra fixa, testada, no texto de sistema e na resposta. Nunca
    diagnostica, ajusta o treino e sugere profissional se persistir. Não fica a critério do
    modelo.
- **Libs/repos a reaproveitar:** nenhuma.

## Sessão 17 — app 1 (planejada em 2026-09-28)

- **Entrega:** no iPhone (app web instalável), login com passkey/Face ID, chat e lembretes; a
  aprovação numa tela que o modelo nunca vê (D52).
- **Escolhas de arquitetura previstas** (seção 6 de `docs/fontes/pesquisa-roteiro.md`):
  - **O app é um segundo serviço, público,** que fala com o motor fechado da S10 pela conta de
    serviço dele. Toda rota do app começa pela checagem de sessão (skill `seguranca` §1).
  - **Aprovar = assinar um desafio ligado à ação.**
    - O servidor sorteia um desafio de uso único e grava junto o hash dos dados exatos da ação,
      com prazo.
    - O `get()` do WebAuthn exige verificação do usuário.
    - Quem liga a assinatura à ação é o **servidor**: o Face ID só mostra o nome do site, e a
      tela mostra os dados.
    - A extensão `txAuthSimple` foi retirada, e a SPC é só para pagamento.
  - **"Face ID" não é garantido:** com verificação obrigatória, o iPhone aceita o código do
    aparelho no lugar da biometria (https://passkeys.dev/docs/reference/ios/).
    - Aprovar prova que o dono estava com o iPhone desbloqueável, não que usou o rosto.
    - O texto da D52 diz "passkey" por isso.
  - **Não medido:** passkey numa PWA aberta da tela de início, porque não há fonte oficial.
    **Primeiro passo:** medir no iPhone dele. Se falhar, o login abre no Safari.
  - **Front sem build:**
    - htmx 2.0.11 (0BSD, ~17 KB) e JS puro na gravação e no passkey;
    - os arquivos são servidos pelo próprio backend, sem CDN, com `script-src 'self'` na tela de
      aprovação;
    - um framework com build seria manutenção sem ganho para um usuário só.
    - Gatilho: uma tela que o htmx não faça sem JS demais.
  - **A voz só alcança uma lista explícita de tools,** como o "expor à voz" do Home Assistant:
    arquivar, finanças e navegador em conta ficam fora da voz.
- **Libs/repos a reaproveitar:**
  - `webauthn` (py_webauthn, BSD-3, 3.0.1): `py3-none`, com desafio próprio e exigência de UV. Ele
    puxa pyOpenSSL, cuja 26.4 exige cryptography < 51 — anotar junto da D45;
  - `fido2`, da Yubico, como alternativa;
  - as skills `webapp-testing` e `frontend-design` do anthropics/skills, **lidas e copiadas, não
    instaladas**.

## Sessão 18 — app 2 (planejada em 2026-09-28)

- **Entrega:** notificação de lembrete no iPhone; apertar para falar e ouvir a resposta; gráfico
  de volume semanal dos treinos.
- **Escolhas de arquitetura previstas:**
  - **O push no iPhone não é o único aviso.**
    - Só funciona na tela de início, e o pedido tem de sair de um toque
      (https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
    - Há relatos de inscrição que some e de entrega que para.
    - Por isso o e-mail do lembrete continua, a inscrição se refaz a cada abertura do app, e uma
      falha de entrega aparece (skill `falha-ruidosa`).
  - **Voz: gravar → `generateContent` com o áudio → TTS,** reaproveitando o laço atual (execução
    automática das tools).
    - A Live API custa a mesma ordem (US$ 0,005 por minuto de entrada e US$ 0,018 de saída) e
      obrigaria a devolver as respostas das tools à mão.
    - Gatilho: a latência medida incomodar.
  - **Formato do áudio:**
    - o Safari 18.4+ grava WebM/Opus, e o Gemini aceita `audio/webm` e `audio/aac`, mas não
      `audio/mp4`;
    - mandar o tipo real (`MediaRecorder.isTypeSupported`);
    - a permissão do microfone não persiste na PWA: esperar um pedido por abertura;
    - reconhecimento de fala do navegador fica fora, porque falha na PWA.
  - **Gráfico com uPlot** (MIT, ~22 KB), servido pelo backend.
- **Libs/repos a reaproveitar:**
  - `pywebpush` 2.5.0 (MPL-2.0) puxa o **`http-ece`, que só tem sdist**, e o `tests/test_lock.py`
    recusa. Adaptar: `py-vapid` mais a cifra da RFC 8291 sobre o cryptography, ou uma exceção
    decidida pelo dono;
  - o `kevinbadi/jev-voice` como referência de voz, sem adotar.

## Sessão 19 — Claude, cérebro e revisor (planejada em 2026-09-28)

- **Entrega:** a segunda opinião do Claude num plano de treino, registrada com o custo; nenhuma
  trava muda por causa dela; um teste garante que nada de e-mail, finanças ou páginas vai para
  ele (D49).
- **Sem pedido à Garmin** (decisão do dono, 2026-09-28): o relógio entra pelo Strava na Sessão 21.
- **Escolhas de arquitetura previstas:**
  - **A entrada do Claude é montada de campos tipados,** nunca do histórico do chat, porque o
    histórico carrega o resultado das tools (e-mail, página, finanças).
    - O teste planta uma frase-sentinela num resultado de e-mail, de finanças e de página, e
      confere que ela nunca chega ao pedido do Claude.
    - Fatos de memória de origem externa ficam fora.
    - Resultado de busca na web também fica fora (termos do Google, S12).
  - **O revisor só anota:** a resposta dele vira texto para o dono, nunca uma chamada de tool nem
    uma mudança de trava.
  - **Custo:** o Sonnet 5 custa ~7× o 3.8 Flash na entrada (US$ 2/10). Sob demanda, com teto no
    `custos.py`, e o Batch (50% mais barato) para o que não tem pressa.
  - **Retenção:** a API guarda até 30 dias e não treina sem permissão
    (https://platform.claude.com/docs/en/manage-claude/api-and-data-retention). Retenção zero só
    por vendas, o que reforça a D49.
- **Libs/repos a reaproveitar:** `anthropic` 1.8.0. Só o `jiter` 0.17.0 seria novo no lock, e ele
  tem wheel cp312/cp313 para Mac Intel e Linux.

## Sessão 20 — auto-diagnóstico (planejada em 2026-09-28)

- **Entrega:** um relatório semanal dos erros do registro, e um rascunho de issue só com campos
  técnicos, criado no repo privado depois do código (D50). O conserto é feito numa sessão com o
  Claude Code, e o código passa pelo dono.
- **Travas:**
  - a issue é montada a partir de uma lista fixa de campos técnicos (classe do erro, módulo,
    trace), nunca do conteúdo;
  - o token só escreve issues daquele repo;
  - o texto da issue é conteúdo não confiável para quem for consertar.
- **Escolhas de arquitetura previstas:**
  - **O "trace" é o tipo da exceção e os quadros (arquivo relativo, linha, função) de
    `src/lifeos`, sem a mensagem da exceção.** A mensagem carrega conteúdo: o título de um evento,
    um assunto de e-mail, o erro do Google com o número do projeto. Do registro, só `operacao`,
    `estado`, `origem` e datas, nunca `parametros`, `resultado` nem `erro`.
  - **O Claude Code que for consertar lê a issue como dado;** a skill `evidencia` vale para ela.
- **Libs/repos a reaproveitar:** o `gh`, já usado, com um token fino que só escreve issues daquele
  repo.

## Sessão 21 — relógio pelo Strava (planejada em 2026-09-28; era "Garmin")

- **Entrega:** uma atividade real do relógio do dono chega ao coach, **pela API oficial do
  Strava**. O relógio (Garmin) sincroniza com o Strava, e o Viking lê de lá.
- **Por que Strava, não Garmin (D54, decisão do dono em 2026-09-28):**
  - o programa de desenvolvedor da Garmin é "only for business use"
    (https://developer.garmin.com/gc-developer-program/program-faq/), e uso pessoal muito
    provavelmente seria recusado;
  - o Strava oficial nasce em "single-player mode", só com a própria conta, com limites de 200
    pedidos por 15 min e 2.000 por dia (https://developers.strava.com/docs/getting-started/).
  - Continua recusada a biblioteca não oficial da Garmin, que usa a senha dele.
- **Primeiro passo:**
  - conferir com o dono que a sincronização Garmin → Strava está ligada na conta dele;
  - ler o acordo de API do Strava inteiro (https://www.strava.com/legal/api), sobretudo o uso com
    IA. A pesquisa só fez uma busca por palavras.
  - Hipótese, não conferida: um treino de musculação pode chegar ao Strava sem as séries e as
    cargas. Medir com uma atividade real dele antes de prometer o que o coach lê dali.
- **Escolhas de arquitetura previstas:**
  - **O webhook é uma rota pública do serviço do app, não do motor,** e confere a assinatura ou o
    token da plataforma na primeira instrução.
  - **A atividade entra pelo mesmo registro de treino da 15,** com a origem gravada.

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

- **Logo do Viking no e-mail** (pedido do dono na abertura da Sessão 8, 2026-09-28: "uma logo
  que podemos fazer pra ele bem depois"). Hoje o e-mail leva só a linha "Escrito pelo Viking
  (Assistente AI)"; uma imagem exige HTML ou anexo, que a D46 deixou de fora.

Com sessão desde 2026-09-28: paginação e séries (8b), notas buscáveis (13), migrations formais
(9), RAG (13–14), aprovação fora do terminal (17). Sem sessão: decidir se o Viking é só-checkout
ou pacote instalável de verdade (§9.3); anexos no e-mail; MCP para outros apps na nuvem (fica
local por stdio até existir autenticação); multiusuário (o dono decidiu: só ele); teste preventivo para o caso de uma função virar tool do Gemini e do MCP ao mesmo
tempo (armadilha do future-import) — sem bug real hoje (conferido na Sessão 3), só rede de
segurança para um cenário hipotético. Residuais da Sessão 4: o objetivo, os rótulos/valores
de campos e o histórico de ações ainda vão ao OpenRouter sem redação (ver
`docs/fontes/jev-typesafe.md`, "Egress e redação"); domínio em punycode/IDN: desde a Sessão 8 o host passa por NFKC (largura dupla, pontos e invisíveis viram o domínio de verdade); um domínio sósia em punycode é outro domínio e não é bloqueado;
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
