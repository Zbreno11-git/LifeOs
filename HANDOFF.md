# HANDOFF — do Claude para o Codex

Escrito em 2026-09-20 por uma sessão do Claude Code, para o Codex assumir e **auditar** este
repositório. Assume que você não viu nada daqui antes.

> **Atualização (2026-09-20, mesmo dia):** o Codex fez a auditoria pedida abaixo —
> `auditoria_codex_1.md`. Uma sessão seguinte do Claude corrigiu a primeira leva de achados P0/P1
> (exclusão/reagendamento de calendário, contagem de custo do Gemini, vazamentos do runner do
> navegador) — ver `docs/diario-de-bordo.md`, entrada "primeira rodada de correções da auditoria".
> Em particular, o risco nº1 abaixo (trava de exclusão por substring) **já está corrigido**. O que
> ficou de fora dessa rodada está organizado em `sessoes.md`. O corpo deste documento abaixo foi
> mantido como escrito originalmente — não reescrevi para refletir as correções.

Antes de mais nada: leia `AGENTS.md` (guia canônico, compartilhado entre nós dois — o `CLAUDE.md` só
o importa) e `docs/diario-de-bordo.md` (log datado; a última entrada tem o detalhe cronológico de
tudo que descrevo aqui). Este documento não repete nenhum dos dois — ele te diz **o que eu fiz, o que
eu não consegui verificar, e onde eu suspeito que está errado**.

## O projeto em um parágrafo

**Viking** (codinome técnico *Life OS*, pacote Python `lifeos`, comando `viking`) é um assistente
pessoal em CLI que faz três coisas: administra Google Calendar, dirige um Chrome de verdade, e guarda
lembretes em SQLite local. É de uso pessoal de uma pessoa só — não é multiusuário, não tem servidor.
O dono roda no Mac dele; o desenvolvimento acontece num VPS Linux. Existe uma trilha de hardware
(assistente de pulso com ESP32) **pausada** — ignore, a menos que ele reative.

## O que eu construí nesta sessão

Duas entregas grandes, ambas com o produto funcionando ao vivo no fim.

**1. Reorganização do repo** (commit `2251586`). O repo era um esqueleto de outro produto (o
dispositivo de pulso) com peças soltas ao redor: um protótipo de bot de calendário sem README, um
clone de agente de navegador, e um doc de arquitetura que não mencionava nem a marca nem metade das
ideias. Consolidei: docs ganharam taxonomia (`docs/arquitetura/`, `docs/fontes/`), a trilha de
hardware foi para `archive/`, o protótipo de calendário virou pacote de verdade em `src/lifeos/`.

**2. O navegador de verdade** (commits `a8424ff` até `dd284de`). A ferramenta de navegador era um
stub que abria uma aba e ignorava o objetivo. Agora o Viking executa tarefas reais numa Chrome.

### A decisão de arquitetura que mais importa

O Viking chama o executor de navegador (**Jev**, em `jev-ultrafast/`, clone externo gitignorado) como
**subprocesso**, não como import:

```
viking chat → assistant/agent.py → browser/jev_runner.py
                                      │ subprocess.Popen
                                      ▼
                                   uv run --directory <JEV_DIR>
                                     python browser/_jev_subprocess.py
                                       └── jev_ultrafast.Agent → browser_harness → Chrome
                                   ◄── JSONL no stdout
```

Motivo: o Jev **não tem timeout de wall-clock nem cancelamento** — seus limites internos levantam
exceção e a única parada limpa é entre passos do gerador. In-process, uma tarefa travada congelaria o
REPL sem saída. Como processo separado, temos prazo e kill de verdade. De quebra, o pin
`browser-harness==0.1.13` fica fora da venv do Viking.

Consequência importante para você: **`src/lifeos/browser/_jev_subprocess.py` roda sob outro
interpretador**. Ele só pode importar stdlib + `jev_ultrafast`, e nunca `lifeos`. Há teste que falha
se alguém importar (`tests/test_browser_mensagens.py::test_runner_nao_importa_lifeos`).

## Onde olhar para auditar, em ordem de risco

Eu ordenei pelo que me deixaria mais desconfortável se estivesse errado.

### 1. `calendar/tools.py::apagar_evento_por_id` — a trava é fraca e eu sei

É a única operação destrutiva do sistema. O desenho é bom: exige `event_id` (que só sai de uma busca)
e confere `titulo_esperado` contra o título real. **Mas a conferência é substring:**

```python
if titulo_esperado.strip().lower() not in titulo_real.lower():
```

Uma palavra curta e comum fura a trava: verifiquei que `titulo_esperado="com"` apaga um evento
chamado "Reunião com o time". Se o modelo passar algo genérico, a trava não trava. Não corrigi porque quis te entregar isto explícito em vez de silenciosamente
"resolvido". Testes em `tests/test_calendar_apagar.py` (4) cobrem o caminho feliz e o de título
divergente, mas **não** cobrem o caso do título curto demais. Sugestão: exigir casamento forte
(igualdade normalizada, ou limiar mínimo de tamanho/similaridade).

### 2. `browser/jev_runner.py` — ciclo de vida de subprocesso

277 linhas, a parte com mais superfície de erro. Pontos que valem olho:

- `_matar()` usa `os.killpg` no grupo de processos, porque o `uv run` é pai do python real e matar só
  o `uv` deixaria o Jev órfão. **O daemon do browser-harness fica de fora do grupo de propósito** —
  ele deve sobreviver entre execuções. Confira que isso continua verdade.
- Duas threads leitoras (stdout→`queue`, stderr→`deque(maxlen=200)`) com laço principal por deadline.
  Escolhi isso em vez de `asyncio.create_subprocess_exec` porque o único chamador é síncrono e o
  roadmap inclui Windows. Vale checar se há como vazar processo ou thread em algum caminho de erro.
- **O ramo Windows nunca rodou.** `CREATE_NEW_PROCESS_GROUP`/`CTRL_BREAK_EVENT` estão escritos por
  analogia, não testados. Bosgame está no roadmap.
- Trava de execução única é `threading.Lock` — protege dentro de um processo, **não** entre processos.
  Dois `viking` simultâneos brigariam pelo mesmo daemon e pela mesma Chrome.

### 3. `browser/_jev_subprocess.py` — classificação de erro por substring

A tradução de exceção para código de erro casa **texto de mensagem** do `browser_harness` e do Jev
(`"chrome-not-running"`, `"permission-blocked"`, `"returned HTTP 401"`, `"budget"`...). Se o upstream
mudar uma string, o erro cai silenciosamente em `unknown` e o usuário perde a orientação específica.
Não sei qual é a melhor saída — talvez aceitar e ter teste de fumaça contra a versão pinada.

Também aqui: o supervisor do daemon (`preparar_navegador`) e os detectores de loop (`_oscilando`,
`_normalizar`). Os detectores são **heurística**, com risco real de falso positivo: exigem 3 ciclos
completos antes de cortar, mas uma tarefa legítima que revisite os mesmos estados muitas vezes seria
interrompida. Os testes replicam rastros reais de três loops observados em uso — leia antes de mexer.

### 4. Injeção de prompt — superfície nova e não resolvida

Texto de página entra no contexto do Gemini (até 1200 caracteres por tarefa, e depois viaja no
histórico da conversa). Hoje a mitigação é: truncagem, um delimitador dizendo "conteúdo não
confiável", e uma regra no `system_instruction`. **Isso é tudo.** Não há sanitização, e o Jev dirige
a Chrome logada do dono (Gmail, GitHub, banco). Se você achar um caminho por onde conteúdo de página
vira ação sem confirmação, é o achado mais importante que pode sair desta auditoria.

### 5. `custos.py` — números que podem estar mentindo

O custo do Jev é real (vem do provedor). **O do Gemini é estimativa minha**, com tarifas que eu
coloquei de memória (`VIKING_PRECO_GEMINI_ENTRADA=0.30`, `_SAIDA=2.50`, US$ por 1M tokens) e **nunca
conferi no painel do Google**. Estão marcadas com `~` na saída, mas se estiverem erradas, todo número
que mostramos ao dono está errado junto. Verificar a tabela vigente é uma tarefa de cinco minutos que
eu não fiz.

### 6. Cobertura de teste — o buraco é grande e específico

111 testes, todos offline. **Nada** toca Chrome, Gemini, OpenRouter ou Google Calendar de verdade.
Consequência: `calendar/tools.py` tem 7 funções e só a de apagar é testada; `calendar/oauth.py` e
`mcp_server/server.py` têm **zero** testes. O `mcp_server` nunca foi executado nem uma vez — é a
parte do produto com menos confiança de todas.

## O que está verificado ao vivo e o que não está

**Funcionou de verdade, na máquina do dono:** listar/criar/apagar evento; lembrete com prazo gravando
em SQLite; abrir site e manter a aba em foco; buscar e abrir o primeiro resultado; Ctrl-C matando o
subprocesso limpo; recuperação do daemon do Browser Harness após ele reportar 0 conexões.

**Nunca executado:** `viking mcp-server`; o ramo Windows do kill; qualquer coisa no Bosgame; o fluxo
OAuth do zero (o token veio do protótipo antigo).

**Limitação conhecida sem conserto na nossa camada:** ordinais além do primeiro ("abre o *segundo*
resultado") fazem o Jev tentar alvos indefinidamente, porque ele escolhe entre elementos da página e
não conta posições. Está como regra na descrição da tool e os detectores de loop cortam rápido, mas
a capacidade não existe. Se virar necessidade, o caminho é uma ferramenta nossa que leia a lista de
resultados e devolva URLs.

## Um aviso sobre o clone do Jev

`jev-ultrafast/` é um clone externo gitignorado, com git próprio. O `origin` aponta para o fork
pessoal `Zbreno11-git/jev-ultrafast`, branch `viking-openrouter`, que carrega **um patch nosso**
trocando o endpoint da TypeSafe pelo de decisões da OpenRouter — é a única razão pela qual a chave do
dono funciona. Esse patch passou um dia existindo só como modificação não commitada numa pasta
gitignorada; qualquer `git checkout` o teria apagado. Não mexa nessa pasta sem ler
`docs/fontes/jev-typesafe.md`.

## Como rodar

Está tudo em `AGENTS.md`, seção "Comandos". O resumo: `pip install -e ".[dev]"`, `pytest`,
`ruff check .`. Para exercitar o navegador sem gastar token de modelo:
`viking browser --url ... --goal ...` — esse subcomando existe justamente para isolar falha de
navegador de falha de modelo. E `viking browser --doctor` antes de culpar o código.
