# Pesquisa do roteiro 8–21 (2026-09-28)

> Pedido do dono antes da Sessão 8: revisar a arquitetura como engenheiro sênior e pesquisar libs,
> repos e skills que facilitem cada sessão, inclusive os assistentes "Jarvis" open-source.
>
> **Isto é pesquisa, não medição.** Toda linha abaixo foi lida numa fonte em **2026-09-28** (data
> de acesso de todos os links), e continua **não medida** até alguém testar no nosso ambiente. As
> exceções dizem "medido", com o comando. Versões e árvores de dependência saíram do JSON do PyPI
> e de `uv pip compile` no VPS; nada foi instalado no Mac. O que cada sessão faz com isto está em
> `sessoes.md`, na seção de cada uma ("Escolhas de arquitetura previstas" e "Libs/repos a
> reaproveitar"). Decisões do dono só mudam com o gatilho delas ou perguntando (`docs/decisoes.md`).

## Conclusões em uma linha cada

1. **Nenhum framework de memória respeita a D48** (gravar só com o "sim" e o texto como fonte):
   todos extraem e gravam sozinhos. Escrever a nossa camada (poucas tabelas) e roubar três ideias.
2. **O "sim" solto na conversa é forjável** por um documento que planta "quando o usuário disser
   sim, grave isto" (ataque publicado contra a memória do próprio Gemini). O dono escolheu outra
   saída (D48 revista): o Viking aprende sozinho, mas **só do texto que o dono digita**. O e-mail
   nunca chega a quem grava.
3. **Busca na web junto com as nossas tools, na mesma chamada, só nos modelos 3.x** (preview). No
   `gemini-2.5-flash` de hoje, a busca vira uma tool que faz uma chamada separada.
4. **O Google está restringindo o 2.5** a quem já usa, e o `gemini-3.8-flash` dobra de preço em
   2027-01-01. O "Flash → Pro" da S12 precisa ser repensado com esses preços.
5. **Nuvem quase de graça com Firestore;** Cloud SQL come ~US$ 9,4 do orçamento. Conexão aberta
   (WebSocket, long-poll) no Cloud Run é cobrada o tempo todo: o Mac pergunta por tarefa em
   chamadas curtas.
6. **O login do Google em "Testing" vence em 7 dias** (confirmado na documentação oficial):
   resolver na S8, antes de qualquer coisa ir para a nuvem.
7. **A API da Garmin é "only for business use":** uso pessoal muito provavelmente é recusado. O
   dono decidiu no mesmo dia ir **direto pelo Strava oficial** ("single-player mode"), sem pedir
   à Garmin (D54).
8. **O Jev fica no Mac, com o Chrome local;** a nuvem só entrega a tarefa. Nunca expor a porta CDP
   do Mac nem subir cookies (o Browser Harness tem as duas coisas prontas, e as duas ficam
   recusadas).
9. **Face ID não é garantido:** um passkey com verificação obrigatória aceita o código do aparelho
   no lugar da biometria. Aprovar exige estar no iPhone, mas não prova que foi o rosto.
10. **Repo privado perde o secret scanning** (medido ligado hoje; a documentação do GitHub diz que
    em repo privado de conta pessoal ele não existe): um scanner nosso no CI antes de fechar.

## 1. Assistentes "Jarvis" open-source

| Projeto | Fonte | Licença, atividade | O que aproveitar | Veredito |
|---|---|---|---|---|
| OpenClaw | https://github.com/openclaw/openclaw · https://docs.openclaw.ai/tools/exec-approvals · https://docs.openclaw.ai/nodes/node-host | MIT; release 2026-09-23 | aprovação presa ao pedido exato (mudou depois de aprovado = negado); sem interface para aprovar, nega; **nó local que abre conexão de saída para o gateway, pareado uma vez, com lista fixa de comandos** — é o desenho das "mãos" do Viking | **adaptar as regras**, não adotar a plataforma (Node, escopo enorme) |
| Hermes Agent | https://github.com/NousResearch/hermes-agent | MIT; ativo | agendamento que entrega em qualquer canal; busca FTS5 nas sessões | adaptar só a FTS5; **recusar** a memória que o agente grava sozinho (contra a D48) |
| Leon | https://github.com/leon-ai/leon | MIT; núcleo em reescrita (README) | memória em camadas: preferências duráveis / contexto do dia / conversa recente | adaptar a divisão |
| Khoj | https://github.com/khoj-ai/khoj · https://docs.khoj.dev/features/automations | AGPL-3.0; beta | "pergunta agendada → relatório por e-mail", no fuso do usuário | adaptar a ideia (coach, resumo diário); não depender (AGPL, ritmo lento) |
| OpenJarvis (Stanford) | https://github.com/open-jarvis/OpenJarvis | Apache-2.0; ativo | agentes sob demanda / agendados / contínuos; resumo matinal (e-mail, agenda, saúde) com áudio | adaptar a taxonomia e o resumo matinal |
| isair/jarvis | https://github.com/isair/jarvis | sem licença declarada (NOASSERTION); release 2026-09-19 | redação antes do contexto; **visor da memória** (ver e apagar o que foi guardado); escolher um subconjunto de tools por pedido | adaptar o visor e o roteamento de tools (hoje são 21) |
| Letta (ex-MemGPT) | https://github.com/letta-ai/letta · https://docs.letta.com/guides/agents/memory | Apache-2.0 | o agente edita a própria memória por tool | **recusar** (é exatamente o que a D48 proíbe) |
| Home Assistant Assist | https://www.home-assistant.io/voice_control/voice_remote_expose_devices/ | Apache-2.0 | expor à voz é opt-in por entidade | **adotar a regra:** a voz só alcança uma lista explícita de tools |
| Open Interpreter | https://github.com/openinterpreter/openinterpreter | Apache-2.0 | hoje é agente de código | recusar (fora do escopo) |

## 2. Jev, Browser Harness e quem os usa

- **jev-ultrafast** (https://github.com/browser-use/jev-ultrafast, MIT). Em 2026-09-28:
  - só 3 commits no `main` (17 e 18/09), 125 PRs abertos, 37 issues, nenhum release;
  - o README diz "fastest and cheapest" e mede o Google Flights em 7,1 s. A própria fonte avisa
    que não é um benchmark geral de confiabilidade;
  - o `docs/performance.md` diz que a TypeSafe devolve contagem de tokens sem valor em dólar. **O
    custo total por tarefa não é publicado.** O nosso número (US$ 0,0000137 por decisão) continua
    sendo o medido em 2026-09-19.
  - **Consequência:** manter o commit fixo e o aviso de versão (D41), e não esperar correção do
    upstream. Recusar o PR #123 ("fill passwords from a local secret vault") se ele entrar.
- **Quem usa o Jev.** Todos os projetos são de setembro de 2026, novos demais para confiar:
  - `kevinbadi/jev-voice` (voz local com whisper.cpp + Jev no Mac) é a referência mais próxima do
    apertar-para-falar;
  - também existem um MCP (`jiawei686/jev-ultrafast-mcp`) e skills (`kerpopule/hermes-jev-skills`).
- **Browser Harness** (https://github.com/browser-use/browser-harness, MIT, v0.1.13 de
  2026-09-04):
  - aceita CDP remoto (`BU_CDP_URL`/`BU_CDP_WS`);
  - o `SKILL.md` manda serializar o Chrome local ("one shared browser lane"), o que confirma a D40;
  - tem um `profile-sync` que **sobe cookies do Chrome local para a nuvem da Browser Use**.
  - **Recusados:** expor o CDP do Mac para a nuvem, porque a porta CDP dá controle total da
    Chrome logada; e o `profile-sync`, porque manda cookies de conta para fora da máquina.
- **Segurança do browser-use.** Referências:
  https://docs.browser-use.com/examples/templates/sensitive-data e
  https://github.com/browser-use/browser-use/issues/4763 (endereços `data:`/`blob:` contornam a
  lista de domínios permitidos).
  - **Medido aqui em 2026-09-28:** o nosso `_redacao.dominio_bloqueado` tem a mesma classe de
    furo. `blob:https://<banco>/…`, `view-source:https://<banco>/` e `filesystem:https://<banco>/…`
    devolvem "não bloqueado", enquanto `https://<banco>/x` é bloqueado.
  - **Não medido:** se o Chrome abre `view-source:` por CDP com os cookies do dono.
  - O conserto é o primeiro passo da Sessão 8.

## 2b. Browser Use Cloud (pesquisado em 2026-10-06, depois da lista de espera)

Pesquisa só de leitura, feita por um subagente; quase tudo é **ALEGADO** pela empresa. Medido por
terceiros só há sobre o Jev, e pouco. Decisão: D62 (não migrar).

- **A lista de espera é de um modo "SUPERFAST"** do Cloud, "Coming soon", sem preço nem número
  (https://browser-use.com/ultrafast). O dono confirmou que a conta liberada é a normal.
- **O agente v4 do Cloud não usa o Jev.** O modelo padrão é o deles ("Luna"); BYOK de Anthropic,
  OpenAI e Google com acréscimo de 0,2× (https://docs.browser-use.com/cloud/agent/models.md).
- **Custo e tempo (dado de produção publicado por eles,
  https://docs.browser-use.com/cloud/choosing-an-agent.md):** tarefa mediana bem-sucedida v2 ~1
  min e US$ 0,70; v3 ~2 min e US$ 0,87; v4 ~5 min e US$ 1,64. A alegação de lançamento (US$ 0,03
  por tarefa) não diz tarefas, rodadas nem juiz. Navegador alugado: US$ 0,02/h; proxy
  residencial US$ 5/GB (https://browser-use.com/pricing.md). **Conta nossa:** 10–30 tarefas por
  dia a US$ 0,70–1,64 passam de US$ 200/mês.
- **A Chrome do dono não é alcançável** pelo agente deles: o `cdpUrl` aponta para um navegador
  deles. O único jeito de usar os logins é o `profile-sync` (cookies sobem), recusado na D53.
- **Termos** (revisados em 2026-07-15): licença "perpetual and irrevocable, sublicensable" sobre o
  conteúdo; entradas e saídas podem ir a provedores de modelo terceiros
  (https://browser-use.com/legal/terms-of-service). SOC 2 Type II alegado. Gravação de sessão
  desligada por padrão na API; o modo sem retenção (ZDR) **não aceita o v4**.
- **Controles:** `allowed_domains`; nada como o nosso bloqueio de banco e e-mail, nem aprovação
  antes de um clique (o "human in the loop" deles é pausar depois da run).
- **O Jev em si (2026-10-06):** o `main` do upstream continua no commit de 2026-09-18 (`git fetch`
  no VPS); há correções em PR para o `TYPE_TEXT` digitar no campo errado quando dois campos têm o
  mesmo rótulo (issues #191, #198, #202) e para `{"text": null}` recusado (#203). HN de
  2026-09-17: 93 pontos, opiniões divididas ("at best misleading"). Os ~7 s do Google Flights são
  do Jev **local**, uma tarefa, três repetições.
- **A forma barata, se um dia houver navegador na nuvem sem login:** o nosso Jev no motor (com o
  freio, a redação e o bloqueio) dirigindo um navegador alugado sem perfil pelo Browser Harness
  (que já aceita CDP remoto). A medir na S12, depois da busca; nunca o agente deles.

## 3. Memória de agente

| Lib | Fonte | Licença, versão | Árvore e wheels | Como grava / contradição | Veredito |
|---|---|---|---|---|---|
| mem0 | https://github.com/mem0ai/mem0 · https://docs.mem0.ai/core-concepts/memory-operations/add | Apache-2.0; 2.2.1 (2026-09-25) | 34 pacotes (qdrant, sqlalchemy, grpcio, openai, posthog); telemetria ligada por padrão | extrai por LLM; desde a v2.0.0 só faz ADD: o fato novo **não** substitui o velho | recusar; a lição é que ADD-only acumula contradição |
| Letta | https://docs.letta.com | Apache-2.0 | o pacote novo só tem wheel para macOS 14+ | o agente edita a própria memória | recusar |
| Graphiti | https://github.com/getzep/graphiti · https://help.getzep.com/graphiti/getting-started/overview | Apache-2.0; 0.30.2 | exige neo4j/FalkorDB/Neptune | extração automática; o fato substituído ganha `invalid_at`, não some | **roubar a ideia** da invalidação temporal |
| LangMem | https://github.com/langchain-ai/langmem | MIT; parado desde 2025-10 | 50 pacotes (langchain, langgraph) | o agente decide o que gravar | recusar |
| cognee | https://github.com/topoteretes/cognee | Apache-2.0; 1.6.1 | 163 pacotes (onnxruntime, lancedb, pyarrow); no Mac Intel volta à 0.5.1 | grafo automático | recusar |
| Memobase | https://github.com/memodb-io/memobase | Apache-2.0 | o servidor exige Postgres e Redis | perfil extraído por LLM | roubar só o **esquema de perfil definido pelo dono** |

**Ataques e defesas.** As fontes:
- MINJA (https://arxiv.org/abs/2503.03704) injeta memória só conversando;
- AgentPoison (https://arxiv.org/abs/2407.12784) passa de 80% de sucesso envenenando menos de 0,1%
  da base;
- o "delayed tool invocation" contra a memória do Gemini
  (https://embracethered.com/blog/posts/2025/gemini-memory-persistence-prompt-injection/) usa um
  documento que planta "se o usuário disser X, grave isto";
- OWASP ASI06, Memory & Context Poisoning
  (https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/);
- OWASP LLM08:2025 (https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/);
- confiança limitada pela origem (https://arxiv.org/abs/2606.22030).

O que isso muda no desenho da S13:

| Defesa | A D48 já faz | Falta |
|---|---|---|
| Consentimento que conteúdo externo não forja | (D48 revista) quem grava só vê o texto do dono | extração numa chamada separada, sem resultado de tool; o modelo do chat não tem tool de gravar; a linha "📝 anotei" sai do que foi gravado |
| Confiança pela origem, não pelo texto | origem gravada e marcada | nada vindo de tool vira instrução nem receita; na leitura, o fato de origem externa continua no bloco de não confiável |
| Recusar forma de instrução | documentos um por um | texto com cara de ordem ("se o usuário disser…", "sempre faça…") vindo de conteúdo externo não vira fato |
| Log auditável | texto em tabela é a fonte | tabela só de acréscimos (quem, quando, origem, qual fato substituiu, `invalida_em`), com listar e desfazer, como o `viking registro` |
| Menos superfície | sem histórico, sem extração automática | teto de fatos injetados por turno |
| Índice verificável | índice descartável com modelo e dimensão | reconstruir o índice dá o mesmo top-k no conjunto fixo; vetor sem linha de texto é erro |

**Vetores:**
- **sqlite-vec** (https://github.com/asg017/sqlite-vec, MIT/Apache-2.0, 0.1.9) não tem
  dependências e tem wheel `py3-none` para Mac x86_64 e manylinux. Fica para o Mac e para o dev.
  - A conferir no Mac: se o Python 3.13 de lá tem `sqlite3.enable_load_extension`.
- **Firestore `find_nearest`** (https://docs.cloud.google.com/firestore/native/docs/vector-search):
  dimensão até 2048, só índice plano, até 1000 resultados.
- **pgvector:** extensão 0.8.5 no Cloud SQL.
- **Recusados:** LanceDB (sem Mac x86_64 desde a 0.25.3) e Chroma. O Chroma exige onnxruntime, que
  para no Mac Intel na 1.23.2, e o `chromadb-client` exige um servidor à parte.

**Embeddings do Gemini** (https://ai.google.dev/gemini-api/docs/embeddings):
- `gemini-embedding-2`, multimodal, até 8192 tokens, de 128 a 3072 dimensões (Matryoshka). Custa
  US$ 0,20 por 1M de tokens, e US$ 0,10 no Batch.
- Sem `task_type`: a instrução vai dentro do texto.
- Gravar junto do índice o modelo, a dimensão e a instrução.
- Com Firestore, a dimensão tem de ser de no máximo 2048.

**Avaliação da busca:**
- ragas tem 92 pacotes, e o deepeval 66, com telemetria e LLM como juiz.
- **À mão no pytest:** perguntas de ouro com o id esperado, recall@k e MRR. Nos testes offline,
  vetores gravados como fixture; uma rodada ao vivo no Mac.

## 4. Gemini, Claude e APIs do Google

**Busca na web** (https://ai.google.dev/gemini-api/docs/tool-combination,
https://ai.google.dev/gemini-api/docs/google-search, https://ai.google.dev/gemini-api/terms):
- **Combinar com as nossas tools:** "built-in and custom tools combinations are in Preview and
  supported for Gemini 3 models only".
- **Preço:**
  - no 2.5 Flash: 1.500 prompts por dia grátis, depois US$ 35 por 1.000;
  - no 3.x: 5.000 buscas por mês grátis, depois US$ 14 por 1.000.
- **As fontes** vêm em `groundingMetadata.groundingChunks`/`groundingSupports`.
- **Os termos exigem** mostrar as "Search Suggestions" (um HTML) a quem perguntou e proíbem
  "intersperse"/"syndicate". Um terminal não desenha HTML, e isso pesa a favor do app. Repassar o
  resultado da busca ao Claude pode contar como "syndicate" (inferência): não repassar.
- **A Interactions API** guarda o histórico no servidor por padrão (`store=true`). Se um dia
  migrar, usar `store=false`. Fonte: https://ai.google.dev/gemini-api/docs/migrate-to-interactions
- **`url_context`:** até 20 URLs públicas por pedido (https://ai.google.dev/gemini-api/docs/url-context).

**Modelos e preços** (https://ai.google.dev/gemini-api/docs/pricing,
https://ai.google.dev/gemini-api/docs/deprecations), por 1M de tokens de entrada/saída:

| Modelo | Preço | Nota |
|---|---|---|
| 2.5 Flash (o do chat hoje) | US$ 0,30/2,50 | "No shutdown date announced", mas o acesso está sendo limitado a quem já usa |
| 3.5 Flash-Lite | US$ 0,30/2,50 | um dos substitutos indicados |
| 3.8 Flash | US$ 0,75/3,75 | **dobra em 2027-01-01** |
| Pro | — | só existe em preview (`gemini-3.1-pro-preview`, US$ 2/12) |
| Cache implícito | 10% da entrada | ligado por padrão do 2.5 em diante |

**Claude** (https://platform.claude.com/docs/en/about-claude/pricing,
https://platform.claude.com/docs/en/manage-claude/api-and-data-retention):
- **Preços:** Sonnet 5 a US$ 2/10, Haiku 4.5 a US$ 1/5, Opus 5.5 a US$ 4/20.
- **Retenção:** a API apaga em até 30 dias e não treina sem permissão. Retenção zero só por
  vendas, o que reforça a D49.
- **SDK:** `anthropic` 1.8.0 puxa uma dependência nova só, o `jiter` 0.17.0, que tem wheel
  cp312/cp313 para `macosx_10_12_x86_64` e manylinux. O resto já está no `uv.lock`.

**NotebookLM:**
- **API só no Enterprise,** e sem conta pessoal: pede Cloud Identity ou outro provedor de
  identidade (https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/overview).
- **Na conta pessoal,** o produto se chama "Gemini Notebook" e exporta **notas** para um Google Doc
  (https://support.google.com/notebooklm/answer/16262519).
- **Caminho prático:** notas exportadas para o Docs e lidas com `drive.file`, ou o arquivo baixado
  e mandado ao Viking.

**Gmail e o login:**
- **Resposta na mesma conversa:** `threadId` mais `In-Reply-To`/`References`, com o `Subject`
  igual (https://developers.google.com/workspace/gmail/api/guides/threads).
- **Quem pode enviar:** `messages.send` é aceito com `gmail.modify` e com `gmail.send`. O
  `gmail.send` é **sensível**; o `modify` é **restrito**
  (https://developers.google.com/workspace/gmail/api/auth/scopes).
- **Cabeçalho com quebra de linha. Medido aqui em 2026-09-28:** `email.message.EmailMessage` do
  Python 3.12 recusa CR/LF num cabeçalho com `ValueError`.
- **"Testing":** o refresh token vence em 7 dias, a não ser que os escopos sejam só nome, e-mail e
  perfil (https://developers.google.com/identity/protocols/oauth2).
- **Verificação opcional** para "personal use (fewer than 100 users)", com a tela de "app não
  verificado" (https://support.google.com/cloud/answer/13464323).
  - Inferência: publicar "In production" sem verificar, só para o dono, tira o prazo de 7 dias.
  - **Não conferido:** se isso vale para escopo restrito. Medir na S8.
- **`drive.file`** não é sensível
  (https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

**Voz:**
- **Live API:** US$ 0,005 por minuto de entrada e US$ 0,018 de saída. Chama funções, mas o laço
  tem de devolver as respostas à mão (https://ai.google.dev/gemini-api/docs/live-api/tools).
- **Gravar → `generateContent` com áudio (32 tokens/s) → TTS** (`gemini-3.8-flash-tts`, cerca de
  US$ 0,00225 por 10 s):
  - custa a mesma ordem da Live;
  - reaproveita o laço atual;
  - a Live só ganha em latência.

## 5. Nuvem barata no GCP

Fontes: https://cloud.google.com/run/pricing, https://docs.cloud.google.com/run/docs/triggering/websockets,
https://docs.cloud.google.com/run/docs/authenticating/developers,
https://docs.cloud.google.com/docs/authentication/use-service-account-impersonation,
https://docs.cloud.google.com/iam/docs/best-practices-for-managing-service-account-keys,
https://cloud.google.com/scheduler/pricing, https://docs.cloud.google.com/scheduler/docs/http-target-auth,
https://cloud.google.com/firestore/pricing, https://cloud.google.com/sql/pricing,
https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts,
https://cloud.google.com/secret-manager/pricing,
https://docs.cloud.google.com/billing/docs/how-to/disable-billing-with-notifications,
https://docs.cloud.google.com/run/docs/logging, https://cloud.google.com/artifact-registry/pricing.

| Peça | O que a fonte diz | Consequência |
|---|---|---|
| Cloud Run | grátis por mês: 180 mil vCPU-s, 360 mil GiB-s, 2 milhões de requisições; ocioso não cobra; recusa do IAM não cobra; requisição até 3600 s | mínimo 0 serve; região Tier 1, escolhida com o dono na S10 |
| Conexão aberta | "an instance that has any open WebSocket connection is considered active" | long-poll de 8 h/dia ≈ US$ 16/mês (estimativa): **o Mac pergunta em chamadas curtas** (a cada 5–10 s, só com `viking maos` ligado) |
| Quem chama | token de usuário do `gcloud` não tem audience e é "susceptible to replay"; recomendado: ID token de conta de serviço, por impersonação, sem chave em disco | CLI e Mac se fazem passar por contas de serviço estreitas |
| Chave de conta de serviço | o Google manda evitar | nada de chave fixa no VPS (pergunta ao dono sobre o deploy) |
| Scheduler | 3 jobs grátis; mínimo 1 min; entrega "at least once" | o disparo do lembrete tem de ser idempotente (`enviado_em` da S9); o token OIDC é conferido pela identidade |
| Firestore | grátis por dia: 1 GiB, 50 mil leituras, 20 mil gravações; vetor até 2048 dimensões | cabe; o lembrete a cada minuto gasta ~1.440 leituras/dia |
| Cloud SQL `db-f1-micro` | US$ 0,0105/h + disco ≈ US$ 9,4/mês, fora do SLA | só se o Firestore não servir |
| SQLite num volume do Cloud Storage | "does not provide… file locking… last write wins" | **não usar** |
| Secret Manager | 6 versões ativas e 10 mil acessos grátis | ler ao subir a instância, não a cada pedido |
| Orçamento | alerta não põe teto; desligar o faturamento por Pub/Sub pode apagar recursos | alerta por e-mail, e o teto de verdade no `custos.py` |
| Logs | um log por requisição (URL, IP, user agent); stdout vira log; 30 dias grátis | nada de conteúdo na URL nem no stdout; filtro de exclusão; se o corpo fica fora do log: **não conferido** |
| Imagem | Artifact Registry 0,5 GiB grátis; Cloud Build 2.500 min grátis | política de limpeza (2–3 imagens) |

**Estimativa, não medido:** com Firestore, a nuvem sai de US$ 0 a 0,10 por mês, e o orçamento
fica quase todo para os modelos. Com Cloud SQL, cerca de US$ 9,5.

**Wheels das libs de nuvem para Mac:**
- grpcio 1.84.0 tem `cp313-macosx_11_0_universal2`, e o protobuf 7.36.2 tem `abi3-macosx_10_9`;
- ainda assim, o Mac não precisa delas: ele é cliente HTTP e "mãos". As libs da nuvem entram só
  onde rodam (S10).

## 6. App no iPhone

| Tema | O que a fonte diz | Consequência |
|---|---|---|
| Passkey | iOS 16+; a verificação é Face ID/Touch ID, **com o código do aparelho como alternativa** (https://passkeys.dev/docs/reference/ios/); em PWA da tela de início: **nenhuma fonte oficial** | medir no iPhone na S17; o texto da D52 diz "passkey", não "prova de Face ID" |
| Aprovar uma ação | `get()` com desafio próprio, ligado ao hash dos dados exatos da ação, e verificação obrigatória; `txAuthSimple` foi retirada; SPC é só pagamento (https://www.w3.org/TR/secure-payment-confirmation/) | a ligação à ação é **do servidor**, e o Face ID só mostra o nome do site |
| py_webauthn | BSD-3; 3.0.1 (2026-09-25); `py3-none`; puxa cbor2, pyasn1, cryptography ≥ 49 e pyOpenSSL (a 26.4 exige cryptography < 51) | **adotar**, de olho no teto do cryptography |
| fido2 (Yubico) | 2.2.1; só o cryptography | alternativa mais baixo nível |
| Web Push | iOS 16.4+, só na tela de início, pedido a partir de um toque (https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/); relatos de inscrição que some e de entrega que para | **o lembrete não depende só do push**: e-mail continua, reinscrição ao abrir, falha ruidosa |
| pywebpush | MPL-2.0; 2.5.0; puxa aiohttp e o **http-ece, que só tem sdist** | o `tests/test_lock.py` recusaria; adaptar (py-vapid + cifra da RFC 8291 sobre o cryptography) ou exceção decidida pelo dono |
| Microfone | o Safari 18.4 grava WebM/Opus (https://webkit.org/blog/16574/webkit-features-in-safari-18-4/); a permissão não persiste em modo tela de início (https://bugs.webkit.org/show_bug.cgi?id=215884); reconhecimento de fala falha na PWA | mandar o áudio ao servidor; esperar um pedido de permissão por abertura |
| Áudio no Gemini | aceita aac, m4a, webm e opus; `audio/mp4` não está na lista (https://ai.google.dev/gemini-api/docs/audio) | mandar o tipo real, via `isTypeSupported` |
| Front sem build | htmx 2.0.11 (0BSD, ~17 KB), uPlot 1.6.32 (MIT, ~22 KB); Chart.js 3× maior | htmx + JS puro + uPlot, **servidos pelo backend** (sem CDN), com `script-src 'self'` na tela de aprovação |

## 7. Garmin e alternativas

- **Garmin Connect Developer Program**
  (https://developer.garmin.com/gc-developer-program/program-faq/):
  - "only for business use";
  - resposta em 2 dias úteis, sem taxa;
  - OAuth 2.0 com PKCE;
  - os dados chegam por push ou "ping/pull" num endereço HTTPS público.
  - **Uso pessoal: muito provavelmente recusado.** É inferência da frase, confirmada só por blogs.
- **Strava** (https://developers.strava.com/docs/getting-started/,
  https://developers.strava.com/docs/rate-limits/, https://www.strava.com/legal/api):
  - app novo começa em "single-player mode", só com a própria conta;
  - limites de 200 pedidos por 15 min e 2.000 por dia;
  - webhook obrigatório.
  - Escolhido pelo dono (D54): o relógio sincroniza com o Strava, e o Viking lê de lá.
- **Outra saída:** exportar o FIT à mão. Não conferido.

## 8. Skills e plugins do Claude Code

- **`/security-review` e `/code-review`** vêm embutidos, segundo o relatório da pesquisa (não conferido por mim: conferir na abertura da 8), e revisam o diff, sem sobrepor as nossas
  skills, que ensinam como agir. **Adotados** no fechamento de toda sessão a partir da 8.
- **anthropics/claude-plugins-official** (https://github.com/anthropics/claude-plugins-official,
  Apache-2.0). O README avisa que o conteúdo dos plugins não é verificado.
  - `pyright-lsp` tem utilidade;
  - `security-guidance` roda por hooks e se sobrepõe em parte à `seguranca`;
  - `playwright` serve para testar a PWA, mas **roda um MCP**.
- **anthropics/skills** (https://github.com/anthropics/skills): `webapp-testing` e
  `frontend-design` servem na S17–18.
- **obra/superpowers** (https://github.com/obra/superpowers, MIT):
  - sobrepõe-se muito a `testes-que-provam`, `depuracao`, `evidencia` e `software-build`;
  - tem hook de início de sessão, ou seja, código que roda sozinho.
  - **Recusado para instalar;** no máximo ler e roubar ideias.
- **Regra de cadeia de suprimento.** Skill é instrução que o agente segue, e plugin pode trazer
  hook, MCP e script com as permissões da sessão: segredos, `git push`, o Chrome real. Por isso:
  - copiar o texto para `.claude/skills/` com o commit de origem anotado;
  - ler tudo antes;
  - nada com hook sem o dono revisar;
  - sem atualização automática.

## Afirmações não conferidas (a medir na sessão que as usa)

- **S8:** se o Chrome abre `view-source:` por CDP com os cookies; se "In production" sem
  verificação, com escopo restrito, tira o prazo de 7 dias.
- **S10:**
  - se o Cloud Run repassa o token e o app consegue conferir o e-mail de quem chamou;
  - se o corpo da requisição fica fora do log;
  - quantos segundos leva a partida a frio;
  - se o `gcloud` aceita um access token de 1 h num arquivo para o deploy.
- **S12:** se busca e funções combinam pelo `generateContent` no 3.x (o campo
  `include_server_side_tool_invocations` existe no SDK 2.25.0 instalado; não testado).
- **S13:** se o Python do Mac carrega extensão do SQLite; o preço da consulta vetorial do
  Firestore.
- **S17:** WebAuthn em PWA da tela de início no iPhone; se o MP4 do Safari passa no Gemini como
  `audio/m4a`.
- **S19/S21:** se a Garmin recusa de fato; se o acordo do Strava permite o uso com IA (só uma
  busca por palavras-chave, não uma leitura).
- **Números que mudam rápido:** estrelas e atividade dos repositórios.
