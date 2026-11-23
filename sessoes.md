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

- **Sessão:** **H2c2 — a coleta da wake word, 2 de 4, com música** (na seção "Sessões H2c1–H2c4";
  D71). **A H2c1 fechou em 2026-11-23: o Colab ficou com os 38 takes**, e nada se repõe. A H2c2 não
  pede firmware nem ferramenta nova. A H2 abriu em 2026-11-22: o ganho 2, o modo de coleta e o piloto, aprovado pelo agente do
  Colab. As 4 coletas vão uma por dia, quando o dono quiser. Entre elas, ou depois, a escolher com o
  dono: a **H1h** (o reforço da voz: o endereço de e-mail soletrado e achado pelo nome, a
  velocidade, com 13 s medidos do soltar ao `ok`, e o HA que reconheceu 1 de 2), a **H1b** (o som no
  aparelho, quando o MAX98357A chegar), a **H3** e a **15 — coach 1**. A H1 fechou no Mac em
  2026-11-22 (D70); a 14b, em 2026-11-21, e os alertas dela estão no ar desde 2026-11-22 ~22:55Z.
  As 3 mutações da voz, no VPS, morreram 3 de 3 (2026-11-22 ~23:02Z). A 11b (formulários) segue na
  fila, sem posição decidida.
- **Fora do repo, no estúdio:** o som do laptop sai pela Scarlett 2i2 (`~/.asoundrc` no laptop);
  sem ela plugada, a voz falha com erro no LED. A luz NEEWER RGB62 precisa de uma ESP32 com o
  ESPHome (o laptop não tem Bluetooth).
- **Revisão sênior e pesquisa do roteiro: feitas em 2026-09-28** (pedido do dono).
  - Fontes em `docs/fontes/pesquisa-roteiro.md`; as escolhas, na seção de cada sessão abaixo;
    regras e recusas na D53.
  - As 4 perguntas que tocavam decisões do dono foram respondidas no mesmo dia e já estão nas
    seções: a memória, que aprende sozinha só do dono (13, D48), o repo privado no começo da 10 (D50), o deploy sem
    credencial fixa (10, D47) e o relógio pelo Strava (21, D54).
- **Agora (2026-10-09):** 25 de 33 sessões fechadas (a 13b entrou na abertura da 13). O dono ainda não usa o Viking ativamente
  ("só vou usar ativo quando eu tiver ele em hardware ou em app/site com ele completo") e decidiu
  **manter a ordem**: 11d, 12–16 e então o app (17–18).
- **Ao abrir qualquer sessão (D45, desde a 7):** `uv lock --upgrade --dry-run` — há versão nova?
  Se houver, `uv lock --upgrade` num commit próprio, com a suíte antes e depois; e conferir o CI do
  último commit pelo SHA (`gh run list --commit <sha>`). Alerta do Dependabot aberto = atualizar
  aquele pacote primeiro.
- **Ler antes:** `AGENTS.md`, `PROGRESSO.md`, `docs/erros.md`, `docs/decisoes.md` (D45–D68), o
  roteiro de 2026-09-28 abaixo, e a memória do Claude (fuso e visão do dono).
- **Depende do dono:** as perguntas de abertura da 15 (o que registrar, como corrigir, o
  catálogo de exercícios). Na segunda 2026-10-12, depois das 9h no fuso dele, chega o primeiro
  resumo semanal (os fatos e o documento do teste, já esquecidos): conferir na primeira sessão
  depois disso, sem travar nada.

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

## Sessão 3b — MCP: calendário estruturado (feita em 2026-09-26; validada ao vivo em 2026-09-29, na 8b)

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

## Sessão 4 — privacidade e egress do navegador (feita em 2026-09-26; validada ao vivo em 2026-09-29, na 8b)

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
abertura. Dividir uma sessão em duas é decisão do dono; a 10, a 13 e a 17 são as candidatas (a 10 foi dividida em 10 e 10b pelo dono em 2026-09-29, e a 10b em 10b e 10c em 2026-09-30).

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

## Sessão 8b — pequenos (feita e testada no Mac em 2026-09-29)

- **Testado no Mac pelo dono (2026-09-29):** o "manda pra mim um e-mail apresentando quem você é"
  chegou formatado ("o email chegou bem sim - tudo certo"); a página da Wikipédia do CPF terminou
  com "🔒 Escondi dos modelos, antes de enviar a página: 2 CPF." e `[CPF]` no trecho (fecha a
  parcial 4); o roteiro da 3b criou pelo MCP o evento de dia inteiro, listou, buscou (completa),
  pediu para apagar, `viking aprovar` apagou com o código e `--conferir` deu 0 (fecha a 3b). A
  linha final do `pytest` no Mac não foi colada; o código novo estava lá (o contador só existe
  nele).

- **Feito no VPS (2026-09-29; plano e checkpoints no `PROGRESSO.md`):** e-mail em
  `multipart/alternative` a partir do texto aprovado (`gmail/formato.py`, D46 reaberta no "só
  texto" pelo dono); `buscar`/`por_data` seguem as páginas até 500 eventos e 10 páginas, e dizem
  quando param; o contador do que o envelope escondeu dos modelos (a régua do teste ao vivo da
  4); o roteiro da 3b (`scripts/calendario_mcp_ao_vivo.py`). Pedido novo do dono no meio: a
  Sessão 11b (formulários, D55).

- **Feito antes da abertura (2026-09-28):**
  - ~~o "manda pra mim" ao vivo~~: o dono testou no Mac, e saiu direto, sem perguntar o endereço;
  - ~~o nome de usuário do Mac no repo público~~: tirado das 3 linhas, a pedido do dono, com um
    teste que impede a volta (`tests/test_repo_publico.py`). O histórico do git ainda tem 3
    commits antigos com ele: reescrever exigiria force push, e isso se resolve com o repo privado
    na Sessão 10.
- **Primeiro passo (pedido do dono, 2026-09-28): o e-mail sai com formatação de verdade.**
  - **Medido:**
    - No Gmail do dono (captura de tela, 2026-09-28), um e-mail do Viking mostrou `**Gestão de
      Calendário:**` e as listas `- ` como texto cru. O Gemini escreve em markdown, e o Viking
      manda só `text/plain` (`envio.montar`; o teste exige uma parte só).
    - No VPS, com o Python 3.12.3: o `EmailMessage` com `set_content(texto)` e
      `add_alternative(html, subtype="html")` gera `multipart/alternative` com `text/plain` e
      `text/html`, `iter_attachments()` vazio, e `get_body(("html", "plain"))` escolhe o HTML.
    - **Não medido:** como o Gmail do dono mostra a parte HTML (esperado: a HTML, pela RFC 2046),
      e se ele transforma em link uma URL solta dentro do HTML.
  - **Plano proposto (confirmar com o dono na abertura; reabre a D46 só no "sem HTML", e o
    gatilho é o pedido dele):**
    1. **A fonte continua uma só:** o texto que o Gemini escreve e que o dono aprova no terminal.
       O código liga esse texto. As duas partes saem dele por uma **função pura** (`envio.montar`),
       testada, então o aprovado e o enviado não divergem.
    2. **Um conversor nosso, pequeno, só stdlib, sem lib de markdown:** `html.escape` em **tudo**
       primeiro; depois só um subconjunto:
       - `**x**` → `<b>`, `*x*` → `<i>`;
       - linhas `- `/`* ` → `<ul><li>`, e `1. ` → `<ol><li>`;
       - linha `# x` → `<b>x</b>`;
       - parágrafo → `<p>`, quebra simples → `<br>`.

       Nada de `<a>`, imagem, estilo externo ou HTML vindo do Gemini: um `<img src=…>` no texto
       sai escapado, como texto. Recusadas: `markdown`/`mistune`, que seriam dependência nova e
       deixam HTML cru passar sem configuração a medir.
    3. **A parte `text/plain`** perde os marcadores (`**x**` → `x`), para cliente sem HTML ler
       limpo. A linha "Escrito pelo Viking (Assistente AI)" vai no fim das duas, e no HTML em
       cinza. É o lugar da logo, depois.
    4. **O terminal mostra o texto fonte**, mais uma linha: "no Gmail, **negrito** e listas saem
       formatados".
    5. **A docstring das tools diz o subconjunto:** negrito, itálico, listas; sem tabelas nem
       títulos grandes.
    6. **Testes:**
       - entrada adversarial (`<script>`, `<img onerror>`, `"><a href=…>`, `**` sem fechar,
         `***x***`, lista dentro de parágrafo): nenhum `<a`, `<img`, `<script`, `<style`, `on…=`
         no HTML;
       - nenhuma parte de anexo;
       - a parte texto sem `**`;
       - o emoji com ZWJ inteiro;
       - o teste de "uma parte só" vira "exatamente `text/plain` + `text/html`, sem anexo".
       - Mutações: tirar o escape; deixar `<a` passar; manter `**` no texto.
    7. **No Mac:** o mesmo pedido da captura ("manda pra mim um e-mail apresentando quem você
       é") chega com negrito e lista de verdade.

- **Entrega:** uma série semanal de 300 ocorrências aparece inteira na busca; os testes ao vivo
  que faltam nas parciais 4 (redação de CPF/cartão numa página real) e 3b (tools de calendário
  do MCP contra o Google real, evento de dia inteiro conferido no Google Calendar) estão feitos.
- **Medido:** `calendar/service.buscar()` não tem `timeMax` e usa `singleEvents=True`. Lê só a
  1ª página (até 250 resultados), e uma série pode enchê-la em silêncio (§4.5).
- **Escolha de arquitetura prevista:** seguir o `nextPageToken` até um teto declarado. Quem bate no
  teto diz que a lista está incompleta, e quantos vieram (skill `falha-ruidosa` §2: um teto
  silencioso é uma interrupção). Janela com `timeMax` quando a pergunta tem prazo. Nenhuma lib
  nova.

## Sessão 9 — fundação de dados (feita e testada no Mac em 2026-09-29)

- **Feito (2026-09-29, detalhe no diário e em `PROGRESSO.md`; decisões D56 e D57):**
  - `lifeos/banco.py` é o único que abre o `viking.db`, com uma lista de migrations para o arquivo
    inteiro, ledger com checksum, transação, backup automático e recusa de banco mais novo;
    testado contra o formato de `5d0ace4` com dados;
  - a suíte não grava mais no banco real (gravava um "Pagar conta" por rodada desde a Sessão 5);
    `scripts/limpar_lembretes_de_teste.py` apaga o lixo no Mac;
  - lembretes com UUID, `reminders/interface.py` e o contrato que a S10 reusa;
  - `viking lembretes --enviar`: um e-mail por lembrete vencido em 24 h, uma vez só (reserva);
  - `mypy` como portão do CI nos módulos de dados;
  - "o que mora onde" na D57; as tabelas de memória foram para a S13 (dono).
- **Testada no Mac (2026-09-29):** o banco do dono migrou com o backup; a limpeza apagou 8
  lembretes de teste; o lembrete saiu por e-mail uma vez só, e a 2ª rodada não mandou nada.

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
  - **Tabelas de memória com cara de registro:** foram para o primeiro passo da S13 (dono,
    2026-09-29: sem consumidor até lá; com as migrations prontas, é uma migração nova).
- **Libs/repos a reaproveitar:** nenhuma lib de migrations. A régua numerada é pequena e é nossa:
  Alembic traria o SQLAlchemy só para isso.

## Sessão 10 — nuvem 1: o motor (feita e testada no Mac em 2026-09-30)

> **Dividida pelo dono na abertura (2026-09-29):** esta sessão entrega o chão da nuvem e um
> caminho de ponta a ponta pelos lembretes; o chat na nuvem foi para a **10b**. O plano com as
> medições da abertura está em `PROGRESSO.md`; as decisões, na D47 (revista) e na D58.
> - **Entrega da 10:** repo privado com o gitleaks no CI e no commit; projeto GCP só do Viking
>   (faturamento, orçamento de US$ 20 com alertas 50/90/100%) em `southamerica-east1` (o dono
>   volta ao Brasil em ~1 mês); Firestore passando o contrato de `tests/test_reminders_contrato.py`
>   no emulador; o motor no Cloud Run (0 instâncias mínimas, fechado por IAM, e o código recusa
>   quem não é o `viking-cli@`), com o `describe` mostrando o SHA; `viking lembretes --nuvem` no
>   Mac.
> - **Feito (2026-09-30, medido):** tudo acima no ar; `python scripts/nuvem.py deploy` → 9 provas
>   ✅ (o token pessoal do dono passou pelo IAM e o motor recusou; o `viking-cli@` recebeu 200);
>   228/228 mutações; o faturamento ligou depois de o dono desligar o de outro projeto (limite de 9
>   da conta). **No Mac (2026-09-30):** `1966 passed, 31 skipped` (os 31 = Firestore e gitleaks, que
>   o Mac não instala; conferido no VPS simulando o Mac: os mesmos 1966/31); `viking gmail
>   --login` entrou sem navegador; `viking lembretes --nuvem` respondeu da nuvem; `curl` sem
>   token → 403. O login do Google Cloud do Mac guardou como cota outro projeto do dono, e o
>   cliente a trocou pela do Viking, como desenhado.
> - **Deploy:** com o login do `gcloud` que o VPS já tem, por decisão do dono (D47 revista); todo
>   comando leva `--project` do Viking explícito, preso por teste. O ritual do token de 1 h saiu.
> - O texto abaixo é a proposta de partida de 2026-09-28, mantida como registro.


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

## Sessão 10b — nuvem 1b: o chat na nuvem (feita e testada no Mac em 2026-09-30)

> **Dividida na abertura (2026-09-30), pela data do Gmail:** a prova de que o token do Gmail não
> vence em 7 dias só vale depois de 2026-10-03, e no chat só o Gmail aprova com código (o clique
> do navegador fica no Mac). O Gmail e o código pela rede foram para a **10c**. Plano completo,
> com as medições da abertura, no `PROGRESSO.md`; decisões na D59.

- **Entrega:**
  - `viking chat --nuvem` no Mac conversa com o motor: o laço do Gemini roda no Cloud Run com a
    agenda, os lembretes e `acoes_recentes`; o histórico fica só no terminal do Mac e vai a cada
    turno (a nuvem não grava a conversa); o `viking chat` local continua igual;
  - a chave do Gemini e o token da agenda no **Secret Manager**, lidos pelo `viking-motor@` como
    arquivo de um volume (nunca variável de ambiente, imagem, `describe` ou log);
  - o registro de ações no Firestore quando a ação roda na nuvem (D57), pelo mesmo contrato do
    SQLite; a retenção de 30 dias pela TTL nativa;
  - o teto de gasto do Gemini no app, conferido antes de cada chamada: US$ 10/mês, até US$ 1/dia,
    no fuso do dono;
  - nenhuma linha com cara de aprovação vai ao Gemini na nuvem (na 10b, "nada a aprovar ainda");
  - o lembrete criado pelo chat da nuvem diz que o aviso por e-mail dele só vem na S11.
- **Respostas do dono (2026-09-30):** dividir em 10b e 10c; os dois chats convivem até a S11 (os
  lembretes ficam em dois lugares até a migração); teto de US$ 10/mês e US$ 1/dia; o histórico só
  no Mac; o lembrete da nuvem criado e avisado em voz alta; medir o turno com a chave do VPS.
- **Medido na abertura (2026-09-30):** 5 turnos reais (agenda e lembretes) levaram de 0,9 a 3,0 s,
  com 2 ou 3 chamadas ao Gemini, 13.224 tokens e ~US$ 0,0062 no total (estimativa pelas tarifas
  do `config`); o histórico chegou a 7 KB. O token da agenda do VPS, de 2026-09-20, renovou em
  2026-09-30: dez dias depois, o que indica que o app OAuth não está no modo "Testing" (onde vence
  em 7). Não substitui a prova do Gmail.
- **Feito (2026-09-30, no VPS e no ar):** tudo da entrega acima.
  - Deploy do `36fcd13` com 12 provas ✅: os segredos só como volume, a chave lê e o token da
    agenda renova no motor, e as consultas do registro passam na produção.
  - Um turno real no ar: 4,9 s e ~US$ 0,0015, sem conteúdo no log.
  - Diário de 2026-09-30.
  - **No Mac (2026-09-30):**
    - `2048 passed, 64 skipped`;
    - `viking chat --nuvem`: a agenda respondida, um lembrete de teste criado com o aviso do
      e-mail e concluído, o `confirma 1234` barrado sem ir ao modelo, e o `/custos` somando o
      gasto do VPS e do Mac;
    - `viking lembretes --nuvem` com a marca;
    - o `viking chat` local igual.

## Sessão 10c — nuvem 1c: o Gmail na nuvem e a aprovação pela rede (feita e testada no Mac em 2026-10-06)

- **Respostas do dono na abertura (2026-09-30, D60):** começar já a parte que não depende da
  prova, com a prova como portão antes de subir o token e publicar; 3 tentativas erradas cancelam
  a proposta (nos dois chats e no `viking aprovar`); pela nuvem, envio e limpeza exigem terminal
  interativo no Mac; só o Gmail (nada da S11); "verbo + 4 dígitos" barrado também no chat do Mac.
  Plano, medições e checkpoints no `PROGRESSO.md`.
- **Portão (adiado da 8, da 10 e da 10b; tem data):** provar que o login do Google não
  vence em 7 dias. `viking gmail --login` no Mac **depois de 2026-10-03**, sem abrir o navegador
  (o token do Gmail é de 2026-09-26). Se pedir login de novo, os tokens do Gmail não sobem (a
  verificação do Google, ou um escopo menor, antes). Indício a favor, medido na abertura da 10b:
  o token da agenda, do mesmo cliente OAuth, renovou dez dias depois de feito. **Não é a prova:**
  o `viking gmail --login` do dono em 2026-09-29 23:50 (Seattle) entrou sem navegador, mas o
  token tinha só 3 a 4 dias. Como não houve consentimento novo, a contagem dos 7 dias continua a
  partir de 2026-09-26.
- **Entrega:**
  - as tools do Gmail no chat da nuvem, com o token do Gmail no Secret Manager (subido do Mac, que
    é onde ele mora: o VPS não guarda token do Gmail, D57);
  - `confirmacao.py` atrás de uma interface, com o store no Firestore pelo mesmo contrato do SQLite;
  - o código de aprovação volta ao terminal num **campo próprio da resposta** (`ao_dono`), nunca
    no texto do modelo, e só é mostrado num terminal interativo; a linha `confirma NNNN` é lida
    pelo motor antes do modelo e não entra no histórico;
  - **limite de tentativas erradas por proposta** (hoje o TTY era a barreira);
  - o prazo do motor conferido contra o pior caso do Gmail (as esperas de cota somam até 126 s):
    um prazo de 220 s por turno na nuvem;
  - nenhuma linha com verbo de aprovação e 4 dígitos vai ao Gemini, nos dois chats.
- **Herdado da 10b:** o laço do chat no motor, o teto de gasto, o registro de ações no Firestore,
  os segredos como volume e `viking chat --nuvem`.

## Sessão 11 — nuvem 2: as mãos e os lembretes com uma fonte só (feita e testada no Mac em 2026-10-06)

- **Respostas do dono na abertura (2026-10-01, D61):**
  - esta sessão = as mãos e a migração; o Drive e as finanças vão para a 11c, depois de 04/10;
  - depois da migração, o Mac lê e grava lembretes **na nuvem, pelo motor** (uma fonte só);
  - o chat da nuvem usa o navegador **esperando no mesmo turno**, e a liberação de um clique fica
    no terminal do `viking maos`;
  - **publicar antes de 04/10 com o Gmail opcional** na nuvem (revê o "nenhum deploy antes da
    prova" da D60);
  - a migração de verdade **só com o e-mail da nuvem ligado** (antes, só o ensaio);
  - o limite de 20 e-mails em 24 h fica **separado** no Mac e na nuvem;
  - migra **tudo** (abertos, concluídos, o estado do envio).

  Plano, medições e checkpoints no `PROGRESSO.md`.
- **Entrega desta sessão:** `viking maos` e o navegador no `viking chat --nuvem`; a identidade
  conferida por rota no motor; o Gmail opcional na nuvem; os lembretes do Mac pela nuvem com a
  marca da migração 7; `viking lembretes --migrar`; a rota do envio pela nuvem (o agendador liga
  depois do portão da 10c).
- O texto abaixo é a proposta de partida de 2026-09-28, mantida como registro.

- **Adiantada (dono, 2026-10-01):** "quero adiantar outras coisas antes do dia 04": a 11 se
  abre, planeja e implementa **antes** do portão da 10c, que fica parada no C6 (a prova do
  token do Gmail a partir de 2026-10-04 em Seattle). Dependências que a abertura confere e
  pergunta ao dono: o lembrete por e-mail com o Mac desligado **envia pelo Gmail da nuvem**
  (depende do token do Gmail no Secret Manager, portanto do portão); o backup no Drive pede
  um escopo novo (`drive.file`, outro consentimento no Mac); `viking maos` e a migração dos
  dados não dependem do Gmail. O deploy do C7 da 10c publica o HEAD daquele momento: o
  trabalho da 11 tem de estar em commit limpo, com portões e CI verdes, ou o C7 espera.
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

## Sessão 11c — backup no Drive e a medição das finanças (feita e testada no Mac em 2026-10-07)

- **Separada pelo dono na abertura da 11 (2026-10-01, D61):** a 11 ficou com as mãos e a
  migração; o backup e a medição das finanças vieram para cá, depois da prova do Gmail.
- **Respostas do dono na abertura (2026-10-06, D63):**
  - o backup roda **na nuvem, todo dia**: uma 2ª tarefa do Cloud Scheduler, com o token do Drive
    (`drive.file`) no Secret Manager, subido do Mac como o do Gmail;
  - **entram** os lembretes e as notas, o registro de ações da nuvem (30 dias) e os gastos do
    teto. Ficam fora as confirmações, as tarefas das mãos e o `viking.db` do Mac;
  - **todas as cópias ficam**: o Viking nunca apaga nada no Drive;
  - a prova real é **no Mac, num banco vazio** (`viking backup --conferir`: um `viking.db`
    temporário, comparado lembrete por lembrete com a nuvem);
  - o aviso de falha sai **na abertura do `viking chat --nuvem`** (backup com mais de 48 h);
  - a medição da D51 foi feita (dois GETs, com o ok do dono) e deu "pode"; a mudança das finanças
    é a **Sessão 11d**.
- **Respostas do dono em 2026-10-07** ("ainda não estou usando o Viking ativamente, só vou usar
  ativo quando eu tiver ele em hardware ou em app/site com ele completo"):
  - o backup **só cria um arquivo quando algo mudou** (a rodada confere todo dia o mais novo do
    Drive; D63, item 3b);
  - o roteiro **mantém a ordem**: 11d, 12–16 e então o app (17–18), que chega com tudo dentro.

  Plano, medições e checkpoints no `PROGRESSO.md`.
- **Entrega:**
  - o backup diário no Drive, que restaura num banco vazio (provado no emulador e, uma vez, no Mac
    com o arquivo real);
  - `viking backup --restaurar` para um desastre (nunca sobrescreve);
  - a D51 medida e escrita.
- **Junto, no mesmo deploy:** as recusas sem terminal do Gmail falam com o dono e citam `viking
  chat --nuvem` (achado no teste do Mac de 2026-10-06).
- **Libs:** só o `googleapiclient` (já no lock).

## Sessão 11d — finanças na nuvem, só leitura (criada em 2026-10-06; feita e testada no Mac em 2026-10-07)

- **Por quê:** a medição da D51 (2026-10-06 22:27Z, na abertura da 11c) deu "pode":
  - `GET /smart-transfers/preauthorizations` → **403 `PAYMENT_INITIATION_NOT_ALLOWED`**. É o único
    caminho que paga "without user interaction" (docs da Pluggy), e a aplicação do dono não o
    alcança;
  - a documentação oficial diz que "Payments must be enabled specifically for your client" e que o
    produto é "exclusivo para clientes com assinatura" (Q&A verificado);
  - todo PIX avulso nasce `CONSENT_AWAITING_AUTHORIZATION` ("the user needs to authorize it in the
    institution"), com o link do banco vencendo em 5 min.

  O dono decidiu fazer a mudança numa sessão própria (2026-10-06).
- **A nuance que a abertura mede de novo:** `GET /payments/requests` → **200**, 0 pedidos. A
  listagem abre; se **criar** um pedido seria recusado não se mede sem escrever (proibido). Mesmo
  criado, um pedido só move dinheiro com a autorização do dono no banco.
- **Entrega prevista:**
  - as finanças no `viking chat --nuvem` por um **serviço isolado só de leitura**: um 2º serviço
    do Cloud Run, com conta e segredo próprios (`viking-pluggy`). Escrito em 2026-10-06 como "só
    nos `GET` da lista fechada de `financas/pluggy.py`", mas o cliente aceita **qualquer** caminho
    GET (lido em 2026-10-07): o plano trocou isso por 5 perguntas fechadas com texto pronto (D64);
  - o motor nunca vê a chave da Pluggy.
- **Perguntas para a abertura:**
  - o serviço isolado ou a chave no motor (a D51 diz isolado);
  - o que o chat da nuvem pode perguntar (saldo, gastos, busca, fatura: as mesmas tools do Mac);
  - se o `viking chat` do Mac continua com as finanças locais.
- **Respostas do dono na abertura (2026-10-07, D64):**
  - **serviço isolado**: o `financas` (2º serviço do Cloud Run), com a conta `viking-financas@`,
    a única que lê o segredo `viking-pluggy`; o motor pede texto pronto e nunca vê a chave;
  - o chat da nuvem pergunta **as 4 do Mac** (saldo, gastos, busca, fatura);
  - o `viking chat` do Mac **continua como hoje**, com as finanças locais;
  - a nuance da D51 **medida de novo** (18:46:45Z, os mesmos 2 GETs): igual a 2026-10-06;
  - o segredo **sobe do Mac** (os IDs das conexões só existem lá);
  - as provas automáticas do deploy **não chamam a Pluggy**; a `prova-financas` só com o pedido
    do dono.

  Plano, medições e checkpoints no `PROGRESSO.md`.
- **Feita e testada no Mac em 2026-10-07** (diário, mesma data; D64): o serviço `financas` no ar
  (`dda075f`), só o `motor@` o invoca e só o `financas@` lê o `viking-pluggy`; a `prova-financas`
  → as 2 conexões `UPDATED`; no Mac, `viking financas --saldo/--gastos/--fatura` local e
  `--nuvem` **iguais** pelo `cmp`, e o `viking chat --nuvem` respondendo as finanças.

## Sessão 11b — formulários: o Viking preenche, o dono envia (pedida em 2026-09-29)

- **Pedido do dono (2026-09-29):** "o Viking consegue preencher formulários pra mim? … ele teria
  que saber meu cpf e etc, mas ia ser bom ele conseguir responder e preencher formulários". Posta
  depois da 11 por decisão dele: as Sessões 10–11 mudam como o navegador recebe tarefas (o Mac
  vira as "mãos"), e o preenchimento passa exatamente por aí (D55).
- **Entrega:** num formulário de teste e num real escolhido pelo dono, o Viking preenche nome,
  CPF e endereço a partir de um pedido na conversa e **para antes de enviar**; o CPF não aparece
  em nenhum texto que saiu para o Gemini ou o OpenRouter (conferido na saída e no registro).
- **Decidido pelo dono (2026-09-29, D55):**
  - o cofre guarda **só dados pessoais**: nome, CPF, RG, data de nascimento, endereço, telefone,
    e-mail. Cartão, conta bancária e senha **nunca** (dinheiro continua proibido ao navegador,
    D38);
  - **o Viking só preenche; quem clica em "Enviar" é o dono**, na Chrome.
- **Escolhas de arquitetura previstas (confirmar na abertura):**
  - **Cofre local no Mac**, fora do repo e fora do banco que vai para a nuvem (arquivo com
    permissão 600, como os tokens em `secrets/`); nada disso vai para a memória da Sessão 13,
    que o Gemini lê.
  - **Os modelos veem só o apelido** (`{cpf}`, `{endereco}`): o Gemini e o modelo do Jev decidem
    "digitar {cpf} no campo CPF", e o subprocesso no Mac troca o apelido pelo valor na hora de
    digitar. A redação da Sessão 4 continua valendo, e o valor digitado em campo sensível
    continua redigido no que volta.
  - **Parar antes de enviar:** o freio de cliques (`_acoes_sensiveis`) ganha a classe "enviar
    formulário"; recusada sempre nesta tarefa, sem liberação por código.
  - Testes offline: um apelido que o modelo inventa (`{cartao}`) não vira nada; o valor nunca
    aparece no envelope enviado ao modelo; página que pede "digite seu CPF aqui" num campo que
    não é de CPF (injeção) — decidir na abertura quem casa campo com apelido.
- **Antes de preencher (2026-10-06, D62):** conferir se as correções do Jev para o `TYPE_TEXT` que
  digita no campo errado quando dois campos têm o mesmo rótulo (issues #191, #198, #202 do upstream)
  entraram no `main`; sem elas, um formulário com "Nome" duas vezes (titular e dependente) recebe o
  CPF no lugar errado. Em 2026-10-06 o `main` seguia no commit de 2026-09-18.
- **Perguntas para a abertura:** onde o dono cadastra os dados (comando `viking cofre`?); se o
  Viking pode perguntar um dado que falta e guardá-lo; quais formulários reais ele quer usar no
  teste.

## Sessão 12 — agente geral (planejada em 2026-09-28; feita e testada no Mac em 2026-10-08)

- **Feita (2026-10-08):** a busca com fontes, o Flash-Lite, o forte pedido pelo Viking, as cotas
  do dia e o tom, no ar (`ed92a0c`) e testados no Mac (o diário e a barra têm o detalhe; D65).

- **Abertura (2026-10-07), as respostas do dono (D65):**
  - **Modelos:** o 3.5 Flash-Lite no dia a dia, nos dois chats. O 3.8 Flash é o forte, e quem o
    pede é o próprio Viking (uma tool).
  - **Onde:** a busca e o forte só no chat da nuvem.
  - **Tetos:** o forte a US$ 0,30 por dia e a busca a 30 consultas por dia.
  - **Tom:** caloroso e direto.
  - **A busca na tela:** a resposta aparece igual, com as fontes à parte.
  - **Releitura das páginas e medições:** em `docs/fontes/pesquisa-roteiro.md`, seção 9.
    O que mudou desde 2026-09-28:
    - a busca nos 3.x cobra por consulta;
    - a combinação busca + tools só aparece na Interactions API;
    - o 3.8 continua a conversa do Flash-Lite (medido).
  - **O plano, por fases:** está no `PROGRESSO.md`.
  - **A 3ª rota do navegador (D62)** segue "medir depois da busca": fica para a próxima abertura
    que tocar o navegador, não para esta.

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
  - **Navegador na nuvem sem login (D62, 2026-10-06): terceira rota, a medir depois da busca.**
    Pergunta factual vai à busca; site com a conta do dono vai ao Mac. Sobra a tarefa interativa
    num site público com o Mac desligado. Se medir, na forma barata: o nosso Jev no motor dirigindo
    um navegador alugado sem perfil (Browser Use, US$ 0,02/h alegado), com o freio, a redação e o
    bloqueio; nunca o agente v4 deles (~US$ 1,64 por tarefa) nem o perfil da Chrome do dono.
- **Libs/repos a reaproveitar:** nada novo. O google-genai do lock já tem a busca e o
  `url_context` (era o 2.25.0 em 2026-09-28; 2.29.0 desde a abertura, em 2026-10-07).

## Sessão 13 — memória de fatos (planejada em 2026-09-28; feita e testada no Mac em 2026-10-08)

- **Feita (2026-10-08):** a memória de fatos no chat da nuvem (anotar sozinho só do que o dono
  digita, lembrar por significado, "esquece isso", a troca, o `viking memoria`, o resumo semanal e
  o backup versão 2), no ar (`a964aff`) e testada no Mac (o diário e a barra têm o detalhe; D66). A
  mais, no fechamento: o 429 do serviço de finanças repetido pelo motor, os testes de tempo que
  medem o crescimento, e a regra que mede o "anotado" do modelo (a prosa não é confiável: vale a
  linha 📝).

- **As respostas do dono na abertura (2026-10-08; D66):**
  - a memória mora **na nuvem** (Firestore), e só o `viking chat --nuvem` anota e lembra; o
    `viking chat` do Mac fica sem memória, e o `viking memoria` do Mac fala com o motor. Por isso o
    "primeiro passo" abaixo (a migração no `viking.db`) **não acontece**: as tabelas viram a coleção
    `memoria` do Firestore, com as mesmas regras (só se acrescenta, `invalida_em`, a origem);
  - **dividida:** a 13 fica com os fatos e o resumo semanal; as **receitas** vão para a 13b;
  - o extrator roda em **toda** mensagem do dono, em paralelo com a resposta;
  - **embeddings agora** (`gemini-embedding-2`, 768 dimensões, `find_nearest` do Firestore);
  - **nunca anotar:** valores das finanças, dados de outras pessoas e planos com data (além de
    senha e código de aprovação, sempre);
  - **"esquece isso"** tira a última anotação da conversa na hora, dá para desfazer, e o texto some
    de vez em 30 dias; um fato específico se esquece pelo `viking memoria`;
  - **até 8 fatos** por resposta;
  - o **resumo semanal** chega na segunda às 9h (fuso do dono), só se houve anotação.

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
- **Primeiro passo (vinda da 9, decisão do dono em 2026-09-29):** as tabelas de memória com cara
  de registro, numa migração nova de `lifeos/banco.py` (a lista única da 9). Só se acrescenta
  linha; um fato substituído ganha `invalida_em` e aponta para o que o substituiu (ideia do
  Graphiti); a origem e a mensagem de onde veio ficam gravadas. Ficaram fora da 9 porque não
  tinham consumidor: aqui nascem já com o uso real.
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

## Sessão 13b — receitas (criada em 2026-10-08, na abertura da 13; feita e testada no Mac em 2026-10-09)

- **Feita (2026-10-09):** a receita nasce proposta pelo extrator (📋, com todos os passos), se
  guarda com `guarda receita`, roda com `roda NOME`, aparece no `viking memoria` (`--receitas`),
  no resumo de segunda e no backup v3; no ar (`2c78d8b`) e testada no Mac (o diário e a barra
  têm o detalhe; D67). A mais: o desfazer de uma cadeia de trocas, também nos fatos da 13. Fica
  vigiado (o dono): no ensinar, o modelo às vezes faz os passos de leitura na hora.


- **Por quê:** o dono dividiu a 13 na abertura: os fatos e o resumo semanal na 13, as receitas aqui,
  logo depois.
- **Entrega:** uma receita (um procedimento que o dono ensina, como "quando eu pedir o resumo da
  semana, faz X, Y e Z") nasce **só de mensagem do dono e com pergunta** (D48), e é reusada **sem
  ganhar permissão nova**: cada passo continua com as tools e as aprovações de sempre (o código de
  um envio a outra pessoa, o da limpeza, o freio do navegador).
- **Parte da 13:** a coleção `memoria`, o extrator, o filtro de forma de ordem e o `viking memoria`
  existem; a receita é outro tipo de anotação, que o extrator propõe e o dono confirma.
- **As respostas do dono na abertura (2026-10-08, ~21:55Z; D67):**
  - **nasce proposta:** quem anota (o extrator, que lê só a mensagem digitada) propõe numa linha
    própria, com todos os passos; só vira receita quando o dono digita `guarda receita`, lido antes
    do modelo; ignorada, a proposta morre em 1 dia;
  - **roda pelo nome:** `roda NOME` (o nome ou o começo único dele), lido antes do modelo; os
    passos vão ao modelo como texto do dono;
  - **passos que enviam, apagam ou arquivam podem**, com a aprovação de sempre (o código do envio
    a outra pessoa a cada rodada);
  - **a 13b inteira** nesta sessão (nascer, guardar, listar, rodar, esquecer, desfazer);
  - **no `viking memoria`**, marcadas (📋), e `--receitas` com os passos inteiros;
  - **até 8 passos** (e 800 caracteres no total);
  - **o resumo de segunda** mostra as receitas guardadas e esquecidas na semana.
- **Técnico (agente):** coleção própria `receitas` (sem vetor; a busca é pelo nome), com a TTL em
  `apagar_em`; um filtro próprio (a forma de ordem dos fatos recusaria toda receita); o backup
  versão 3. O plano inteiro está no `PROGRESSO.md`.
- **Vindo do fechamento da 13 (2026-10-08):** a regra `turno._MEMORIA` foi medida (o modelo dizia
  "anotado" sem ser quem anota; D66, "Como ficou"). Se a 13b mexer nela (uma receita também se
  anota), meça de novo com frases inventadas e leia as respostas inteiras: a régua de palavras
  errou duas vezes (`docs/erros.md`, classe 7). O primeiro resumo semanal sai na segunda
  2026-10-12, depois das 9h no fuso do dono (`estado/resumo-2026-W42`): conferir na abertura que
  chegou.

## Sessão 14 — documentos (planejada em 2026-09-28; feita e testada no Mac em 2026-10-09)

- **Feita (2026-10-09):** `viking documentos --aprender ARQUIVO --tema T` manda um `.md`/`.txt`
  (até 1 MB); no chat da nuvem o modelo consulta só o tema da pergunta, cita o arquivo, e a
  linha 📄 diz o que ele achou; listar, esquecer, desfazer e substituir; o backup v4 e o resumo
  de segunda com os documentos; a avaliação fixa (recall@5 = 1,0 e MRR ≥ 0,95, o limiar do
  dono). No ar (`56f0807`) e testada no Mac (o diário e a barra têm o detalhe; D68). A mais: a
  redação que trocava um pedaço de ~1 em mil ids por "[cartão]". Aceito pelo dono: dois envios
  simultâneos do mesmo arquivo podem tirar o documento da busca (`--desfazer` o devolve).

- **As respostas do dono na abertura (2026-10-09, ~03:15–03:31Z; D68):**
  - o material é **`.md` ou `.txt`** (o Docs exporta os dois; lido na página da API do Drive):
    **sem PDF**, e o `pypdf` não entra (medido: 1 pacote, mas 101 avisos de PDF malformado);
  - chega por **`viking documentos --aprender ARQUIVO --tema T`** no Mac, sem escopo novo do Google;
  - **a 14 inteira:** aprender, consultar com citação, listar, esquecer, desfazer, substituir,
    backup e a avaliação fixa;
  - **um documento nunca vira fato** (nem sugestão): a D48 fica mais estrita do que permitia;
  - **busca por tema** ("mais precisa, mais rápido e… menos tokens"), escolhido **pelo modelo**
    numa tool só de leitura (`consultar_documentos(tema, pergunta)`), só no chat da nuvem;
  - **até 5 trechos** por consulta; **até 1 MB** por documento;
  - **esquecer como os fatos** (some na hora, desfaz, apaga em 30 dias), e **o backup leva o
    texto** (o gatilho da D63 de ~1 MB passa a ~20 MB);
  - **o mesmo arquivo no mesmo tema substitui** o anterior (marcado, desfazível);
  - o limiar da avaliação fixa: perguntado no C1, com os números medidos.
- **Técnico (agente):** coleções `documentos` e `trechos` (o vetor 768 no trecho, com o tema e o
  `ativo`), um índice vetorial composto (`tema_lido`, `ativo`, `vetor`), as TTLs nas duas,
  aprender em duas fases (nada pela metade na busca), cortes por parágrafo com o título e as
  linhas, o backup versão 4. O plano inteiro está no `PROGRESSO.md`.

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
  - **Um fato que só um documento diz vira, no máximo, sugestão** que o Viking pergunta (D48). Veio
    da abertura da 13 (2026-10-08): lá não há documento ainda, e aqui nasce o primeiro produtor.
  - **O limiar da avaliação é do dono,** medido antes de combinado.
- **Libs/repos a reaproveitar:** medir na abertura um leitor de PDF só com wheel (a árvore e o Mac
  Intel, se ler lá). Nenhum candidato aprovado ainda.

## Sessão 14b — manutenção da mini-auditoria (criada, feita e testada no Mac em 2026-11-21)

- **Por quê:** a mini-auditoria de 2026-11-21 (`docs/auditorias/mini-auditoria-2026-11-21.md`)
  achou, depois de 43 dias sem push: 20 vulnerabilidades em 8 pacotes da imagem (a `certifi`
  crítica, no TLS de saída), 2 testes vermelhos por data fixa, nenhuma auditoria agendada, nenhum
  alerta se o envio de lembretes ou o backup parar, o fuso da nuvem ainda em Seattle (o dono já
  mora em SP) e `roles/editor` na conta padrão do Compute.
- **Entrega:** o lock atualizado (D45) e no ar; o teste com o relógio real; a prova do valor do
  fuso no `deploy`; os passos `alertas` (canal de e-mail + 2 políticas de ausência) e `editor` no
  `scripts/nuvem.py`; o CI semanal; o repo público (D58 revista, item 3, decisão do dono).
- **O plano por checkpoints:** `PROGRESSO.md`.

## Sessão H1 — a voz do estúdio: ESP32 → servidor de casa → motor (criada em 2026-11-21; aberta no mesmo dia; fechada no Mac em 2026-11-22, com as 5 verificações do E2E)

- **Reabre a trilha de hardware (D2) por decisão do dono (2026-11-21):** "faz a manutenção
  primeiro, depois o ESP32". Vem antes da 15. Decisões da abertura: D70.
- **Mudou na abertura (respostas do dono, 2026-11-21):** o aparelho **não é de pulso**, fica fixo
  no estúdio ("quero todas as funções do Viking lá + controle de HA"); responde **por voz, no
  alto-falante do laptop de casa** até o amplificador chegar; botão externo já, palavra de ativação
  depois ("é o perfeito para mim"); a voz alcança **tudo**, "sem senha também", com um jeito de
  desligar; o HA é **Container (Docker)**, sem add-ons.
- **Entrega:** segurar o botão, falar, ouvir a resposta no laptop. "Liga a luz do estúdio" é do HA
  (local, sem nuvem); o resto vai ao Viking; um e-mail para outra pessoa pede **dois toques no
  botão**; o interruptor "Viking voz" do HA desligado corta tudo antes da nuvem.
- **O desenho (D70):**
  - firmware próprio (Arduino-ESP32 3.x, como o teste do mic) em `/root/esp32/projects/viking-voz`:
    grava enquanto o botão está apertado e manda o WAV à ponte por HTTPS na rede de casa, com o
    certificado da ponte fixado e um token do aparelho (`src/segredos.h`, fora do git);
  - a ponte `viking casa` (`src/lifeos/casa/`) no laptop: confere o interruptor do HA, transcreve
    pelo motor, tenta o HA local (`/api/conversation/process`, agente `conversation.home_assistant`)
    e só no `no_intent_match` chama o turno do Viking; toca a resposta com `aplay`;
  - o motor ganha `/voz/ouvir`, `/voz/responder`, `/voz/falar` e `/voz/saude`, só para a conta
    `viking-casa@` (e ela só nessas); o canal "voz" tira a busca na web (os termos do Grounding
    mandam *mostrar* as sugestões) e liga o `interativo` pelo canal, porque o botão é o canal
    físico de aprovação;
  - a `viking-casa@` só invoca; a chave é um par gerado **no laptop**, e só o certificado público
    sobe ao Google (`keys upload`); `scripts/nuvem.py casa-cortar` a desliga em segundos.
- **O plano por checkpoints:** `PROGRESSO.md`.
- **O que já existe, medido em 2026-11-21 (antes da abertura):**
  - **Um workspace de firmware no próprio VPS, `/root/esp32`** (git próprio, branch `main`; o
    `CLAUDE.md` e o `README.md` de lá são as regras). A VPS compila e **grava a XIAO que está
    plugada no Mac do dono** por um túnel SSH reverso que o Mac abre (porta 443) até um servidor
    RFC2217 (`127.0.0.1:4000` no VPS). Só pelo `bin/esp` (`esp build`, `esp flash`, `esp log`,
    `esp reset-log`, `esp check`; nunca `pio`/`esptool` direto); **um cliente por vez na placa**;
    túnel fora do ar = pedir ao dono `cd ~/esp32-mac && ./service.sh status` no Mac. A rede do Mac
    é corporativa (inspeção TLS, Tailscale bloqueado): não propor contornar.
  - **Skills de lá** (`/root/esp32/.claude/skills/`, não carregadas no LifeOs, mas legíveis):
    `esp32-development` (o contrato: placa exata, datasheet antes do pino, uma camada por vez,
    "pronto" só no limite físico, segredo de Wi-Fi nunca no git), `electronics`,
    `embedded-systems`, `tinyml-keyword-spotting`, `edge-model-deployment`,
    `ml-experiment-discipline`.
  - **O projeto `projects/viking-hardware-teste`** (Arduino-ESP32 3.x pelo pioarduino, `ESP_I2S.h`):
    o INMP441 já ligado e lido a 16 kHz (VDD→3V3, GND, L/R→GND, SCK→D8/GPIO7, WS→D9/GPIO8,
    SD→D10/GPIO9), um LED externo em D6/GPIO43, o da placa em GPIO21 (ativo em baixo), e a
    detecção de palma dupla. O MAX98357A ainda não aparece ali (a conferir: ligado? que pinos?).
  - **A ponte de casa** (dito pelo dono em 2026-11-21): um laptop antigo com Debian, Home Assistant
    e um túnel ("opentunnel") instalados, sempre ligado. A conferir na abertura: o VPS alcança esse
    laptop? Por qual caminho? Ele roda Python 3.12? Qual é o túnel exatamente? O ESP32 e o laptop
    ficam na mesma rede Wi-Fi?


## Sessão H1b — o som no aparelho e a fala mais rápida (criada em 2026-11-21, na abertura da H1)

- **Quando:** o MAX98357A chegar (o dono vai comprar: um só basta para voz, fonte USB de 5 V e 2 A).
- **Entrega:** a resposta sai do próprio aparelho (I2S para o MAX98357A; os dois alto-falantes do
  Acer em série se forem de 4 Ω cada, conferido na etiqueta ou no multímetro antes de ligar).
- **Junto:** "pensar enquanto fala" (o turno do Gemini em streaming, falando frase a frase enquanto
  gera), se a latência medida na H1 incomodar.

## Sessão H1h — o hardening da voz (criada em 2026-11-22, no E2E da H1, a pedido do dono)

- **Por quê (medido no E2E de 2026-11-22):** um e-mail para outra conta do dono saiu **duas vezes**
  para um domínio errado ("team" no lugar de "teen"): na 1ª o teto de 15 s cortou a soletração
  (consertado na H1: 30 s com aviso no LED); na 2ª, dentro do teto, a transcrição ou o modelo
  trocou o domínio, e o dono aprovou sem entender a leitura falada. A proteção dos dois toques só
  vale com uma leitura que se entende.
- **O que entra (a decidir com o dono, nesta ordem):**
  1. **Soletrar todo endereço falado** (na ponte, `casa/ponte.texto_para_falar`: "breno, arroba, tê,
     é, é, ene…"), com teste; só no laptop, sem deploy. Recusado na H1 como item do motor; o dono
     pediu agora para o hardening;
  2. **Achar o destinatário pelo nome**, só entre os endereços para os quais o dono **já mandou**
     e-mail (os Enviados: o dono os escolheu); nunca pelo remetente de e-mails recebidos (um estranho
     manda de um endereço parecido e vira o "contato"). Hoje a busca mostra só o remetente; o
     destinatário de um enviado é código novo;
  3. pela voz, um e-mail para um endereço **que nunca recebeu e-mail do dono** é recusado (ou só
     pelo chat), enquanto o 2 não existir;
  4. **por que o HA reconheceu "que horas são" uma vez e não a outra** (sem guardar a transcrição:
     registrar só se o HA reconheceu e qual intenção);
  5. a **velocidade** (5,5 s do soltar ao `aplay`): medir cada etapa na ponte e o 1º som, juntar as
     idas ao motor, comparar `flash-lite` e `transcribe` com a voz do dono, o preço do motor
     sempre acordado;
  6. a **saturação** da fala de perto (189 amostras numa fala alta, com o ganho 4): ver se atrapalha
     a transcrição antes de mexer no ganho (o ganho muda o treino da wake word: avisar o agente do
     Colab antes).

## Sessão H2 — a palavra de ativação (criada em 2026-11-21, na abertura da H1; aberta no Mac em 2026-11-22)

- **Entrega:** "Hey Viking" acorda o aparelho sem o botão (o botão continua, e os dois toques
  continuam sendo a aprovação).
- **Como:** pelas skills `tinyml-keyword-spotting`, `edge-model-deployment` e
  `ml-experiment-discipline` do `/root/esp32` (dataset com o INMP441 final, split por gravação,
  falsas ativações por hora como a métrica). Comparar com o microWakeWord do ESPHome antes de
  treinar do zero.
- **Decidido pelo dono (2026-11-22, na H1):** a frase "Hey Viking", dita "VI-king" (à
  portuguesa); só o dono ativa; **no máximo 1 ativação falsa por dia**; latência até ~1 s; a
  coleta só **depois de fechar a H1**. Ativar só começa a gravar, nunca aprova (D26/D70).
  **"Só o dono ativa" não é requisito** (decidido em 2026-11-22, depois de o agente do Colab
  explicar que o microWakeWord não reconhece quem fala: qualquer voz acorda, e isso só grava).
- **O treino** (microWakeWord, streaming int8) roda no Colab, por outro agente (o Claude in Chrome
  do dono), com o notebook no Drive dele. O que ele pediu deste lado, respondido em 2026-11-22:
  - um **modo de coleta** no firmware (WAV 16 kHz/mono/16 bits pelo mesmo caminho do mic, pela USB
    até o Mac, um contador por bloco para provar que nada caiu; de perto pelo botão, de longe por
    gravação contínua cortada pela energia; os arquivos em `~/viking-wakeword/`, fora do repo, e o
    dono sobe para o Drive). Os dados de voz nunca vêm ao repo;
  - a **paridade do frontend** (micro_frontend: 30 ms/10 ms, 40 canais): ele manda um WAV de
    referência e as features dele, e a placa roda o mesmo WAV, injetado, e devolve as dela;
  - o **TFLM no arduino-esp32 4.0.0** (as ops de variável de recurso: VarHandle, ReadVariable,
    AssignVariable, CallOnce) **não conferido**: é o primeiro passo;
  - o orçamento (limites meus, a medir com a Wi-Fi e o TLS ligados): modelo + frontend ≤ 300 KB
    de flash; arena ≤ 40 KB (teto 64 KB) na SRAM interna; ≤ 10 ms por passo de 30 ms no core 1;
  - a decisão: média de 5 probabilidades > limiar, 2 s de espera, o limiar no NVS, suspensa
    enquanto o aparelho fala e durante um turno.
- **O que o agente do Colab mandou de volta (2026-11-22; dito por ele, não conferido aqui):**
  - o frontend do treino é o `pymicro-features` 2.0.2, com os parâmetros do
    `preprocessor_settings.h` do ESPHome; o **pacote de paridade** (`parity.zip`: o WAV de
    referência, o CSV das features dele e um README) está com o dono. O retorno que ele espera é o
    CSV das features **do chip** para esse WAV;
  - as ops do modelo streaming (a lista do resolver do `micro_wake_word` do ESPHome), a validar
    no TFLM primeiro: CallOnce, VarHandle, ReadVariable, AssignVariable, Reshape, StridedSlice,
    Concatenation, Conv2D, DepthwiseConv2D, Mul, Add, Mean, FullyConnected, Logistic, Quantize,
    AveragePool2D, MaxPool2D, Pad, Pack, SplitV; com `MicroResourceVariables`;
  - a entrada int8 do modelo: `((raw*256+333)/666)-128` (a escala e o zero_point reais virão no
    README do modelo; conferir lá, não aqui);
  - a coleta aceita como proposta (perto pelo botão; 1 m e 1,5 m contínuo, cortado pela energia;
    200 ms das pontas fora; os takes saturados marcados): 150+ positivos, 16+ h de negativos com 8+
    h só para teste; a voz do aparelho (o TTS original e o tocado no Mac) quando o dono autorizar.
- **O contrato da 2ª mensagem (2026-11-22, a do notebook v1.3; dito por ele):** a entrada do modelo
  `[1, 3, 40]` int8, escala 0,101961 e zp -128 (o valor do frontend × 0,0390625, **não** a fórmula
  do ESPHome); a saída uint8, escala 1/256, zp 0; 13 ops (ASSIGN_VARIABLE, CALL_ONCE,
  CONCATENATION, CONV_2D, DEPTHWISE_CONV_2D, FULLY_CONNECTED, LOGISTIC, QUANTIZE, READ_VARIABLE,
  RESHAPE, SPLIT_V, STRIDED_SLICE, VAR_HANDLE); a arena até ~10,9 KB (o teto dele, sem reuso); o
  modelo de fumaça (60,8 KB) não vale como qualidade. **Divergências respondidas:** o CSV int8 do
  pacote usa a fórmula do ESPHome (pedi um novo, com a regra de arredondamento); o firmware
  **trunca** e só então multiplica pelo ganho (as amostras são múltiplas de 4), o que a augmentation
  dele tem de imitar; distância até 4 m e outras vozes são extras que o dono decide.
- **A primeira etapa (2026-11-22, no Mac):**
  - o ganho 2 congelado; o modo de coleta (na época, `env:xiao_s3_coleta`; desde 2026-11-23, o
    firmware único) e o `coleta.py`;
  - a USB medida (0 lacunas em 3.697 quadros);
  - **o piloto:** 1 min de sala e 10 takes de 0,5 a 1,5 m, todos contínuos, no
    `~/viking-wakeword/piloto_2026-11-22.zip` para o Colab;
  - o firmware de uso de volta com o ganho 2, conferido no ar.

  **Falta:**
  - a coleta grande, em 4 sessões (H2c1–H2c4, logo abaixo; D71);
  - o TFLM e o micro_frontend no arduino-esp32 4.0.0, com o CSV de paridade do chip contra o
    `parity_v2`;
  - a voz do aparelho, com o ok do gasto.
- **A resposta do agente do Colab ao piloto (parte 5, notebook v1.6, 2026-11-22; medido por ele):**
  - **pode seguir para a coleta grande.** O ganho 2 se confirmou na grade (todas as amostras
    pares), com o pico de 11.342 e 3× de folga, e a relação sinal-ruído na faixa de 22,5 a
    32,5 dB;
  - **62% da energia da sala fica abaixo de 125 Hz** (o ronco, perto do corte de ~12,7 Hz do
    nosso passa-alta), que o frontend não vê. O passa-alta fica como está. **Reabre** se as
    saturadas da coleta grande se concentrarem em graves (porta, caminhão, música). Os níveis
    se trocam sempre **na faixa** (125–7500 Hz), porque no tempo o ruído sai ~1,6× maior;
  - o ronco revelou um defeito no cortador de silêncio dele, já corrigido. As faixas dele com o
    ganho 2, na faixa: SPEECH_RMS 350–6000 e MIC_NOISE_RMS 40–120;
  - o FALE é silencioso: o take 10 foi barulho solto. Ele pediu que o resumo aponte os takes
    com barulho antes da fala. Feito: o `pre_fala` mede, na faixa, a janela de 0,45 a 0,70 s
    sobre o fundo do take, com o limite de 1,4. No piloto deu 1,01–1,08 em 9 takes e 1,67 no
    10, como ele mediu;
  - **as sessões:** as 16 h de negativos em 3–4 sessões (dias, horários e condições
    diferentes) e os 150 takes em vários dias, uma subpasta datada por sessão.
- **A resposta do agente do Colab à coleta 1 (notebook v1.8, 2026-11-23; medido por ele, salvo onde
  dito):**
  - **a sessão 1 está aprovada**, com 3 takes para o dono ouvir: 004, 007 e 026. Se saírem, 2
    reposições a 50 cm e 1 a 1,5 m;
  - **a sala mais quieta** perdeu chiado agudo (−11 dB em 4–7,5 kHz, −0,6 dB em 250–500 Hz): ele lê
    como ventoinha; o dono disse que a ventoinha do Mac estava ligada no piloto (não medido). MIC_NOISE_RMS 8–60, e a calibração dele virou por sessão. Anotar no
    LEIA-ME se o ar-condicionado estava ligado;
  - **a régua do barulho antes da fala** era sobre o fundo; a nova é sobre a fala do take (25%).
    **Feito no `coleta.py` em 2026-11-23**; conferido por nós nos dados: 0 marcados em 38, 15 e 10
    (maior 12,8%, o take 010 do piloto). O limite novo também não marca mais esse take;
  - o cortador dele (do primeiro ao último som) dava 2,55 s de mediana; agora corta no segmento
    dominante: 0,64–1,53 s;
  - **as parecidas:** fora do treino, sem apagar, as da coleta 1 "Hey King" (take_001) e "Vai, King"
    (take_010): a lista está em `~/viking-wakeword/fora_do_treino.md`. Nas próximas, palavras com "Vi"
    e 2 a 3 repetições de cada frase;
  - **decisões do dono (confirmadas por ele em 2026-11-23, D72):** "Rei Viking" e "Ei, Viking" ativam
    (gravadas, vão para `real_positive`); "Hey King" e "Vai, King" tanto faz; o aparelho em uso
    registra as quase-ativações (ver "Depois do modelo na placa");
  - **os suspeitos, ouvidos pelo dono (a 2ª mensagem, notebook v2.1):** 004, 007 e 026 são um "Hey
    Viking" só, em cadência lenta (1,53–1,56 s); o 015 é um "Hey Viking" e uma **tosse** 2× mais
    alta, que o cortador dele guardava como positivo. Ele passou a só aceitar trechos vozeados;
  - **nosso, a partir disso:** ele disse que os 3,0 s depois do FALE resolvem o fim do 007, mas o 007
    foi gravado com eles. Medido: 007 e 008 com menos de 0,3 s de sala no fim, e o dono começou até
    2,05 s depois do FALE. O take passou a ter **4,0 s** depois do FALE, e o `anotar` nasceu;
  - **divergências nossas:** o `parte_007` não está no zip que o dono recebeu (0 entradas), e o LEIA-ME
    dele o cita; ele leu outra cópia. E 4 h sem nenhuma falsa dão um limite de 12 por dia de 16 h (3/T),
    não 20.
- **O pacote de paridade** está em `~/viking-wakeword/parity/` no Mac (fora do repo; o WAV é
  sintético, o SHA-256 confere com o README); o `.gitignore` recusa `*.wav`, `*.zip` e
  `viking-wakeword/` desde que um `parity.zip` caiu solto na raiz do repo.

## Sessões H2c1–H2c4 — a coleta grande da wake word (planejadas em 2026-11-22; D71)

**O total:** ~4 h do estúdio normal, 150 "Hey Viking" (38 + 38 + 37 + 37) e ~60 frases
parecidas. São 4 sessões, **cada uma num dia e numa condição diferentes**, e cada uma em pastas
próprias:
- `real_positive/AAAA-MM-DD_cN_takes`;
- `real_negative/AAAA-MM-DD_cN_parecidas`;
- `real_negative/AAAA-MM-DD_cN_estudio`.

A H2c4 inteira fica guardada para o teste. **O teste do treino é por sessão inteira** (o Colab,
2026-11-23, notebook v2.2): uma pasta por sessão e nunca dois dias na mesma, e o `coleta.py` recusa a
pasta de outro dia (o dia vira às 6 h). Um take duvidoso (o 007 da coleta 1) fica só no treino.

**O que vale nas 4:**
- **Antes de gravar, o roteiro na tela e o "vai" do dono.** Os takes rodam numa janela do
  Terminal que espera o Enter, e eu leio os resultados nos arquivos.
- **A ordem é sempre a mesma:** os takes (~5 min), depois as parecidas (~3 min), depois o estúdio
  normal (1 h). O estúdio normal roda sem a pessoa olhar para a tela, com `caffeinate -i` para o
  Mac não dormir. Um cliente por vez na porta.
- **Durante o estúdio normal, o dono não diz "Hey Viking"** (fala, trabalha e toca música à
  vontade). Se escapar, ele me diz a hora, e eu corto o trecho.
  **Na hora do estúdio normal, o dono não fica parado nem calado** (dito por ele em 2026-11-22): é
  um dia comum de estúdio, e é o que ensina o aparelho a não acordar sozinho. **Eu aviso cada
  troca:**
  - o roteiro e o "vai" antes dos takes;
  - "agora 1 h normal, não diga a palavra";
  - "acabou, a voz do estúdio voltou".
- **O ✅ de cada sessão:**
  - todo arquivo com `lacunas: []` e 0 checksums errados;
  - o `ganho` igual a 2 em todos;
  - as saturadas contadas, e se elas se concentrarem em graves, avisar o Colab (é o gatilho do
    passa-alta, D71);
  - a lista do `pre_fala` (o barulho antes da fala);
  - as horas da sessão;
  - o zip com o LEIA-ME e os SHA256SUMS, que o dono sobe para o Drive com a mensagem ao Colab.
- **A voz do estúdio fica desligada só enquanto a coleta roda** (o firmware único volta ao uso
  sozinho no fim).
- **A prova do "≤ 1 falsa por dia" não sai daqui.** Ela vem de uma semana de uso com a placa
  ouvindo, na sessão que põe o modelo na placa (D71).

### H2c1 — o firmware único, as ferramentas e a coleta 1 (o estúdio quieto, de dia) — ✅ fechada em 2026-11-23

**O resultado (2026-11-23; o detalhe está no diário):** o firmware único na placa, com a volta ao uso
provada (pelo pedido e por 30 s sem sinal). 38 takes, 15 parecidas e 3.600 s de estúdio, todos com
`lacunas: []`, 0 checksums errados e ganho 2.
**Mudou do plano abaixo:** a placa escuta o pedido sempre que está parada (não só 1,5 s no boot), e o
estúdio sai em partes de 10 min. **Para as próximas:** puxar o ar durante o 3-2-1 (as parecidas
saíram com 2 marcas em 15, contra 18 em 38 dos takes, com o fundo parecido, 13 contra 16); os
roteiros de tela desta sessão estão em `~/viking-wakeword/_roteiros/` (copiar e trocar as dicas).


1. **O firmware único** (~30 min):
   - a placa liga no modo de uso de sempre. Nos primeiros ~1,5 s depois do boot, se chegar a linha
     `VKC1 COLETA` pela USB, ela entra no modo de coleta (o mesmo `coletar()`, o mesmo
     `converter()`);
   - no modo de coleta, a linha `VKC1 USO` reinicia a placa no modo de uso. O `coleta.py` manda o
     `COLETA` ao abrir a porta e o `USO` ao fechar, mesmo depois de um Ctrl-C;
   - os testes: a mesma linha nos dois lados, lida do `main.cpp`; e o boot de uso não espera mais
     que 1,5 s;
   - as mutações: o comando ignorado, e o `USO` que não reinicia;
   - os portões: os dois lados compilam sem aviso, e o env `xiao_s3_coleta` some.
2. **As ferramentas:**
   - `takes --dica TEXTO`: a dica aparece na tela a cada take e vai para o `.seq.json`, para o
     Colab separar por distância e tom. A numeração continua de uma rodada para a outra;
   - `pacote --sessao …`: o zip, o LEIA-ME (os níveis, a distância e o tom de cada take, o
     `pre_fala`, as horas), os SHA256SUMS e a conferência do zip lido de volta;
   - o `caffeinate`.
3. **Gravar a placa (com o ok) e conferir:**
   - o boot de uso chega ao PRONTO;
   - uma fala de teste dá a resposta certa (centavos);
   - `coleta.py medir --minutos 1`: 0 lacunas e o `ganho=2`, e depois a placa volta ao PRONTO
     sozinha.
4. **Os 38 takes** (estúdio quieto, de dia; o dono sentado, a placa no lugar de sempre):
   - 10 a ~50 cm, voz normal;
   - 10 a ~1 m, voz normal;
   - 10 a ~1,5 m, voz normal;
   - 8 a ~2 m, um pouco mais alto.
5. **15 parecidas** (`--negativo`): "Hey King", "hey vizinho", "Viking" no meio de uma frase ("vi
   um viking na TV"), "hey, liga", "ei, Vi". A lista sai do LEIA-ME e o Colab pode trocar.
6. **1 h de estúdio normal** (quieto: o dono trabalhando, teclado, mouse, cadeira, falando
   sozinho), enquanto eu fecho os docs.
7. **O pacote, o Drive e a mensagem ao Colab.** Pedir a ele o ok da 1ª sessão antes da 2ª, porque
   ela é a primeira com a 2 m e as parecidas.

### H2c2 — a coleta 2: com música (no mesmo dia da H2c1, por decisão do dono em 2026-11-23)

**O cuidado:** a H2c1 e a H2c2 ficam no mesmo lado do treino (o Colab separa treino e teste por sessão,
e as duas têm o mesmo dia, a mesma voz e o mic no mesmo lugar). A H2c3 e a H2c4 ficam noutros dias.

- **38 takes** com música tocando nas caixas da Scarlett, em volume de fundo a médio:
  - 10 a ~50 cm, normal;
  - 10 a ~1 m, mais baixo;
  - 10 a ~1,5 m, mais rápido;
  - 8 a ~2 m, normal.
- **22 parecidas**, com a música (proposta minha, com os ajustes do Colab de 2026-11-23, a confirmar
  no roteiro): as 10 frases em duas distâncias, e "Hey, Vi" 4 vezes, porque é o começo exato da
  palavra:
  - 11 a ~1 m, voz normal: as 10 e mais um "Hey, Vi";
  - 10 a ~2 m, voz normal: as 10;
  - 1 a ~2 m, apressado: "Hey, Vi".

  As 10: Vinícius · Vitória · Vivian · Hey, Vi · Hey, vida · Hey, viu? · Hey, vi um negócio · Hey
  vizinho · Hey Vicky · Vi um viking na TV.
- **1 h de estúdio normal com música:** os gêneros que o dono ouve, com grave (é onde o passa-alta
  pode aparecer). O dono trabalha junto.

- **Se tossir, espirrar, rir ou bater em algo num take, não se refaz:** o dono me diz o número, e
  eu anoto (`coleta.py anotar`; o Colab pediu, 2026-11-23).

### H2c3 — a coleta 3: de noite, com conversa

- **37 takes** de noite:
  - 10 a ~50 cm, cansado ou rouco;
  - 10 a ~1 m, de lado para a placa;
  - 10 a ~1,5 m, normal;
  - 7 de outro canto do estúdio.
- **15 parecidas.**
- **1 h de estúdio com fala que não é a palavra:** uma ligação ou chamada de vídeo, um vídeo ou
  podcast nas caixas, o dono falando. São os negativos que mais valem: a maior parte das ativações
  falsas vem de fala.
- **Se o dono der o ok do gasto** (centavos): 10 min da voz do próprio Viking (o TTS) pelas caixas,
  gravados pelo mic, para o aparelho não acordar com a própria voz.

### H2c4 — a coleta 4: um dia comum, guardada para o teste

- Outro dia e outro horário, **tudo misturado** como num dia de uso:
  - **37 takes** em todas as condições de antes, sem ordem: a dica sorteada pelo `coleta.py`;
  - **15 parecidas;**
  - **1 h de estúdio** do jeito que o estúdio estiver.
- O LEIA-ME marca a sessão como **teste**: ela nunca entra no treino. É o número de falsas por hora
  em que dá para confiar (com os limites da D71).
- **No fim, a conta da coleta inteira:** as horas, os takes por distância e tom, as saturadas, e a
  lista do que o Colab descartou.

### Depois do modelo na placa — o registro das quase-ativações (pedido do Colab, confirmado pelo dono em 2026-11-23, D72)

O pedido dele, para o firmware que roda o modelo:
- dois limiares na média deslizante de 5: o de ativar e um bem mais baixo (`T_registro`, 0,5);
- cada cruzamento de `T_registro` vai ao log, sempre (o horário, o pico e se ativou), e um clipe de
  ~3 s (2 s antes e 1 s depois) vai ao laptop de casa, com teto de 200 por dia;
- um jeito simples de apagar tudo.

**O que falta decidir ou desenhar (nosso):**
- **a consequência, dita ao dono e aceita (D72):** o aparelho guarda pedaços de voz no laptop de casa,
  inclusive de outras pessoas no estúdio;
- **o log guarda as horas ouvindo**, não só os cruzamentos: um contador acumulado de segundos com o
  modelo rodando, gravado a cada minuto, que sobrevive a uma queda de energia e **para, sem zerar**,
  quando o interruptor do HA desliga (o Colab aceitou e detalhou em 2026-11-23);
- **as horas que provam "≤ 1 por dia de 16 h", a 95%:** 48 h com 0 falsas, 76 h com 1 e 101 h com 2
  (Poisson, conferido aqui). A sessão de 1 h guardada para o teste, com 0 falsas, só dá 48 por dia:
  quem mede é o uso (D71); a coleta serve para treinar;
- o caminho é a ponte (`viking casa`), com o mesmo HTTPS e o token do aparelho, e não um serviço novo;
  o interruptor do HA desliga também o registro;
- os clipes nunca vão ao repo nem à nuvem do Viking; saem do laptop só pelas mãos do dono;
- a contagem continua exata com a Wi-Fi caída e depois de um reinício.

## Sessão H3 — o Viking mandando no Home Assistant (criada em 2026-11-21, na abertura da H1)

- **Entrega:** o chat (Mac, e depois o app) e as frases compostas ("apaga tudo e me lembra
  amanhã") alcançam o HA pelo Viking, não só pelo reconhecimento local do HA.
- **Ideia, a medir:** a ponte de casa como "mãos" do HA (como o `viking maos` do navegador): uma
  intenção tipada e de uma lista fechada de domínios, executada no laptop pela API REST local;
  nunca o HA aberto para a internet.

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
- **Pergunta do dono (2026-09-30, na 10b):** "o viking tem api depois que vai pra nuvem? ele pode
  ser chamado num micro controlador dai?". Resposta registrada, sem decisão:
  - sim, o motor é uma API HTTP (`POST /chat`, `GET /lembretes`), mas **fechada para sempre**
    (D47, "duas portas"): só entra quem mostra um token de identidade assinado pelo Google de uma
    conta da lista, hoje só o `viking-cli@`;
  - um ESP32 fala HTTPS, mas para entrar ali precisaria de uma chave de conta de serviço gravada
    no firmware, e isso é proibido (`AGENTS.md`: nunca chave em firmware; D47: nenhuma chave
    baixada);
  - o caminho que cabe no desenho: o dispositivo fala com uma **porta própria**, como o app da
    S17 (um segundo serviço, com uma credencial por aparelho, revogável e limitada ao que o pulso
    faz), e essa porta chama o motor pela conta de serviço dela;
  - decidir quando a trilha voltar: o que o pulso pode pedir (só lembrete? chat por voz?), e se a
    porta é a mesma do app da S17 ou uma só dele.
  - **De novo em 2026-10-06 (depois da 11), sem decisão:** a resposta acima vale (as contas da
    lista agora são três: `cli@`, `maos@`, `agendador@`). Dois fatos novos: um aparelho sem tela
    já é tratado pelo `interativo: false` do `/chat` (o que pede código recusa antes de o código
    nascer; agenda, lembretes e leitura do e-mail funcionam), e dá para testar **hoje** por uma
    **ponte pelo Mac** (ESP32 → serial/Bluetooth → um programa no Mac que usa o cliente do
    `viking chat --nuvem`), sem chave no aparelho, com o Mac ligado: o padrão do
    `archive/wristband-fail-test/`. Turno de ~5–6 s, mais a partida a frio do Cloud Run; só texto.

## Backlog sem sessão marcada

- **Checagem de tipos como portão do CI** (§15.3, adiada pelo dono em 2026-09-28, Sessão 7):
  `uvx mypy==2.3.1 --python-executable .venv/bin/python src` → `Found 67 errors in 15 files
  (checked 41 source files)`. Em 2026-09-29, na abertura da 9: `Found 68 errors in 15 files
  (checked 43 source files)` (o novo é da 8b: `list[Evento]` sem `completa` no MCP). Desde a 9 o
  `mypy` é portão do CI **só nos módulos de dados** (dono, 2026-09-29); o resto segue aqui. 34 são um padrão só em `browser/jev_runner.py` (`**dict` num
  dataclass), 9 são imports do ambiente do Jev e 3 são pacotes do Google sem tipos; nos ~12 que li,
  nenhum defeito real. Para virar portão: consertar os 67, ignorar os imports do ambiente do Jev
  (`_jev_subprocess.py` roda noutro Python) e pôr o `mypy` fixado no CI.

- **Logo do Viking no e-mail** (pedido do dono na abertura da Sessão 8, 2026-09-28: "uma logo
  que podemos fazer pra ele bem depois"). Hoje o e-mail leva só a linha "Escrito pelo Viking
  (Assistente AI)"; uma imagem exige HTML ou anexo, que a D46 deixou de fora.

Com sessão desde 2026-09-28: paginação e séries (8b), notas buscáveis (13), migrations formais
(feitas na 9), RAG (13–14), aprovação fora do terminal (17). Sem sessão: decidir se o Viking é só-checkout
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

## Sessão final — repo privado de novo (criada em 2026-11-21)

- **Quando:** quando o Viking for para o Home Assistant, ou antes, se o dono fizer algo comercial
  (decisão do dono em 2026-11-21, ao tornar o repo público na 14b; D58 revista, item 3).
- **Faz:** `gh repo edit Zbreno11-git/LifeOs --visibility private` (o `gh` 2.45 do VPS não tem
  a flag `--accept-visibility-change-consequences`, que as versões novas pedem; medido em
  2026-11-21 ao tornar público); o `AGENTS.md` volta a dizer que o scanner de segredos
  do GitHub não roda no privado (o gitleaks segue no CI e no hook).
- **Ressalva:** forks e caches de enquanto o repo foi público não voltam.
