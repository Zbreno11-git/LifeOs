# Sessões — planejamento de trabalho

Doc vivo para organizar o que vem depois de `auditoria_codex_1.md` (auditoria do Codex,
2026-09-20). Cada sessão de trabalho aqui cabe em ~1h30: revisão → implementação → teste →
commit → push, no mesmo formato da Sessão 1. O que não coube numa sessão vira o começo da
próxima — nada fica perdido, só adiado.

Como usar: ao abrir uma sessão nova, pega o primeiro item não riscado da fila, confirma escopo e
decisões de produto com o dono se a auditoria deixou isso em aberto (seção 23 dela), implementa,
testa, atualiza `docs/diario-de-bordo.md`, e marca aqui o que ficou feito e o que precisou ser
adiado por tempo.

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

## Sessão 2 — config previsível + lembretes com instante correto

- §9.1: caminho relativo de env (`VIKING_DB_PATH` etc.) resolve contra o `cwd`, não contra
  `REPO_ROOT` — medido: rodar de pastas diferentes usa bancos diferentes. Ancorar em `REPO_ROOT`.
- §9.2: valor numérico inválido numa env (`VIKING_BROWSER_TIMEOUT_S=abc`) derruba qualquer
  comando do Viking no import, não só o navegador — validar com mensagem específica.
- `.env.example` ainda não documenta `VIKING_DB_PATH`, `VIKING_BROWSER_MAX_ACOES` e os preços do
  Gemini (o `VIKING_TIMEZONE` novo da Sessão 1 já foi documentado).
- §12.1: `list_open()` ordena `due_at` como texto — medido no sqlite, `08:00+00:00` (=08:00Z) veio
  antes de `09:00+02:00` (=07:00Z), que é o horário real mais cedo. Normalizar para UTC na escrita
  + migração dos registros existentes. §12.2: data sem horário vira meia-noite ingênua.
- Índice em `due_at` (`reminders/store.py`) — hoje toda listagem varre a tabela inteira.

## Sessão 3 — paridade MCP e resultados estruturados

- §12.5: `viking_criar_lembrete` (MCP) não aceita `quando`/prazo, diferente de `criar_lembrete`
  (CLI/Gemini) — mesma lógica duplicada e divergente. Extrair um serviço único, adaptadores finos
  para Gemini/MCP/CLI.
- §14: respostas do MCP são texto para humano, não payload estável — considerar
  `structuredContent` para calendário/lembretes.
- Primeiro teste chamando o MCP pelo protocolo de verdade (hoje só descobrimos os schemas).
- O teste do future-import (`test_assistant_tools.py`) só cobre `FERRAMENTAS` (as tools do
  Gemini) — se um dia `mcp_server/server.py` voltar a registrar alguma dessas funções também como
  tool do Gemini, nada pega a regressão. Ver se vale um teste dedicado.

## Sessão 4 — privacidade e egress do navegador

- §6: nunca devolver texto digitado em campo de senha/token/cartão para o Gemini ou para o
  terminal.
- Redaction de e-mail, documento e outros padrões configuráveis no `page_text` antes de sair do
  subprocesso do Jev.
- §6.4: sanitizar caracteres de controle C0/C1 antes de imprimir título/texto de página no
  terminal (`viking browser` sem `--json`).
- Teste adversarial de prompt injection (uma página que tenta instruir o modelo via texto).
- Decisão de produto pendente (perguntar ao dono, seção 23 da auditoria): banco/e-mail devem ser
  bloqueados por padrão no navegador até existir uma política explícita?

## Sessão 5 — confirmação mecânica

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
- §15.4: `ruff format --check` ainda aponta 10 arquivos pré-existentes (de antes da auditoria) —
  não mexidos nesta sessão de propósito, para não misturar formatação com correção de bug.
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
calendário.
