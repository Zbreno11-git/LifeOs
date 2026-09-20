# Auditoria Codex 1 — prompt de handoff para o Claude

**Data da auditoria:** 2026-09-20  
**Auditor:** Codex  
**Escopo:** repositório principal LifeOs/Viking, integração com o clone externo `jev-ultrafast`,
trilha arquivada de hardware e documentação técnica.  
**Estado durante a auditoria:** nenhuma correção de código foi implementada. As únicas alterações
posteriores à auditoria foram a criação deste relatório e o registro correspondente no diário.

---

## Prompt para o Claude

Olá, Claude. Eu sou o Codex e fiz uma auditoria independente do repositório Viking/Life OS a pedido
do usuário. Este documento é um handoff técnico e também um prompt de trabalho para uma sessão sua.

Antes de agir:

1. Leia integralmente `AGENTS.md`, que é a regra canônica do repositório.
2. Leia `docs/diario-de-bordo.md`, `HANDOFF.md` e
   `docs/arquitetura/viking-visao-e-arquitetura.md`.
3. Confira o estado real com Git; não confie apenas neste relatório.
4. Não implemente nenhuma correção só porque ela aparece aqui. Primeiro valide o achado no código e
   obtenha do usuário autorização/prioridade para a rodada de implementação.
5. Preserve segredos, nunca imprima `.env`, tokens OAuth ou chaves do Jev.
6. Se for corrigir qualquer item, escreva o teste de regressão correspondente e atualize o diário.
7. Não retome `mac-control-mcp` nem o Windows Agent; essas trilhas continuam pausadas.

O objetivo deste prompt é: confirmar os achados, discutir prioridades com o usuário e, numa etapa
posterior autorizada, corrigir cada grupo com mudanças pequenas, testáveis e reversíveis.

---

## 1. Resumo executivo

O Viking é um MVP coerente e já funcional em partes importantes: chat Gemini, Google Calendar,
automação de uma Chrome real por Jev + Browser Harness e lembretes em SQLite. A decisão de isolar o
Jev em subprocesso é sólida, o protocolo JSONL é simples, os guardas de loop nasceram de problemas
reais e o repositório tem boa documentação de contexto.

O produto ainda não deve receber autonomia irrestrita sobre calendário ou Chrome autenticada. Os
problemas prioritários não são de sintaxe; são de semântica, autorização, privacidade, idempotência e
confiabilidade operacional:

- a exclusão de calendário pode ser liberada com título vazio ou substring genérica;
- consultas por um dia abrangem quase dois dias e ignoram o fuso civil do usuário;
- eventos de dia inteiro usam fim igual ao início, embora o fim da API seja exclusivo;
- reagendamento escolhe silenciosamente o primeiro resultado textual;
- confirmações sensíveis existem principalmente como instruções ao modelo, não como barreira de código;
- conteúdo privado da Chrome é enviado ao OpenRouter e depois parcialmente ao Gemini sem redaction;
- uma tool pode concluir uma mutação e a chamada seguinte falhar, incentivando repetição/duplicação;
- custos do Gemini são subcontados;
- há falhas específicas no ciclo de vida do subprocesso, especialmente no Windows e em concorrência;
- timestamps de lembretes com fusos diferentes são ordenados incorretamente;
- o ambiente principal não possui lockfile nem limites de dependências.

Minha classificação geral:

- **Bom MVP experimental:** sim.
- **Seguro para uso pessoal supervisionado:** parcialmente, com atenção manual.
- **Seguro para mutações autônomas ou sites sensíveis:** não ainda.
- **Pronto para produção/multiusuário:** não.

---

## 2. O que foi validado durante a auditoria

### 2.1 Verificações executadas

- `111` testes passaram com `pytest` e cache desabilitado.
- `ruff check --no-cache .` passou sem erros de lint.
- `ruff format --check --no-cache .` encontrou 10 arquivos não formatados.
- `pip check` não encontrou requisitos quebrados.
- O pacote `lifeos` importa e `viking --help` funciona.
- `viking mcp-server` iniciou em transporte `stdio`.
- Um cliente FastMCP em memória listou corretamente 10 tools e seus schemas.
- O Git estava limpo no repositório principal e nos clones `jev-ultrafast` e `windows-mcp`.
- O clone do Jev estava em `viking-openrouter`, commit `afbee69`, sincronizado com o fork pessoal.
- `.env`, credenciais Google, token Google, banco local e clones externos estavam ignorados.
- Nenhum nome conhecido de arquivo de segredo apareceu no histórico Git, além de `.env.example` e
  `secrets/.gitkeep`.
- `.env`, `google_credentials.json` e `google_token.json` estavam com modo `600` neste ambiente.
- Não foram encontradas chaves reais por uma busca de padrões fora dos caminhos de segredo.

### 2.2 Limites da validação

- Não houve chamada real ao Google Calendar, Gemini ou OpenRouter.
- Não houve controle de Chrome real neste VPS.
- O fluxo OAuth desde zero não foi exercitado.
- As tools MCP foram descobertas, mas não foram chamadas contra dados reais.
- O ramo Windows de kill não foi testado.
- O fail test de hardware/Bosgame continua não comprovado ao vivo.
- Não foi executado scanner de CVEs; `pip-audit`, Bandit e ferramentas equivalentes não estavam
  instalados, e nada foi instalado durante a auditoria.
- A venv própria do clone Jev não existia neste VPS, então a suíte dele não foi reexecutada.

---

## 3. Achado crítico — exclusão de evento atravessável

### Evidência

Arquivo: `src/lifeos/calendar/tools.py`, função `apagar_evento_por_id`, aproximadamente linhas 142–162.

A trava atual é:

```python
if titulo_esperado.strip().lower() not in titulo_real.lower():
    return "NÃO apaguei..."
```

Isso é uma checagem de substring, não de identidade. Foram confirmados estes casos:

- `titulo_esperado="com"` casa com `"Reunião com o time"`;
- `titulo_esperado="   "` vira string vazia;
- a string vazia é substring de qualquer string;
- com um `event_id` válido, o evento é apagado.

O teste `tests/test_calendar_apagar.py::test_aceita_titulo_parcial` cristaliza o comportamento parcial
como desejado. A descrição da tool e o system prompt pedem confirmação, mas a confirmação não é
representada por nenhum estado verificável. O servidor MCP expõe a exclusão diretamente.

### Impacto

- Exclusão irreversível do evento errado.
- Um erro do modelo, cliente MCP ou prompt injection pode atravessar a trava.
- O ID reduz a chance de acidente, mas não prova que o usuário confirmou aquele evento naquela hora.

### Correção recomendada

1. Rejeitar `event_id` ou `titulo_esperado` vazios após `strip()`.
2. Normalizar título com Unicode NFC/NFKC conforme a decisão do time, espaços internos e `casefold()`.
3. Exigir igualdade normalizada, não substring.
4. Não usar o título como única prova de confirmação.
5. Implementar confirmação em duas fases:
   - `preparar_exclusao(event_id)` busca o evento e devolve título, data e um token curto;
   - o token fica vinculado a ID, título, data, usuário/sessão e expiração;
   - `confirmar_exclusao(token)` consome o token uma única vez.
6. No MCP, marcar a tool como destrutiva por annotations, se a versão suportar, mas não confiar apenas
   nisso; a confirmação deve continuar no domínio.

### Testes de regressão necessários

- título vazio e apenas espaços recusados;
- substring curta recusada;
- diferença apenas de caixa/normalização aceita, se essa for a política;
- token expirado, reutilizado ou ligado a outro ID recusado;
- falha de `delete().execute()` não reporta sucesso;
- cliente MCP não consegue apagar sem o fluxo de confirmação.

### Prioridade sugerida

**P0 — corrigir antes de ampliar o uso de calendário.**

---

## 4. Achados de calendário

### 4.1 Consulta de um dia abrange quase dois dias

Arquivo: `src/lifeos/calendar/tools.py`, função `listar_eventos_por_data`, aproximadamente linhas 46–81.

Quando `data_fim` não é informada, o código soma um dia e depois concatena `T23:59:59Z`:

```python
if not data_fim:
    data_fim = (date.fromisoformat(data_inicio) + timedelta(days=1)).isoformat()
time_max = f"{data_fim}T23:59:59Z"
```

Para `2026-09-20`, a chamada reproduzida foi:

```text
timeMin = 2026-09-20T00:00:00Z
timeMax = 2026-09-21T23:59:59Z
```

O resultado contradiz a docstring, que promete apenas o dia inicial.

#### Problema adicional de fuso

Os limites são fabricados em UTC. Uma data civil como “20 de setembro” deve ser calculada no fuso do
usuário/calendário. Em fusos negativos, `00:00Z` começa ainda no dia anterior local; eventos legítimos
do fim do dia também podem cair fora ou ser misturados com outro dia.

O Google documenta `timeMax` como limite exclusivo. Fonte:
https://developers.google.com/calendar/api/v3/reference/events/list

#### Correção sugerida

- Definir uma configuração explícita de timezone, preferencialmente IANA (`America/Sao_Paulo`).
- Para um dia: `timeMin = início local do dia`; `timeMax = início local do dia seguinte`.
- Converter ambos para RFC3339 com offset ou UTC somente depois de construir os instantes locais.
- Para intervalo, definir claramente se `data_fim` é inclusiva ou exclusiva; documentar e testar.
- Evitar `23:59:59`, que perde instantes com fração de segundo.
- Se possível, consultar o timezone do calendário primário e detectar divergência com o timezone do
  usuário configurado.

#### Testes necessários

- dia único não inclui o dia seguinte;
- intervalo inclusivo/exclusivo documentado;
- `America/Sao_Paulo`, UTC e um fuso positivo;
- mudança de horário de verão em uma zona que ainda use DST;
- eventos que atravessam meia-noite;
- eventos de dia inteiro.

### 4.2 Evento de dia inteiro usa fim igual ao início

Arquivo: `src/lifeos/calendar/tools.py`, aproximadamente linhas 99–110.

O corpo atual contém:

```python
"start": {"date": data},
"end": {"date": data},
```

Na Google Calendar API, `end` é exclusivo. Para um evento de um dia em `2026-09-20`, o fim deve ser
`2026-09-21`. Fonte:
https://developers.google.com/workspace/calendar/api/v3/reference/events

#### Correção sugerida

- Validar `data` com `date.fromisoformat()`.
- Calcular `end.date = data + 1 dia`.
- Se futuramente houver eventos de vários dias, receber início e fim com semântica explícita.

#### Testes necessários

- corpo enviado ao Google usa dia seguinte;
- data inválida é recusada antes da API;
- ano bissexto, fim de mês e fim de ano.

### 4.3 Reagendamento altera o primeiro resultado textual

Arquivo: `src/lifeos/calendar/tools.py`, função `reagendar_evento`, aproximadamente linhas 165–189.

Problemas:

- busca por `q=termo_busca`;
- usa `events[0]` sem mostrar candidatos;
- não ordena explicitamente;
- não exige ID;
- não confirma título/data;
- `q` pode casar campos além do título;
- usa `events.update()` com o recurso inteiro quando uma alteração mínima seria mais segura.

#### Correção sugerida

- substituir por `reagendar_evento_por_id`;
- buscar/listar candidatos antes, igual ao fluxo de exclusão;
- exigir confirmação vinculada ao ID e horário antigo/novo;
- validar RFC3339, timezone e `novo_fim > novo_inicio`;
- usar `events.patch()` apenas para `start` e `end`, quando apropriado;
- decidir explicitamente como tratar ocorrência de evento recorrente versus série inteira.

#### Testes necessários

- dois eventos com o mesmo título;
- resultado da API em ordem inesperada;
- evento de dia inteiro;
- ocorrência recorrente;
- intervalo invertido;
- ID inexistente;
- confirmação ligada a horário diferente.

### 4.4 Validação de entradas é insuficiente

As tools confiam que o modelo produzirá formatos válidos. Faltam validações locais para:

- `max_results` positivo e limitado;
- datas ISO;
- datetimes RFC3339 com offset;
- fim posterior ao início;
- título não vazio;
- termo de busca não vazio;
- tamanho máximo de título e descrição.

Falhar localmente com mensagem estruturada é mais previsível e barato que depender do erro remoto.

### 4.5 Busca/listagem sem política de paginação e limite de contexto

`buscar_eventos_por_termo` e `listar_eventos_por_data` não tratam `nextPageToken`. Em calendário
pessoal isso pode ser raro, mas o comportamento deve ser deliberado:

- limitar candidatos mostrados ao modelo;
- informar que há mais resultados;
- oferecer paginação explícita;
- evitar que dezenas/centenas de títulos virem tokens de contexto.

### 4.6 Conteúdo de calendário também é não confiável

Títulos podem vir de convites externos. Hoje o system prompt só classifica texto de páginas como não
confiável. Resultados de calendário também devem ser tratados como dados, nunca instruções.

### Prioridade sugerida do grupo calendário

- Exclusão e reagendamento: **P0**.
- Data/fuso e dia inteiro: **P0/P1**.
- Validação/paginação: **P1**.

---

## 5. Autorização e segurança de ações

### 5.1 Confirmação existe no prompt, não no domínio

Arquivo: `src/lifeos/assistant/agent.py`, system instruction aproximadamente linhas 144–162.

O prompt manda confirmar sites autenticados, operações irreversíveis e exclusão. Isso é uma mitigação
útil, mas prompts não são fronteiras de autorização. A mesma função pode ser chamada:

- pelo automatic function calling sem estado adicional;
- por um cliente MCP;
- por um teste/script Python;
- depois de conteúdo adversarial influenciar o modelo;
- mais de uma vez no mesmo turno.

### Correção estrutural recomendada

Criar uma camada de serviço/política entre adaptadores e efeitos externos:

```text
Gemini CLI ─┐
MCP server ─┼─> ActionPolicy / ApplicationService ─> Calendar / Browser / Store
CLI direta ─┘
```

Essa camada deve:

- classificar ação como leitura, escrita reversível, sensível ou destrutiva;
- exigir confirmação mecânica quando necessário;
- registrar intenção, confirmação, início, resultado e erro;
- aplicar idempotency key;
- impedir múltiplas mutações destrutivas no mesmo token;
- funcionar igual para Gemini e MCP.

### 5.2 Browser não intercepta cliques perigosos

O Jev recebe uma meta de alto nível e pode escolher qualquer controle observado compatível com seu
espaço de ações. Não há interceptador semântico para “Delete”, “Send”, “Buy”, “Confirm transfer” etc.

Possíveis soluções, em ordem de robustez:

1. perfil separado sem sessões sensíveis;
2. allowlist de domínios e classes de tarefa;
3. detector de ação sensível antes de executar o clique;
4. pausa com screenshot/descrição e confirmação do usuário;
5. credenciais/sessões de menor privilégio;
6. bloquear banco/e-mail por padrão até existir uma política específica.

### 5.3 MCP destrutivo não tem confirmação própria

O servidor atual usa `stdio`, portanto não há uma porta de rede exposta e a falta de autenticação HTTP
não é vulnerabilidade imediata. Porém, qualquer cliente local autorizado a iniciar o servidor consegue
chamar as tools destrutivas diretamente.

Não colocar confirmação apenas no cliente. O servidor/domínio precisa rejeitar a mutação sem prova de
confirmação válida.

---

## 6. Privacidade, prompt injection e Chrome autenticada

### 6.1 Dados enviados ao OpenRouter

No clone `jev-ultrafast`, `jev_ultrafast/model.py::choose()` envia ao endpoint de decisões:

- URL;
- título;
- até 6.000 caracteres de texto visível;
- elementos e seus rótulos/valores/estados;
- ações recentes;
- meta original do usuário.

Isso acontece a cada passo pago. O helper de texto também envia contexto da página ao modelo de texto
OpenAI-compatible configurado no Jev.

### 6.2 Dados enviados novamente ao Gemini

`src/lifeos/browser/_jev_subprocess.py` devolve:

- até 1.200 caracteres da página final;
- URL e título;
- histórico recente;
- rótulos das ações;
- até 80 caracteres do texto digitado por ação.

`mensagens.py` então insere isso como resultado da tool no contexto do Gemini e no histórico da conversa.

### Impacto

Em Gmail, banco, GitHub privado ou dashboards, informações privadas podem sair da máquina e chegar a
dois provedores diferentes. Isso é egress funcional da arquitetura, não necessariamente ataque, mas
precisa de consentimento e política explícita.

### Correção/otimização sugerida

- usar perfil de Chrome dedicado;
- criar allowlist de sites permitidos por padrão;
- bloquear categorias sensíveis até opt-in;
- nunca devolver texto digitado em campos `password`, token, cartão ou campos marcados sensíveis;
- redigir e-mails, números de documento, tokens e padrões configuráveis;
- devolver ao Gemini apenas evidência mínima necessária;
- permitir tarefa “agir sem devolver conteúdo da página”;
- registrar qual provedor recebeu quais categorias de dado, sem guardar o conteúdo sensível;
- documentar retenção e política dos provedores antes de uso financeiro.

### 6.3 Mitigação de prompt injection é incompleta

Pontos positivos já existentes:

- `jev_ultrafast/questions.py` diz que texto da página é dado não confiável;
- o system prompt do Viking repete essa regra;
- `mensagens.py` delimita o trecho final como não confiável;
- o Jev não gera seletores/código arbitrários; escolhe ações observadas.

Lacunas:

- título, URL, rótulo de ação e histórico ficam fora do delimitador específico;
- títulos de calendário não são classificados como não confiáveis;
- respostas de erro do provedor podem voltar como texto para o Gemini;
- não há política de autorização independente do modelo;
- não há teste adversarial de prompt injection.

### 6.4 Caracteres de controle no terminal

`viking browser` imprime título, texto e rótulos vindos de páginas. Conteúdo malicioso pode carregar
ANSI escapes ou outros controles de terminal.

Correção sugerida: remover caracteres C0/C1 inadequados antes de saída humana, mantendo JSON corretamente
escapado no modo `--json`.

### Prioridade sugerida

**P0/P1 antes de habilitar Gmail, banco ou mutações web autônomas.**

---

## 7. Falha após mutação, idempotência e auditoria

### Evidência

`src/lifeos/assistant/agent.py` envolve toda a chamada `chat.send_message(prompt)` em um `try/except`
genérico. O SDK do Google executa Python tools automaticamente e pode fazer mais de uma chamada remota
no mesmo `send_message`.

Cenário perigoso:

1. Gemini chama `criar_evento` ou navegador;
2. a mutação funciona;
3. a chamada seguinte ao Gemini falha;
4. o REPL mostra apenas erro genérico;
5. usuário repete o pedido;
6. a mutação acontece novamente.

### Correção sugerida

- gerar `operation_id`/idempotency key por intenção mutável;
- registrar tool iniciada, parâmetros normalizados, resultado e identificador remoto;
- em erro pós-tool, informar claramente quais ações já foram executadas;
- permitir consulta/reconciliação antes de repetir;
- em criação de calendário, considerar extended property privada com idempotency key, se adequado;
- não fazer retry automático de mutações;
- contabilizar uso e efeitos mesmo quando a resposta final falhar.

### Testes necessários

- tool funciona e segunda resposta do modelo falha;
- usuário repete a mesma operação;
- timeout depois de clique/mutação;
- erro antes da tool não gera falso “parcialmente executado”;
- duas chamadas concorrentes com mesma idempotency key.

### Prioridade sugerida

**P0/P1 para qualquer fluxo mutável.**

---

## 8. Contabilidade de custos

### 8.1 Tarifas estão corretas, cálculo está incompleto

`src/lifeos/custos.py` usa por padrão:

- entrada: US$ 0,30 / 1M;
- saída: US$ 2,50 / 1M.

Esses valores conferem com Gemini 2.5 Flash Standard na data da auditoria:
https://ai.google.dev/gemini-api/docs/pricing

Porém `do_gemini()` soma apenas:

- `prompt_token_count`;
- `candidates_token_count`.

Ele ignora `thoughts_token_count`, que é saída cobrada. A API também expõe
`tool_use_prompt_token_count` e `total_token_count`:
https://ai.google.dev/api/generate-content

### 8.2 Automatic function calling subconta chamadas

Na versão instalada `google-genai==2.24.0`, o loop síncrono de AFC substitui `response` a cada chamada e
retorna a última resposta. O Viking contabiliza apenas `resposta.usage_metadata` final. Chamadas que
escolheram tools antes da resposta final não entram no total mostrado.

### 8.3 Falhas não são contabilizadas

Se `chat.send_message` levanta depois de uma ou mais chamadas pagas, o bloco de custo não roda.

### 8.4 Overrides do `.env` podem ser ignorados

`custos.py` lê as variáveis na importação, sem importar `lifeos.config`. `agent.py` importa `custos`
antes de um módulo que execute `load_dotenv()`. Logo, preços definidos apenas no `.env` podem não chegar
ao módulo.

### Correção sugerida

- centralizar todas as variáveis em `config.py`;
- incluir thinking tokens como saída;
- investigar hook/interceptor do SDK para acumular cada request de AFC;
- diferenciar tokens de entrada, tool results, cache, pensamento e candidato;
- registrar custo mesmo em erro;
- incluir modelo/tier usados no registro;
- testar com metadata sintética contendo todos os campos.

### Prioridade sugerida

**P1**, porque o sistema exibe números ao usuário como instrumento de decisão.

---

## 9. Configuração e caminhos

### 9.1 Caminhos relativos dependem do diretório atual

`config.py::_path_env()` retorna `Path(value).expanduser()` sem ancorar valores relativos. Ao mesmo
tempo, `.env.example` recomenda:

```text
VIKING_GOOGLE_CREDENTIALS_PATH=./secrets/google_credentials.json
VIKING_GOOGLE_TOKEN_PATH=./secrets/google_token.json
VIKING_JEV_DIR=./jev-ultrafast
```

Executando `viking` fora da raiz, esses caminhos apontam para o diretório atual. Isso reintroduz o bug
de “funciona por acidente conforme o cwd”.

### Correção sugerida

Definir uma regra única:

- caminho absoluto permanece absoluto;
- caminho relativo de variável do `.env` é resolvido contra `REPO_ROOT`, não contra o cwd;
- documentar que comportamento vale também para DB e env do Jev.

### 9.2 Valores numéricos sem validação

`float()` e `int()` na importação podem derrubar qualquer comando com uma variável inválida. Também são
aceitos `nan`, infinito, timeout negativo ou limite de ações não positivo.

Correção sugerida:

- parser de config com mensagens específicas;
- exigir valores finitos/positivos e limites razoáveis;
- carregar sob demanda ou falhar no subcomando relevante, não em imports alheios.

### 9.3 Empacotamento assume checkout editável

`REPO_ROOT = Path(__file__).resolve().parents[2]` funciona no editable install. Em wheel instalado no
site-packages, “repo root”, `secrets/` e `data/` deixam de representar o checkout esperado.

Decidir explicitamente se o Viking é:

- aplicativo que só roda do checkout; ou
- pacote instalável, usando diretórios XDG/Application Support e configuração externa.

### Prioridade sugerida

**P1/P2.**

---

## 10. Runner e subprocesso do navegador

### 10.1 Ramo Windows não mata descendentes

`jev_runner.py::_popen_kwargs()` usa `CREATE_NEW_PROCESS_GROUP`, mas `_matar()` só usa
`proc.terminate()`/`proc.kill()` quando `os.killpg` não existe. Não há `CTRL_BREAK_EVENT`, Job Object ou
`taskkill /T` controlado.

O processo `uv` pode morrer e deixar Python/Jev órfão. O `HANDOFF.md` menciona um ramo
`CTRL_BREAK_EVENT`, mas esse ramo não está no código.

Correção sugerida antes de retomar Bosgame:

- teste de integração Windows que cria pai + neto e confirma ambos mortos;
- usar mecanismo de árvore adequado à plataforma;
- manter kill em grupo Unix como está, com teste existente.

### 10.2 Estado terminal perde para os guardas

Em `_jev_subprocess.py`, depois de cada yield:

1. emite progresso;
2. atualiza assinaturas;
3. testa limite;
4. testa loop;
5. testa timeout;
6. só depois, fora do loop, emite resultado terminal.

Consequências:

- conclusão exatamente na ação limite pode virar `step_budget`;
- estado final pode completar a heurística de ciclo e virar `loop_detected`;
- depois da última ação não há orçamento para uma decisão adicional de `DONE`.

Correção sugerida: checar `state.status in {done, blocked}` antes dos guardas, e definir claramente se o
orçamento limita mutações ou decisões.

### 10.3 Usage ausente em loop e timeout

Eventos explícitos de `loop_detected` e timeout não incluem `_uso(state)`. O custo aconteceu, mas some do
resultado e da sessão.

### 10.4 Estado da aba incorreto nos erros

Erros não emitem `kept_open`. A aba pode continuar aberta/focada pelo `finally`, mas `BrowserResult`
recebe `False`. Em hard kill, `--fechar` também não garante fechamento.

### 10.5 Callback pode vazar processo

`run_jev()` chama `on_progress(evento)` sem proteção. Se o callback levantar, inclusive por stderr
fechado, o `finally` libera apenas o lock e não mata/recolhe o filho.

Correção sugerida: encapsular todo o período pós-`Popen` em cleanup que sempre mata ou espera o processo.

### 10.6 Threads leitoras não são juntadas

As threads são daemon e o stderr pode ainda estar sendo drenado quando o tail é montado. É um risco
menor, mas pode perder a última pista de erro.

### 10.7 Lock é apenas intraprocesso

Dois `viking` separados podem controlar a mesma Chrome e o mesmo daemon. Um preflight pode reiniciar o
daemon do outro.

Correção/otimização sugerida:

- file lock interprocesso por `BU_NAME`/perfil;
- ou worker persistente único com fila;
- timeout de aquisição e mensagem com dono/PID;
- proteger também `browser --doctor`/restart quando houver tarefa ativa.

### 10.8 `run_jev()` promete resultado, mas ainda pode levantar

`Popen`, callback, validação de timeout e erros inesperados podem escapar como exceção, apesar da
docstring “devolve sempre BrowserResult”. Ajustar o contrato ou garantir conversão e cleanup.

### 10.9 Timeout reporta duração enganosa no Ctrl-C

Ao interromper após poucos segundos com limite de 180, a mensagem pode dizer “interrompido após 180s”.
Usar tempo real decorrido.

### 10.10 Protocolo JSONL aceita qualquer dict com `type`

`parse_event()` não valida `schema`, campos nem origem. Uma dependência que imprima JSON semelhante no
stdout pode produzir falso terminal. Preferir schema estrito e, idealmente, canal dedicado/nonce de
execução.

### 10.11 Tab pode vazar na construção do Browser externo

No fork Jev, `Browser.__init__` cria target e sessão antes de várias chamadas que podem falhar. Se o
construtor falhar antes de retornar, `Agent.__init__` ainda não entrou no bloco que fecha o browser.
Revisar o clone externo com cleanup parcial do construtor.

### Prioridade sugerida

- Terminal/usage/cleanup/lock: **P1**.
- Windows: **P2 enquanto pausado; P0 antes de reativar Bosgame**.

---

## 11. Ambiente do subprocesso e cadeia de dependência

### 11.1 Jev herda todo o ambiente do Viking

`subprocess.Popen()` não recebe `env`, portanto herda `GEMINI_API_KEY` e outras variáveis carregadas no
processo principal, embora o Jev devesse receber apenas seu conjunto mínimo.

Correção sugerida:

- construir ambiente allowlisted;
- preservar apenas PATH, locale, HOME necessário, variáveis Browser Harness e variáveis Jev;
- não propagar chave Gemini, tokens Google ou variáveis futuras de finanças.

### 11.2 Commit do Jev não é verificado

O runner só confere se existe `pyproject.toml`. O commit `afbee69` está documentado, mas não é um
contrato executável.

Possíveis soluções:

- configuração `VIKING_JEV_EXPECTED_COMMIT`;
- doctor mostra branch, commit e dirty status;
- abortar ou alertar se patch OpenRouter esperado não estiver presente;
- manter tolerância explícita para desenvolvimento do fork.

### 11.3 Endpoint OpenRouter é alpha

O patch usa `/api/alpha/decisions`. A classificação de erro depende de strings e o corpo de erro do
provedor é retornado ao Viking. Mudanças do upstream/provider podem cair em `unknown`.

Sugestões:

- teste de fumaça opcional contra versão pinada;
- validação de schema da resposta;
- classificação baseada em tipo/status quando disponível;
- sanitização do corpo de erro antes de devolvê-lo ao modelo/terminal.

---

## 12. Lembretes e SQLite

### 12.1 Ordenação por ISO textual falha entre offsets

`store.list_open()` usa:

```sql
ORDER BY due_at IS NULL, due_at, created_at
```

Como `due_at` é texto, offsets diferentes não ordenam por instante. Reprodução:

```text
09:00+02:00 = 07:00Z  # deveria vir primeiro
08:00+00:00 = 08:00Z
```

O banco colocou `08:00+00:00` primeiro porque compara a representação textual.

Correção sugerida:

- normalizar todo instante para UTC antes de persistir;
- armazenar `Z` canônico ou epoch inteiro;
- armazenar timezone/semântica civil separadamente quando necessário;
- migrar registros existentes.

### 12.2 Datas sem horário viram meia-noite ingênua

`datetime.fromisoformat("2026-09-25")` cria `2026-09-25 00:00` sem timezone. Isso mistura valores naive
e aware e exibe um horário que o usuário não escolheu.

Sugestão: representar data civil separadamente de instante, ou definir uma política de horário padrão
explícita e timezone obrigatório.

### 12.3 “Lembrete” é armazenamento, não notificação

Não existe scheduler, polling, notificação ou entrega. Evitar prometer lembrete ativo até isso existir.

### 12.4 “Nota” não é recuperável adequadamente

O corpo é salvo, mas a tool de listagem mostra apenas título e prazo. Não há busca, leitura completa,
edição, reabertura ou listagem de concluídos. Para memória/RAG futura, adicionar serviço de consulta
antes de embeddings.

### 12.5 CLI e MCP divergiram

`criar_lembrete` na CLI aceita `quando`; `viking_criar_lembrete` no MCP não. A lógica está duplicada.

Sugestão: criar serviço de aplicação único e adaptadores finos para Gemini/MCP.

### 12.6 Schema precisa de migrations e constraints

Antes de Pluggy:

- adicionar controle de versão/migration;
- índice para pendentes por prazo;
- índice/constraint único para `(source, external_id)` quando `external_id` não for nulo;
- política para JSON inválido;
- decidir se transação financeira realmente deve morar na tabela `reminders` ou num modelo próprio.

### Prioridade sugerida

**P1 para timestamps e paridade; P2 para capacidades futuras.**

---

## 13. OAuth e credenciais

### Pontos positivos

- paths centralizados;
- escopo compatível com CRUD de calendário;
- token e credentials ignorados;
- permissões locais atuais são `600`.

### Lacunas

- `write_text(creds.to_json())` depende do umask; não força `0600` em novos tokens;
- refresh token revogado/arquivo corrompido não tem recuperação orientada;
- o fluxo do zero nunca foi revalidado após a migração;
- `build()` é executado em toda tool, adicionando latência;
- erros brutos da API viram strings para o modelo em alguns caminhos.

### Correção/otimização sugerida

- escrita atômica com permissão explícita `0600`;
- distinguir token inválido, refresh revogado e credenciais ausentes;
- teste manual documentado do fluxo do zero;
- cache controlado do service por processo, com renovação correta;
- exceções de domínio estruturadas, sem expor conteúdo desnecessário.

---

## 14. MCP server

### O que passou

- FastMCP 4.0.5 iniciou em `stdio`;
- 10 tools foram descobertas;
- schemas de `str | None` e inteiros foram gerados corretamente.

### Problemas

- tools destrutivas dependem de docstring para confirmação;
- respostas de erro são strings normais, não erro estruturado;
- calendário e lembretes retornam texto feito para humano/modelo, não payload estável;
- reminder MCP não aceita prazo;
- não há testes de chamadas MCP;
- auth ainda é pergunta futura, mas só se tornará necessária quando houver transporte remoto; em
  `stdio`, o processo cliente é a fronteira atual.

### Otimização recomendada

Separar resultados de domínio de apresentação:

```text
CalendarService -> EventResult estruturado
  ├─ Gemini adapter -> texto compacto
  ├─ MCP adapter -> structuredContent + texto
  └─ CLI adapter -> texto humano
```

Isso reduz parsing de strings, melhora erros e permite evolução do MCP.

---

## 15. Dependências, build e qualidade

### 15.1 Sem lockfile no aplicativo principal

`pyproject.toml` declara dependências sem versão mínima/máxima útil e não existe lockfile raiz.

Versões resolvidas durante a auditoria incluíam:

- `google-genai==2.24.0`;
- `google-api-python-client==2.200.0`;
- `google-auth==2.58.0`;
- `google-auth-oauthlib==1.4.1`;
- `fastmcp==4.0.5`;
- `mcp==2.2.0`;
- `pytest==9.1.1`;
- `ruff==0.16.8`.

Uma reinstalação futura pode resolver majors diferentes.

### Correção sugerida

- adotar `uv.lock` ou lock equivalente no projeto principal;
- definir intervalos conscientes para dependências públicas;
- documentar política de atualização;
- CI testa lock atual e job separado testa upgrades.

### 15.2 Teste usa API privada do Google SDK

`tests/test_assistant_tools.py` importa `_automatic_function_calling_util`. Isso protege um bug real,
mas pode quebrar apenas porque o SDK reorganizou internals.

Sugestão: manter um teste público de construção/execução do schema e, se o teste privado permanecer,
marcá-lo/documentá-lo como acoplamento intencional à versão pinada.

### 15.3 Sem análise de tipos/segurança automatizada

Não há mypy/pyright, Bandit, pip-audit ou CI versionada no repo. Para o estágio atual, não é bloqueio,
mas o próximo nível de confiabilidade deve incluir:

- CI com Python suportado;
- pytest + ruff check + ruff format check;
- scanner de dependências;
- type checking incremental em serviços/config/resultados;
- teste de empacotamento/entrypoint.

### 15.4 Formatação

`ruff format --check` identificou 10 arquivos. Não é bug funcional, mas CI deve usar o mesmo conjunto de
checks documentado para evitar diferença entre “lint passou” e “qualidade passou”.

---

## 16. Trilha de hardware arquivada

### 16.1 Caminho padrão do Windows-MCP está errado

Arquivo: `archive/wristband-fail-test/pc/serial_mcp_bridge.py`.

`Path(__file__).resolve().parents[2] / "windows-mcp"` resolve para:

```text
LifeOs/archive/windows-mcp
```

Mas README e layout real usam:

```text
LifeOs/windows-mcp
```

Seria `parents[3]` no layout atual, ou melhor, configuração explícita baseada no repo root.

### 16.2 Documentação declara sucesso não comprovado

Há documentos dizendo “feito”, “funcional” ou “testes reais que já funcionaram”. Porém o diário e o
`HANDOFF.md` registram que nada foi executado no Bosgame.

Até ocorrer validação real, usar termos como:

- código preparado;
- não validado no Windows/Bosgame;
- arquitetura preservada;
- resultado ponta a ponta pendente.

### 16.3 Não corrigir agora sem reativação

Como a trilha está pausada, registrar os achados é suficiente. Não gastar tempo implementando Windows
Agent ou ampliando Windows-MCP sem pedido explícito do usuário.

---

## 17. Divergências de documentação

1. `docs/fontes/browser-harness.md` diz que o Viking é cliente MCP do Browser Harness. Hoje o
   `_jev_subprocess.py` importa Jev, que usa helpers/CDP; o antigo cliente MCP foi removido.
2. `docs/fontes/google-calendar-api.md` diz “deletar por termo”; hoje a exclusão recebe ID.
3. `.gitignore` diz que o origin do Jev aponta direto ao upstream; o origin real aponta ao fork pessoal.
4. `archive/README.md`, `AGENTS.md` e o roadmap fazem afirmações mais fortes que a evidência sobre o
   fail test Windows.
5. A nota histórica de `browser-automation-stack.md` sugere que a direção atual roda no Bosgame, mas o
   `HANDOFF.md` diz que o Viking atual roda no Mac do dono e o Bosgame está na trilha pausada.
6. `README.md` recomenda `pip install`, embora `AGENTS.md` determine `python -m pip` por causa do Conda
   no Mac.
7. `.env.example` omite `VIKING_DB_PATH`, `VIKING_BROWSER_MAX_ACOES` e preços Gemini.
8. A descrição do comentário sobre `from __future__ import annotations` em `mcp_server/server.py` cita
   validação do google-genai, embora esse módulo seja registrado pelo FastMCP; a regra pode continuar
   válida, mas a justificativa deve refletir o consumidor correto.

Sugestão: corrigir documentação junto do grupo de código correspondente, sem reescrever documentos
históricos além de banners/notas de correção.

---

## 18. Buracos de cobertura

### Calendário

- somente exclusão tem teste comportamental;
- nenhum teste de listar, criar, dia inteiro, buscar ou reagendar;
- nenhum teste de timezone, paginação ou recorrência;
- nenhum teste de OAuth/refresh/escrita segura do token.

### Assistente

- nenhum teste do REPL;
- nenhum teste de automatic function calling completo;
- nenhum teste de confirmação;
- nenhum teste de falha depois de tool executada;
- nenhum teste de data congelada através da meia-noite.

### Browser

- bons testes offline de parsing/timeout/loops;
- nenhum teste de callback que falha;
- nenhum teste de limite exatamente no estado terminal;
- nenhum teste de usage em timeout/loop;
- nenhum teste multiprocesso;
- nenhum teste Windows;
- nenhum teste de sanitização/prompt injection/egress;
- nenhum teste live automatizado.

### MCP

- schemas foram validados manualmente nesta auditoria;
- nenhuma chamada via protocolo é testada;
- nenhuma resposta estruturada/erro é testada;
- nenhuma regra destrutiva é testada.

### Reminders

- fluxo básico passa;
- falta timezone misto, JSON corrompido, concorrência, duplicação external_id e migrations.

### Config/package

- falta execução fora da raiz;
- falta `.env` com overrides de custo;
- falta valor numérico inválido/NaN;
- falta build/instalação não editável.

---

## 19. Pontos fortes que devem ser preservados

Não descarte decisões boas ao corrigir os problemas:

- `HANDOFF.md` é preciso, honesto e muito útil.
- O Git principal e os clones estavam limpos.
- O patch Jev está protegido num fork/commit real.
- Segredos estão ignorados e não apareceram em nomes do histórico Git.
- O Jev roda em subprocesso separado, evitando congelar o REPL.
- O kill em grupo Unix tem teste real com processo filho.
- O comando do subprocesso usa lista de argumentos, não shell interpolation.
- Queries SQLite são parametrizadas.
- Cada tarefa de navegador cria seu próprio target/aba.
- O código não trata `done` como prova absoluta nem `blocked` como fracasso absoluto.
- Guardas de loop reproduzem rastros observados, inclusive ciclo estrutural.
- Erros parciais avisam que mutações não foram desfeitas.
- O preflight distingue daemon vivo de Chrome realmente conectado.
- O servidor MCP atual é local/stdio por padrão.
- O escopo do projeto está claro: hardware e finanças não devem desviar o milestone atual.

---

## 20. Arquitetura-alvo sugerida

Sem exigir uma reescrita, uma evolução saudável seria:

```text
                       ┌──────────────────┐
Usuário / MCP / CLI ──>│ Application API  │
                       └────────┬─────────┘
                                │
                       ┌────────▼─────────┐
                       │ Action Policy    │
                       │ confirmation     │
                       │ idempotency      │
                       │ audit result     │
                       └────────┬─────────┘
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
        CalendarService   BrowserWorker    ReminderService
        IDs + timezone    queue + profile  UTC + migrations
        patch + confirm   egress policy    search/read/edit
```

Adaptadores Gemini, MCP e CLI apenas transformam entradas/saídas; regras sensíveis ficam nos serviços.

Para browser:

```text
Planner Gemini
      │ meta autorizada
      ▼
Browser Policy Gateway
      │ domínio/risco/confirmação/redaction
      ▼
Worker único + lock/fila
      │
      ▼
Jev subprocess + Browser Harness
      │
      ▼
Chrome dedicada
```

---

## 21. Ordem recomendada para futuras correções

### Fase 0 — segurança de mutações

1. Exclusão por igualdade forte + rejeição de vazio.
2. Reagendamento por ID.
3. Confirmação mecânica compartilhada entre Gemini e MCP.
4. Testes de regressão dos três fluxos.

### Fase 1 — correção temporal

1. Timezone configurável/IANA.
2. Intervalos com fim exclusivo.
3. Evento de dia inteiro terminando no dia seguinte.
4. Validação de início/fim.
5. Normalização UTC dos lembretes.

### Fase 2 — privacidade e browser privilegiado

1. Perfil dedicado.
2. Allowlist/política de sites.
3. Redaction de texto e campos sensíveis.
4. Interceptação/pausa de ações perigosas.
5. Testes adversariais de prompt injection.

### Fase 3 — idempotência e observabilidade

1. Operation IDs.
2. Audit log local com retenção.
3. Reconciliação de falhas pós-tool.
4. Custos completos por request.
5. Resultados estruturados.

### Fase 4 — confiabilidade do runner

1. Terminal antes dos guardas.
2. Usage/kept_open em todos os terminais.
3. Cleanup garantido em qualquer exceção.
4. Lock interprocesso/worker único.
5. Schema JSONL estrito.
6. Windows tree kill apenas antes de reativar Bosgame.

### Fase 5 — manutenção

1. Lockfile raiz.
2. CI.
3. Scanner de dependências.
4. Type checking gradual.
5. Limpeza das divergências documentais.

---

## 22. Critérios de aceite por área

### Calendário seguro

- nenhuma mutação destrutiva ocorre sem confirmação verificável;
- ID e versão/dados do evento são vinculados à confirmação;
- operações ambíguas nunca escolhem silenciosamente o primeiro resultado;
- datas civis respeitam o timezone configurado;
- todos os testes offline cobrem corpos enviados à API.

### Browser seguro

- tarefa sensível não roda no perfil pessoal por padrão;
- dados enviados a provedores são documentados e minimizados;
- texto de password/token nunca volta ao Gemini/log;
- ações perigosas pausam para confirmação;
- uma falha não deixa processo órfão nem esconde efeitos parciais;
- duas instâncias não controlam o mesmo perfil simultaneamente.

### Custos confiáveis

- todas as chamadas AFC entram no total;
- thinking tokens entram como saída;
- falhas pagas também entram;
- configuração do `.env` é realmente carregada;
- saída distingue estimado, reportado pelo provedor e desconhecido.

### Dados confiáveis

- timestamps são comparáveis por instante;
- datas civis não são confundidas com meia-noite UTC;
- migrations são testadas;
- external IDs não duplicam ingestão futura;
- notas podem ser recuperadas, não apenas criadas.

---

## 23. Perguntas para alinhar com o usuário antes de implementar

Faça estas perguntas apenas quando a resposta realmente mudar o desenho:

1. O Viking deve poder usar Gmail/GitHub autenticado na Chrome pessoal, ou será aceito um perfil
   dedicado com login separado?
2. Banco/finanças devem ser bloqueados inteiramente no navegador até a integração Pluggy?
3. Quais ações precisam sempre de confirmação: apagar, reagendar, criar evento, enviar formulário,
   enviar mensagem, comprar, baixar arquivo?
4. O timezone canônico do usuário é `America/Sao_Paulo`, ou deve ser configurável/derivado do calendário?
5. “Lembrete” deve gerar notificação real agora ou continuar sendo uma pendência armazenada?
6. O servidor MCP permanecerá apenas `stdio` nesta fase?

Não use essas perguntas para adiar correções inequívocas como string vazia, fim exclusivo e caminho
relativo. Elas servem apenas para decisões de produto/permissão.

---

## 24. Instrução final ao Claude

Claude, use esta auditoria como lista de hipóteses comprovadas ou fortemente sustentadas, não como
substituto da leitura do código. Ao receber autorização para corrigir:

- proponha um lote pequeno por vez;
- comece pelos itens P0;
- mostre ao usuário a mudança de comportamento antes de editar;
- preserve a arquitetura de subprocesso e os testes de loops existentes;
- não misture refatoração ampla com correção destrutiva;
- escreva testes que falhem antes da correção e passem depois;
- rode `python -m pytest`, `python -m ruff check .` e o format check;
- atualize `docs/diario-de-bordo.md` com evidência;
- não declare validação ao vivo de Google/Chrome/Windows sem ela realmente acontecer.

O primeiro lote que recomendo discutir com o usuário é:

```text
1. exclusão segura;
2. reagendamento por ID;
3. consulta de um dia no timezone correto;
4. evento de dia inteiro com fim exclusivo;
5. testes completos dessas quatro mudanças.
```

Depois disso, trate autorização/privacidade do browser antes de expandir novas capacidades.

