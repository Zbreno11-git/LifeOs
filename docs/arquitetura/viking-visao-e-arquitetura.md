# Viking — Visão e Arquitetura (v2.0)

**Data:** 2026-09-20
**Substitui/mantém:** este documento é a nova referência de visão/arquitetura do projeto, sucedendo
`viking-visao-e-arquitetura-v1-pulso.docx` (v1.0, 19 set 2026) como fonte principal. O v1 não é
descartado — ele continua correto para o que descreve (a trilha do dispositivo de pulso) e fica
arquivado nesta mesma pasta como referência histórica. O que muda aqui: introduz a marca **Viking**,
reenquadra o dispositivo de pulso como uma fase pausada (não a prioridade atual), define a automação de
navegador como o mecanismo principal de execução no lugar do controle local de PC, e registra a direção
de finanças (via Pluggy) e de memória/RAG — nenhuma dessas ideias está no v1. Ver `docs/diario-de-bordo.md`
(2026-09-20) para o histórico da decisão.

---

## 1. Marca e codinome

- **Viking** é a marca do produto: um assistente pessoal unificado, acessível via chat (CLI hoje, web
  possivelmente depois), que administra calendário, navegação web e lembretes/notas — com finanças e
  memória de longo prazo (RAG) como direções futuras.
- **Life OS** é o codinome técnico interno do projeto. O pacote Python continua se chamando `lifeos`; o
  comando instalado é `viking`. Não há rename do repositório neste momento.
- A ideia original ("um robô assistente, com RAG") é a visão de longo prazo do Viking — não implica
  necessariamente um robô físico; a forma atual é software (CLI/app), com o dispositivo de pulso como
  uma possível interface física futura, não a única.

## 2. Visão de produto

Reduzir a fricção entre ter uma intenção e executá-la ou registrá-la — via texto/voz, o Viking deve
conseguir: consultar/criar eventos de calendário, navegar a web e executar tarefas nela, e guardar
lembretes/notas de forma confiável.

Por que **CLI-first agora**: é a forma mais rápida de validar se as três capacidades (calendário,
navegador, lembretes) funcionam juntas de forma útil no dia a dia, reaproveitando padrões já testados
neste repo (`calendar-bot/` era um REPL; o demo do `jev-ultrafast/` também é local). Uma interface
visual/web é adiada deliberadamente para depois que o loop central do assistente for validado — não é
uma limitação técnica, é uma escolha de sequenciamento.

## 3. Estado atual (milestone corrente)

O milestone corrente é o **assistente de chat CLI unificado**: calendário (Google Calendar) + automação
de navegador (executor Jev via Browser Harness) + lembretes gerais. Ver `docs/diario-de-bordo.md` para o
status vivo de implementação — este documento descreve a arquitetura-alvo, não necessariamente o que já
está construído em cada momento.

## 4. Arquitetura do Viking CLI

```
                         ┌─────────────────────┐
   usuário (texto/voz) → │   viking chat (CLI)  │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │ assistant/agent.py    │  (loop de function-calling, ex.: Gemini)
                         └──────────┬───────────┘
                    ┌───────────────┼────────────────┐
                    ▼               ▼                ▼
            ┌───────────────┐ ┌───────────┐  ┌──────────────┐
            │  calendar/     │ │ browser/  │  │ reminders/   │
            │  (Google Cal.) │ │ (subproc. │  │ (SQLite,     │
            │                │ │ → Jev →   │  │  schema      │
            │                │ │ Harness → │  │  RAG-ready)  │
            │                │ │ Chrome)   │  │              │
            └───────────────┘ └───────────┘  └──────────────┘

                         ┌──────────────────────┐
                         │  mcp_server/server.py │  ← Viking como SERVIDOR MCP
                         │  (expõe calendar +    │    (outras ferramentas podem
                         │   reminders como tools)│    chamar o Viking)
                         └──────────────────────┘
```

### 4.1 Calendário (Google Calendar)

Portado do protótipo `calendar-bot/` (funcional, testado): OAuth via `google-auth-oauthlib`, operações
de listar/criar/deletar/reagendar eventos via `googleapiclient`. Ver `docs/fontes/google-calendar-api.md`.

### 4.2 Automação de navegador — as "mãos" do Viking

O Viking chama o **Jev** (`jev-ultrafast`) como **subprocesso**, rodando no ambiente do próprio Jev
(`uv run --directory <VIKING_JEV_DIR>`), e conversa com ele por um protocolo JSONL no stdout. O Jev
dirige uma Chrome real via Browser Harness/CDP.

Por que subprocesso e não import: o Jev não tem timeout de wall-clock nem cancelamento — seus
limites internos levantam exceção e a única parada limpa é entre passos. Como processo separado,
ganhamos prazo e kill de verdade (um objetivo travado não congela o chat), e o pin
`browser-harness==0.1.13` fica fora da venv do Viking.

Antes de qualquer tarefa, o runner faz a supervisão de saúde que o relatório de validação exige —
`daemon vivo != navegador pronto`: probe CDP real, tentativa de reattach, e no limite um restart do
daemon, com retentativas limitadas. Ver `docs/fontes/browser-harness.md`.

Isto substitui o controle local de PC via Windows-MCP como caminho padrão de execução. Detalhes do
stack e do incidente do daemon: `docs/arquitetura/browser-automation-stack.md`;
referências: `docs/fontes/browser-harness.md` e `docs/fontes/jev-typesafe.md`.

Princípios herdados da validação: cada tarefa cria sua própria aba (nunca reaproveita "a aba ativa
atual"); `done` do executor não é prova de sucesso — e `blocked` não é prova de fracasso; nunca
reexecutar uma mutação de navegador automaticamente após erro/timeout. Por padrão a aba fica aberta
e em foco ao terminar: o navegador é o do usuário, e uma aba que some é o avesso do esperado.

**Guardas contra loop.** O executor entra em ciclo quando o objetivo não é alcançável por nenhuma
ação — e o guard do próprio Jev não pega, porque ele só detecta página que *não* muda. Três camadas,
todas em `_jev_subprocess.py`: detector de ciclo em assinatura exata `(url, ação)`; detector em
assinatura ampla `(url sem query, tipo da ação)`, que pega o caso em que o alvo clicado muda toda
volta; e um teto próprio de 30 ações, metade do teto de 60 do Jev, limitando o custo do pior caso.
Os três nasceram de loops observados em uso real — ver `docs/diario-de-bordo.md`, 2026-09-20.

**Custo.** Cada passo é uma chamada paga ao modelo de decisão, que recebe até 6000 caracteres de
texto da página. Em site simples isso é desprezível (~US$0,0001 por tarefa); numa SPA densa como o
YouTube, medimos 24.507 tokens em 6 chamadas. Em dólar continua barato (~US$0,001), mas o texto da
página também entra no contexto do modelo de conversa e viaja no histórico — é por ali que uma
tarefa de navegador encarece os turnos seguintes.

### 4.3 Lembretes e notas

Armazenamento estruturado (SQLite, `data/viking.db`) com um schema deliberadamente genérico — ver
`src/lifeos/reminders/models.py`. "RAG-ready" significa: dados consistentes, com ids/timestamps/tipo,
prontos para indexação futura — **não** implica embeddings ou busca semântica hoje (ver seção 7).

### 4.4 Servidor MCP do Viking

O Viking expõe seu **próprio** servidor MCP
(`src/lifeos/mcp_server/`), com calendário e lembretes como tools. Isso permite que outras ferramentas
(Claude Desktop, Gemini CLI, etc.) chamem o Viking como um serviço, e não só o contrário.

## 5. Trilha de hardware (pausada)

O dispositivo de pulso (Arduino/ESP32, captura de áudio, controle local de PC via Windows-MCP) fica
**pausado, não descontinuado**. Código e docs mantidos em `archive/wristband-fail-test/` e
`docs/arquitetura/wristband-hardware-pausado.md`. Motivo da pausa: a automação de navegador é hoje o
caminho mais validado e útil para "mãos" do assistente; o hardware pode voltar depois, especialmente
para ações que precisem rodar localmente no dispositivo/PC (algo que um navegador não alcança).

## 6. Finanças e Pluggy (futuro)

Administração financeira continua sendo um objetivo core do Life OS a longo prazo, mas **não via entrada
manual** — o dono do projeto já observou que adicionar gastos manualmente (texto ou voz) não é
consistente o suficiente para ser confiável. A direção é integrar com a **Pluggy**
(agregador de open finance brasileiro, pluggy.ai) — já existe uma conta conectada lá; falta avaliar
custo/viabilidade de puxar dados sem pagar a API completa, ou pagando pouco. Ver
`docs/fontes/pluggy-open-finance.md`. Nenhum código de finanças existe ainda; o gancho de compatibilidade
é o schema genérico de `reminders/models.py` (campos `type`/`source`/`external_id`), que permite uma
linha `type="finance_transaction", source="pluggy"` no futuro sem migração de schema.

## 7. RAG (direção de longo prazo)

Hoje, "RAG-ready" significa apenas: schema estruturado e estável (ids, timestamps, tipos consistentes)
que não vai brigar com indexação futura. O que está **deferido** deliberadamente: embeddings, busca
semântica de verdade, e qualquer recuperação automática de contexto sobre notas/calendário/histórico de
navegação. Isso é fase futura — ver roadmap (seção 9).

## 8. Segurança e segredos

- Segredos reais (`.env`, credenciais OAuth do Google) vivem em `secrets/` (gitignored) e no `.env` da
  raiz — nunca commitados. Ver `AGENTS.md`.
- Princípio herdado do design original do Windows Agent (v1): ações irreversíveis ou sensíveis (deletar
  eventos, navegar em contas autenticadas, etc.) devem pedir confirmação explícita, não rodar
  silenciosamente. Isso vale também para a automação de navegador — controlar o Chrome real do usuário é
  uma capacidade privilegiada (acesso a Gmail, GitHub, dashboards autenticados), tratada como tal.

## 9. Roadmap

1. **Assistente CLI (atual)** — calendário + navegador + lembretes, unificados em `viking chat`.
2. **Servidor MCP do Viking** — expor calendário/lembretes para outras ferramentas.
3. **Revival do hardware (futuro)** — retomar o dispositivo de pulso como interface física, se/quando
   fizer sentido.
4. **Finanças via Pluggy (futuro)** — ingestão automática de transações, sem entrada manual.
5. **RAG / busca semântica (futuro)** — memória de longo prazo real sobre notas, calendário e navegação.

## 10. Perguntas em aberto

Herdadas de `docs/arquitetura/browser-automation-stack.md` (ainda relevantes):
- O Jev generaliza para SPAs/dashboards dinâmicos além dos casos testados (GitHub, Google Flights)?
- Quando o planejador (LLM geral) deve interromper o Jev em vez de deixá-lo continuar?
- Quais ações de navegador precisam de confirmação humana explícita?

Novas, da definição do Viking:
- Qual o custo real de acessar dados via Pluggy sem (ou com pouco) pagamento pela API?
- Qual modelo de autenticação o servidor MCP do Viking deve ter para aceitar clientes externos?
- Vale a pena portar `oauth.py`/`calendar_tools.py` como estão, ou já refatorar para suportar múltiplas
  contas Google no futuro?
