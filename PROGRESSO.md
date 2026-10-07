# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-10-06 ~23:30Z: Sessão 11c aberta e planejada (backup no Drive); C0 em curso

**Estado (2026-10-06 ~23:30Z):**
- A 11c foi aberta depois de um compact. As conferências bateram com o bloco anterior:
  - `2386 passed`;
  - CI `success` em `12e775e`;
  - a infraestrutura com 11 ✅;
  - o motor `bbcba1a` com 17 ✅;
  - o Scheduler `ENABLED`.
- **As duas rodadas de perguntas foram respondidas**, e o plano foi aprovado (logo abaixo deste
  bloco, "Plano — Sessão 11c"; as respostas na tabela dele; D63).
- **O lock** (opentelemetry-api 1.45.1) está em `d4f5127`, com `2386 passed` antes e depois.
- **A D51 foi medida (2026-10-06 22:27Z, com o ok do dono): pode.**
  - `GET /smart-transfers/preauthorizations` → 403 `PAYMENT_INITIATION_NOT_ALLOWED`;
  - `GET /payments/requests` → 200, 0 pedidos;
  - as docs dizem que todo PIX avulso exige a autorização no banco.
  - A mudança das finanças vai para a **11d nova** (resposta do dono).
- **No ar:** o motor `bbcba1a`, sem mudança.

**Checkpoints da 11c:**
- C0 ✅: o lock em `d4f5127`, os docs em `8db5ab7`.
- C0b ⬜: a medição de 24 h, só depois de 2026-10-07 ~17:00Z.
- C1 ✅ (2026-10-06, commit às 23:39Z):
  - `backup/formato.py`: o arquivo versionado, que `ler` confere inteiro;
  - a cópia do registro (`registro_interface.CAMPOS_DA_COPIA`, `exportar`/`importar` nos dois
    stores e `registro.exportar`/`importar`);
  - `todos`/`importar` dos lembretes no `Protocol` (o SQLite ganhou `importar`, o Firestore
    `todos`);
  - `custos.exportar_gastos`/`importar_gasto`.
  - Medido: `2437 passed`; ruff, format e mypy limpos; mutações `10 · mortas pelo teste esperado:
    10` (8 novas e a reancorada do `store: add`, que passou a casar duas vezes).
- C2 ✅ (2026-10-06, commit às 23:48Z):
  - o token do Drive (`config.DRIVE_TOKEN_PATH`/`_ARQUIVO`, `drive_no_motor`, o `google_auth` na
    nuvem);
  - `backup/drive.py` (só cria, lista e baixa; o envio dentro de `registro.acao("backup.drive")`;
    5xx = `incerta`);
  - `backup/rodada.py` (`estado/backup` só depois do Drive);
  - `POST /tarefas/backup` (só o `agendador@`);
  - `/versao` com `backup`/`backup_em`;
  - `viking backup` e `--login`;
  - o segredo `viking-drive` no script (opcional, como o do Gmail; `_token_do_mac` generaliza a
    conferência);
  - a régua dos efeitos enxerga `files().create`;
  - `backup/` no mypy.
  - Medido: `2458 passed`, ruff, format e mypy (38) limpos; mutações `9 · mortas pelo teste
    esperado: 9` (7 novas e 2 reancoradas pela generalização do token).
- C3 ✅ (2026-10-07, commit às ~04:05Z):
  - `backup/conferir.py` (`viking backup --conferir`): restaura num `viking.db` temporário (o real
    intocado, provado por sha256) e compara com a nuvem;
  - `/lembretes/impressoes` ganhou os instantes `criado`/`mudou`, para separar "mudou depois" de
    "divergente";
  - `backup/restaurar.py` (`--restaurar ARQUIVO [--executar]`) e `POST /backup/importar` (só o
    `cli@`, formato conferido, nunca sobrescreve);
  - o aviso de 48 h na abertura do `viking chat --nuvem`.
  - Medido: `2476 passed`; ruff, format e mypy (40) limpos; mutações `7 · mortas pelo teste
    esperado: 7`.
- C4 ✅ (2026-10-07, ~04:10Z):
  - o passo `backup` no `scripts/nuvem.py` (a tarefa `viking-backup`, `0 9 * * *` UTC, e um
    `jobs run` ao ligar; `_tarefa_certa` parametrizada);
  - as provas do deploy: `/fumaca/segredos` com `drive`, `/versao` `backup` coerente, `cli@`
    recusado em `/tarefas/backup`, e o último backup com menos de 48 h com o passo pronto;
  - as recusas sem terminal do Gmail falam com o dono e citam `viking chat --nuvem` na nuvem;
  - os docs (`AGENTS.md`, `.env.example`, as fontes do GCP e do OAuth).
  - Medido: `2488 passed`; ruff, format, mypy (40), gitleaks e `uv lock --check` limpos; a
    varredura de controles nos 11 arquivos; mutações `7 · mortas pelo teste esperado: 7` (4 novas
    e 3 reancoradas).
- C5 ⬜.

**Próximo passo exato:** o C5. A rodada inteira de mutações e o `docker build` em background, as
duas passadas de revisão, o push e o CI pelo SHA. Depois, pedir os oks na hora:
1. `--executar segredos`, que cria o `viking-drive` vazio;
2. o deploy;
3. o roteiro do Mac (o login, o segredo);
4. o `--executar backup`;
5. o `--conferir` no Mac.

**Reler, nesta ordem:**
- `CLAUDE.md`/`AGENTS.md`;
- este bloco e o plano da 11c logo abaixo;
- `sessoes.md` (a 11c e a 11d);
- `docs/decisoes.md` (D51, D56–D63);
- o índice de `docs/erros.md` e as classes 2, 4, 5 e 6;
- as skills `software-build`, `testes-que-provam`, `dados-e-banco`, `nuvem-e-deploy`,
  `seguranca` e `integracoes`.

**Não pode ser esquecido:**
- **O backup nunca apaga nada no Drive** (resposta do dono: todas as cópias ficam). O módulo do
  Drive só cria, lista e baixa.
- **O token do Drive** (`drive.file`) faz o login no Mac e sobe ao Secret Manager como o do Gmail;
  o VPS não o guarda.
- **O `--conferir` restaura num `viking.db` temporário;** o real não muda.
- **O cliente OAuth do Google mora noutro projeto do dono.** A API do Drive já está ligada lá
  (medido em 2026-10-06).
- **O motor envia e-mail sozinho**, a cada minuto, só para a conta do dono: um lembrete de teste
  na nuvem vira e-mail de verdade.
- **O código de aprovação** nunca vai ao Gemini, ao MCP, ao registro, ao log nem por e-mail. Na
  nuvem, vai só no `ao_dono`, e no motor o stdout e o stderr são o log.
- **O VPS:** nada que envie, apague ou arquive roda daqui; todo `gcloud` leva `--project`; segredo
  só pela entrada padrão.
- **A chave da Pluggy alcança PIX:** nada a usa sem o pedido do dono, e nunca uma escrita.
- **Rotina:**
  - mutações em background, sem `timeout`, com a saída num arquivo, e nada editado enquanto
    rodam;
  - nenhuma checagem antes de commit com `| tail`;
  - migração publicada não se edita;
  - nenhum `<…>` dentro de um comando para o dono colar.
- **O fuso do dono:** Seattle até ~fim de outubro, depois o Brasil (perguntar a cidade).

**Depende do dono:**
- os oks do deploy e do passo `backup`;
- no Mac: o login do Drive (`viking backup --login`) e o `segredo viking-drive --executar`;
- a saída do `viking backup --conferir`.

**Antes de confiar neste bloco:**
- `git status --short` vazio, HEAD = remoto, `ls .mutacao.lock` → não existe;
- `VIKING_EXIGIR_EMULADOR=1 .venv/bin/python -m pytest -q` → `2386 passed` (antes do C1);
- `gh run list --commit $(git rev-parse HEAD)` → `success`;
- `python scripts/nuvem.py` → 11 ✅; `python scripts/nuvem.py deploy` → o motor `bbcba1a`,
  17 ✅.

### 2026-10-06 — o fechamento da 10c e da 11 (o registro)

**Depois do compact (~16:30Z):** as conferências bateram com o bloco anterior (`2380 passed`,
17 ✅, 10 ✅ + ⬜, `viking-gmail` 0 versões, 19 versões no lock). O lock em `53dda98`; as
respostas do dono (a prova passou sem navegador; a próxima é a 11c); a pausa pedida e o estudo do
Browser Use Cloud → D62 (`66cf7d9`).

**O portão passou (2026-10-06, ~16:45–17:00Z, com os oks do dono no chat):**
- **10c C6 ✅:** no Mac, `segredo viking-gmail --executar` → "✅ viking-gmail: versão nova
  enviada (1 habilitada(s))"; no VPS, `viking-gmail: 1 versão(ões)`.
- **10c C7 ✅:** `deploy --executar` → o motor **`66cf7d9`** no ar com os 3 segredos como volume;
  17 ✅ (`{'gemini': True, 'agenda': True, 'gmail': True}`, `gmail: True`, log 0 erro).
  `prova-chat "quantos e-mails não lidos chegaram hoje?"` (o argumento é **posicional**; o plano
  da 10c dizia `--mensagem`) → `HTTP 200 em 6.1 s`, 9969 tokens, ~US$ 0,003389, "Chegaram 16
  e-mails não lidos hoje.". O log da revisão (22 linhas desde 16:50Z): nem a pergunta nem a
  resposta; os únicos 4 dígitos são a porta 8080; 0 erro.
- **11, agendador ✅:** `--executar agendador` → a API, o `viking-agendador@`, o `run.invoker` e a
  tarefa `viking-lembretes` em `southamerica-east1` (aceita); "✅ agendador: a cada minuto, como
  agendador@, só na rota do envio". 4 min depois: a tarefa `ENABLED`, última execução
  16:57:03Z sem erro; `deploy` → `envio_de_lembretes: True (esperado True)`, os três invocam, 0
  erro.
- **Falta:** a prova do lembrete com o Mac desligado (roteiro entregue ao dono), a migração no
  Mac (`viking lembretes --migrar --executar`), o C8/C9 da 10c e o fechamento da 11; então a 11c.
- **A prova do lembrete e a migração (2026-10-06, no Mac):** criado pelo chat da nuvem para
  10:02 Seattle (17:02:00Z); o motor enviou às 17:02:02.9Z (Firestore); o e-mail na caixa às
  10:02. `viking lembretes --migrar --executar` → "✅ Migrado: 5 copiado(s), todos conferidos".
- **O C9 da 10c no Mac:** passou (o diário tem a lista); um defeito achado (a resposta vazia do
  Gemini calada) e consertado em `bbcba1a` (6 testes, 4 mutações, `2386 passed`, CI `success`),
  publicado com o ok do dono (17 ✅); refeitos no Mac os dois testes sem terminal: a pergunta
  responde, a limpeza recusa sem código.

**O que a 11 já tem (C0–C5 ✅; o C4 e o C5 em detalhe logo abaixo, o resto nos bullets "C0…C3" do fim do bloco):**
- **C1:** o Gmail opcional na nuvem; a identidade conferida por rota (`motor.QUEM_FALA`); o
  texto de sistema com `onde`.
- **C2:** a fila das mãos (`maos/fila.py`, `fila_firestore.py`, `pedir.py`) e
  `navegar_e_executar` no chat da nuvem.
- **C3:** `viking maos` (`maos/mac.py`).

**O C4 fechou (2026-10-01, ~05:00Z; commit "C4 da 11").** O código descrito no plano (fase 4)
mais o que os testes acharam:
- `tests/test_lembretes_nuvem.py` (41): o caminho do Mac contra o motor **em processo**
  (`TestClient` + o token do `viking-cli@`; a sessão troca `config.STORE`, o token do Gmail,
  `service.store`, `envio.store` e `registro._STORE` só durante cada pedido) e o emulador:
  migrado grava na nuvem e o `viking.db` não muda; "migrando" não grava; o ensaio não copia; sem
  o envio ligado recusa e não marca; com ele copia tudo e confere; de novo = "já migrou"; queda
  no meio retoma; divergente não é sobrescrito; a nuvem que diz que gravou e não gravou é pega
  pela conferência; `--enviar` recusa; o MCP não escreve no stdout; `/tarefas/lembretes` só do
  agendador, só contagens, sem reler os atrasados, parada não liga; `/versao`; o aviso; a
  migração 7 sobre um banco da 6.
- `tests/test_reminders_transporte.py` (25): ida e volta pelo JSON, recusas, a impressão muda
  com cada um dos 14 campos e não com o fuso.
- **Defeitos achados e consertados:** (1) depois de migrado, a nuvem fora ou a cópia em curso
  subiam como exceção crua no chat do Mac, no MCP e na CLI → `onde.Indisponivel` (base de
  `MigracaoEmCurso`; `service` converte o `ErroDaNuvem`), tratada nos três adaptadores; (2)
  `--migrar --executar` num Mac já migrado dizia "✅ Migrado: 0 copiado(s)" →
  `Relatorio.migrou_agora`; (3) `viking lembretes --nuvem` dizia sempre que o e-mail "ainda não
  existe" → segue o `/versao`; (4) a queda no meio da cópia não dizia para rodar de novo; (5)
  `agendador.ligado()` era verdade sem o token do Gmail no motor (uma rodada sem vencido termina
  sem parar) → exige `config.gmail_no_motor()`.
- Mutações do C4: `python scripts/mutacoes.py "migração:" "firestore: importar" "lembretes na
  nuvem:" "agendador:" "motor: /" "transporte:"` → `mutações: 24 · mortas pelo teste esperado:
  24`, e a do Gmail no `ligado` 1/1.
- Portões: `VIKING_EXIGIR_EMULADOR=1 pytest -q` → `2360 passed`; ruff "All checks passed!";
  format "146 files already formatted"; mypy "Success: no issues found in 34 source files";
  gitleaks "no leaks found"; `uv lock --check` ok.

**O C5, código (2026-10-01, ~05:40Z; commit "C5 da 11: o código"):**
- `scripts/nuvem.py`: o `viking-maos@` no passo `contas` (`DO_DONO = (CLI, MAOS)`: criada, e o
  dono com `serviceAccountTokenCreator` nas duas); o `run.invoker` das duas no deploy; a prova
  "quem invoca" (`_invocadores_certos`: cli@ e maos@ sempre, agendador@ permitido, ninguém mais);
  as provas das portas (`_provas_das_portas`: cli@ recusado em `/maos/pegar`, maos@ recusado em
  `/versao`, maos@ entra em `/maos/pegar` com um pedido torto → 400, nada pego) e a do
  `envio_de_lembretes` (esperado = o Gmail montado e o passo `agendador` pronto); o passo
  **`agendador`** (a API do Scheduler, o `viking-agendador@`, o `run.invoker`, a tarefa
  `viking-lembretes` `* * * * *` POST em `/tarefas/lembretes` com OIDC e a audience do motor,
  `--attempt-deadline=250s`, sem retentativa), **escrito, não executado** (depois do portão).
- `scripts/limpar_lembretes_de_teste.py`: `--aplicar` recusa com a marca da migração.
- O aviso do lembrete na nuvem e a docstring do cliente, que ficaram falsos com a 11.
- Docs parciais: `AGENTS.md` (estrutura `reminders/` e `maos/`, o motor por rota, `viking maos`,
  `--migrar`, o passo `agendador`, duas armadilhas) e `docs/fontes/gcp-cloud-run-firestore.md`.
- Portões: `2380 passed`; ruff, format (146), mypy (34) limpos. **A rodada inteira de mutações:
  `mutações: 337 · mortas pelo teste esperado: 337`** · recusadas 0 · sobreviventes 0.
- Duas passadas de revisão: (1) por onde mais se grava lembrete (achou o script de limpeza); (2)
  o que ficou falso (o aviso "chega numa próxima etapa", a docstring do cliente). As provas das
  portas falam com a rede e não têm teste de unidade (rodam no `deploy`).

**No ar (2026-10-01 ~06:00Z), com o ok do dono ("Os dois", pedido no chat às ~05:40Z):**
- `--executar contas` → `✅ contas: motor@ (Firestore), cli@ e maos@ (o dono pede o token)`;
- `--executar ttl` → `tarefas.apagar_em: CREATING`, depois `ACTIVE`;
- `deploy --executar` → o motor **`1480027`** no ar, sem o Gmail (`viking-gmail` fora da
  revisão). As provas: 15 ✅ na hora e 2 ❌ nas do `viking-maos@` (403 da **página do Google**: o
  `run.invoker` dado no mesmo deploy ainda propagando; o token tinha e-mail, audience e emissor
  certos). Depois de ~5 min, as duas ✅ (`403 'identidade sem acesso'` e `400`). A espera pela
  propagação agora vale para todo pedido das portas (commit seguinte; erros, classe 6).
- `python scripts/nuvem.py` → **10 ✅** e o ⬜ do `agendador` ("a API do Cloud Scheduler
  desligada (liga depois do portão da 10c)").
- `deploy` só-leitura → **17 ✅**, `envio_de_lembretes: False (esperado False)`, `gmail: False`.

**O roteiro do Mac passou (colado pelo dono em 2026-10-01; "outputs me parecem válidos e
corretos"):**
- `git pull` → `f0f9cfc`; `uv sync` trocou as 4 versões do lock da 11 (cyclopts 5.1.1,
  google-api-python-client 2.201.0, google-auth 2.59.1, google-genai 2.26.0);
- `python -m pytest -q` → `2207 passed, 173 skipped in 51.43s` (2380 no total, o mesmo do VPS;
  os pulados são os do extra `nuvem`, que o Mac não instala);
- `viking maos` → "🧭 Tarefa da nuvem: «abrir example.com e me dizer o título» em
  https://example.com", `0 ações · 0.8s · done`, 1392 tokens do navegador (~US$ 0,000056), "✅
  Resultado devolvido à nuvem."; Ctrl-C → "Viking maos desligado.";
- `viking chat --nuvem` → a abertura com o navegador do Mac e sem Gmail; "O título da página é
  "Example Domain"." (5891 tokens, ~US$ 0,0022); com o `viking maos` desligado: "O `viking maos`
  não está ligado no Mac: a tarefa não rodou, e nada foi feito no navegador." (6407 tokens);
- `viking lembretes --migrar` → "5 lembrete(s) (3 aberto(s), 2 concluído(s), 1 já enviado(s)
  por e-mail)", "Na nuvem já iguais: 0.", "Envio por e-mail da nuvem: ainda não ligado.",
  "Ensaio: nada foi copiado".

### Sessão 11 — os checkpoints feitos

**Sessão 11 (aberta em 2026-10-01, ~01:40Z; plano aprovado logo abaixo deste bloco):** as
duas rodadas de perguntas foram respondidas na recomendada (tabela "Respostas do dono" do plano;
D61). Medido na abertura: `2216 passed`, CI `success` em `687068d`, 10 ✅, o motor `36fcd13`, e
4 versões novas no lock.
- C0: o lock em `5b0df87` (`2216 passed` antes e depois; `DEFAULT_HTTP_TIMEOUT_SEC` continua 60 na
  2.201.0); o plano aqui; `sessoes.md` (a 11, a 11c nova); D61.
- C1 (2026-10-01, ~03:10Z): o Gmail opcional na nuvem (o deploy monta só o segredo com versão;
  um `do_mac` vazio fica de fora e qualquer outro vazio recusa; o token que sobe pede revisão
  mesmo sem código novo; as provas comparam com os montados; `/versao` diz `gmail`;
  `na_nuvem.ferramentas()` e `config.gmail_no_motor()`); a identidade por rota no motor
  (`QUEM_FALA`); `turno.instrucao(..., onde=)` com os textos de antes iguais (sha256 de
  2026-10-01 do Mac, da nuvem 10b e da 10c); a abertura do `viking chat --nuvem` pelo `/versao`.
  Portões: `2234 passed`, ruff, format, mypy, gitleaks. Mutações do C1 e vizinhas: 25/25.
- C2 (2026-10-01, ~03:20Z): a fila das mãos (`maos/fila.py`, o formato fechado, sem rede, que o
  Mac também usa; `maos/fila_firestore.py`, a coleção `tarefas` por comparar e trocar, o resultado
  apagado ao ser lido, TTL de 1 dia em `TTLS`); `maos/pedir.py` (a tool da nuvem espera no mesmo
  turno: 15 s para ser pega, senão vence; o limite da tarefa = o restante do turno menos 95 s, no
  máximo os 180 do navegador; "não sei" quando o Mac pegou e sumiu); `navegar_e_executar` no chat
  da nuvem com o texto do Mac; as rotas `/maos/pegar` e `/maos/entregar`, só do `viking-maos@`; a
  abertura e o texto de sistema com o navegador do Mac. A corrida das 16 mãos cai 5 de 5 sem o
  comparar e trocar (medido antes de confiar). Suíte `2281 passed` (emulador exigido); mutações do
  C2 e vizinhas 34/34, e as duas reancoradas 2/2.
- C3 (2026-10-01, ~03:26Z): `viking maos` (`maos/mac.py`): só com TTY; pergunta a cada 5 s com
  o token do `viking-maos@` (`cliente.sessao_das_maos`); confere o formato antes de rodar (um
  `liberar` vindo da nuvem é recusado e nada roda); roda por `browser.executar_e_contar` (o mesmo
  caminho do chat do Mac: bloqueio, freio, trava, redação) e entrega o texto; a liberação de um
  clique aparece e se aprova no próprio terminal (3 erradas cancelam); rede caída espera 5→60 s
  sem desistir; Ctrl-C no meio entrega e desliga. `maos/mac.py` é o terceiro chamador de
  `clicar_aprovado` (o teste que lê o código foi atualizado). Suíte `2293 passed`; mutações do C3
  e da liberação 29/29.
- C4 (2026-10-01, ~05:00Z): os lembretes do Mac pela nuvem, a migração e o envio pela nuvem,
  com os testes e as mutações (o resumo e os defeitos achados estão no topo deste bloco).

### A 10c — o estado registrado em 2026-09-30 (parada no portão)

**Estado (2026-09-30 ~22:40Z):**
- `git status --short` limpo · HEAD = o checkpoint depois de `187079c` = remoto · trava de
  mutação: nenhuma · background: nenhum.
- Commits da 10c: `2529615` (lock), `38e1870` (plano, D60), `8cba1fd` (C1), `52570bc` (a corrida
  do SQLite), `9f6243d` (C2), `51e61de` (C3), `bded8f1` (C4), `ab8c704` (checkpoint), `187079c`
  (C5) e este checkpoint. CI `success` pelo SHA inteiro em `ab8c704` e `187079c`.
- C0: o lock em `2529615` (suíte `2125 passed` antes e depois), os docs em `38e1870`.
- C1 (2026-09-30, commit às 17:33Z): a confirmação atrás de `confirmacao_interface`, com os stores SQLite e
  Firestore; o contrato nos dois (`VIKING_EXIGIR_EMULADOR=1 pytest tests/test_confirmacao.py
  tests/test_confirmacao_firestore.py` → `74 passed`, 0 pulados); a migração 6 (`erros`); 3
  erradas cancelam. Suíte `2174 passed`; `python scripts/mutacoes.py confirmação` → 18/18 mortas
  pelo teste esperado (8 novas, 7 antigas com âncora nova: o código mudou de arquivo).
- **CI do `8cba1fd` falhou (3.13)** no teste novo de corrida: `propor` do SQLite lia os reservados
  fora da transação (defeito desde a Sessão 5, só com `substituir=False`, o MCP). Consertado em
  `52570bc` (`BEGIN IMMEDIATE`; o teste agora cai 10/10 sem o conserto), CI `success` pelo SHA.
- C2 (commit às 17:53Z): `lifeos/ao_dono.py` (a porta do que só o dono vê; na nuvem, o campo `ao_dono`, e
  sem o coletor erra alto); `interativo` no pedido; a barreira da nuvem = `agent.aprovacao_local`
  + o número sozinho; "verbo + 4 dígitos" barrado também no Mac (`agent.NAO_E_CODIGO_AQUI`); as 7
  tools do Gmail na nuvem; o texto de sistema da nuvem com o Gmail. `tests/test_na_nuvem_gmail.py`
  (13). Suíte `2192 passed`; mutações do C2 e vizinhas 78/78 pelo teste esperado (uma âncora
  minha casava como pedaço de linha e virava erro de sintaxe: corrigida). CI de `9f6243d`: `success`.
- C3 (commit às 17:58Z): `lifeos/prazo.py`; o turno da nuvem com 220 s (`na_nuvem.PRAZO_DO_TURNO_S`); o
  Gmail confere antes de cada espera (`_esperar`) e de cada pedido (`_no_prazo(REDE_S=60)`); o
  gancho do Gemini exige 60 s de sobra (`_antes_do_modelo`). `tests/test_prazo.py` (9, relógio
  falso). Suíte `2201 passed`; mutações `prazo:` 6/6 (rodadas em primeiro plano, por erro meu:
  classe 5, sem dano).
- C4 (fechado às ~18:10Z): o token do Gmail na nuvem (`config.gmail_token`, `VIKING_GMAIL_TOKEN_ARQUIVO`;
  `google_auth.credenciais_da_nuvem` com os dois tokens, cada um com o seu escopo e a mensagem de
  onde subir de novo); `/fumaca/segredos` com `gmail`; `scripts/nuvem.py`: o segredo
  `viking-gmail` (`do_mac=True`: vazio não reprova o passo, mas o deploy não publica com um
  segredo sem versão), `_token_do_gmail` (JSON, `refresh_token`, `gmail.modify`, nada mostrado),
  o `segredo` roda só com `VIKING_NUVEM_PROJETO` (no Mac), a TTL em duas coleções (`TTLS`:
  `acoes.expira_em` e `confirmacoes.apagar_em`), as provas esperam `gmail: True`; o cliente do Mac
  manda `interativo` e mostra `ao_dono` só num terminal. Régua nova: todo `VIKING_*_ARQUIVO` que
  o `config` lê tem um segredo no deploy, nos dois sentidos. Uma mutação equivalente (o `True` no
  lugar de `creds.valid`, que só existe válido) foi trocada pela que importa (falha vira `True`).
- C5 (2026-09-30, 21:00–22:40Z):
  - portões lidos antes do commit `187079c`: `2216 passed in 45.55s`; `ruff check` "All checks
    passed!"; `ruff format --check` "132 files already formatted"; `mypy` "Success: no issues
    found in 25 source files"; gitleaks "no leaks found"; `uv lock --check` "Resolved 112
    packages";
  - `docker build` ok, 513 MB (a 10b: 512 MB);
  - duas passadas de revisão. Achados, consertados em `187079c`: `gmail/service._avisar`
    imprimia no stderr, que no motor é o log do Cloud Run (agora não sai lá; teste e mutação); o
    teste do turno da nuvem exigia só o stdout vazio (agora stdout e stderr); textos velhos nos
    passos `segredos` e `ttl` do `scripts/nuvem.py`; docstrings do Gmail diziam "direto no
    terminal". Novo: `test_o_script_abre_no_mac_sem_o_extra_nuvem` (o `segredo viking-gmail`
    roda no Mac, que não instala o extra `nuvem`), com mutação;
  - `python scripts/mutacoes.py` (a rodada inteira, em background, sem `timeout`, ~22:39Z) →
    `mutações: 282 · mortas pelo teste esperado: 282` · `recusadas: 0 · sobreviventes ou mal
    atribuídas: 0`;
  - docs parciais: `AGENTS.md` (estrutura, comandos, variáveis e as armadilhas "no motor o stdout
    e o stderr são o log", "o terminal que conta é o do Mac", o `BEGIN IMMEDIATE`),
    `.env.example`, `docs/fontes/gmail-api.md` (a nuvem);
  - **com o ok do dono (2026-09-30, "sim - pode prosseguir... tem meu ok"):** `python
    scripts/nuvem.py --executar segredos` (criou `viking-gmail` vazio; `secretAccessor` do
    `motor@` nos três) e `--executar ttl` (`confirmacoes.apagar_em`: CREATING → ACTIVE em ~4
    min). Medido depois: **10 ✅**, `viking-gmail: vazio (sobe do Mac…)`.
- **No ar:** o motor `36fcd13` (sem o Gmail). O `deploy` só-leitura mostra 4 ❌ **esperados** até
  o C7 (a imagem e o `/versao` não são o código de agora; os volumes e o `/fumaca/segredos` sem o
  Gmail); e o deploy **recusa publicar** enquanto `viking-gmail` não tiver versão.

- **O roteiro só-leitura do Mac passou** (colado pelo dono; 2026-09-30 à noite em Seattle):
  `e248de6` = `origin/master`; `uv sync` trocou `charset-normalizer` 3.5.2 e `cryptography`
  50.0.2 (o lock da 10c); `2105 passed, 111 skipped in 51.06s` (2216 no total, o mesmo do VPS;
  os pulados são os do extra `nuvem`); `gcloud auth list` com a conta do dono ativa; `segredo
  viking-gmail` → "viking-gmail: 0 versão(ões) habilitada(s); a fonte é o token do Gmail de
  secrets/ (no Mac)." e "Nada foi enviado (sem --executar)." O `gcloud` do Mac lê o Secret
  Manager do Viking: o passo do C6 não depende de login novo.

## Plano — Sessão 11c: backup diário no Drive que restaura num banco vazio, e a D51 medida (aprovado em 2026-10-06)

### Context
As Sessões 10c e 11 fecharam no Mac em 2026-10-06:
- os lembretes do dono moram **só** na nuvem (Firestore);
- o motor `bbcba1a` envia os e-mails sozinho.

Hoje não existe cópia nenhuma desses dados fora do projeto do GCP. A 11c, separada da 11 em
2026-10-01 (D61), entrega um backup automático no Drive do dono que se prova restaurável num banco
vazio. Ela também fecha a medição da D51 (finanças), que foi feita nesta abertura.

Aprovado este plano, o C0 o copia para o `PROGRESSO.md`, acima do plano da 11. A execução segue até
o fim sem pedir confirmação por fase. Os oks do que custa, cria recurso ou publica são pedidos **na
hora**.

### O que esta sessão entrega (verificável)
1. **Uma vez por dia, com o Mac desligado:**
   - o Cloud Scheduler (uma 2ª tarefa, `viking-backup`, 09:00 UTC) chama `POST /tarefas/backup`,
     só do `viking-agendador@`;
   - o motor lê lembretes e notas (todos), o registro de ações da nuvem (30 dias) e os gastos do
     teto;
   - monta um arquivo JSON versionado, com contagens e a impressão sha256 de cada lembrete;
   - sobe o arquivo à pasta "Viking — backups" do Drive do dono (escopo `drive.file`);
   - o envio passa por `registro.acao("backup.drive")`;
   - a resposta da rota e o log levam só contagens e o tipo do erro.
2. **Nada apaga no Drive:** as cópias se acumulam (KB por dia). Um teste que lê o código proíbe
   `delete`, `update`, `trash`, `emptyTrash` e `permissions` no módulo do Drive.
3. **`viking backup --conferir` (Mac) é a prova real:**
   - baixa o último arquivo e restaura num `viking.db` **novo, vazio e temporário** (o `viking.db`
     real não muda: conferido por sha256);
   - compara cada lembrete (impressão) com a nuvem (`/lembretes/impressoes`) e diz o que mudou
     depois do backup;
   - não toca a nuvem nem o Drive além de ler.
4. **`viking backup --restaurar ARQUIVO [--executar]`** é o caminho do desastre: um ensaio e
   depois a cópia de verdade para a nuvem, em lotes:
   - lembretes por `/lembretes/importar`, que já existe;
   - ações e gastos por `/backup/importar`, nova;
   - idempotente, nunca sobrescreve e confere relendo;
   - provado no emulador num Firestore vazio.
5. **Aviso:** `/versao` passa a dizer `backup` (o token montado) e `backup_em`. A abertura do
   `viking chat --nuvem` avisa quando não há backup há mais de 48 h, e a prova do deploy confere.
6. **O token do Drive:**
   - `viking backup --login` no Mac (`drive.file`, outro consentimento), gravado em
     `secrets/google_token_drive.json` (600);
   - sobe pela entrada padrão (`python scripts/nuvem.py segredo viking-drive --executar`, no Mac)
     como o segredo opcional `viking-drive` (`do_mac=True`);
   - o VPS não o guarda.
7. **Junto, no mesmo deploy:** as duas recusas sem terminal de `gmail/tools.py` (a limpeza, linha
   60, e o envio, linha 353) falam **com o dono** e citam `viking chat --nuvem` na nuvem (ou
   `viking chat` no Mac).

### O que ela NÃO faz (e para onde foi)
- **As finanças na nuvem** (a D51 deu "pode") → **Sessão 11d** nova, escrita no C0: um serviço
  isolado só de leitura, com conta e segredo próprios.
- **O `viking.db` do Mac** fica fora do backup, por resposta do dono. Os backups
  `antes-da-migracao` continuam no Mac.
- **Confirmações e tarefas das mãos** ficam fora: duram 10 min e 1 dia.
- **Podar cópias no Drive** fica fora, por resposta do dono: todas ficam.
- **A medição de 24 h do agendador** vem no C0b, a partir de 2026-10-07 ~17:00Z. Ela não depende
  do resto.

### Respostas do dono (2026-10-06, ~22:30Z)
| Pergunta | Resposta | Consequência |
|---|---|---|
| Onde e quando | na nuvem, todo dia | 2ª tarefa do Scheduler; o token do Drive no Secret Manager (sobe do Mac) |
| O que entra | lembretes e notas, registro de ações da nuvem, gastos do teto | três coleções no arquivo; confirmações e tarefas fora |
| Quantas cópias | todas, sem apagar | nenhum caminho de exclusão; um teste o proíbe |
| A medição da D51 | sim, os dois GETs | feita em 2026-10-06 22:27Z (abaixo) |
| As finanças depois do "pode" | sessão própria, 11d | a 11c só registra a medição e atualiza a D51 |
| A prova real | no Mac, num banco vazio | `viking backup --conferir` com um `viking.db` temporário |
| O aviso de falha | na abertura do chat | `/versao` com `backup_em`; nada novo por e-mail |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Formato:** `src/lifeos/backup/formato.py`, puro, sem rede. `{"formato": "viking-backup", "versao": 1, "criado_em", "commit", "contagens", "lembretes": [transporte.para_dict], "acoes": [...], "gastos": [...]}`. A leitura recusa versão desconhecida, campo a mais e contagem que não bate, sem ecoar conteúdo | reaproveita o formato fechado e a impressão da migração (`reminders/transporte.py`); a mesma régua confere a cópia | — |
| **As ações** num formato fechado próprio (`id`, `turno`, `origem`, `operacao`, `parametros`, `estado`, `resultado`, `erro`, `desfazer`, `desfeita_em`, `criada_em`, `terminada_em`); `expira_em` é recalculada na volta | a TTL apaga com atraso: restaurar uma ação velha a faz sumir de novo, o que é o certo | — |
| **Restaurar nunca sobrescreve:** lembretes por `store_firestore.importar` (já idempotente); ações por `create()` com o mesmo id; gastos só se o mês não existe; o que já existe diferente é **listado**, não trocado | o desastre pode ser parcial; sobrescrever apagaria o que é mais novo | — |
| **O módulo do Drive** (`backup/drive.py`) só usa `files().create` (a pasta e o arquivo), `files().list` (com `pageToken`) e `files().get_media` | `drive.file` só enxerga o que o Viking criou; o raio fica menor ainda sem exclusão | — |
| **`registro.acao("backup.drive")`** em volta do `files().create` do arquivo; a régua de `tests/test_registro_ganchos.py` passa a enxergar `files().create` | todo efeito externo passa pelo registro | — |
| **`estado/backup`** (`ultimo`, `arquivo`, `contagens`) é gravado só depois de o Drive confirmar; uma rodada que falha não mexe nele | a falha aparece como "backup velho", nunca como sucesso | — |
| **O `viking.db` temporário do `--conferir`:** `banco.CAMINHO` é trocado só dentro de um contexto, num `tempfile.TemporaryDirectory`, com a migração inteira; os lembretes entram por `store.importar` novo (SQLite) e as ações por `registro_sqlite.importar` novo (o mesmo id); os gastos só se validam (não há tabela de gastos no SQLite) | a prova restaura de verdade num banco vazio, sem tocar o real nem a nuvem | — |
| **O horário:** 09:00 UTC (2h de Seattle e 6h do Brasil), com `--time-zone=Etc/UTC` | não depende do fuso do dono, que vai mudar | — |
| **O passo `backup` em `scripts/nuvem.py`**, separado do `agendador`: mede a tarefa e o segredo com versão; com `--executar`, cria a tarefa e a roda uma vez (`jobs run`) para o primeiro backup existir já | o deploy publica o código; o passo liga o relógio | — |
| **Prazo da rodada:** 200 s (`prazo.ate`), como a rodada dos lembretes | abaixo dos 300 s do Cloud Run | — |

### Medido na abertura (2026-10-06, VPS, ~22:20–22:30Z)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `rev-parse`, `ls-remote`, `ls .mutacao.lock` | limpo; `12e775e` = origin; sem trava | ok |
| Suíte | `VIKING_EXIGIR_EMULADOR=1 .venv/bin/python -m pytest -q` | `2386 passed in 59.86s` | a base |
| CI | `gh run list --commit 12e775e…` | `completed success` | ok |
| Infraestrutura | `python scripts/nuvem.py` | 11 ✅ | ok |
| No ar | `python scripts/nuvem.py deploy` | o motor `bbcba1a`, 0 commits desde ela, 17 ✅, `gmail: True`, `envio_de_lembretes: True`, log com 0 erro | ok |
| Scheduler | `gcloud scheduler jobs describe viking-lembretes … --project` | `ENABLED`, última 22:23:02Z, sem `status` de erro | ok |
| Versões | `uv lock --upgrade --dry-run` | opentelemetry-api 1.45.0 → 1.45.1 | **já aplicado na árvore** (`uv lock --upgrade`, `uv sync`): `2386 passed in 50.74s`, ruff "All checks passed!", format "146 files already formatted", mypy "Success… 34 source files", `uv lock --check` ok. Falta o commit (C0) |
| A medição de 24 h | — | o agendador ligou em 2026-10-06 16:53Z | **ainda não dá**: C0b depois de 2026-10-07 ~17:00Z |
| **D51, pagamento sem o dono** | `GET /smart-transfers/preauthorizations` (cliente só leitura; código e contagem) | **403 `PAYMENT_INITIATION_NOT_ALLOWED`** | o caminho que paga "without user interaction" (docs) está fechado para a aplicação |
| **D51, pedidos de pagamento** | `GET /payments/requests` | **200**, 0 pedidos | a listagem abre; se **criar** é recusado não se mede sem escrever (proibido) |
| **D51, documentação** | MCP pluggy-docs (`payments/overview`, `search_qa`) | "Payments must be enabled specifically for your client"; "O produto de pagamentos é exclusivo para clientes com assinatura" (Q&A verificado); todo PIX avulso nasce `CONSENT_AWAITING_AUTHORIZATION`, "the user needs to authorize it in the institution", com o `consentUrl` vencendo em 5 min | as duas condições da D51 se cumprem → a 11d |
| O cliente OAuth | o `client_id` do `secrets/google_credentials.json` contra o número do projeto | é **outro** projeto do dono | a API do Drive tem de estar ligada **lá** |
| A API do Drive | `gcloud services list --enabled --project=<o do cliente OAuth>` (só leitura) | `drive.googleapis.com` ligada (com calendar e gmail) | o login do Drive não precisa de passo no console |
| O modo do app OAuth | o token da agenda, de 2026-09-20, renova no motor em 2026-10-06 (`/fumaca/segredos`) | não venceu em 7 dias | o app não está no modo "teste": o token do Drive não morre em uma semana |
| Os textos sem terminal | `grep -rn "SemTerminal" src/lifeos` | dois: `gmail/tools.py:57-60` (limpeza) e `:353` (envio) | os dois mudam juntos |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | o lock num commit próprio, com o CI pelo SHA; o plano no `PROGRESSO.md`; `sessoes.md` (a 11c com as respostas, a **11d nova**, o ▶️); D63 e a D51 com a medição; `docs/fontes/pluggy-open-finance.md` (a medição) | — | ⬜ |
| C0b | a medição de 24 h do agendador, com data, comando e número (a partir de 2026-10-07 ~17:00Z) | o relógio | ⬜ |
| C1 | `backup/formato.py`; os `importar` das ações (Firestore e SQLite) e o `todos` das coleções; os testes de ida e volta | C0 | ⬜ |
| C2 | o token do Drive (`config`, `google_auth`, `viking backup --login`); `backup/drive.py`; a rodada `backup/rodada.py`; a rota `/tarefas/backup`; `estado/backup`; `/versao` | C1 | ⬜ |
| C3 | `viking backup --conferir` e `--restaurar` (com a rota `/backup/importar`); o aviso na abertura do chat | C2 | ⬜ |
| C4 | `scripts/nuvem.py`: o segredo `viking-drive`, o passo `backup`, as provas; os textos do Gmail | C2 | ⬜ |
| C5 | portões, mutações, duas passadas, docs, commit, push, CI; **ok** → deploy; roteiro do Mac (o login, o segredo); **ok** → `--executar backup`; o `--conferir` no Mac; fechamento | C3, C4 | ⬜ |

### Fase 0 — C0: o lock e os documentos
**Faz:**
- **O commit do lock** (`uv.lock`, já na árvore, portões já verdes): push e `gh run list --commit
  <sha>`.
- **`PROGRESSO.md`:** este plano acima do plano da 11; o bloco RETOMAR aponta para o C1.
- **`sessoes.md`:**
  - a 11c com as respostas;
  - a **11d nova**: as finanças na nuvem num serviço isolado só de leitura (D51 satisfeita, com a
    nuance do `GET /payments/requests` 200 e o que mede a abertura dela);
  - o ▶️.
- **`docs/decisoes.md`:**
  - **D63** (as 7 respostas e as decisões técnicas acima);
  - a D51 ganha "medida em 2026-10-06: pode; a mudança é a 11d".
- **`docs/fontes/pluggy-open-finance.md`:** a seção "Pagamentos (medido em 2026-10-06)".

**✅ Checkpoint:**
- `git log --oneline -2` mostra o lock e os docs;
- `gh run list --commit <sha>` → `success`;
- `uv lock --upgrade --dry-run` → "No lockfile changes"... ou só versões novas do dia;
- o diff inteiro dos `.md` relido (classe 5).

**🐞 → Depurar:** o CI cair no lock → `uv lock --upgrade-package opentelemetry-api==1.45.0` e
perguntar (classe 3).

### Fase 0b — C0b: a medição de 24 h do agendador (quando der)
**Faz:** pela API do Cloud Monitoring, só leitura: `curl` com `gcloud auth print-access-token`, em
`projects/<projeto>/timeSeries`, de 2026-10-06 17:00Z a 2026-10-07 17:00Z:
- `firestore.googleapis.com/document/read_count`;
- `firestore.googleapis.com/document/write_count`;
- `run.googleapis.com/request_count`, separado por `response_code_class`.

Agregação: `ALIGN_SUM` com `alignmentPeriod=86400s`. O projeto sai do `.env`, nunca no repo.

**✅ Checkpoint:** os três números com data no `PROGRESSO.md` e em
`docs/fontes/gcp-cloud-run-firestore.md`, contra os ~1,5 mil por dia da D61. O gatilho é passar de
25 mil leituras.

**🐞 → Depurar:** a série vir vazia → conferir o nome da métrica com
`metricDescriptors?filter=metric.type=starts_with("firestore")` (classe 2: abrir antes de afirmar).

### Fase 1 — C1: o formato e os importadores
**Faz:**
- `src/lifeos/backup/__init__.py` e `formato.py`:
  - `montar(lembretes, acoes, gastos, *, agora, commit) -> dict`;
  - `ler(dados) -> Backup` (conferido);
  - `acao_para_dict` e `acao_de_dict` (formato fechado);
  - `gasto_para_dict` e `gasto_de_dict`.
- `reminders/store_firestore.todos()`.
- `registro_firestore.todas(desde)` e `registro_firestore.importar(acao) -> "criada"|"igual"|"diferente"`.
- `registro_sqlite.importar(acao)`.
- `reminders/store.importar(lembrete)` no SQLite (o mesmo contrato do Firestore).
- `custos.Teto.todos()` e `custos.Teto.importar(mes, dados)`.
- `registro_interface`: `importar` e `todas` entram no `Protocol`, e o contrato roda nos dois
  stores.

**Testes:**
- ida e volta de cada formato;
- recusas (campo a mais, versão 2, contagem errada, id que não é UUID ou inteiro) sem ecoar
  conteúdo;
- `importar` duas vezes dá "igual";
- conteúdo diferente dá "diferente" e o documento continua o de antes (nos dois stores, no
  emulador);
- `todas` corta pelos 30 dias.

**✅ Checkpoint:** `VIKING_EXIGIR_EMULADOR=1 pytest tests/test_backup_formato.py
tests/test_registro.py tests/test_reminders_contrato.py -q` verde, 0 pulados; a suíte verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `ler` aceita campo a mais | "campo a mais recusado" |
| `importar` das ações com `set` | "diferente não é sobrescrito" |
| contagem não conferida | "contagem errada recusada" |

**🐞 → Depurar:** classe 4 (o teste de "não sobrescreve" passar porque o conteúdo era igual) →
o caso negativo muda **um** campo.

### Fase 2 — C2: o token do Drive, a rodada e a rota
**Faz:**
- **`config`:** `DRIVE_TOKEN_PATH` (`secrets/google_token_drive.json`, env
  `VIKING_DRIVE_TOKEN_PATH`), `VIKING_DRIVE_TOKEN_ARQUIVO`, `drive_token()` e `drive_no_motor()`.
- **`google_auth._tokens_da_nuvem`** ganha o Drive.
- **`backup/drive.py`:**
  - `SCOPES = ["https://www.googleapis.com/auth/drive.file"]`;
  - `pasta()` acha ou cria "Viking — backups";
  - `subir(nome, conteudo)`;
  - `ultimo()`: lista com `orderBy=createdTime desc` e `pageToken`;
  - `baixar(id)`;
  - a cota e o erro cru passam por uma descrição sem o número do projeto (como `gmail/_descrever`).
- **`backup/rodada.py`:**
  - `rodar(agora)` lê as três coleções, `formato.montar`, depois `with registro.acao("backup.drive",
    {...contagens, nome})` em volta de `drive.subir`, e só então `estado/backup`;
  - corre sob `prazo.ate(200)`;
  - `ultimo_backup()` lê o estado.
- **`motor.py`:**
  - `POST /tarefas/backup` em `QUEM_FALA` (`AGENDADOR`), com a resposta só com contagens e o
    erro só com o tipo;
  - `/versao` ganha `backup` (`drive_no_motor()`) e `backup_em`.
- **`cli.py`:** `viking backup --login`.
- **`tests/test_registro_ganchos.py`:** `files().create` entra como efeito externo, e a régua
  confere que o enxerga.

**Testes:**
- com o Drive dublê e o emulador: a rodada sobe um arquivo que `formato.ler` aceita, com as
  contagens certas;
- o Drive falha → `estado/backup` não muda, o registro diz `falhou` ou `incerta` (5xx) e a rota
  dá 500 com o tipo só;
- a resposta da rota não tem título (sentinela);
- só o `agendador@` entra na rota (`cli@` → 403);
- `/versao` com e sem o token;
- o módulo do Drive não chama `delete`, `update`, `trash`, `emptyTrash` nem `permissions` (lido
  pelo AST);
- a pasta existente é reaproveitada, sem criar outra.

**✅ Checkpoint:** `VIKING_EXIGIR_EMULADOR=1 pytest tests/test_backup_rodada.py
tests/test_backup_drive.py tests/test_motor*.py tests/test_registro_ganchos.py -q` verde; a suíte
verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `estado/backup` gravado antes de subir | "o Drive falha → o estado não muda" |
| a rota sem `QUEM_FALA` | "`cli@` → 403" |
| `subir` fora do `registro.acao` | a régua dos ganchos |
| a pasta criada a cada rodada | "pasta reaproveitada" |
| o título na resposta | o sentinela |

**🐞 → Depurar:**
- classe 6, outro caminho que sobe ao Drive sem registro → `grep -rn "files()" src/lifeos`;
- classe 2, o formato do `files().list` (o campo `nextPageToken`) → a doc da API antes de
  escrever o dublê.

### Fase 3 — C3: conferir, restaurar e o aviso
**Faz:**
- **`backup/conferir.py`** (Mac):
  - `drive.ultimo()` e `baixar`, depois `formato.ler`;
  - dentro de `banco_temporario()` (troca `banco.CAMINHO` por um arquivo num `TemporaryDirectory`
    e devolve depois), `store.importar` e `registro_sqlite.importar`;
  - relê do banco temporário e compara as impressões com `cliente.impressoes_dos_lembretes`;
  - relatório: iguais, mudaram depois do backup (`updated_at` > `criado_em`), novos depois, e
    divergentes **sem explicação**; este último é o erro alto.
- **`backup/restaurar.py`:**
  - o ensaio (contagens, o que já existe igual ou diferente) e `--executar` (lotes de 100);
  - lembretes por `cliente.importar_lembretes`, que já existe;
  - ações e gastos por `POST /backup/importar` (`cli@`, até 4 MiB), nova no motor;
  - confere relendo.
- **`cli.py`:** `viking backup` (o último backup pelo `/versao`), `--conferir` e `--restaurar
  ARQUIVO [--executar]`. A saída só tem contagens (ela é colada em conversa).
- **`chat_cliente.py`:** a abertura avisa "o último backup é de há N dias" ou "nenhum backup
  ainda" quando `backup: true` e `backup_em` passa de 48 h.

**Testes:**
- `--conferir` com o Drive dublê e o motor em processo: o banco temporário nasce vazio, recebe
  tudo, e o sha256 do `viking.db` real não muda;
- um lembrete que mudou depois vira "mudou depois", não erro;
- um divergente sem explicação vira saída 1;
- `--restaurar --executar` num emulador vazio deixa as três coleções iguais às de antes (as
  impressões, e as ações campo a campo);
- de novo dá tudo "igual";
- o aviso nos 47 h e nos 49 h (relógio falso).

**✅ Checkpoint:** `VIKING_EXIGIR_EMULADOR=1 pytest tests/test_backup_conferir.py
tests/test_backup_restaurar.py tests/test_chat_cliente*.py -q` verde; a suíte verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `--conferir` sem trocar o `banco.CAMINHO` | "o `viking.db` real não muda" |
| o divergente contado como igual | "saída 1" |
| o aviso com `>=` 24 h | "47 h e 49 h" |
| `/backup/importar` sem `QUEM_FALA` | o 403 |

**🐞 → Depurar:**
- classe 4, o banco temporário herdando a marca "migrado" → `onde.estado()` dentro do contexto
  (tem de ser `None`);
- classe 6, outro lugar que lê `banco.CAMINHO` cedo (no import) → `grep -rn "CAMINHO"
  src/lifeos`.

### Fase 4 — C4: o script da nuvem e os textos do Gmail
**Faz:**
- **`scripts/nuvem.py`:**
  - `Segredo("viking-drive", "/segredos/drive/token.json", "VIKING_DRIVE_TOKEN_ARQUIVO",
    do_mac=True)`;
  - `segredo viking-drive` lê `secrets/google_token_drive.json` (o JSON, o `refresh_token`, o
    escopo `drive.file`; nada mostrado), generalizando o `_token_do_gmail`;
  - o passo **`backup`** (depois do `agendador`): mede a tarefa `viking-backup` (`0 9 * * *`,
    `Etc/UTC`, POST `/tarefas/backup`, OIDC do `agendador@`, a audience do motor, sem
    retentativa) e o segredo com versão; `--executar` cria a tarefa e roda uma vez
    (`scheduler jobs run`);
  - as provas: `/fumaca/segredos` com `drive`, `/versao` `backup` coerente com o montado, `cli@`
    recusado em `/tarefas/backup`, e `backup_em` com menos de 48 h quando o passo está pronto.
- **`gmail/tools.py`:** as duas recusas sem terminal falam com o dono ("Diga ao dono: …") e citam
  `viking chat --nuvem` quando `config.STORE == "firestore"`, `viking chat` no Mac.

**Testes:**
- o deploy sem e com o `viking-drive`;
- a régua "todo `VIKING_*_ARQUIVO` tem segredo" já cobre;
- os comandos do passo `backup`, com as flags certas;
- `_tarefa_certa` para a tarefa nova;
- os dois textos do Gmail nos dois lugares (Mac e nuvem).

**✅ Checkpoint:** `pytest tests/test_nuvem_script.py tests/test_gmail*.py -q` verde; a suíte
verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| montar o `viking-drive` sem versão | "deploy sem o Drive" |
| a tarefa a cada minuto | `_tarefa_certa` |
| o texto da nuvem citando `viking chat` | o teste do texto da nuvem |

**🐞 → Depurar:** classe 7, a segunda vida do script (o segredo existe sem versão e depois com) →
os dois estados testados.

### Fase 5 — C5: fechar, publicar e testar no Mac
**Faz:**
- **Portões lidos:** pytest (o emulador exigido), ruff, `ruff format --check` (o formatador só nos
  arquivos editados), mypy (`backup/` entra na lista do `pyproject`), gitleaks, `uv lock --check` e
  o `docker build` em background.
- **Mutações:** as novas em `scripts/mutacoes.py`, depois a rodada inteira em background, sem
  `timeout`, com a saída num arquivo. Antes, reler a classe 5. Esperado: 337 mais as novas, mortas
  pelo teste nomeado.
- **Duas passadas** (`referencia/revisao.md`). A 2ª pergunta: quem mais escreve no Drive, e o que
  a segunda rodada do mesmo dia encontra (dois arquivos com nome igual? o nome leva a hora e o
  minuto).
- **Docs:**
  - `AGENTS.md` (estrutura `backup/`, comandos, variáveis, uma armadilha se aparecer);
  - `docs/fontes/gcp-cloud-run-firestore.md`;
  - `docs/fontes/google-calendar-api.md` (o token do Drive);
  - `.env.example`.
- **Commit, push e o CI pelo SHA.**
- **Ok → `deploy --executar`** (centavos): o motor novo, sem o `viking-drive` ainda; `backup:
  false`; os textos do Gmail no ar.
- **Roteiro do Mac** (comandos sem `<…>`, sem `#`, com `&&`):
  1. `cd ~/LifeOs && git pull && git log --oneline -1`
  2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
  3. `viking backup --login` (a tela do Google pede "ver, editar, criar e excluir só os arquivos
     do Google Drive que você usa com este app")
  4. `python scripts/nuvem.py segredo viking-drive` (o ensaio), depois o mesmo com `--executar`
- **No VPS:**
  - `python scripts/nuvem.py` mostra o ⬜ do `backup`;
  - **ok → `deploy --executar`**, porque o segredo novo pede revisão (centavos);
  - **ok → `--executar backup`**: a tarefa e a primeira rodada. Custo: de US$ 0 a 0,10 por mês. As
    3 tarefas grátis são por conta de faturamento, e se os outros projetos do dono já usam alguma,
    isso não está medido.
- **No Mac:** `viking backup` (a data), `viking backup --conferir` (as contagens), e
  `viking chat --nuvem` (a abertura sem aviso).
- **Fechamento:**
  - o diário (com "Erros desta sessão"), a barra (20 de 32, com a 11d nova), `sessoes.md` (a 11c
    feita, o ▶️ na 11d) e a D63;
  - commit, push e CI.

**✅ Checkpoint:**
- `python scripts/nuvem.py` → 12 ✅;
- `deploy` → todas as provas ✅, com `backup: True` e `backup_em` de hoje;
- no Drive, a pasta com 1 arquivo;
- a saída do Mac colada: o `--conferir` diz "N iguais, 0 divergentes".

**🐞 → Depurar:**
- `403 insufficientPermissions` no Drive → o escopo do token gravado (`_escopos_do_arquivo`);
- `accessNotConfigured` → a API no projeto do cliente OAuth (medida ligada hoje);
- o job não roda → `scheduler jobs describe viking-backup` (o `status`).

### Riscos e o que é irreversível
| Passo | Custo | Irreversível? | O ok |
|---|---|---|---|
| Deploy (duas vezes) | centavos | a revisão anterior fica | pedido na hora |
| A tarefa `viking-backup` | US$ 0 a 0,10/mês | não: `jobs delete` a desfaz | pedido na hora |
| O segredo `viking-drive` (1 versão) | grátis (4 de 6 versões ativas) | não | o dono roda no Mac |
| Arquivos no Drive | a cota do dono, KB por dia | o Viking nunca apaga; o dono apaga à mão se quiser | coberto pela resposta "todas" |
| `--restaurar --executar` | — | escreve na nuvem, mas nunca sobrescreve | só num desastre, pelo dono |

Nada do VPS usa o token do Drive. O `--conferir` e o login rodam no Mac, e os testes usam o
dublê do Drive e o emulador.

### Regra de conserto
Todo defeito começa pela classe dele em `docs/erros.md`, e o conserto não para no ponto: o `grep`
da forma inteira antes de dar por pronto. Os já previstos:
- `files()` fora de `backup/drive.py`;
- `banco.CAMINHO` lido no import;
- `QUEM_FALA` nas rotas novas;
- `print(` no motor;
- "peça ao usuário" nos textos de tool.

Nenhuma checagem antes de um commit leva `| tail`. Emenda por script ancora na linha inteira.
Mutações vão com `run_in_background`.

## Plano — Sessão 11: nuvem 2, as mãos e os lembretes com uma fonte só (adiantada antes do portão da 10c) (aprovado em 2026-10-01)

### Context
A 10c está parada no portão: o token do Gmail só sobe depois da prova no Mac, a partir de
2026-10-04 em Seattle. O dono decidiu adiantar a Sessão 11 em 2026-10-01 ("quero adiantar
outras coisas antes do dia 04").

A medição da abertura mostrou duas travas:
- **o deploy recusa publicar** enquanto o `viking-gmail` não tem versão, então nada novo iria ao
  ar antes de 04/10;
- **o lembrete por e-mail com o Mac desligado envia pelo Gmail da nuvem**, ou seja, depende do
  portão.

As duas rodadas de perguntas, todas respondidas na opção recomendada, dão o tamanho:
- **esta sessão entrega:** as mãos (`viking maos`), os lembretes com uma fonte só (a nuvem, com o
  Mac falando com ela pelo motor), a migração e o código do envio pela nuvem;
- **ela publica antes de 04/10**, com o Gmail opcional na nuvem;
- **depois do portão,** o agendador liga e só então a cópia de verdade acontece, sem nenhum dia
  sem e-mail de lembrete.

O backup no Drive e a medição das finanças (D51) vão para uma sessão nova, a **11c**, depois de
04/10.

Aprovado este plano, o C0 o copia para o `PROGRESSO.md`, abaixo do bloco RETOMAR e acima do plano
da 10c. A execução segue até o fim sem pedir confirmação por fase. Os oks do que cria recurso,
custa ou publica são pedidos **na hora**.

### O que esta sessão entrega (verificável)
1. **`viking maos` no Mac** é um terminal em primeiro plano, que exige TTY. Ele pergunta ao motor a
   cada 5 s se há tarefa de navegador:
   - roda a tarefa com todas as travas do Mac (domínios bloqueados, freio, trava, redação);
   - devolve só o texto já redigido;
   - a liberação de um clique aparece e se aprova **no próprio terminal do `viking maos`**;
   - nenhuma porta é aberta e a CDP nunca sai do Mac.
2. **`viking chat --nuvem` usa o navegador:** a tool `navegar_e_executar` põe a tarefa numa fila e
   espera o resultado no mesmo turno, dentro do prazo de 220 s:
   - sem o `viking maos` ligado, em ~15 s diz isso, e a tarefa vence sem rodar;
   - a tarefa nunca carrega uma liberação.
3. **O motor separa quem fala com cada rota:**
   - o `viking-cli@` fala só com o chat e os lembretes;
   - o `viking-maos@` só com `/maos/*`;
   - o `viking-agendador@` só com `/tarefas/lembretes`;
   - um teste lê o código e reprova uma rota sem a lista explícita.
4. **Os lembretes têm uma fonte só depois da migração.** O chat local, o MCP e `viking lembretes`
   do Mac leem e gravam na nuvem pelo motor, e o registro dessas ações é o da nuvem (D57).
   - Uma marca no `viking.db` (a migração 7) diz que migrou, então o Mac não tem como gravar no
     SQLite por engano.
   - `viking lembretes --enviar` no Mac passa a recusar: quem envia é a nuvem.
5. **A migração tem dois modos:**
   - `viking lembretes --migrar` é o ensaio: conta, confere a nuvem e não copia;
   - com `--executar`, copia tudo (lembretes e notas, abertos e concluídos, com o estado do
     envio): idempotente pelo UUID, conferida relendo cada id, com a marca "migrando" e depois
     "migrado";
   - **ela recusa** enquanto o envio da nuvem não estiver ligado (o motor não rodou o agendador
     nos últimos 10 min).
6. **O envio pela nuvem:** a rota `POST /tarefas/lembretes` reaproveita `reminders/envio.py` e
   devolve só contagens. Ela não relê os atrasados a cada minuto, para caber na cota grátis do
   Firestore. O aviso "o e-mail deste lembrete ainda não existe" some sozinho quando o envio liga.
7. **O Gmail é opcional na nuvem:**
   - sem versão do `viking-gmail`, o deploy não monta o segredo e as 7 tools do Gmail não
     aparecem;
   - o texto de sistema e a abertura do `viking chat --nuvem` não prometem o Gmail;
   - com a versão, tudo volta, sem mudar código.
8. **No ar antes de 04/10**, com o ok do dono, e o dono testa as mãos no Mac.

### O que ela NÃO faz (e para onde foi)
- **Para a 11c, depois de 04/10:** o backup no Drive (`drive.file`, com o consentimento novo
  **depois** da prova do Gmail, para não misturar logins) e a medição só de leitura das finanças
  (D51). A seção dela é escrita no C0.
- **O agendador ligado e a cópia de verdade** acontecem depois do portão, na retomada da 10c (os
  passos estão no fim deste plano). O código fica pronto e publicado agora.
- **O limite de 20 envios em 24 h continua separado** no Mac e na nuvem (dono, 2026-10-01): cada
  lado continua parando um laço. A dívida da 10c fecha como decisão (D61).
- **O registro de ações do Mac fica no Mac** (D57). A nuvem não vê os cliques do navegador no
  `acoes_recentes`; eles estão no `viking registro` do Mac.
- **As finanças continuam só no `viking chat` local** (D51), e o chat local continua com o
  navegador (D59).

### Respostas do dono (2026-10-01)
| Pergunta | Resposta | Consequência |
|---|---|---|
| Tamanho | 11 = mãos e migração; Drive e finanças depois de 04/10 | Nasce a **11c**; o código do e-mail se escreve agora e fica desligado |
| Lembretes no Mac depois da migração | na nuvem, pelo motor | `reminders/service.py` vai ao motor quando a marca diz "migrado"; o SQLite vira cópia congelada |
| Como o chat da nuvem usa as mãos | espera no mesmo turno | A tool espera pelo resultado dentro do prazo do turno; a liberação fica no terminal do `viking maos` |
| A medição das finanças | depois, com o Drive | Vai para a 11c |
| Deploy antes de 04/10 | sim, com o Gmail opcional | Reabre o item "nenhum deploy antes da prova" da D60: o motivo (código sem uso no ar) deixou de valer |
| Quando migrar de verdade | só com o e-mail da nuvem ligado | `--migrar --executar` recusa sem o agendador vivo; antes, só o ensaio |
| O limite de 20 | manter separado | A dívida da 10c fecha como decisão (D61) |
| O que migra | tudo (abertos, concluídos, estado do envio) | `importar` grava todos os campos; o registro do Mac fica |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **O Gmail opcional se mede pelo segredo, não por uma flag:** `comandos_do_deploy` monta só o segredo que tem versão; um `do_mac` vazio fica de fora e um não-`do_mac` vazio recusa. `na_nuvem.FERRAMENTAS` inclui o Gmail só se `config.GMAIL_TOKEN_ARQUIVO` está posto. A prova `/fumaca/segredos` espera `gmail` só se o volume foi montado | uma fonte só: o estado do Secret Manager decide o deploy, e o deploy decide o motor | — |
| **A identidade é conferida por rota:** `_quem(request, pode={...})`, e `quem_pode` vira um mapa de conta para rotas | menor privilégio: o `maos@` vive num Mac, e com o token dele não se lê a conversa | — |
| **A fila das mãos no Firestore** (`tarefas`, id UUID) usa comparar e trocar (`firestore_comum.trocar`), com estados `pendente → pega → feita` ou `vencida`. Campos: `pegar_ate` (criada + 15 s), `limite_s`, `apagar_em` (TTL de 1 dia). O resultado é apagado assim que o turno o lê | o molde dos lembretes; o texto da página não fica guardado além do turno | o dono não querer o texto da página no Firestore nem por segundos |
| **O prazo do turno manda no prazo da tarefa:** `limite_s = min(BROWSER_TIMEOUT_S, prazo.restante() − 60 (o próximo Gemini) − 15 (pegar) − 20 (folga))`. Se der menos de 30 s, a tool recusa ("não cabe neste turno"). Se a tarefa já foi pega e o prazo acabou, o texto diz "não sei se terminou" | 220 s por turno (D60); uma tarefa de 180 s não cabe inteira | o turno real com o navegador ficar perto do limite |
| **O formato da tarefa é fechado:** `id`, `url`, `objetivo`, `manter_aberta`, `limite_s`. O Mac recusa qualquer campo a mais (`liberar` incluído) sem rodar nada | a nuvem nunca libera um clique (D38, D57) | — |
| **A liberação no `viking maos`:** depois de uma recusa liberável, o terminal mostra a proposta (`liberacao.texto_da_proposta`) e espera o código com prazo (`select` na entrada). Aprovado, `liberacao.clicar_aprovado`. A nuvem recebe só o aviso `AVISO_AO_GEMINI`, sem o código. `tests/test_browser_liberacao.py` passa a aceitar o `maos/mac.py` como terceiro chamador | o código nasce e se confere no Mac (D57); um terminal do Mac lendo o TTY é o mesmo canal do chat local | — |
| **`viking maos` exige TTY** (`stdin` e `stdout`) para começar; Ctrl-C para tudo, e a tarefa em curso é entregue como interrompida | o dono recusou processo em segundo plano; a liberação precisa de uma pessoa | — |
| **O Mac fala com a nuvem pelo serviço, não pelo store:** `reminders/service.criar_lembrete`, `pendentes` e `concluir` chamam o motor quando o `viking.db` diz "migrado". O motor registra a ação (D57) e o Mac não registra de novo. O `quando` é interpretado no fuso do Mac (a borda) e vai como instante | o registro mora onde a ação roda; nada é registrado duas vezes | — |
| **A marca da migração é a migração 7 do `viking.db`:** uma tabela `lembretes_na_nuvem(estado, em)`, criada por um `execute`, com o checksum em `PUBLICADAS`. "migrando" recusa as gravações no Mac; "migrado" manda tudo à nuvem | a marca mora no banco e não numa variável que se esqueça; o backup automático da migração 7 guarda o SQLite de antes | — |
| **`importar` em lote de até 100,** só no store do Firestore, fora do `Protocol`. Ele grava o documento inteiro com o id do Mac por `create()`; se o id já existe, compara e responde `igual` ou `diferente`, sem sobrescrever. Roda dentro de `registro.acao("lembrete.importar")` (`test_registro_ganchos`) | idempotente: rodar de novo depois de uma queda não duplica nada | — |
| **O envio da nuvem** é `envio.enviar_vencidos(listar_atrasados=False)`. Cada rodada grava `estado/envio_de_lembretes.ultima`, e "envio ligado" quer dizer `ultima` com menos de 10 min. O agendador roda a cada 1 min | um disparo por minuto lendo os atrasados custaria N leituras por minuto (com 20 atrasados, ~29 mil/dia, perto das 50 mil grátis); sem eles, ~1,5 mil/dia | a cota real medida no ar |
| **O texto de sistema ganha `onde` ("mac" ou "nuvem")** em vez de deduzir pela presença do navegador. O do Mac fica igual byte a byte (o teste existente) | com as mãos, a nuvem passa a ter o navegador, e `_SECOES` usava isso para saber onde estava | — |
| **Contas novas:** `viking-maos@` (o dono pode se fazer passar por ela; `run.invoker`) agora, e `viking-agendador@` (`run.invoker`; o agente do Scheduler emite o token OIDC) só no passo `agendador`, depois do portão | sem chave em disco (D47); cada identidade com uma porta só | — |

### Medido na abertura (2026-10-01, VPS, ~01:40Z)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `rev-parse`, `ls-remote`, `ls .mutacao.lock` | limpo; `687068d` = origin; sem trava | ok |
| Suíte | `.venv/bin/python -m pytest -q` | `2216 passed in 44.35s` | base |
| CI | `gh run list --commit 687068d…` | `completed success` | ok |
| **Divergência: versões** | `uv lock --upgrade --dry-run` | cyclopts 5.1.0→5.1.1, google-api-python-client 2.200.0→2.201.0, google-auth 2.59.0→2.59.1, google-genai 2.25.0→2.26.0 | C0: commit próprio, com a suíte antes e depois; reler o `DEFAULT_HTTP_TIMEOUT_SEC` do googleapiclient novo (o prazo da 10c depende dele) |
| Infraestrutura | `python scripts/nuvem.py` | 10 ✅, `viking-gmail` vazio | ok |
| No ar | `python scripts/nuvem.py deploy` | `36fcd13`, 7 commits nos caminhos da imagem, 4 ❌ esperados | o deploy recusa sem o Gmail: "Gmail opcional" |
| O envio de lembretes | `reminders/envio.py`, `store_firestore.py` | já depende só do store; a reserva "sai uma vez" passa o contrato nos dois | a rota da nuvem só chama `enviar_vencidos` |
| A leitura dos atrasados | `envio.enviar_vencidos` | relê `atrasados` a cada rodada | `listar_atrasados=False` na nuvem |
| Quem fala com o motor | `motor.quem_pode` | só o `viking-cli@`, a mesma lista em toda rota | a identidade por rota |
| O Mac e o Firestore | o extra `nuvem`, D58(9) | o Mac não instala o Firestore | os lembretes e a migração do Mac vão pelo motor |
| O texto de sistema | `turno._SECOES` | "estou na nuvem" = "não tenho navegador" | o parâmetro `onde` |
| O ID dos lembretes do Mac | `banco._m5_lembretes_com_uuid_e_envio` | UUID desde a migração 5 | `importar` mantém o id |
| Preço do Cloud Scheduler | página de preços (lida 2026-10-01) | US$ 0,10 por tarefa por mês; 3 grátis por conta de faturamento | 1 tarefa: US$ 0 a 0,10/mês |
| Custo da espera das mãos | uma conta, não uma medição | 8 h/dia a cada 5 s ≈ 5,8 mil pedidos/dia e ≈ 5,8 mil leituras/dia | dentro do grátis do Cloud Run (2 M pedidos/mês) e do Firestore (50 mil/dia); medir no ar no C5 |

### Caminho crítico
```
AGORA (independe do portão)
C0 lock+docs ─► C1 Gmail opcional + identidade por rota ─┬─► C2 fila + tool da nuvem ─► C3 viking maos (Mac) ─┐
                                                        └─► C4 lembretes pelo motor + migração + envio ─────┤
                                                                                                            ▼
                     C5 portões, mutações, revisão, push, CI, ok → contas (maos@) e TTL, ok → deploy, roteiro do Mac
                                                                                                            │
A PARTIR DE 2026-10-04 (Seattle), na retomada da 10c ══════════════════════════════════════════════════════╧═
10c C6 (token do Mac) ─► 10c C7 (ok → deploy com o Gmail) ─► ok → passo `agendador` ─► prova: lembrete com o Mac
desligado ─► `viking lembretes --migrar --executar` no Mac ─► fechamento (diário, barra, D61)
```
O C2 e o C4 são independentes entre si: um mexe na fila e nas mãos, o outro nos lembretes.

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | o lock num commit próprio (`2216 passed` antes e depois, CI pelo SHA); o plano no `PROGRESSO.md`; `sessoes.md` (a 11 com as respostas, a 11c nova, o ▶️); D61; D60 anotada | — | ✅ |
| C1 | o deploy monta só os segredos com versão; as tools do Gmail dependem do token; a identidade por rota; `onde` no texto de sistema (o do Mac igual byte a byte) | C0 | ✅ |
| C2 | a fila (contrato no emulador, corrida de 16 threads no `pegar`); `/maos/pegar` e `/maos/entregar`; `navegar_e_executar` na nuvem com prazo e vencimento | C1 | ✅ |
| C3 | `viking maos`: TTY, a espera, o formato fechado, a liberação no terminal, Ctrl-C; contra o motor em processo e um Jev falso | C2 | ✅ |
| C4 | as rotas dos lembretes e `importar`; o serviço do Mac pela nuvem com a marca (migração 7); `--migrar` (ensaio e `--executar` com a recusa); `--enviar` recusa depois de migrado; `/tarefas/lembretes` e "envio ligado"; o aviso do lembrete condicional | C1 | ✅ |
| C5 | portões; mutações em background (282 + as novas); duas passadas; docs parciais; push; CI; **ok** → `--executar contas` (`maos@`) e `ttl` (`tarefas`); **ok** → deploy; provas; roteiro do Mac | C2, C3, C4 | ✅ |
| Pós-portão | 10c C6 e C7; **ok** → `agendador`; prova com o Mac desligado; a migração de verdade no Mac; fechamento | C5 e o portão | ⬜ |

### Fase 0 — C0: o lock e os documentos
**Faz:**
- `uv lock --upgrade` num commit próprio, com a suíte antes e depois, e o CI pelo SHA. Reler
  `googleapiclient.http.DEFAULT_HTTP_TIMEOUT_SEC` na 2.201.0: se mudou de 60, o prazo da 10c volta
  à mesa.
- `PROGRESSO.md`: este plano abaixo do bloco e acima do da 10c; o bloco aponta para o C1.
- `sessoes.md`:
  - a 11 com as respostas e a entrega acima;
  - a **11c nova** (Drive e D51, depois de 04/10, o consentimento do Drive depois da prova);
  - o ▶️.
- `docs/decisoes.md`: **D61** (as 8 respostas e as decisões técnicas), e na D60 uma nota de que
  "nenhum deploy antes da prova" foi revisto pela D61.

**✅ Checkpoint:**
- `uv lock --upgrade --dry-run` → `No lockfile changes detected`;
- a suíte → `2216 passed`;
- `gh run list --commit <sha>` → `success`;
- `head -3 PROGRESSO.md` e o `git diff` inteiro dos `.md` (classe 5).

**🐞 → Depurar:** o google-auth ou o googleapiclient novos quebrarem algo → `uv lock
--upgrade-package` para a versão anterior e perguntar ao dono (classe 3: o changelog antes).

### Fase 1 — C1: o Gmail opcional e a identidade por rota
**Faz:**
- `scripts/nuvem.py`:
  - `comandos_do_deploy(ctx, sha, montados)` recebe os segredos com versão;
  - `deploy` recusa só um não-`do_mac` vazio;
  - as provas "segredos só como volume" e `/fumaca/segredos` comparam com os montados;
  - o `run.invoker` do `maos@` entra no deploy.
- `motor.py`:
  - `QUEM` = um mapa de conta para conjunto de rotas, e `_quem(request)` confere a rota pedida;
  - `/versao` devolve `{"commit", "gmail": bool, "envio_de_lembretes": bool}`;
  - `_segredos` diz `gmail` só se o arquivo está posto.
- `na_nuvem.py`: `FERRAMENTAS` montado por função (o Gmail só com `config.GMAIL_TOKEN_ARQUIVO`).
- `turno.py`: `instrucao(ferramentas, hoje, onde=...)`.
- `chat_cliente.py`: a abertura diz o que a nuvem tem, a partir do `/versao`.
- **Testes:**
  - deploy sem o Gmail: nem o `--set-secrets` nem a variável dele aparecem;
  - deploy com o Gmail: os três aparecem;
  - um não-`do_mac` vazio é recusado;
  - o motor sem o token do Gmail: nenhuma tool do Gmail, e o texto diz "sem navegador, e-mail nem
    finanças";
  - `cli@` em `/maos/pegar` → 403; `maos@` em `/chat` → 403; `agendador@` só em
    `/tarefas/lembretes`;
  - o teste que lê o código reprova uma rota sem a lista;
  - o texto do Mac igual byte a byte.

**✅ Checkpoint:** `pytest tests/test_nuvem_script.py tests/test_motor.py tests/test_na_nuvem*.py
tests/test_turno*.py -q` verde; a suíte inteira verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| montar `viking-gmail` sem versão | "deploy sem o Gmail" |
| as tools do Gmail sempre presentes | "o motor sem o token do Gmail" |
| `_quem` sem conferir a rota | "`cli@` em `/maos/pegar` → 403" |
| `onde` ignorado | "o texto do Mac igual byte a byte", ou o da nuvem com as mãos |

**🐞 → Depurar:** classe 7, a segunda vida do script (o segredo existe sem versão, e depois com) →
os dois estados testados.

### Fase 2 — C2: a fila e o navegador no chat da nuvem
**Faz:**
- `src/lifeos/maos/fila.py`: as regras e o formato fechado da tarefa (`validar_tarefa`, usado dos
  dois lados).
- `src/lifeos/maos/fila_firestore.py`: `criar`, `pegar`, `entregar`, `vencer`, `ler_e_apagar`,
  todos por `trocar`; documento inteiro; `apagar_em`.
- `motor.py`: `POST /maos/pegar` (devolve a tarefa mais antiga pendente e ainda não vencida, ou
  `null`) e `POST /maos/entregar` (resultado de até 20 KB, só de quem pegou).
- `na_nuvem.navegar_e_executar`:
  - a mesma assinatura e a mesma docstring do Mac;
  - cria a tarefa com o `limite_s` derivado do prazo e espera, lendo o Firestore a cada 1 s:
    15 s para ser pega (senão `vencer` e "o `viking maos` não está ligado no Mac");
  - depois espera até `limite_s + 20`;
  - sai da lista `SO_NO_MAC`.
- `scripts/nuvem.py`: `TTLS` ganha `("tarefas", "apagar_em")`.
- **Testes, no emulador:**
  - 16 threads pegando a mesma tarefa: uma só ganha, com as exceções das threads recolhidas;
  - tarefa vencida não é pega;
  - `entregar` de quem não pegou é recusado;
  - o resultado é apagado ao ser lido;
  - a tool com o relógio falso: sem as mãos, vence em 15 s; com prazo curto, recusa antes de
    criar;
  - o `limite_s` nunca passa do restante do turno menos 95 s;
  - um campo a mais na tarefa é recusado por `validar_tarefa`.

**✅ Checkpoint:** `VIKING_EXIGIR_EMULADOR=1 pytest tests/test_maos_fila.py tests/test_na_nuvem_maos.py
-q` → 0 pulados; a suíte verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `pegar` com `set` no lugar de `trocar` | a corrida das 16 threads |
| `pegar_ate` não conferido | "tarefa vencida não é pega" |
| `limite_s` sem descontar o prazo | "o `limite_s` nunca passa do restante" |
| o resultado não apagado | "apagado ao ser lido" |
| `validar_tarefa` aceita campo a mais | "um campo a mais é recusado" |

**🐞 → Depurar:**
- classe 4, a corrida que passa por acaso → medir sem o conserto, em 10 rodadas, com uma pausa
  entre a leitura e a escrita;
- o contextvar do prazo dentro da thread do turno → já definido em `na_nuvem.turno`.

### Fase 3 — C3: `viking maos` no Mac
**Faz:**
- `src/lifeos/maos/mac.py`:
  - `iniciar()` recusa sem TTY;
  - o laço a cada 5 s: `pegar` → `validar_tarefa` → `run_jev` (com o progresso no terminal) →
    `formatar` → `entregar`;
  - na recusa liberável: `liberacao.propor`, depois o texto da proposta no terminal, depois o
    código com prazo (`select`), depois `clicar_aprovado`;
  - a rede caída: espera crescente, sem sair;
  - Ctrl-C: a tarefa em curso é entregue como interrompida.
- `nuvem/cliente._sessao(conta=...)` passa a servir o `cli@` e o `maos@`.
- `cli.py`: o subcomando `maos`.
- `tests/test_browser_liberacao.py`: o `maos/mac.py` entra na lista de chamadores.
- **Testes, contra o motor em processo e o roteiro falso do Jev (`_fake_cmd`):**
  - a tarefa roda e o texto chega à fila;
  - uma tarefa com `liberar` não roda;
  - sem TTY não começa;
  - o código da liberação aparece só no terminal do `maos`: não sai na entrega nem no registro
    (`tests/sentinela.aparece`);
  - "ocupado" (a trava de outro processo) vira o texto de ocupado na nuvem.

**✅ Checkpoint:** `pytest tests/test_maos_mac.py tests/test_browser_liberacao.py -q` verde; a suíte
verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| o `maos` sem `validar_tarefa` | "uma tarefa com `liberar` não roda" |
| o código da liberação no texto da entrega | o teste do sentinela |
| o `maos` sem exigir TTY | "sem TTY não começa" |

**🐞 → Depurar:**
- classe 6, outro caminho que manda o código para fora → `grep -rn "texto_da_proposta\|ao_dono"
  src/lifeos/maos`;
- classe 1, o `select` na entrada no macOS → um roteiro para o Mac no C5.

### Fase 4 — C4: os lembretes pelo motor, a migração e o envio
**Faz:**
- `banco.py`: migração 7 (`lembretes_na_nuvem`), com o checksum; nenhuma publicada editada.
- `motor.py`:
  - `POST /lembretes/criar`, `/lembretes/concluir` e `/lembretes/importar` (do `cli@`);
  - `GET /lembretes/ids` (para conferir a cópia);
  - `POST /tarefas/lembretes` (do `agendador@`): `enviar_vencidos(listar_atrasados=False)`, grava
    `estado/envio_de_lembretes.ultima`, devolve só contagens.
- `store_firestore.importar(lote)`.
- `reminders/service.py`: com a marca "migrado", vai ao motor; com "migrando", recusa gravar.
- `reminders/envio.py`: o parâmetro `listar_atrasados`.
- `cli.py`:
  - `viking lembretes --migrar [--executar]`;
  - `--enviar` recusa depois de migrado;
  - `--nuvem` continua como está.
- `na_nuvem.criar_lembrete`: o `AVISO_SEM_EMAIL` só sem o envio ligado.
- **Testes** (o caminho do Mac contra o motor em processo e o emulador, e o `viking.db` do teste):
  - criar no Mac depois de migrado: aparece no Firestore, o registro é o da nuvem, e o SQLite não
    muda;
  - `--migrar --executar` sem o envio ligado recusa e não copia;
  - com o envio ligado, copia;
  - rodar de novo dá "igual" para tudo;
  - um id com conteúdo diferente vira "diferente" e não é sobrescrito;
  - uma queda no meio deixa "migrando", e rodar de novo termina;
  - o MCP depois de migrado não escreve no stdout;
  - `/tarefas/lembretes` não lê os atrasados (o dublê conta as consultas);
  - a resposta da rota não tem título;
  - a migração 7 sobre um banco no formato da 6, com dados.

**✅ Checkpoint:** `VIKING_EXIGIR_EMULADOR=1 pytest tests/test_lembretes_nuvem*.py
tests/test_banco_migracoes.py tests/test_reminders*.py tests/test_registro_ganchos.py -q` verde; a
suíte verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `--executar` sem conferir o envio ligado | "recusa e não copia" |
| `importar` com `set` (sobrescreve) | "diferente não é sobrescrito" |
| o serviço do Mac ignorando a marca | "o SQLite não muda" |
| a rota da nuvem lendo os atrasados | "não lê os atrasados" |
| `--enviar` sem a recusa | o teste do `--enviar` migrado |
| o aviso sempre presente | o aviso condicional |

**🐞 → Depurar:**
- classe 6, outro caminho que grava lembrete no SQLite → `grep -rn "reminders.store\|store.add"
  src/lifeos`;
- classe 2, a docstring sobre a transação → abrir o `banco.conectar` antes de escrever.

### Fase 5 — C5: fechar, publicar e testar no Mac
**Faz:**
- **Portões lidos, com a linha citada:** `pytest`, `ruff check`, `ruff format --check` (o
  formatador só nos arquivos editados), `mypy` (os módulos novos na lista), gitleaks e
  `uv lock --check`; o `docker build` em background.
- **Mutações:** as novas em `scripts/mutacoes.py`; a rodada inteira em background, sem `timeout`,
  com a saída num arquivo. Antes, reler a classe 5. Esperado: 282 + as novas, todas mortas pelo
  teste nomeado.
- **Duas passadas** (`referencia/revisao.md`), e `/security-review` e `/code-review` se existirem.
- **Docs parciais:** `AGENTS.md` (estrutura, comandos, `viking maos`, uma armadilha se aparecer),
  `docs/fontes/gcp-cloud-run-firestore.md` (o Scheduler e o preço lido).
- **Commit, push e o CI pelo SHA.**
- **Ok → `--executar contas`** (o `viking-maos@` e o papel do dono nele; custo zero) **e
  `--executar ttl`** (a TTL de `tarefas`; ela apaga tarefas com mais de 1 dia).
- **Ok → `deploy --executar`** (centavos), sem o Gmail. Provas: as de hoje, ajustadas, mais:
  - `cli@` recusado em `/maos/pegar`;
  - `/versao` com `gmail: false` e `envio_de_lembretes: false`;
  - o log sem erro.
- **Roteiro do Mac:**
  1. `cd ~/LifeOs && git pull && git log --oneline -1`
  2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
  3. num terminal: `viking maos`
  4. noutro: `viking chat --nuvem` → "abre example.com e me diz o título"; depois "abre o
     youtube" com o `viking maos` desligado (esperado: "não está ligado")
  5. `viking lembretes --migrar` (o ensaio: as contagens e "o envio da nuvem ainda não está
     ligado; nada copiado")

**✅ Checkpoint:**
- `python scripts/nuvem.py` → 10 ✅ (ou 11, com o passo novo);
- `deploy` → todas as provas ✅;
- a saída do Mac colada: o título do `example.com` veio pelas mãos, e o ensaio não copiou nada.

**🐞 → Depurar:**
- `PERMISSION_DENIED` ao pedir o token do `maos@` no Mac → o papel do dono **na conta**
  (`get-iam-policy`);
- 403 do motor → a rota na lista do `maos@`.

### Depois do portão (na retomada da 10c, a partir de 2026-10-04 em Seattle)
1. O 10c C6: o token do Gmail sobe do Mac.
2. O 10c C7: **ok** → `deploy --executar`; a prova com `gmail: True`; **ok** → `prova-chat`.
3. **Ok** → `python scripts/nuvem.py --executar agendador`:
   - a API do Scheduler;
   - o `viking-agendador@` e o `run.invoker` dele;
   - a tarefa `* * * * *` com OIDC e audience = a URL do motor;
   - custo de US$ 0 a 0,10/mês.

   Medido depois: `/versao` → `envio_de_lembretes: true`.
4. **A prova:** o dono cria pelo chat da nuvem um lembrete para daqui a 3 min e fecha o Mac. O
   e-mail chega em até ±2 min do prazo. A medição é o horário do e-mail contra o prazo, com os
   dois fusos escritos.
5. No Mac: `viking lembretes --migrar` (o ensaio), depois `--executar` → "copiados N, iguais 0,
   diferentes 0", e `viking lembretes` lista da nuvem.
6. **Fechamento:**
   - diário, barra, `sessoes.md` (a 11 feita) e D61 fechada;
   - as leituras do Firestore e os pedidos do Cloud Run medidos depois de 24 h com o agendador
     ligado, contra a conta acima;
   - commit, push, CI.

### Paralelismo
- A suíte, as mutações, o CI e o `docker build` vão em background e avisam quando terminam: sem
  laço de espera.
- O C2 e o C4 se escrevem em sequência, mas cada suíte de um roda enquanto o outro se escreve.

### Regra de conserto
Todo defeito começa pela classe dele em `docs/erros.md`, e o conserto não para no ponto: o `grep`
da forma inteira antes de dar por pronto. Os já previstos:
- `quem_pode`/`_quem` em toda rota;
- `print(`/`sys.stdout` no caminho do motor e do MCP;
- `reminders.store` direto fora do serviço;
- `clicar_aprovado` e os chamadores;
- `liberar` no caminho da nuvem;
- `from __future__` nos módulos de tool (`na_nuvem.py`).

Nenhuma checagem antes de um commit leva `| tail`. Emenda por script ancora na linha inteira.

### Riscos e o que é irreversível
| Passo | Custo | Irreversível? | O ok |
|---|---|---|---|
| C5: o `viking-maos@` e a TTL de `tarefas` | zero | a TTL apaga tarefas com mais de 1 dia, que já são lixo | pedido na hora |
| C5: deploy sem o Gmail | centavos | a revisão anterior fica | pedido na hora |
| Depois do portão: o agendador | US$ 0 a 0,10/mês | o motor passa a enviar e-mail sozinho, só para a conta do dono, no limite de 20 em 24 h | pedido na hora |
| Depois do portão: a migração de verdade | zero | o Mac passa a gravar na nuvem; o SQLite fica como cópia, e o backup da migração 7 também | o dono roda no Mac |

Nada do VPS toca o Gmail nem a Chrome do dono: os testes usam o dublê e o Jev falso, e o
`viking maos` só roda no Mac.

## Plano — Sessão 10c: nuvem 1c, o Gmail na nuvem e a aprovação pela rede (aprovado em 2026-09-30)

### Context
A 10b pôs o chat no motor (a agenda, os lembretes e o registro), e o Gmail ficou de fora por um
motivo com data: a prova de que o token do Gmail não vence em 7 dias só vale **a partir de
2026-10-04 (Seattle)**. O token do Mac é de 2026-09-26.

No chat, só o Gmail aprova com código. A 10c traz para a nuvem:
- as 7 tools do Gmail;
- a confirmação atrás de uma interface, com o store no Firestore;
- o código indo ao terminal por um campo próprio, sem nunca passar pelo modelo nem pelo log;
- o limite de tentativas erradas;
- um prazo do turno contra as esperas de cota.

**A prova é portão, não bloqueio:** tudo o que não depende dela se constrói agora (decisão do
dono). O token sobe do Mac e o deploy acontece só depois dela. Critério herdado do dono: "precisão,
otimização e software resiliente".

Com o plano aprovado, o C0 o copia para o topo do `PROGRESSO.md`, e a execução segue até o
portão sem pedir confirmação a cada fase. Os ok's do que custa, cria recurso ou publica continuam
pedidos **na hora**.

### O que esta sessão entrega (verificável)
1. **`viking chat --nuvem` lê o Gmail:** buscar, não lidos de hoje, ler e raio-x.
2. **O chat da nuvem arquiva com aprovação e desfaz por 7 dias.**
3. **O chat da nuvem envia:** para a própria conta, na hora; para outra pessoa, com código.
4. **O código de aprovação nasce e se confere no Firestore** (D57), por um contrato só com o
   SQLite do Mac:
   - vale uma vez e por 10 min;
   - é único entre ações por 8 dias;
   - **3 erradas cancelam a proposta**, nos dois chats e no `viking aprovar`.
5. **O código volta só no campo `ao_dono` da resposta:**
   - nunca no texto do modelo, no histórico, no log do Cloud Run ou num `print`;
   - o terminal do Mac o mostra só se for interativo;
   - sem terminal interativo, nenhuma proposta com código nasce (envio e limpeza).
6. **Nenhuma linha com verbo de aprovação e 4 dígitos vai ao Gemini, em nenhum dos dois chats**
   (resposta do dono; muda um comportamento testado do Mac).
7. **O turno na nuvem tem prazo total de 220 s.** A pior soma (um pedido em curso de até 60 s) fica
   em 280 s, abaixo dos 300 s do Cloud Run e dos 320 s do cliente. Esgotado o prazo, o turno diz o
   que já fez e para.
8. **O token do Gmail está no Secret Manager** (`viking-gmail`), lido como volume e renovado em
   memória. Ele sobe **do Mac**, por um comando que o dono roda lá.

### O que ela NÃO faz (e para onde foi)
- **Da S11** (resposta do dono: "só o Gmail"; a S11 continua inteira): migrar os lembretes do
  Mac, o lembrete por e-mail com o Mac desligado, `viking maos` e o backup no Drive.
- **O navegador e o clique liberado com código (D38)** ficam no Mac até a S11.
- **As finanças** seguem a D51.
- **O limite de 20 envios em 24 h conta separado no Mac e na nuvem** (D57: o registro mora onde a
  ação roda). Cada lado continua parando um laço. Unificar é S11 (a migração).
- **Tentativa errada de `desfaz NNNN`** não conta para o limite: não há proposta aberta a cancelar,
  e o desfazer só devolve e-mails à caixa.
- Nenhum destino novo precisa ser escrito: tudo acima já está na S11 e na D51.

### Respostas do dono (2026-09-30)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| Começar a parte independente antes de 04/10? | começar já | C0–C5 agora; C6 (a prova) em diante a partir de 04/10 |
| Tentativas erradas por proposta | 3 | `confirmacao.TENTATIVAS = 3`, no contrato dos dois stores (a migração 6 no SQLite) |
| Terminal interativo pela nuvem | exigir no envio e na limpeza | O pedido leva `interativo`; sem ele, envio e limpeza na nuvem recusam **antes** de criar código |
| Algo da S11 junto? | não, só o Gmail | Sessão do tamanho previsto |
| Barrar "verbo + 4 dígitos" no Mac também? | sim | A regra da `barreira` da nuvem vai para `aprovacao_local`. O teste `test_numero_que_nao_e_codigo_vivo_segue_para_o_gemini` muda nos casos com verbo; "tenho 4821 e-mails?" (sem verbo) continua indo ao Gemini |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **`confirmacao.py` mantém a API pública e as regras**, com o store atrás de `confirmacao_interface.Confirmacoes`: `confirmacao_sqlite.py` (o SQL de hoje) e `confirmacao_firestore.py`, escolhido por `config.STORE` | o molde do registro na 10b; os 11 usos de `confirmacao.*` não mudam | — |
| **No Firestore:** coleção `confirmacoes`, com id `time_ns` + `create()` (crescente) e todo campo gravado. `dados` e `resultado` vão como JSON literal. `apagar_em` = criada + 30 d (TTL) | ids crescentes ordenam como o `INTEGER` do SQLite; a TTL é maior que os 8 d da unicidade e os 7 d do desfazer | — |
| **A unicidade do código é estrutural:** um documento `codigos/NNNN` com `reservado_ate`, criado por `create()`. Se ele existe e venceu, é trocado por comparar e trocar | duas instâncias sorteando o mesmo número não podem vencer as duas; no SQLite, a transação já garante | — |
| **`consumir` por comparar e trocar** (`firestore_comum.trocar`). A reserva do código se estende para `consumida + 8 d` **antes** de gastar a proposta | o passo que consome vai por último (skill `integracoes`): se ele falhar, sobra só a reserva mais longa, que é inofensiva | — |
| **Consultas de um campo só** (`acao ==`, `codigo ==`, `reservado_ate >=`), com o resto filtrado em Python; nenhum índice composto novo | o emulador não exige índice e a produção exige (armadilha paga); a TTL limita o volume | a medida no ar passar de ~1 s |
| **A tentativa errada conta dentro de `confirmacao.consumir`**, no `CodigoInvalido`. Ela soma `erros` nas propostas abertas daquela ação (o laço já resolve a ação por `_tipo_do_codigo` ou `_tipo_aberto`). Na 3ª, a proposta fica `substituida` e o texto diz "3 códigos errados: cancelei; peça de novo". Expirado e já usado não contam | o contrato mora onde todo caminho passa (chat do Mac, chat da nuvem, `viking aprovar`) | — |
| **`lifeos/ao_dono.py`:** `mostrar(texto)` e `coletar()` (um contextvar com a lista do turno) e `interativo()`. Com o coletor ligado, o texto vai à lista; **na nuvem sem coletor, erra alto** (nunca imprime, porque o stdout é o log); no Mac, imprime como hoje. `gmail/tools._ao_dono` e `browser/liberacao.ao_dono` passam por ele | uma porta só para "o que só o dono vê"; o log do Cloud Run nunca recebe um código | — |
| **A resposta do motor ganha `ao_dono: list[str]`.** As respostas da barreira (aprovar, desfazer, código errado) também vão nele, e não em `resposta`. Invariante testável: **o sentinela do código aparece só em `ao_dono`** | uma regra só, sem exceção para lembrar | — |
| **`interativo`** vem do pedido (o cliente manda `sys.stdin.isatty() and sys.stdout.isatty()`), e na nuvem `ao_dono.interativo()` o lê. `envio._terminal()` passa a perguntar a ele; `limpeza.preparar` confere só na nuvem | o terminal que importa é o do Mac; quem manda é o `viking-cli@` do dono, que o motor já autentica | — |
| **`na_nuvem.barreira`** chama `agent.aprovacao_local` (o Firestore, pelo `STORE`), e depois a regra "verbo + 4 dígitos". O texto da regra passa a ser "não achei esse código aqui; se é do outro chat, digite lá" | `test_so_o_laco_do_chat_e_a_cli_confirmam` continua valendo: quem confirma é `agent.py` | — |
| **Prazo do turno:** `lifeos/prazo.py` (um contextvar com o instante-limite), 220 s na nuvem e nenhum no Mac. Quem consulta: `gmail/service._dormir` e `_Cota.gastar` (espera que passaria do prazo → `LimiteDoGmail("não deu tempo…")`, certeza de nada feito), `_executar` (menos de 60 s de sobra → não manda) e o gancho `antes` do Gemini (menos de 60 s → para o turno com o aviso das ações feitas) | medido: o `googleapiclient` 2.200.0 tem 60 s por operação de rede (`DEFAULT_HTTP_TIMEOUT_SEC`); uma chamada do Gmail passaria de 500 s (7 tentativas + 126 s de espera) | a medida no ar mostrar turnos normais perto de 220 s |
| **O token do Gmail na nuvem:** `/segredos/gmail/token.json` (`VIKING_GMAIL_TOKEN_ARQUIVO`); `credenciais_da_nuvem` aceita os dois tokens, cada um com o seu escopo; `/fumaca/segredos` ganha `gmail` (renova, sem chamar a API) | o molde da agenda na 10b | — |
| **`scripts/nuvem.py segredo viking-gmail --executar` roda no Mac:** o subcomando `segredo` passa a exigir só `VIKING_NUVEM_PROJETO`. Quem valida o arquivo é `_token_do_gmail` (JSON, `refresh_token`, `gmail.modify`), sem mostrar nada | o VPS não guarda token do Gmail (D57); hoje o `_contexto` exige `_FATURAMENTO` e `_ORCAMENTO`, que só existem no VPS (lido em 2026-09-30) | o `gcloud` do Mac não ter login de CLI (a medida do C5) |
| **Na nuvem com Gmail, o texto de sistema** troca "sem navegador, e-mail nem finanças" por "sem navegador nem finanças"; o do Mac fica igual byte a byte | `turno._SECOES` por presença de tool | — |

### Medido na abertura (2026-09-30, VPS)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `rev-parse`, `ls-remote`, `ls .mutacao.lock` | limpo; `646e268` = origin; sem trava | ok |
| Suíte | `.venv/bin/python -m pytest -q` (~16:00Z) | `2125 passed in 57.02s` | base |
| CI | `gh run list --commit 646e268…` | `completed success` | ok |
| **Divergência: versões** | `uv lock --upgrade --dry-run` | `charset-normalizer 3.5.1→3.5.2`, `cryptography 50.0.1→50.0.2` | C0: commit próprio, com a suíte antes e depois (D45) |
| Infraestrutura | `python scripts/nuvem.py` | 10 ✅ | ok |
| No ar | `python scripts/nuvem.py deploy` | `36fcd13`, 0 commits nos caminhos da imagem, 12 ✅ | ok |
| Prazo de rede do Google | `inspect(googleapiclient.http.build_http)` | 2.200.0, `DEFAULT_HTTP_TIMEOUT_SEC = 60` | o prazo do turno (acima) |
| Esperas do Gmail | `gmail/service.py` | `ESPERAS_S` soma 126 s por chamada; `_Cota` espera até 60 s; orçamento de 4.800/min; raio-x até 200 × 20 = 4.000; limpeza até 250 × 20 = 5.000 | raio-x e limpeza no mesmo minuto esperam ~60 s: cabem uma vez nos 220 s |
| **Achado: o código no log** | `gmail/tools._ao_dono` | `print(…, file=sys.stdout)`; no motor, o stdout é o log do Cloud Run | `ao_dono.py` erra alto na nuvem |
| **Achado: o terminal** | `gmail/envio._terminal` | `sys.stdin.isatty()` do processo; no motor, sempre falso | `interativo` do pedido |
| **Achado: o `segredo` no Mac** | `scripts/nuvem.py _contexto` | exige `VIKING_NUVEM_FATURAMENTO`/`_ORCAMENTO` (só no VPS) | só `_PROJETO` para `segredo` |
| Custo das tools do Gmail | **por diferença, sem gasto novo:** a mesma pergunta no Mac (C8 da 10b, 2026-09-30) → 9.019 tokens no local (23 tools) e 3.982 na nuvem (11) | as 12 tools só do Mac somam ≈ 5.000 tokens/turno. As 7 do Gmail: **teto** de ~+5.000 tokens ≈ US$ 0,0015/turno (US$ 0,30/M) | o teto de US$ 1/dia cabe ~300 turnos; o número exato sai do turno real do C7 |
| Onde a aprovação é executada | `test_gmail_aprovacao.py:294` | `confirmar`/`desfazer` só em `assistant/agent.py` e `cli.py` | a nuvem reaproveita `aprovacao_local` |

### Caminho crítico
```
AGORA (independe da prova)                          A PARTIR DE 2026-10-04 (Seattle)
C0 docs+lock ─► C1 confirmacao ─► C2 ao_dono/barreira ─┐
                         └────► C3 prazo do turno ─────┼─► C4 token/segredo/cliente ─► C5 portões,
                                                        │     mutações, push, CI, infra (ok),
                                                        │     pré-conferência no Mac (só lê)
                                                        │                │
                                            PORTÃO ═════╧════ C6 a prova no Mac + o token sobe do Mac
                                                                         │
                                                        C7 deploy (ok) + turno real (ok) ─► C8 docs ─► C9 Mac
```
C2 e C3 são independentes entre si (C3 só toca `gmail/service`, `prazo.py` e o gancho do Gemini).

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | lock atualizado em commit próprio (suíte `2125 passed` antes e depois, CI verde pelo SHA); este plano no topo do `PROGRESSO.md`; `sessoes.md` 10c com as respostas; D60; commit | — | ✅ |
| C1 | confirmacao atrás da interface; contrato nos dois stores (emulador, 0 pulados); migração 6 (`erros`); 3 erradas cancelam; corridas com 16 threads recolhendo exceções | C0 | ✅ |
| C2 | `ao_dono.py`; `interativo`; `barreira` = `aprovacao_local` + a regra; a mesma regra no Mac; as tools do Gmail na nuvem com dublê; o texto de sistema; o sentinela só em `ao_dono`; `capsys.out == ""` num turno inteiro da nuvem | C1 | ✅ |
| C3 | `prazo.py` e os quatro pontos que o consultam; relógio falso: o pior caso termina em ≤ 220 s + um pedido | C0 | ✅ |
| C4 | `SEGREDOS` + `viking-gmail`; `credenciais_da_nuvem` para o Gmail; `/fumaca/segredos` com `gmail`; `_token_do_gmail`; `segredo` só com o projeto; o passo `ttl` com `confirmacoes`; o cliente com `interativo` e `ao_dono`; a prova do deploy exige o volume do Gmail | C2, C3 | ✅ |
| C5 | portões lidos; mutações novas + 251 antigas em background; duas passadas; docs parciais; push; CI pelo SHA; **ok** → o segredo `viking-gmail` vazio e o papel, e a TTL de `confirmacoes`; `python scripts/nuvem.py` → 10 ✅; roteiro do Mac **só leitura** | C4 | ✅ |
| C6 | **portão (dono, ≥ 2026-10-04 Seattle):** `viking gmail --login` sem navegador → ✅; então, no Mac, `python scripts/nuvem.py segredo viking-gmail --executar` → 1 versão; o VPS mede → 1 versão | C5 | ⬜ |
| C7 | **ok** → `deploy --executar`; as provas ✅ (com `gmail: True`); **ok** → `prova-chat` com uma pergunta do Gmail (tempo, tokens, custo); o log sem conteúdo nem código | C6 | ⬜ |
| C8 | diário, barra 18/30, `sessoes.md`, `AGENTS.md`, fontes, D60 fechada; commit, push, CI | C7 | ⬜ |
| C9 | teste do dono no Mac (roteiro abaixo) | C8 | ⬜ |

### Fase 0 — C0: o lock e os documentos
**Faz:**
- `uv lock --upgrade` num commit próprio (D45), com a suíte antes (já medida: `2125 passed`) e
  depois; o CI desse commit, pelo SHA.
- `PROGRESSO.md`: este plano no topo, e o bloco RETOMAR apontando para o C1.
- `sessoes.md`: na 10c, as respostas do dono e a entrega acima; o ▶️ diz "em curso: a parte
  independente; portão em 04/10".
- `docs/decisoes.md` **D60**: as cinco respostas e as decisões técnicas.

**✅ Checkpoint:**
- `uv lock --upgrade --dry-run` → `No lockfile changes detected`;
- a suíte → `2125 passed`;
- `gh run list --commit <sha>` → `success`;
- `head -1 PROGRESSO.md` → `# Viking — progresso em curso`.

**🐞 → Depurar:** a versão nova do `cryptography` quebrar o `google-auth` → `uv lock --upgrade-package`
com a versão anterior e a pergunta ao dono (classe 3: ler o changelog antes).

### Fase 1 — C1: a confirmação atrás de uma interface
**Faz:**
- `src/lifeos/confirmacao_interface.py` (o `Protocol`) e `confirmacao_sqlite.py` (o SQL de hoje,
  movido).
- `confirmacao_firestore.py` (coleções `confirmacoes` e `codigos`). `confirmacao.py` fica com as
  regras, os erros e `TENTATIVAS = 3`.
- `banco.py`:
  - migração 6: `ALTER TABLE confirmacoes ADD COLUMN erros INTEGER NOT NULL DEFAULT 0`, um
    `execute`;
  - o checksum em `PUBLICADAS`;
  - nenhuma migração publicada editada.
- `firestore_comum.trocar` reaproveitado.
- `tests/test_confirmacao.py` vira o contrato, parametrizado pelos dois stores (o molde de
  `tests/test_registro.py`), mais:
  - a corrida do `consumir` e a do `propor`, cada uma com 16 threads e as exceções recolhidas;
  - a 3ª errada cancela, e a 2ª não;
  - expirado e já usado não contam;
  - o código consumido não se repete em 8 dias;
  - a migração 6 sobre um banco no formato da 5, com dados.

**✅ Checkpoint:**
- `VIKING_EXIGIR_EMULADOR=1 .venv/bin/python -m pytest tests/test_confirmacao.py -q` → os dois
  stores, 0 pulados;
- `tests/test_banco_migracoes.py` verde;
- a suíte inteira verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `consumir` do Firestore com `set` no lugar de `trocar` | a corrida do `consumir` |
| `codigos/NNNN` com `set` no lugar de `create` | a corrida do `propor` (a unicidade) |
| `TENTATIVAS` 3→4 | "a 3ª errada cancela" |
| a reserva estendida depois de gastar, ou sem estender | "consumido não se repete em 8 dias" |
| `erros` sem somar no SQLite | "a 3ª errada cancela" [sqlite] |

**🐞 → Depurar:**
- classe 4, thread que falha calada → a lista de exceções;
- classe 6, um caminho da confirmação que ainda abre o SQLite na nuvem →
  `grep -rn "banco.conectar\|_sessao" src/lifeos/confirmacao*.py`.

### Fase 2 — C2: o código só ao dono, e a barreira
**Faz:**
- `src/lifeos/ao_dono.py` (`mostrar`, `coletar`, `interativo`); `gmail/tools._ao_dono` e
  `browser/liberacao.ao_dono` passam por ele.
- `envio._terminal()` passa a chamar `ao_dono.interativo()`. `limpeza.preparar` na nuvem recusa sem
  terminal: `SemTerminal`, antes de `confirmacao.propor`.
- `assistant/na_nuvem.py`:
  - `_validar` aceita `interativo: bool`;
  - o turno roda dentro de `ao_dono.coletar()`;
  - a resposta ganha `ao_dono`;
  - `barreira` = `agent.aprovacao_local`, depois a regra "verbo + 4 dígitos", com as respostas em
    `ao_dono`;
  - `FERRAMENTAS` ganha as 7 do Gmail, e `SO_NO_MAC` fica só com o navegador e as finanças.
- `assistant/agent.py`: `aprovacao_local` ganha a regra "verbo + 4 dígitos não vivo" (a resposta
  do dono).
- `assistant/turno.py`: a seção da nuvem com o Gmail.
- **Testes, com o dublê do Gmail (`conftest`) e um Gemini falso que chama as tools:**
  - propor pela nuvem: o sentinela aparece (`tests/sentinela.aparece`) **só** em
    `resposta["ao_dono"]`, e em nenhum outro campo do JSON, no histórico, no `caplog` ou no
    `capsys.out`;
  - aprovar pela nuvem: `confirma NNNN` → 0 chamadas ao modelo, arquivado no dublê, e a linha fora
    do histórico;
  - 3 erradas → cancelada;
  - sem `interativo` → nenhuma proposta criada (as duas ações);
  - na nuvem sem coletor, `ao_dono.mostrar` levanta erro;
  - no Mac, "confirma o 4821 da nuvem" é barrado e "tenho 4821 e-mails?" passa;
  - o texto de sistema do Mac igual byte a byte;
  - toda tool classificada.

**✅ Checkpoint:**
- `pytest tests/test_na_nuvem.py tests/test_gmail_aprovacao.py tests/test_gmail_envio*.py
  tests/test_ao_dono.py -q` verde;
- `grep -rn "print(" src/lifeos/gmail src/lifeos/confirmacao*.py src/lifeos/assistant/na_nuvem.py`
  → só o que passa por `ao_dono` (conferido um a um);
- a suíte inteira verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `_ao_dono` com `print` de volta | "sentinela só em `ao_dono`" (`capsys`) |
| a resposta da barreira em `resposta` | "sentinela só em `ao_dono`" |
| `interativo` ignorado | "sem terminal, nenhuma proposta" |
| `barreira` sem `aprovacao_local` | "aprovar pela nuvem" |
| a regra "verbo + 4 dígitos" fora do Mac | "no Mac, 'confirma o 4821 da nuvem' barrado" |
| uma tool do Gmail fora das duas listas | "toda tool classificada" |

**🐞 → Depurar:**
- classe 6, outro caminho que imprime o código → `grep -rn "ao_dono\|isatty\|sys.stdout"
  src/lifeos`;
- classe 7, a regra do Mac pegando frase legítima → listar os vizinhos (horário "15:30", "2027",
  "4821 e-mails") e testar os dois lados;
- o future import num módulo de tool → o teste por tool.

### Fase 3 — C3: o prazo do turno
**Faz:**
- `src/lifeos/prazo.py` (`limite()`, `restante()`, `dentro(segundos)`).
- `na_nuvem.PRAZO_DO_TURNO_S = 220`.
- Quem consulta o prazo:
  - `gmail/service._dormir` e `_Cota.gastar`: uma espera que passaria do prazo vira
    `LimiteDoGmail`;
  - `_executar`: com menos de 60 s de sobra, não manda;
  - o gancho `antes` do Gemini: com menos de 60 s, `TempoEsgotado`, e o turno responde com o aviso
    das ações feitas (`registro.do_turno`).
- No Mac, nenhum prazo (o contextvar vazio).

**✅ Checkpoint:** com o relógio falso, "429 em toda chamada" e "orçamento cheio" terminam em
≤ 220 s de relógio, com o erro dizendo "não deu tempo" e nada feito. Um turno com uma arquivada
antes do prazo avisa que ela foi feita. `pytest tests/test_prazo.py tests/test_gmail*.py -q`
verde.

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `_dormir` sem conferir o prazo | "429 em toda chamada ≤ 220 s" |
| o gancho do Gemini sem o prazo | "turno para antes da chamada que não cabe" |

**🐞 → Depurar:** o contextvar não chegar à thread do `run_in_threadpool` → defini-lo dentro de
`na_nuvem.turno` (a thread), como `registro.ORIGEM`.

### Fase 4 — C4: o token do Gmail, o script e o cliente
**Faz:**
- `config`: `VIKING_GMAIL_TOKEN_ARQUIVO`, lido na nuvem.
- `google_auth.credenciais_da_nuvem`: os dois tokens, cada um com o seu escopo e a sua mensagem.
- `motor._segredos`: `gmail` (renova em memória, sem chamar a API).
- `scripts/nuvem.py`:
  - `SEGREDOS` ganha `viking-gmail` (`/segredos/gmail/token.json`);
  - `FONTES` ganha `_token_do_gmail` (a validação acima);
  - `segredo` exige só o projeto;
  - o passo `ttl` ganha `confirmacoes.apagar_em`;
  - a prova "segredos só como volume" com os três;
  - o deploy recusa, antes de construir, se `viking-gmail` não tem versão.
- `nuvem/chat_cliente.py`:
  - manda `interativo`;
  - mostra `ao_dono` (com `limpar_controles`) só se o próprio terminal for interativo; senão diz
    "(há uma mensagem com código: só num terminal interativo)";
  - a abertura diz que o Gmail está na nuvem.
- **Testes:**
  - o valor do token nunca no argv, na saída ou num erro;
  - todo `gcloud` com `--project`;
  - o `segredo` sem `_FATURAMENTO` roda;
  - token sem `gmail.modify` ou sem `refresh_token` é recusado sem mostrar nada;
  - o cliente sem TTY não imprime `ao_dono`;
  - `credenciais_da_nuvem` nunca abre login nem grava.

**✅ Checkpoint:**
- `pytest tests/test_nuvem_script.py tests/test_motor.py tests/test_google_auth*.py
  tests/test_chat_cliente*.py -q` verde;
- `docker build` ok (em background).

**Mutações** (cada uma derruba o teste nomeado):

| Mutação | O teste que tem de cair |
|---|---|
| `viking-gmail` fora de `SEGREDOS` | a prova "segredos só como volume" |
| `_token_do_gmail` sem conferir o escopo | "token sem `gmail.modify` recusado" |
| o cliente imprimindo `ao_dono` sem TTY | o teste do cliente |

**🐞 → Depurar:** classe 7, a segunda vida do script (o segredo existe sem versão) → um teste do
estado "existe, 0 versões".

### Fase 5 — C5: fechar a parte independente
**Faz:**
- **Portões lidos, com a linha citada:** `pytest`, `ruff check .`, `ruff format --check .` (o
  formatador só nos arquivos editados), `mypy` (os módulos novos entram na lista) e o gitleaks.
- **Mutações:** as novas entram em `scripts/mutacoes.py`, e a rodada inteira vai em background, sem
  `timeout`, com a saída num arquivo. Esperado: **251 + as novas, todas derrubadas pelo teste
  nomeado**.
- **Duas passadas** (`referencia/revisao.md`), mais `/security-review` e `/code-review` se
  existirem.
- **Commit, push, CI pelo SHA.**
- **Ok do dono → `scripts/nuvem.py --executar`**, só os passos que faltam (o custo é zero):
  - o segredo `viking-gmail` criado **sem versão**, com `secretAccessor` para o `viking-motor@`
    **no segredo**. São 3 segredos e até 3 versões ativas, dentro das 6 grátis;
  - a TTL de `confirmacoes.apagar_em`, que apaga confirmações com mais de 30 dias.
- **Roteiro do Mac, só leitura** (não toca o token do Gmail):
  1. `cd ~/LifeOs && git pull && git log --oneline -1`
  2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
  3. `gcloud auth list`
  4. `python scripts/nuvem.py segredo viking-gmail` → "0 versão(ões)… a fonte é o token do
     Gmail"; nada é enviado.

**✅ Checkpoint:**
- `python scripts/nuvem.py` → 10 ✅ (`viking-gmail`: 0 versões, criado);
- o CI `success` pelo SHA;
- a saída do Mac colada, com o passo 4 sem erro de login nem de permissão.

**🐞 → Depurar:** o `gcloud` do Mac sem login de CLI (só o ADC) → `gcloud auth login` do dono
(classe 1: o roteiro testado antes de 04/10, não no dia).

### Fase 6 — C6: o portão (dono, a partir de 2026-10-04 em Seattle)
1. No Mac: `viking gmail --login` → "✅ Login do Gmail ok…" **sem abrir o navegador**.
2. Se passou, no Mac: `python scripts/nuvem.py segredo viking-gmail --executar` → "✅ versão nova
   enviada (1 habilitada)".
3. No VPS: `python scripts/nuvem.py` → `viking-gmail: 1 versão`.

**Se o login pedir o navegador:** o token do Gmail não sobe, e nada é publicado. O modo "Testing"
estava ativo (a verificação do Google ou um escopo menor antes), e a 10c muda: gatilho da D59/D60,
com uma pergunta ao dono.

### Fase 7 — C7: publicar e provar
- **Ok** → `python scripts/nuvem.py deploy --executar`.
- **Provas:** as 12 de hoje, mais:
  - `/fumaca/segredos` → `{'gemini': True, 'agenda': True, 'gmail': True}`;
  - os três segredos só como volume;
  - o log sem erro.
- **Ok** → `python scripts/nuvem.py prova-chat "quantos e-mails não lidos chegaram
  hoje?"`, só leitura, anotando o tempo, os tokens e o custo. Esperado: HTTP 200, menos de 30 s e
  menos de US$ 0,005.
- O log da revisão nova sem a pergunta, a resposta ou um número de 4 dígitos vindo de `ao_dono`.

**✅ Checkpoint:** as provas literais, com horário, no `PROGRESSO.md`.

**🐞 → Depurar:**
- `invalid_grant` no Gmail → subir de novo do Mac (o C6, passo 2);
- `PERMISSION_DENIED` no volume → o papel **no segredo** (`get-iam-policy`).

### Fase 8 — C8: fechamento
- **Docs:**
  - `AGENTS.md`: a estrutura (`confirmacao_*`, `ao_dono.py`, `prazo.py`), as variáveis e duas
    armadilhas novas (o stdout do motor é o log; o terminal que importa é o do Mac);
  - `docs/fontes/gcp-cloud-run-firestore.md` e `gmail-api.md`: o turno medido, o prazo e o token
    na nuvem;
  - o diário (com "Erros desta sessão"), a barra em 18/30, `sessoes.md`, D60 e `PROGRESSO.md`.
- **Fechar:** commit, push, CI pelo SHA.

### Verificação ponta a ponta (C9, roteiro do Mac)
1. `cd ~/LifeOs && git pull && git log --oneline -1`
2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
3. `viking chat --nuvem`:
   - "o que chegou hoje no meu e-mail?" → a lista;
   - "faz um raio-x da caixa";
   - "prepara a limpeza de <um remetente escolhido por ele>" → a lista e o código aparecem no
     terminal; o texto do modelo não tem o código;
   - `confirma 0000` três vezes (a 3ª cancela) → pedir de novo → `confirma <o código>` →
     arquivados;
   - `desfaz <o código>` → os e-mails voltam;
   - "manda um e-mail para eu com o assunto teste 10c" → sai na hora;
   - `sair`.
4. `echo "o que chegou hoje no meu e-mail?" | viking chat --nuvem` → responde; uma proposta nesse
   modo recusa por falta de terminal.
5. `viking chat` (o local) → a mesma pergunta do Gmail, igual a antes; "confirma o 4821 da nuvem"
   → barrado.

### Paralelismo
- A suíte, as mutações, o CI e o `docker build` vão em background, e cada um avisa quando termina:
  sem laço de espera.
- Enquanto a suíte do C1 roda, escrevo o C3, que é independente. Enquanto as mutações do C5 rodam,
  escrevo os docs parciais e o roteiro do Mac, sem tocar código.

### Regra de conserto
Todo defeito começa pela classe dele em `docs/erros.md`. O conserto não para no ponto: antes de
dar por pronto, o `grep` da forma inteira. Os `grep` já previstos:
- `print(`/`sys.stdout` no caminho da nuvem;
- `isatty`;
- `banco.conectar` na confirmação;
- `from __future__` nos módulos de tool;
- um número de 4 dígitos procurado sem `tests/sentinela.aparece`.

### Riscos e o que é irreversível
| Passo | Custo | Irreversível? | O ok |
|---|---|---|---|
| C5: o segredo vazio, o papel e a TTL de `confirmacoes` | zero | a TTL apaga confirmações com mais de 30 dias, acima dos 8 da unicidade e dos 7 do desfazer | pedido na hora |
| C6: o token do Gmail na nuvem | — | o motor passa a poder ler, arquivar e **enviar** pela conta real, sempre atrás do código, do registro e do teto | o dono roda o comando no Mac |
| C7: deploy | centavos | a revisão anterior fica e se volta a ela | pedido na hora |
| C7: turno real | ~US$ 0,002 | — | pedido na hora; só leitura |

Nada do VPS toca o Gmail: o VPS não tem o token, e os testes usam o dublê.

## Plano — Sessão 10b: nuvem 1b, o chat na nuvem (o Gmail e o código pela rede vão para a 10c)

### Context
A 10 pôs no ar o chão da nuvem: o motor fechado por IAM e pelo próprio código, o Firestore com o
contrato dos lembretes, o deploy por script e `viking lembretes --nuvem`. O próximo passo do
roteiro (D47) é o **cérebro na nuvem**: o laço do Gemini roda no motor, e o terminal do Mac vira
cliente dele.

O dono dividiu a 10b em duas (2026-09-30):
- **10b, esta sessão:** agenda, lembretes e o registro de ações;
- **10c:** o Gmail e o código de aprovação pela rede. A prova do token do Gmail só vale depois de
  2026-10-03, e, no chat, só o Gmail usa código (o clique do navegador fica no Mac).

Critério herdado do dono: "precisão, otimização e software resiliente". Com o plano aprovado, o C0
copia este texto para o topo do `PROGRESSO.md`, e a execução segue até o fim sem pedir confirmação
a cada fase. Continuam pedidos, **na hora**, os ok's do que custa dinheiro, cria recurso ou publica.

### O que esta sessão entrega (verificável)
1. **`viking chat --nuvem` no Mac conversa com o motor.**
   - O laço do Gemini roda no Cloud Run, com as tools da agenda (7), dos lembretes (3) e
     `acoes_recentes`.
   - O histórico fica só no terminal do Mac e vai a cada turno; a nuvem não grava a conversa.
   - O `viking chat` local continua igual a hoje.
2. **Chave do Gemini e token da agenda no Secret Manager**, lidos pelo `viking-motor@` como
   arquivo de um volume: nunca em variável de ambiente, na imagem, no `describe` nem no log.
3. **O registro de ações mora no Firestore quando a ação roda na nuvem** (D57).
   - O mesmo contrato do SQLite, nos dois stores, no emulador e no CI.
   - A retenção de 30 dias vira a TTL nativa do Firestore.
   - O `desfaz` sozinho do calendário funciona no chat da nuvem.
4. **Teto de gasto do Gemini no app**, conferido **antes** de cada chamada:
   - US$ 10 por mês e US$ 1 por dia, no fuso do dono;
   - bateu o teto, o turno é recusado e a resposta diz quanto já foi gasto.
5. **Nenhuma linha com cara de aprovação vai ao Gemini na nuvem:**
   - `confirma NNNN`, só o número, ou a palavra sozinha;
   - na 10b, a resposta é "ainda não há o que aprovar na nuvem" (a aprovação chega na 10c).
6. **Os lembretes criados pelo chat da nuvem dizem que ainda não saem por e-mail** (até a S11). O
   `viking lembretes --nuvem` mostra a mesma marca.

### O que ela NÃO faz (e para onde foi)
Todos os destinos são escritos no C0, antes de qualquer código.
- **A prova do token do Gmail** (depois de 2026-10-03) → primeiro passo da 10c.
- **Na nuvem, na 10c:** as tools e os tokens do Gmail; `confirmacao.py` no Firestore; o código no
  campo `ao_dono` da resposta, só num terminal interativo; o limite de tentativas erradas.
- **Navegador e finanças** → ficam no `viking chat` local até a S11 (as mãos) e a D51.
- **Lembretes:**
  - o envio por e-mail dos lembretes da nuvem, e a migração dos dados do Mac → S11 (já estão
    lá);
  - os lembretes ficam em dois lugares até a migração (decisão do dono).
- **Aposentar o `viking chat` local** → S11.

### Respostas do dono (2026-09-30)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| Dividir a 10b pela data do Gmail | 10b agora + 10c depois de 03/10 | Sem Gmail e sem `confirmacao` na nuvem; seção nova da 10c no C0; a barra passa de 29 para 30 sessões |
| O chat local e as tools só do Mac | os dois convivem até a S11 | `viking chat --nuvem` é um comando novo, e o local não muda. O motor registra só as tools que moram na nuvem, e o texto de sistema só fala delas (teste) |
| Teto do Gemini | US$ 10/mês, até US$ 1/dia | Valores em `config`, conferidos antes de cada chamada ao modelo; o dia e o mês no fuso do dono |
| Medir o turno daqui | sim, agora | C0: ~5 turnos reais com a chave do `.env` do VPS, só lendo a agenda, com os lembretes num banco temporário |
| Onde mora o histórico | só no terminal do Mac | O motor não guarda estado: o histórico vai e volta no corpo do pedido (medido: `Content` → JSON → `Content` igual, com a assinatura de raciocínio) |
| Lembrete criado na nuvem sem e-mail até a S11 | criar e avisar em voz alta | O texto de `criar_lembrete` na nuvem e o `viking lembretes --nuvem` levam a marca |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Um núcleo do turno** (`assistant/turno.py`, sem `print` nem `input`), usado pelo REPL local e pelo `/chat` do motor. As tools e o texto de sistema vêm de uma tabela com o lugar de cada tool (`mac` ou `nuvem`), e um teste exige que toda tool esteja nela | duas cópias do laço divergiriam (skill `software-build` §4, estrutura vence disciplina). `aprovacao_local` fica em `agent.py`: os testes do Gmail leem o código de lá | o laço local precisar de algo que a nuvem não pode ter |
| **O motor sem estado:** `POST /chat` recebe `{historico, mensagem, nota, sessao, numero}` e devolve `{resposta, historico, nota, aviso, gasto}`, com o corpo limitado (413 acima do teto) | a decisão do dono; nada de conteúdo na URL (o log guarda a URL) | a conversa ficar grande demais (medir o corpo nos turnos do C0) |
| **As rotas do motor viram `def`** (o Starlette as roda numa thread) | hoje são `async` e chamam código que bloqueia; um turno de chat pararia os outros pedidos da instância | — |
| **O Gemini com prazo:** `HttpOptions(timeout)` por chamada, no máximo N chamadas de tool por turno (`maximum_remote_calls`) e o `--timeout` do Cloud Run acima disso | sem prazo, uma chamada presa segura o pedido até o Cloud Run matar; os números saem da medição do C0 | — |
| **O prazo do motor:** 300 s (o padrão do Cloud Run), ou 3× o turno mais lento medido, o que for maior. O cliente espera o prazo do motor mais 20 s | as esperas do Gmail somam até 126 s (10c); cobrado só enquanto o pedido roda | a medição mostrar turnos acima de 100 s |
| **Segredos como volume:** `/segredos/gemini/chave` e `/segredos/agenda/token.json`; o `config` é o único leitor, lê uma vez por instância e guarda | o Google recomenda o volume para usar `latest`; a cota grátis é de 10 mil acessos por mês (lido em 2026-09-30) | — |
| **O token da agenda na nuvem:** lido do volume, renovado **em memória**, nunca gravado. O login nunca se abre na nuvem (`google_auth.servico` tem o caminho da nuvem). Renovação recusada vira um erro alto com o que fazer | o volume é só leitura; o `InstalledAppFlow` na nuvem penduraria o pedido | — |
| **O token que sobe é a cópia do VPS** (a mesma conta, copiada do Mac em 2026-09-20; ela guarda `client_id`/`client_secret`), por `scripts/nuvem.py`, entrada padrão, sem aparecer em nada | o VPS já o tem; evita um passo no Mac. A prova no ar diz se ele ainda renova | a renovação falhar → subir o do Mac por um comando no Mac |
| **`banco.conectar()` recusa no modo nuvem** (`VIKING_STORE=firestore`) | nada no motor pode abrir um SQLite em silêncio; a pasta da imagem nem é gravável pelo usuário 65532 | — |
| **O registro atrás de uma interface** (`registro_interface.Registro`, como `reminders/interface`); `registro_firestore.py` com ids inteiros crescentes (`time_ns` + `create()`) e a TTL em `expira_em` | a API pública de `registro` e os 13 módulos que o usam não mudam; a ordem por id continua valendo | — |
| **Consultas do registro no Firestore com um campo só**, filtrando o resto em Python; o único índice composto é `(operacao, criada_em)`, para `contaveis`, em `INDICES`; a prova no ar exerce cada consulta | o emulador não exige índice e a produção exige (armadilha paga na 10) | — |
| **O `_trocar` (comparar e trocar) sai para um módulo comum** do Firestore, usado pelos lembretes, pelo registro e pelo teto | o terceiro consumidor é o gatilho | — |
| **Teto:** um documento por mês (`gastos/AAAA-MM`, com o total e os dias), somado depois de cada chamada e conferido antes da próxima. É estimativa pelas tarifas do `config`, e a resposta diz isso | o alerta do GCP só avisa; conferir antes também corta um turno longo no meio (o aviso de ações do turno já existe) | a fatura real divergir da estimativa |
| **O teto vale para o chat da nuvem;** o local continua só mostrando `/custos` | o dono decidiu os dois chats; o local se aposenta na S11 | o dono querer o teto no local também |
| **Linha com cara de aprovação na nuvem:** as mesmas regras de `aprovacao_local` (verbo e número, só o número, a palavra sozinha). Na 10b, a resposta é "nada a aprovar na nuvem ainda"; a linha nunca vai ao modelo nem ao histórico devolvido | a regra "nunca ao Gemini" vale antes de a aprovação existir | — |
| **A prova de chat no ar:** um turno real só com `deploy --executar` (custa, com o ok). As provas de sempre, grátis, conferem que o segredo lê, que o token da agenda renova e as consultas do registro | as provas rodam a cada `deploy`, e não podem gastar | — |

### Medido na abertura (2026-09-30, VPS)
| O quê | Comando / fonte | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `rev-parse`, `ls-remote`, `ls .mutacao.lock` | limpo; `af146ad` = origin; sem trava | ok |
| Suíte | `.venv/bin/python -m pytest -q` | `1997 passed in 34.52s` | base |
| CI do HEAD | `gh run list --commit af146ad5…` | `completed success` | ok |
| Versões | `uv lock --upgrade --dry-run` (e `--refresh`) | `No lockfile changes detected` | nada a subir |
| Infraestrutura | `python scripts/nuvem.py` | 8 ✅ | ok |
| No ar | `python scripts/nuvem.py deploy` | `b7a0635`, 0 commits desde ela, 9 provas ✅ | ok |
| **Divergência** | `git show 736fd1a:PROGRESSO.md` | a linha 1 virou `\1\| ✅ \|1\| ✅ \|1\| ✅ \|` (título perdido numa substituição) | conserto e classe 5 no C0 |
| **Divergência** | `sessoes.md` ▶️ | "as perguntas da abertura da 10" | C0 |
| Quem aprova com código no chat | `aprovacoes.TIPOS` | Gmail (arquivar, enviar) e o clique do navegador; a agenda só pelo MCP | o código pela rede vai para a 10c |
| Registro e confirmação | `grep` | `registro` em 13 módulos; `confirmacao` com 11 funções usadas; ids `INTEGER` sequenciais | interface + ids crescentes |
| Prazo | `gmail/service.py`; laço do chat | as esperas de cota somam até 126 s; o Gemini sem prazo; o motor com `--timeout=60` | prazos da tabela acima |
| Motor | `nuvem/motor.py` | rotas `async` chamando código que bloqueia | viram `def` |
| Cloud Run | docs `request-timeout` (atualizada em 2026-09-29) | o padrão é 300 s e o máximo 3600 s | — |
| Secret Manager | docs de segredos no Cloud Run (2026-09-29); cota grátis (2026-09-24) | volume = sempre a mais nova ao ler; variável = lida ao subir (fixar versão); `secretAccessor`; 6 versões ativas, 10 mil acessos e 3 notificações por mês grátis | volume; 2 segredos com 1 versão cada |
| google-genai 2.25.0 | script | `chats.create(history=)`, `HttpOptions.timeout`, `maximum_remote_calls`; `Content` vai e volta em JSON igual | o motor sem estado dá |
| Token da agenda no VPS | `ls -l`; o campo `expiry` (sem imprimir segredo) | copiado em 2026-09-20 e nunca renovado aqui (`expiry` 2026-09-19); tem `client_id`/`client_secret` | não prova os 7 dias; a prova no ar diz se renova |
| `google_auth.credenciais` | leitura | abre o `InstalledAppFlow` se o token falha, e regrava o arquivo sempre | caminho da nuvem próprio |
| Duração de um turno | diário, fontes | **nunca medida** | C0 mede (ok do dono) |
| **Turno medido (C0, 2026-09-30 ~04:10Z)** | script na pasta de rascunho: 5 perguntas reais, tools de leitura da agenda + lembretes num banco temporário, `gemini-2.5-flash` | 2,01 · 3,02 · 0,94 · 1,94 · 2,55 s; 2–3 chamadas por turno; 13.224 tokens (12.211 in / 1.013 out), ~US$ 0,0062 no total (0,0007–0,0018 por turno, estimativa pelas tarifas do `config`); histórico de 931 B a 7.068 B | `--timeout=300` (3× o mais lento = 9 s; o piso é o padrão); o prazo por chamada ao Gemini 60 s; `maximum_remote_calls` 10; corpo do `/chat` até 4 MiB; o teto de US$ 1/dia ≈ 600 turnos destes |
| Token da agenda do VPS (C0) | `credenciais_sem_login` sem imprimir nada | renovou em 2026-09-30, 10 dias depois de feito (2026-09-20); o arquivo não foi regravado | indício de que o app OAuth não está em "Testing"; a prova do Gmail continua na 10c |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | medição do turno (5 turnos, tempos e custo num arquivo); `PROGRESSO` com a linha 1 consertada e este plano; `sessoes.md` (▶️, 10b, **10c nova**); D59; classe 5 (10); barra 16/30; commit | — | ✅ |
| C1 | registro atrás da interface, Firestore passando o contrato nos dois stores (emulador, CI); `banco.conectar` recusa na nuvem; `_trocar` comum | C0 | ✅ |
| C2 | núcleo do turno + tabela de tools por lugar; teto no Firestore; linha de aprovação barrada; o aviso do lembrete; o REPL local inalterado (os testes do chat de hoje verdes sem edição de asserção) | C1 | ✅ |
| C3 | motor: rotas `def`, `POST /chat`, limite de corpo, fumaças novas; `google_auth` modo nuvem; `config` lê segredo de arquivo; imagem constrói | C2 | ✅ |
| C4 | `viking chat --nuvem` (cliente com histórico e nota, prazo longo, erros em português) e a marca em `viking lembretes --nuvem`; testes offline | C3 | ✅ |
| C5 | `scripts/nuvem.py`: API `secretmanager`, passos `segredos` e `ttl`, subcomando que sobe uma versão sem mostrar, deploy com volumes e prazo; **ok** → API, segredos, versões, TTL; só-leitura 10 ✅ | C3 | ✅ (10 ✅ às 05:17Z) |
| C6 | **ok** → deploy; provas antigas + novas ✅; **ok** → um turno real no ar (tempo e custo anotados) | C4, C5 | ✅ (`36fcd13` no ar às 05:20:59Z; 12 provas ✅; o turno real em 4,9 s) |
| C7 | portões, duas passadas, `/security-review` se houver, docs, mutações em background, commits, push, CI pelo SHA | C6 | ✅ (251/251; CI pelo SHA depois do push) |
| C8 | teste do dono no Mac | C7 | ✅ (2026-09-30: `2048 passed, 64 skipped`; o chat da nuvem e o local conferidos) |

### Fase 0 — documentos e a medição (C0)
**Medição (ok do dono, 2026-09-30):**
- Um script na pasta de rascunho monta o cliente do Gemini com a chave lida do `.env`, sem
  imprimi-la.
- Tools: só as de **leitura** da agenda (listar próximos, por data, buscar) e as de lembretes, com
  `VIKING_DB_PATH` num banco temporário. Nada escreve na agenda.
- 5 perguntas reais: "o que tenho amanhã?", "e na semana que vem?", "lista meus lembretes", "cria
  um lembrete de teste para amanhã às 9h", "resume minha semana".
- Por turno: o tempo de relógio, as chamadas ao Gemini, os tokens, o custo estimado e o tamanho do
  histórico em JSON. Saída inteira num arquivo; o resumo vai para "Medido" com data.
- O token da agenda do VPS pode renovar e ser regravado: é o comportamento normal, e só lê a
  conta.

**Docs:**
- `PROGRESSO.md`: a linha 1 volta a `# Viking — progresso em curso`; este plano no topo.
- `sessoes.md`:
  - o ▶️ aponta para a 10b;
  - a seção 10b com a entrega acima;
  - **seção 10c nova**, que começa pela prova do Gmail e leva o que saiu daqui (o Gmail na
    nuvem, a confirmação no Firestore, o `ao_dono`, o limite de tentativas).
- `docs/decisoes.md` D59: as respostas e as decisões acima.
- `docs/erros.md`, classe 5 (10): a substituição com `\1` no fechamento da 10, que as duas passadas
  não pegaram. O antídoto: `head -3` de cada documento tocado antes do commit.
- Barra: 16 de **30**.

**✅ Checkpoint:**
- o arquivo da medição com 5 turnos;
- `head -1 PROGRESSO.md` → `# Viking — progresso em curso`;
- `git grep -n '^\\1'` → vazio;
- a suíte → `1997 passed`.

**🐞 → Depurar:** um turno pedir login (o token do VPS não renova) → é a medida (registrar), não
um defeito; seguir sem as tools da agenda e anotar para o C6.

### Fase 1 — o registro no Firestore (C1)
**Faz:**
- `registro_interface.py`: o `Protocol` com as primitivas `iniciar`, `terminar`, `do_turno`,
  `recentes`, `contaveis`, `obter`, `ultima_desfazivel`, `reivindicar_desfazer`,
  `devolver_desfazer` e `purgar`.
- `registro.py` mantém a API pública (`acao`, `ORIGEM`, `TURNO`, `Acao`…) e delega ao store
  escolhido por `config.STORE`. O SQLite é o código de hoje.
- `registro_firestore.py`: coleção `acoes`; id `time_ns` + `create()`; todo campo gravado;
  `expira_em` = `criada_em` + 30 dias (TTL). A leitura também filtra os 30 dias, porque a TTL apaga
  com atraso. `reivindicar_desfazer` por comparar e trocar.
- `_trocar` sai para `lifeos/firestore_comum.py`.
- `INDICES` ganha `acoes (operacao, criada_em)`.
- `banco.conectar()` levanta erro no modo nuvem.
- `ORIGEM` ganha `nuvem`.
- **Testes:**
  - `tests/test_registro_contrato.py` roda nas duas implementações (o padrão da
    `test_reminders_contrato`);
  - a corrida do `reivindicar_desfazer` com 16 threads, **recolhendo as exceções**;
  - documento parcial erra alto;
  - `banco.conectar` recusa na nuvem.
- **Mutações:** o `desfazer` reivindicado duas vezes; sem o filtro dos 30 dias; sem `create()`
  (sobrescreve).

**✅ Checkpoint:**
- `pytest tests/test_registro_contrato.py -q` com `VIKING_EXIGIR_EMULADOR=1` → os dois stores, 0
  pulados;
- a suíte inteira verde;
- `tests/test_registro_ganchos.py` sem mudança de asserção.

**🐞 → Depurar:**
- classe 4: uma thread que falha em silêncio → a lista de exceções no teste;
- classe 6: um caminho que ainda chama o SQLite na nuvem → `grep -rn "banco.conectar" src/`.

### Fase 2 — o núcleo do turno, o teto e as barreiras (C2)
**Faz:**
- `assistant/turno.py`:
  - `LUGAR` (tool → `mac`/`nuvem`); `ferramentas(lugar)`; `instrucao(lugar)`, montada por seção;
  - `executar_turno(chat, mensagem, nota)` devolve o texto, a nota e o aviso de ações depois de
    um erro;
  - `historico_para_json` e `historico_de_json`.
- `agent.py`: o REPL chama o núcleo; `aprovacao_local` fica ali.
- `assistant/nuvem.py`, o turno da nuvem:
  - a barreira de aprovação: o `desfaz` sozinho do calendário age; as outras formas respondem "na
    nuvem ainda não há o que aprovar";
  - o cliente do Gemini com prazo e `maximum_remote_calls`;
  - o teto.
- `custos.py`: o `Teto` com os valores do `config` (US$ 10 por mês, US$ 1 por dia), o documento
  `gastos/AAAA-MM` e o fuso do dono. `conferir()` roda antes de cada `_generate_content`, pelo
  gancho que já existe; `somar()` roda depois.
- `criar_lembrete` na nuvem acrescenta a marca "o aviso por e-mail deste lembrete ainda não existe
  na nuvem (chega na S11)".
- **Testes, com um Gemini falso que conta as chamadas:**
  - uma linha de aprovação → 0 chamadas ao modelo e ausente do histórico devolvido;
  - teto no dia → 0 chamadas; teto no meio do turno → para, com o aviso;
  - a virada do dia no fuso do dono (Los Angeles contra UTC);
  - na nuvem, só as tools da nuvem, e o texto de sistema sem navegador, finanças nem Gmail;
  - toda tool classificada;
  - o histórico vai e volta com `thought_signature`;
  - o REPL local: os testes de `agent` de hoje, sem mudança de asserção.
- **Mutações:** conferir o teto depois da chamada; a linha de aprovação ir ao modelo; uma tool do
  Mac na lista da nuvem.

**✅ Checkpoint:**
- `pytest tests/test_turno*.py tests/test_teto*.py -q` verde;
- a suíte inteira verde;
- o `grep` de `from __future__` nos módulos de tool → nenhum novo.

**🐞 → Depurar:**
- classe 7, a regra de aprovação desenhada pelo caso típico → os vizinhos já testados em
  `test_gmail_aprovacao`, rodados também na barreira da nuvem;
- a armadilha do future import → o teste por tool.

### Fase 3 — o motor (C3)
**Faz:**
- As rotas viram `def`.
- `POST /chat`: `_quem` primeiro; o corpo com teto; o `json` validado (erro 400 em português,
  sem ecoar conteúdo); `ORIGEM=nuvem`, `TURNO=sessao:numero`.
- `GET /fumaca/segredos`: a chave lê e o token da agenda renova. Só `true`/`false`, e nenhuma
  chamada paga.
- `GET /fumaca/registro`: cada consulta do registro com parâmetros vazios. Só leitura.
- `config`: `VIKING_GEMINI_CHAVE_ARQUIVO` e `VIKING_AGENDA_TOKEN_ARQUIVO` (lidos uma vez); o
  `GEMINI_API_KEY` do `.env` continua valendo no Mac.
- `google_auth.servico` na nuvem usa `credenciais_da_nuvem`: renova em memória, nunca grava, nunca
  abre login.
- O `Dockerfile` não muda; o `test_dockerfile` confere.
- **Testes:**
  - `/chat` sem token → 401; outra conta → 403;
  - o corpo acima do teto → 413;
  - a régua AST cobre a rota nova;
  - o log (`caplog`) sem a mensagem nem o histórico;
  - o modo nuvem nunca chama `InstalledAppFlow` nem `_gravar_token`;
  - a chave nunca aparece em `repr`, erro ou log.

**✅ Checkpoint:** `pytest tests/test_motor.py tests/test_google_auth*.py -q` verde; `docker build`
ok; o tamanho da imagem medido.

**🐞 → Depurar:** classe 6, uma rota nova esquecendo `_quem` → a régua AST; o contextvar não
chegar à thread da rota → definir dentro da rota (teste que lê `registro.ORIGEM` numa tool falsa).

### Fase 4 — o Mac como cliente do chat (C4)
**Faz:**
- `nuvem/cliente.py` ganha `turno_de_chat(historico, mensagem, nota)`, com `POST` e o prazo do
  motor mais 20 s, e reaproveita `_sessao` (uma por conversa).
- `viking chat --nuvem`: o REPL guarda o histórico e a nota; `sair`; `/custos` mostra o gasto do
  dia e do mês que o motor devolve.
- Os erros em português: sem login do gcloud, teto atingido, o motor fora do ar, o prazo esgotado
  ("o motor pode ter agido: veja `acoes_recentes`").
- `viking lembretes --nuvem` marca que o aviso por e-mail ainda não existe na nuvem.
- **Testes:**
  - o transporte falso;
  - o histórico enviado é o devolvido pelo turno anterior;
  - o token nunca é impresso;
  - o prazo esgotado dá mensagem, não traceback;
  - o `--nuvem` é exclusivo com as outras opções do `chat`, se houver.

**✅ Checkpoint:** `pytest tests/test_nuvem_cliente.py tests/test_cli*.py -q` verde.

### Fase 5 — infraestrutura dos segredos (C5)
**Faz:**
- `APIS` ganha `secretmanager.googleapis.com`.
- **Passo `segredos`:** cria `viking-gemini` e `viking-agenda` (replicação automática), e dá
  `secretAccessor` ao `viking-motor@` **em cada segredo**, não no projeto.
- **Passo `ttl`:** `firestore fields ttls update expira_em --collection-group=acoes --enable-ttl`.
- **Subcomando `segredo NOME`:** sobe uma versão com o valor pela entrada padrão do `gcloud`. O
  valor vem do `.env` (`GEMINI_API_KEY`) ou do arquivo (`secrets/google_token.json`), e nunca é
  impresso. A medida mostra só o número de versões e a data.
- **Deploy:**
  - `--timeout` da medição do C0;
  - `--update-secrets` com os volumes;
  - `VIKING_*_ARQUIVO` e `VIKING_STORE=firestore` nas variáveis;
  - `--set-env-vars` continua trocando todas as variáveis juntas.
- **Testes:** todo comando com `--project`; o valor do segredo nunca no argv nem na saída; o deploy
  nunca usa um segredo como variável de ambiente.
- **Ok do dono, um por vez, com o custo medido:**
  - a API (grátis);
  - os segredos (2 versões, dentro das 6 grátis);
  - subir a chave e o token;
  - a TTL (apaga o registro de ações com mais de 30 dias: a regra dele de 30 dias).

**✅ Checkpoint:** `python scripts/nuvem.py` → 10 ✅; `gcloud secrets versions list` → 1 versão
habilitada em cada.

**🐞 → Depurar:**
- `PERMISSION_DENIED` ao ler o segredo no ar → o papel **no segredo** (`get-iam-policy`), não no
  projeto;
- o volume recusado por caminho → um diretório por segredo.

### Fase 6 — deploy e provas (C6)
**Faz:** **ok** → `python scripts/nuvem.py deploy --executar`.

**Provas:**
- as 9 de hoje;
- `/fumaca/segredos` (a chave lê, o token renova);
- `/fumaca/registro` (sem `FAILED_PRECONDITION`);
- o `describe` sem valor de segredo, só as referências;
- o log sem conteúdo.

Depois, **com o ok**, um turno real no ar ("o que tenho amanhã?"), com o tempo e o custo anotados
no `PROGRESSO`.

**✅ Checkpoint:** as provas literais, com horário, no `PROGRESSO.md`.

**🐞 → Depurar:**
- o token da agenda recusado (`invalid_grant`) → subir o do Mac (roteiro), sem reabrir o desenho;
- a partida fria somada ao turno passar do prazo → medir a partida separada (a `/versao` antes).

### Fase 7 — fechamento (C7)
- **Portões lidos, com a linha citada:** `pytest`, `ruff check .`, `ruff format --check .` (o
  formatador só nos arquivos editados), `mypy` (os módulos novos entram na lista) e o gitleaks.
- **Duas passadas de revisão** (`referencia/revisao.md`), mais `/security-review` e `/code-review`
  se estiverem disponíveis.
- **Docs:**
  - `AGENTS.md`: a estrutura (`turno.py`, `registro_firestore.py`, os segredos), o comando `viking
    chat --nuvem`, as variáveis e as armadilhas novas;
  - `docs/fontes/gcp-cloud-run-firestore.md`: o Secret Manager, o prazo, a TTL e o turno medido;
  - o resto: decisões, diário (com "Erros desta sessão"), barra, `sessoes.md` e `PROGRESSO.md`.
- **Mutações** em background, sem `timeout`, com a saída num arquivo.
- **Fechar:** commits com o porquê; push; CI pelo SHA inteiro.

### Verificação ponta a ponta (C8, roteiro para o Mac)
1. `cd ~/LifeOs && git pull && git log --oneline -1`
2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
3. `viking chat --nuvem`:
   - "o que tenho amanhã?" → os eventos no fuso dele;
   - "cria um lembrete de teste para amanhã às 9h" → a resposta com a marca de "sem e-mail
     ainda";
   - `confirma 1234` → "na nuvem ainda não há o que aprovar";
   - `/custos` → o gasto do dia e do mês;
   - `sair`.
4. `viking lembretes --nuvem` → o lembrete com a marca.
5. `viking chat` (o local) → uma pergunta à agenda, igual a antes.

### Riscos e o que é irreversível
- **Custo:**
  - o C0 (~5 turnos) e o turno real do C6, com ok;
  - o teto do app corta a US$ 1 por dia;
  - o Secret Manager fica dentro da cota grátis (2 versões ativas; acessos só na partida das
    instâncias).
- **A TTL apaga** o registro de ações com mais de 30 dias: é a regra que o dono já decidiu.
- **O token da agenda na nuvem** age na conta real (criar, apagar e reagendar eventos). Passa pelo
  registro de ações e pelo `desfaz`, como no Mac, e o motor só aceita o `viking-cli@`.
- **Segredo no ar:** um volume, lido por uma conta só. Nada no git, na imagem, no argv nem na
  conversa.

## Plano — Sessão 10: nuvem 1, o motor (fechada no Mac em 2026-09-30)

### Context
É a primeira sessão da nuvem (D47): o Viking ganha um lugar que fica ligado sem o Mac. O dono
dividiu a 10 original em duas (2026-09-29):
- **10 (esta):** o chão da nuvem, com o repo privado, o projeto, o Firestore, o motor fechado por
  login, o deploy por script e um caminho de ponta a ponta, do Mac à nuvem, pelos lembretes;
- **10b:** o chat na nuvem.

Critério do dono, herdado da 9: "precisão, otimização e software resiliente". Com o plano aprovado,
o C0 copia este texto para o topo do `PROGRESSO.md`, e a execução segue até o fim sem pedir
confirmação a cada fase. Os ok's por passo que custam dinheiro ou criam recurso continuam sendo
pedidos.

### O que esta sessão entrega (verificável)
1. **Repo privado com scanner próprio.** `gh repo view --json visibility` → `PRIVATE`. O gitleaks
   passa limpo no histórico inteiro, no CI e no commit do VPS. Um segredo plantado num repo de teste
   reprova o scanner.
2. **Projeto GCP só do Viking**, com faturamento e orçamento de US$ 20 (alertas em 50/90/100%),
   em `southamerica-east1`. Tudo criado por `scripts/nuvem.py`, que sem flag só lê.
3. **Firestore passando o mesmo contrato do SQLite** (`tests/test_reminders_contrato.py` com
   `IMPLEMENTACOES = {sqlite, firestore}`) contra o emulador, no VPS e no CI.
4. **Motor no Cloud Run:**
   - mínimo de 0 instâncias e `--no-allow-unauthenticated`;
   - o `describe` mostra a imagem com a tag = SHA do commit;
   - um pedido sem login responde **401/403 do Google** (não chega ao nosso código);
   - um login que não é o `cli@` é recusado pelo nosso código (403).
5. **Do Mac, `viking lembretes --nuvem`** lista os lembretes do Firestore pela nuvem, com token de
   identidade do `cli@` (audience = URL do motor).

### O que ela NÃO faz (e para onde foi)
- **O chat na nuvem** (loop do Gemini no motor; a chave do Gemini e os tokens do Google no Secret
  Manager; o código de aprovação num campo próprio, com limite de tentativas) → **10b**, a ser
  escrita no C0.
- **A prova do token do Gmail** (`viking gmail --login` no Mac depois de 2026-10-03, sem abrir o
  navegador) → primeiro passo da 10b, porque hoje é 2026-09-29.
- **Scheduler e o lembrete com o Mac desligado; migrar os dados do Mac para o Firestore** → S11
  (já está lá).
- **Secret Manager:** nenhum segredo nesta sessão. O motor da 10 só lê e grava no Firestore pela
  identidade do serviço.

### Respostas do dono (2026-09-29)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| O `gcloud` do VPS está logado com a conta dele (desde 2026-09-07; o padrão das bibliotecas junto, vivo, apontando para outro projeto) | "mantém esse login e usa ele mesmo… tem gcloud configurado por querer… só cria um projeto novo apenas pro viking" | O deploy e a infraestrutura usam o login do VPS. Sai o ritual do token de 1 h (D47 revista no C0). Todo comando do `gcloud` leva `--project` do Viking explícito, preso por teste, para nunca tocar o outro projeto pela configuração padrão |
| Dividir a 10 | 10 e 10b | "Não faz" acima |
| Região e orçamento | São Paulo ("volto pro Brasil em 1 mês, minha casa é lá") | `southamerica-east1` para o Cloud Run, o Firestore e o Artifact Registry. **O local do Firestore não se muda depois de criado.** Orçamento de US$ 20 com alertas em 50/90/100% |
| Repo privado | eu troco, com o ok dele | C2: depois do gitleaks limpo no histórico e ligado no CI e no commit, peço o ok e rodo `gh repo edit --visibility private --accept-visibility-change-consequences` |
| (dito junto) Volta ao Brasil em ~1 mês | — | Memória do fuso atualizada no C0. O `VIKING_TIMEZONE` da nuvem vem da configuração de deploy, não do código: trocar é uma variável |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Scanner: gitleaks** v8.30.1 (2026-03-21), binário com sha256 conferido, no CI e num hook `pre-commit` do VPS (`scripts/instalar_hooks.sh`) | detect-secrets sem versão desde 2024-05-06 (medido); o gitleaks não entra no `uv.lock` | um falso positivo que o allowlist estreito não resolva |
| **Configuração do Viking fora do repo:** `VIKING_NUVEM_PROJETO`, `VIKING_NUVEM_REGIAO`, `VIKING_NUVEM_URL` no `.env` (VPS e Mac) | nem ID nem URL no repo, público ou privado | — |
| **Build da imagem no VPS com docker** e push ao Artifact Registry (sem Cloud Build). Tag = SHA; `python:3.12-slim` fixado por digest; usuário não-root; `uv sync --locked --extra nuvem --no-dev`; política de limpeza que guarda as 5 últimas | docker existe no VPS (medido); uma conta de serviço a menos; 0,5 GB grátis no registry | o build local não servir (arquitetura, tamanho) |
| **Motor = Starlette + uvicorn**, que já estão no lock (vêm do `mcp`), declarados explicitamente no extra `nuvem`. Rotas: `GET /versao` (SHA) e `GET /lembretes` (abertos); sem conteúdo na URL; `--no-access-log` | nenhuma lib nova sem gatilho; o log do Cloud Run guarda a URL e não guarda o corpo (medido) | a 10b precisar de streaming |
| **Duas paredes no motor:** o IAM do Cloud Run (`run.invoker` só para o `cli@`) e, no código, o e-mail do token numa lista (`cli@`; `maos@` na S11) como **primeira instrução** da rota | a skill manda verificar pela identidade, não pela audience; se o IAM for afrouxado, o código ainda recusa | — |
| **Contas de serviço:** `motor@` (identidade do serviço: `datastore.user`, nada mais) e `cli@` (só `run.invoker` no motor). O dono ganha `serviceAccountTokenCreator` **só no `cli@`** | o Mac pede um token com audience fazendo-se passar pelo `cli@`; o token de usuário do gcloud não tem audience | — |
| **Cliente no Mac: `google-auth`** (já no lock) com as credenciais do `gcloud auth application-default login` do dono, via `impersonated_credentials.IDTokenCredentials(cli@, audience=URL, include_email=True)` | nada novo na venv do Mac; nenhuma chave em disco | o Mac não tiver `gcloud` (o roteiro confere) |
| **Firestore:** coleção `lembretes`, id = o UUID; instantes como `Timestamp` nativo; **todo campo sempre gravado, `None` explícito** (a igualdade `== None` não casa campo ausente); `add` por `create()` + `AlreadyExists` → devolve o existente; `complete`, `reservar_envio`, `marcar_envio` e `soltar_envio` em **transação**; a ordem do `list_open` feita em Python (um usuário) | o contrato define o comportamento; o Firestore não tem `UPDATE … WHERE` | a cota diária estourar, ou uma consulta pedir índice caro |
| **Índices compostos declarados no `scripts/nuvem.py`** (vencidos/atrasados), e a fumaça no ar exerce `vencidos` | o emulador não exige índice e a produção exige: verde aqui, `FAILED_PRECONDITION` lá | — |
| **`google-cloud-firestore` num extra `nuvem` com marcador Linux**; import preguiçoso (`VIKING_STORE=firestore`); `test_lock` aprende que o extra não vai ao Mac | D53 (2): a nuvem entra só onde roda | — |
| **Testes nunca chegam à nuvem real:** o store Firestore recusa construir um cliente sem `FIRESTORE_EMULATOR_HOST` quando roda sob pytest, e o `conftest` apaga `GOOGLE_APPLICATION_CREDENTIALS`/`GOOGLE_CLOUD_PROJECT` | o VPS tem o ADC do dono vivo: um `firestore.Client()` sem emulador gravaria na conta real (a classe 6 da 9, no banco da nuvem) | — |
| **O emulador é obrigatório no CI:** `VIKING_EXIGIR_EMULADOR=1` transforma o "pulado" do Firestore em falha; `test_ci_workflow` confere o passo | um contrato pulado é verde por outro motivo (classe 4) | — |
| **`scripts/nuvem.py`:** sem flag só lê e imprime o que falta e o que muda; `--executar PASSO` faz um passo por vez, depois do meu pedido de ok ao dono na conversa | skill `nuvem-e-deploy` §6 | — |

### Medido na abertura (2026-09-29, VPS)
| O quê | Comando / fonte | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`; `git rev-parse HEAD origin/master`; `ls .mutacao.lock` | limpo; `26ddc71` = origin; sem trava | ok |
| Suíte | `.venv/bin/python -m pytest -q` | `1884 passed in 30.41s` | base |
| CI do HEAD | `gh run list --commit <sha inteiro>` | `completed success` | ok |
| Versões | `uv lock --upgrade --dry-run` | cyclopts 5.0.0→5.1.0, google-api-core 2.39.0→2.40.0, google-auth-httplib2 0.4.2→0.4.3, google-auth-oauthlib 1.4.1→1.5.0, googleapis-common-protos 1.75.4→1.75.5, platformdirs 4.12.1→4.12.2, proto-plus 1.28.4→1.29.0 | C1, commit próprio |
| `secrets/` | `ls secrets/` | `google_credentials.json`, `google_token.json` | ok, nada do Gmail |
| Visibilidade | `gh repo view`; `gh api repos/…` | `PUBLIC`; secret scanning e push protection ligados | somem no privado: o gitleaks entra antes |
| **gcloud no VPS** | `gcloud auth list`, `config list`, `print-access-token >/dev/null` | a conta do dono, **vivo**; o ADC `authorized_user` desde 2026-09-07; o projeto padrão é outro projeto dele; SDK 583.0.0 | resposta do dono: usar este login. Nenhum doc do Viking registrava isso (classe 2, no C0) |
| Token de 1 h | `gcloud help auth print-access-token`, `gcloud help config` | `--lifetime` padrão de 3600 s, até 12 h só com política de organização; `--access-token-file`/`auth/access_token_file` | não usado (resposta do dono); fica registrado na D47 |
| Log do Cloud Run | `docs.cloud.google.com/logging/.../LogEntry` (HttpRequest) | guarda método, **URL**, tamanhos, status, user-agent, IP, referer e latência; **não guarda o corpo** nem outros cabeçalhos | nada de conteúdo na URL; logs de pedido excluíveis só pelo Cloud Logging |
| Cobrança do Cloud Run | `cloud.google.com/run/pricing` | "requests denied by IAM policy are not billed"; cota grátis aplicada como desconto a preço da faixa 1; **`southamerica-east1` é faixa 2** | um usuário fica muito abaixo da cota (não medido em uso real) |
| Firestore grátis | `docs.cloud.google.com/firestore/quotas` (atualizada em 2026-09-28) | 1 GiB, 50 mil leituras, 20 mil gravações e 20 mil exclusões por dia, 10 GiB de saída por mês; **um banco grátis por projeto**, o primeiro criado | um banco só, o `(default)` |
| Scanner | `gh api …/releases/latest`; PyPI | gitleaks v8.30.1 (2026-03-21); detect-secrets 1.5.0 (2024-05-06) | gitleaks |
| Emulador | `which java`; `gcloud components list`; `docker images` | sem Java; o emulador não está instalado; docker existe | a medir no C4 (imagem docker do emulador ou Java + componente) |
| Minutos de CI | `gh api …/runs/<id>/jobs` | 2 jobs de ~1 min por push; 86 commits em 8 dias | ~2 min por push, dentro de 2.000/mês; medir de novo com o emulador |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | memória do fuso (Brasil em ~1 mês); plano no `PROGRESSO.md`; `sessoes.md` com a 10 dividida e a seção 10b; D47 revista e D58 aberta; classe 2 (20); commit | — | ✅ |
| C1 | lock atualizado, suíte antes e depois iguais, `test_lock` verde; commit próprio | C0 | ✅ |
| C2 | gitleaks no CI e no hook, limpo no histórico, canário reprovado; **ok do dono** → repo privado, conferido pela API | C1 | ✅ |
| C3 | `scripts/nuvem.py` só-leitura mostra tudo "a criar"; **ok** → projeto, faturamento, APIs, orçamento, Firestore em SP, registry, contas de serviço e índices; o só-leitura mostra "nada a criar" | C2 | ✅ |
| C4 | store Firestore passa o contrato no emulador (VPS e CI), sem pulado; mutações novas mortas | C1 | ✅ |
| C5 | motor (Starlette) com testes de 401/403/identidade e sem conteúdo em log; Dockerfile; imagem constrói | C4 | ✅ |
| C6 | **ok** → primeiro deploy; `describe` = SHA; sem login → 403 do Google; fumaça com o `cli@` exerce `/versao` e `/lembretes` (e `vencidos` na produção) | C3, C5 | ✅ |
| C7 | `viking lembretes --nuvem` (cliente com `IDTokenCredentials`), testes offline; roteiro do Mac | C6 | ✅ |
| C8 | portões, duas passadas de revisão, docs, commits, push, CI pelo SHA | C7 | ✅ |
| C9 | teste do dono no Mac | C8 | ✅ |

### Fase 0 — documentos (C0)
- **Memória** `user-fuso-seattle`: ele volta a morar no Brasil por volta de 2026-10-29; lá é a casa
  dele. O fuso muda, e o `VIKING_TIMEZONE` do Mac e da nuvem troca nesse dia.
- **`sessoes.md`:**
  - a 10 vira "nuvem 1a" com a entrega acima;
  - nova seção **10b — o chat na nuvem**, com primeiro passo = a prova do token do Gmail depois de
    2026-10-03, mais o chat, o Secret Manager, o código pela rede e o limite de tentativas;
  - o ▶️ aponta para a 10.
- **`docs/decisoes.md`:**
  - D47 revista: o deploy usa o login do `gcloud` do VPS por decisão do dono, com `--project`
    explícito preso por teste; o token de 1 h fica recusado, com o motivo;
  - D58 = as decisões técnicas acima, mais a região.
- **`docs/erros.md`**, classe 2 (20): o plano da 10 (2026-09-28) escreveu "nenhuma credencial fixa
  no VPS" sem abrir `~/.config/gcloud`.

### Fase 1 — versões (C1)
**Faz:** `uv lock --upgrade` → `uv sync --locked --extra dev` → a suíte → commit próprio.

**✅ Checkpoint:**
- `uv lock --check` ok;
- `python -m pytest -q` → `1884 passed` antes e depois;
- `tests/test_lock.py` verde.

**🐞 → Depurar:** o google-auth-oauthlib 1.5.0 mudar o fluxo de login.
- `python -m pytest tests/test_google_auth*.py tests/test_gmail*.py -q`.
- O login ao vivo só no Mac (roteiro, passo 1).

### Fase 2 — scanner e repo privado (C2)
**Faz:**
- **`scripts/gitleaks.sh`:** baixa a v8.30.1 para `~/.cache/viking/`, confere o sha256 contra o
  `checksums.txt` do release, com o hash também fixado no script, e roda.
- **`.gitleaks.toml`:** as regras padrão; allowlist só para os falsos positivos nomeados, com o
  motivo de cada um.
- **CI:** passo `gitleaks git` com histórico inteiro (`fetch-depth: 0`); `test_ci_workflow` exige o
  passo.
- **`scripts/instalar_hooks.sh`:** grava `.git/hooks/pre-commit` com `gitleaks git --staged`.
- **Testes:** `tests/test_gitleaks.py` (marcado para rodar só com o binário presente, e o CI o
  exige):
  - repo temporário com uma chave falsa de formato real, gerada por script → exit 1;
  - o mesmo conteúdo em arquivo ignorado → exit 0.
- **Antes da troca:** `gitleaks git` no histórico inteiro → 0 achados. Um achado se examina antes
  de seguir, e segredo real vira pergunta ao dono (rotação).
- **Troca:** pedir o ok; `gh repo edit --visibility private --accept-visibility-change-consequences`;
  `gh repo view --json visibility` → `PRIVATE`; o CI do HEAD roda no privado.

**✅ Checkpoint:**
- `bash scripts/gitleaks.sh git .` → `no leaks found`;
- o canário → exit 1;
- `PRIVATE`;
- CI verde pelo SHA.

**🐞 → Depurar:** classe 4 (o canário passar porque o gitleaks não rodou) → a asserção positiva
primeiro: com a chave, exit 1 e o nome da regra na saída.

### Fase 3 — infraestrutura (C3)
**Faz:** `scripts/nuvem.py`, que lê `.env`. Cada passo é uma função que **mede** (existe?) e sabe
**criar**:
1. projeto `viking-…` (ID escolhido na hora, conferindo se está livre);
2. vínculo de faturamento (`gcloud billing accounts list`: a conta do dono);
3. APIs: `run`, `artifactregistry`, `firestore`, `iam`, `iamcredentials`, `billingbudgets`;
4. orçamento de US$ 20 com alertas em 50/90/100%;
5. Firestore `(default)` nativo em `southamerica-east1` (**irreversível**: o local);
6. Artifact Registry `viking`, com a limpeza que guarda as 5 últimas;
7. contas `motor@` e `cli@`, os papéis e o `TokenCreator` do dono no `cli@`;
8. os índices compostos.

Regras do script:
- todo `gcloud` leva `--project`;
- `tests/test_nuvem_script.py` lê o script e reprova qualquer chamada sem ele;
- a saída não imprime token.

Sem flag: a tabela passo → estado. Com `--executar N`: um passo, depois do ok do dono na conversa.

**✅ Checkpoint:** `python scripts/nuvem.py` → todos "ok" depois; `gcloud billing budgets list` →
um orçamento de 20 USD.

**🐞 → Depurar:**
- o orçamento pedir o projeto de cota (a API de budgets) → `--billing-project`;
- `PERMISSION_DENIED` sem nome → log de auditoria antes de repetir (skill §11).

### Fase 4 — Firestore pelo contrato (C4)
**Faz:**
- **`src/lifeos/reminders/store_firestore.py`**, com as funções da interface e um `_cliente()`
  que:
  - recusa construir sob pytest sem emulador;
  - lê `VIKING_NUVEM_PROJETO`.
- **`service.py`** escolhe a implementação por `config.STORE` (`sqlite` | `firestore`); o mypy
  confere `store_firestore` contra `interface.Lembretes`.
- **O emulador:** medir primeiro o caminho (a imagem docker do SDK com `emulators`, ou Java + o
  componente) no VPS e no CI; `conftest` sobe e limpa entre testes (`DELETE` no endpoint do
  emulador).
- **`IMPLEMENTACOES`** ganha `firestore`.
- **Testes novos:**
  - concorrência da reserva com 4 threads e clientes separados → 1 ganha;
  - documento sem um campo nunca é gravado.
- **Mutações:**
  - reserva sem transação;
  - `add` sobrescreve;
  - `None` não gravado.

**✅ Checkpoint:**
- `pytest tests/test_reminders_contrato.py -q` → o dobro dos casos de hoje, 0 pulados, com
  `VIKING_EXIGIR_EMULADOR=1`;
- a suíte inteira passa;
- as mutações novas morrem.

**🐞 → Depurar:**
- classe 5: o emulador aceitar uma consulta que a produção recusa (índice) → a fumaça do C6;
- o `Timestamp` voltar com microssegundo truncado (o Firestore guarda microssegundos; comparar com
  o do SQLite no contrato).

### Fase 5 — o motor (C5)
**Faz:**
- **`src/lifeos/nuvem/motor.py`** (Starlette):
  - `_quem(request)` é a primeira instrução de toda rota: lê o e-mail do token que o Cloud Run já
    validou (o formato do cabeçalho se mede no C6) e recusa fora da lista `QUEM_PODE`;
  - `GET /versao` → `{"commit": VIKING_COMMIT}`;
  - `GET /lembretes` → os abertos, instantes em UTC; o fuso fica no cliente, a borda.
- **`Dockerfile`** e `.dockerignore`: só `src/`, `pyproject.toml` e `uv.lock`; `RUN test -f` do
  pacote; sem `.env` nem `secrets/`; `VIKING_COMMIT` como `ARG`.
- **Testes** (`tests/test_motor.py`, com `TestClient`):
  - sem cabeçalho → 401;
  - outro e-mail → 403;
  - `cli@` → 200;
  - rota nova sem `_quem` na primeira linha → reprova (régua AST);
  - log sem título de lembrete (`caplog`);
  - `test_dockerfile` confere o que é copiado.

**✅ Checkpoint:** `pytest tests/test_motor.py -q` verde; `docker build` ok, imagem < 300 MB.

**🐞 → Depurar:** a classe 6 (proteger `/lembretes` e esquecer uma rota nova) → a régua AST, e não
disciplina.

### Fase 6 — deploy (C6)
**Faz:** `scripts/nuvem.py deploy`:
- só lê: a tag no ar (`gcloud run services describe`), os commits desde ela em `src/`,
  `pyproject.toml`, `uv.lock` e `Dockerfile`, e o CI do HEAD pelo SHA;
- com `--executar deploy`, depois do ok do dono:
  1. `docker build --build-arg VIKING_COMMIT=<sha>`;
  2. push `…/viking/motor:<sha>`;
  3. `gcloud run deploy motor --image … --service-account motor@ --no-allow-unauthenticated
     --min-instances 0 --max-instances 2 --set-env-vars VIKING_STORE=firestore,VIKING_TIMEZONE=…,
     VIKING_NUVEM_PROJETO=…`.

**Provas** (rodam sempre):
- `describe` → a imagem com o SHA do HEAD;
- `curl` sem token → 403, e o corpo é do Google, não nosso;
- com o token do dono (não está na lista) → 403 **nosso**;
- com o do `cli@` → `/versao` = SHA, e `/lembretes` 200;
- `vencidos` exercido por uma rota de fumaça **só leitura** (ou pelo cliente do C7) → sem
  `FAILED_PRECONDITION`;
- logs da revisão sem erro e sem conteúdo.

**✅ Checkpoint:** as cinco provas literais no `PROGRESSO.md`, com horário.

**🐞 → Depurar:**
- o cabeçalho com a assinatura removida → decodificar o payload sem verificar (o Cloud Run já
  verificou) e escrever isso no código;
- `PERMISSION_DENIED` no Firestore → o papel do `motor@`.

### Fase 7 — o Mac como cliente (C7)
**Faz:**
- **`src/lifeos/nuvem/cliente.py`:**
  - `IDTokenCredentials` do `cli@` com audience = `VIKING_NUVEM_URL`;
  - `requests`/`AuthorizedSession` com prazo;
  - erros com texto em português: sem login do gcloud, sem permissão, a nuvem fora do ar.
- **`viking lembretes --nuvem`**: a mesma saída do local, no fuso do dono.
- **Testes** com o transporte falso:
  - o token vai no cabeçalho e nunca é impresso;
  - erro de rede → exit 1 com mensagem;
  - resposta sem fuso → recusada.

**✅ Checkpoint:** suíte verde; o comando rodado do VPS **com o login dele**, só leitura e só com
o ok dele (o VPS age como o dono), lista os lembretes da nuvem (0 ou os de fumaça).

### Fase 8 — fechamento (C8)
- **Portões lidos, citando a linha:** `pytest`, `ruff check .`, `ruff format --check .` (o
  formatador só nos arquivos editados), `mypy` e o gitleaks.
- **Duas passadas de revisão** (`referencia/revisao.md`); `/security-review` se estiver
  disponível.
- **Docs:**
  - `AGENTS.md`: `nuvem/`, os comandos, o extra `nuvem`, e a armadilha "o emulador não exige
    índice";
  - `docs/fontes/`: uma página nova `gcp-cloud-run-firestore.md` com as medições datadas;
  - o resto: decisões, diário, barra, `sessoes.md` e `PROGRESSO.md`.
- **Mutações** em background, sem timeout, com a saída num arquivo.
- **Fechar:** commits com o porquê; push; CI pelo SHA inteiro.

### Verificação ponta a ponta (C9, roteiro para o Mac)
1. `cd ~/LifeOs && git pull && git log --oneline -1`
2. `uv sync --locked --extra dev && source .venv/bin/activate && which python && python -m pytest -q`
3. `viking gmail --login` (o oauthlib novo ainda entra; não é a prova de 7 dias)
4. `which gcloud`; sem ele, instalar (o comando vai no roteiro)
5. `gcloud auth application-default login` (uma vez)
6. acrescentar ao `.env` do Mac `VIKING_NUVEM_URL=` e `VIKING_NUVEM_PROJETO=` (o valor vai no
   roteiro, não no repo)
7. `viking lembretes --nuvem` → a lista da nuvem, no fuso dele
8. `curl` sem token na URL do motor → 403

### Riscos e o que é irreversível
- **O local do Firestore** (São Paulo) não muda: peço o ok nesse passo nomeando isso.
- **Custo:** o orçamento só avisa; nada nesta sessão escala com uso além de pedidos do dono.
  `max-instances 2`, sem instância mínima e sem load balancer.
- **O login do dono no VPS alcança todos os projetos dele:** o `--project` explícito é a única
  parede entre o script e o outro projeto (teste).
- **Repo privado:** reversível, mas o secret scanning do GitHub some; o gitleaks passa a ser a
  única rede.
- **O ADC do dono no VPS:** os testes ficam bloqueados de chegar à nuvem real (o `conftest` e o
  `_cliente()`).

## Plano — Sessão 9: fundação de dados (fechada no Mac em 2026-09-29)

### O que esta sessão entrega (verificável)
(a) Um `viking.db` no formato de hoje (`5d0ace4`), com dados, migra para o formato novo sem
perder nenhuma linha. Rodar de novo não muda nada. Uma falha no meio deixa o banco como estava. O
Viking recusa, em voz alta, um banco migrado por uma versão mais nova que a dele.
(b) Os três módulos que usam o `viking.db` abrem o banco por **um lugar só** (`lifeos/banco.py`),
com migrations numeradas e um ledger. Nenhum teste toca o banco real. Hoje a suíte grava um
"Pagar conta" no `data/viking.db` a cada rodada (medido abaixo).
(c) Os lembretes passam a ter uma interface de store com UUID e UTC, e um teste de contrato que a
S10 reusa para o Firestore.
(d) `viking lembretes --enviar` manda por e-mail, para a própria conta, um e-mail por lembrete
vencido nas últimas 24 h. Rodado duas vezes, ou em dois processos ao mesmo tempo, manda **uma**.
(e) A checagem de tipos (`mypy`) vira portão do CI nos módulos de dados.
(f) "O que mora onde" fica escrito numa decisão.

### O que ela NÃO faz (e para onde foi)
- **Tabelas de memória com cara de registro** → Sessão 13, por decisão do dono em 2026-09-29.
  Com as migrations prontas, é uma migração nova lá. Escrito na S13 no C0.
- **Os outros 65 erros do `mypy`** → backlog, como estava; o número foi atualizado no C0.
- **Interface de store para o registro e as confirmações** → S10. Os dois ficam onde a ação roda
  (D57, abaixo), e a S10 decide o banco deles na nuvem. Aqui ganham o banco único e as migrations.
- **Disparo automático** (sem o dono rodar o comando) → S11, como já estava.
- **Índice único `(source, external_id)`** (auditoria §12.6) → sem produtor hoje; entra com o
  primeiro produtor (gatilho escrito na D56).

### Respostas do dono (2026-09-29)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| Checagem de tipos antes da refatoração? | só no que a 9 toca | C2: conserta os 3 erros, `mypy` fixado no CI só para os módulos de dados |
| Tabelas de memória já na 9? | deixar para a 13 | fora; escrito na S13 (C0) |
| Formato do envio | um e-mail por lembrete, assunto = título | C5 |
| Vencidos há muito tempo | só os das últimas 24 h; os mais velhos listados, não enviados | C5: a janela é 24 h, sem fuso |
| O lixo de teste no banco do Mac | apagar no roteiro do Mac, com backup e com o critério exato | C6: script com `--aplicar`; sem a flag só conta |
| O que o chat mostra do lembrete | nenhum número, só título e prazo | C4: o UUID fica entre o Viking e o Gemini |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Uma lista de migrations para o arquivo inteiro**, em `lifeos/banco.py`, com um ledger `migracoes(numero, nome, checksum, aplicada_em)`. Os três módulos só consomem. O `user_version` não é mais lido nem escrito (o 1 dos bancos de hoje fica lá, inerte) | o `user_version` é um por arquivo: três réguas não cabem nele. Uma lista só dá uma ordem total, sem conflito de número entre módulos. O ledger guarda o checksum, que o `user_version` não guarda | um segundo arquivo de banco (aí, um ledger por arquivo) |
| **Adoção dos bancos de hoje, sem caso especial:** as migrations 1–4 recriam o formato de `5d0ace4` com `CREATE … IF NOT EXISTS` e a normalização do `due_at` (idempotente por construção). Num banco antigo, elas não mudam nada e entram no ledger | um caminho só para banco novo e antigo, testado contra os dois | — |
| **Toda migração pendente roda numa transação só** (`BEGIN IMMEDIATE`, conexão em autocommit para o Python não abrir nem fechar transação sozinho); o ledger é relido **dentro** dela. Um erro dá `ROLLBACK` e sobe | DDL no SQLite é transacional; o Python 3.12 não abre transação antes de DDL por conta própria (é o que faria a falha deixar metade). Dois processos abrindo ao mesmo tempo: o segundo espera e acha o ledger pronto | — |
| **Checksum** (sha256 do SQL ou do código-fonte da função) gravado no ledger e conferido a cada abertura; divergência = erro que diz o número. Um teste prende os checksums das migrations já publicadas, escritos à mão | a regra "migração aplicada não se edita" com dentes: o teste falha no CI antes de chegar ao Mac | o checksum de função disparar por formatação sem mudança de código (aí, só SQL) |
| **Banco mais novo que o código** (ledger com número desconhecido) → recusa abrir, com a mensagem "atualize com `git pull`" | um código velho escrevendo num formato novo é dado ruim em silêncio | — |
| **Backup automático** antes de aplicar migração pendente num banco que já tem tabelas: `Connection.backup` para `viking.db.antes-da-migracao-N` (N = a primeira pendente), sem sobrescrever | o dado do Mac é irreversível; a API de backup copia consistente, mesmo com outro processo aberto | — |
| **Lembretes com `id` UUID (texto)**, por reconstrução da tabela (o jeito do SQLite para trocar a chave). O inteiro antigo não fica | o Firestore não tem contador; UUID gerado no cliente deixa o "criar" ser repetido sem duplicar. O `#12` não aparece mais (dono) | — |
| **Store em UTC e sem conversão:** recebe e devolve `datetime` com fuso; o `naive` é recusado no store e interpretado no fuso do dono só no serviço, na borda. Grava `isoformat(timespec="microseconds")` em UTC, largura fixa | comparar texto só funciona com um formato; a conversão no store escondia o fuso de quem lê | — |
| **Interface = um `Protocol`** (`reminders/interface.py`) que o módulo `store` satisfaz, com um teste de contrato parametrizado (hoje só SQLite; a S10 põe o Firestore). Nada de SQL fora de `banco.py` e dos módulos de store; `sqlite3.connect` só em `banco.py` (teste que lê o código) | a skill `dados-e-banco` §8: duas implementações só se mantêm iguais com contrato | a S10 escolher Cloud SQL (a interface pode encolher para SQL) |
| **Envio como reserva com prazo:** `envio_reservado_por` (id da execução), `envio_reservado_ate` (5 min), `enviado_em`, `envio_estado` (`enviado`/`incerto`). Reserva é um `UPDATE … WHERE` que só uma execução ganha (`rowcount == 1`) | o Scheduler da S10 entrega "at least once"; dois `--enviar` ao mesmo tempo mandariam dois | — |
| **Incerto não reenvia:** uma falha `incerta` do Google marca `envio_estado = 'incerto'` e diz "não sei se enviei; confira na caixa". Falha definitiva, limite de 20 ou texto recusado soltam a reserva | e-mail duplicado a cada rodada seria pior que um aviso; o registro já tem a linha `incerta` | o dono preferir receber duplicado a perder |
| **Saída do `--enviar`:** 0 = tudo que venceu saiu (ou nada venceu); 2 = parcial (limite, incerto, recusado); 1 = não rodou. Nunca imprime endereço | `falha-ruidosa` §3: o Scheduler da S11 precisa distinguir | — |
| **Sem WAL, com `timeout` explícito de 5 s** | 0,25 ms por abertura medido; nenhum "database is locked" visto; WAL poria `-wal`/`-shm` ao lado do arquivo e o `cp` do backup perderia dado | um "database is locked" visto |
| **`mypy` no grupo `dev` do lock** (wheel `py3-none-any` para Mac Intel, `cp312`/`cp313` no Linux), rodado pelo CI só em `banco.py`, `reminders/`, `registro.py` e `confirmacao.py` | a D45 (versão travada e auditada pelo `pip-audit`); `uvx` ficaria fora do lock | o `tests/test_lock.py` recusar a árvore |

### Medido na abertura (2026-09-29, VPS)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `git rev-parse HEAD origin/master`, `ls .mutacao.lock` | limpo; `5d0ace4` = origin; sem trava | ok |
| Suíte | `.venv/bin/python -m pytest -q` | `1804 passed in 19.86s` | base |
| CI do HEAD | `gh run list --commit <sha inteiro>` | `completed success` | ok |
| Versões | `uv lock --upgrade --dry-run` | "No lockfile changes detected" | nada a atualizar |
| Quem abre o banco | `grep -rln sqlite3 src/` | `reminders/store.py` (`reminders`, migração por `user_version`), `registro.py` (`acoes`), `confirmacao.py` (`confirmacoes`); os dois últimos com `CREATE … IF NOT EXISTS`, sem versão | decisão da lista única |
| **A suíte escreve no banco real** | `data/viking.db` somente leitura | 132 lembretes, **todos** "Pagar conta", concluídos ≤ 0,014 s depois de criados, o 1º em 2026-09-27 06:36 UTC. É `tests/test_registro_ganchos.py::test_lembrete_criar_e_concluir_registram` (desde `1b05733`, Sessão 5); o `conftest` isola `confirmacao` e `registro`, e não o store | C1; erro classe 6; no Mac, um por `pytest` rodado |
| Banco do VPS | o mesmo | `user_version` 1; tabelas `reminders` e `acoes` (2 linhas minhas, `navegador.executar` de 2026-09-28); sem `confirmacoes` | a migração cobre "tabela que ainda não existe" |
| Custo de abrir | `list_open` e `registro.recentes` 200× numa cópia | 0,25 ms e 0,23 ms por chamada | abrir por chamada fica; nada de cache |
| SQLite | `sqlite3.sqlite_version` | 3.45.1 no VPS; o do Mac não medido | nada de `STRICT`/`RETURNING` sem medir |
| Tipos | `uvx mypy==2.3.1 --python-executable .venv/bin/python src` | `Found 68 errors in 15 files` (eram 67; o novo é da 8b: `list[Evento]` sem `completa`); nos 3 módulos de dados: 3 | C2 |
| `mypy` no lock | PyPI, 2.3.1 | wheels `cp312`/`cp313` manylinux e `py3-none-any` | serve ao Mac Intel |
| `executescript` numa transação (C3) | script no VPS, Python 3.12 | **comita sozinho** a transação aberta: o `INSERT` anterior e a tabela nova ficaram, mesmo com o erro | migrations só com um `execute` por comando |
| Backup com a transação aberta (C3) | `conn.backup` pela mesma conexão, com `BEGIN IMMEDIATE` | **trava para sempre** (`timeout 15` → 124); por **outra** conexão, funciona e copia só o comitado | backup por outra conexão, com a trava segurada |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | plano aqui; memória na S13; backlog do `mypy` com o número de hoje | — | ✅ |
| C1 | teste vermelho "a suíte não toca o banco real" → `banco.py` com o caminho único + `conftest` → verde; erro classe 6; commit | C0 | ✅ (3 vermelhos → `1807 passed`; `sha256sum data/viking.db` igual antes e depois da suíte; cada camada tirada sozinha derruba o teste dela) |
| C2 | `mypy` no lock e no CI para os módulos de dados; os 3 erros consertados; `test_lock` e `test_ci_workflow` verdes; commit | C1 | ✅ (lista única em `[tool.mypy] files`; `Success: no issues found in 7 source files`; a régua deriva do código quem importa `banco`; `1829 passed`) |
| C3 | migrations 1–4 + ledger + transação + checksum + recusa do mais novo + backup; os três módulos por `banco`; testes contra o banco antigo com dados; commit | C2 | ✅ (18 testes; o fixture bate com o banco que o código de `5d0ace4` cria; a cópia do banco do VPS migrou com 133 lembretes e 2 ações iguais; os mutantes sem `BEGIN IMMEDIATE` e com `executescript` derrubam os testes de falha no meio; `viking` abre o banco antes de tudo; `1845 passed`) |
| C4 | migração 5 (UUID e colunas de envio) + interface + contrato; chat e MCP sem `#id`; commit | C3 | ✅ (contrato: 11 vermelhos → 13 verdes, um deles defeito de hoje: concluir de novo mudava a hora; a cópia real do VPS migra com 133 lembretes iguais pelo conteúdo e UUIDs únicos; o `mypy` pega o store fora do `Protocol`; testes de fuso com o dono em Seattle; `1862 passed`) |
| C5 | `viking lembretes [--enviar]` com reserva, janela de 24 h e limite; testes de sequência e de dois processos; commit | C4 | ✅ (15 testes, com 4 processos de verdade; o mutante da reserva sem prazo derruba 4; `1877 passed`. **Incidente:** rodei o `--enviar` no VPS achando que não havia credencial; o dono aprovou o login que abriu, e um e-mail de teste saiu para a caixa dele; o token do Gmail foi apagado do VPS por decisão dele; erros classe 2 e `CLAUDE.md`) |
| C6 | script de limpeza; mutações; portões; duas passadas de revisão; D56/D57, docs; push; CI pelo SHA | C5 | ✅ (215 de 215 mutações mortas; na 1ª rodada, as 2 de concorrência sobreviveram: o teste de processos dependia de sorte, e dois testes determinísticos com um gancho no `BEGIN` as mataram; a revisão achou o login caindo no meio escondendo o que já saiu; `1884 passed`) |
| C7 | roteiro do Mac: backup, migração, limpeza, envio duas vezes | C6 | ✅ (dono, 2026-09-29: `1884 passed` no Mac com o `shasum` do banco igual antes e depois; migrou com o backup `antes-da-migracao-1`; a limpeza achou e apagou 8 de 12; o lembrete saiu uma vez, a 2ª rodada deu 0 e saída 0; o e-mail chegou; o registro manteve as ações de antes da migração) |

### Fase 0 — adiados (C0)
**Faz:** a S13 ganha "tabelas de memória com cara de registro (vinda da 9, dono 2026-09-29)" no
topo das escolhas dela; na S9, a linha diz que foi para a 13. O backlog do `mypy` ganha o número
de hoje (68; 3 nos módulos de dados, portão desde a 9).
**✅ Checkpoint:** `grep -n "vinda da 9" sessoes.md` → uma linha na seção da 13.

### Fase 1 — a suíte fora do banco real (C1)
**Faz:**
- teste antes em `tests/test_banco.py`: `config.REMINDERS_DB_PATH` e `banco.CAMINHO` não estão
  dentro de `REPO_ROOT/data` durante a suíte; `criar_lembrete` sem fixture nenhuma não muda o
  arquivo real (hash antes e depois). Esperado: **vermelho**;
- `src/lifeos/banco.py`: `CAMINHO` e `conectar()` (o `sqlite3.connect` único, `row_factory`,
  `timeout=5`); `reminders/store.py`, `registro.py` e `confirmacao.py` passam a abrir por ele (os
  `DB_PATH` de módulo somem);
- `tests/conftest.py`: no topo do módulo, antes de qualquer `import lifeos`,
  `VIKING_DB_PATH` aponta para um diretório temporário da sessão (defesa em profundidade); e um
  `autouse` troca `banco.CAMINHO` por `tmp_path` a cada teste (isolamento entre testes). As
  fixtures `temp_db` dos testes passam a trocar esse nome;
- a régua: `sqlite3.connect` só em `banco.py` (teste que lê o código, com piso: acha a chamada lá).

**✅ Checkpoint:** o teste novo vermelho antes e verde depois; `sha256sum data/viking.db` igual
antes e depois de `python -m pytest -q`; a suíte inteira passa.

**🐞 Previsto → Depurar:** classe 6 (um módulo ainda com o caminho próprio; foi exatamente o
defeito) → `grep -rn "DB_PATH\|sqlite3.connect" src/ tests/`. Classe 4 (o teste do hash passar
porque o `pytest` roda do VPS, onde o arquivo é meu) → o teste afirma sobre o caminho, não só
sobre o hash.

### Fase 2 — tipos nos módulos de dados (C2)
**Faz:** `mypy==2.3.1` no `dev` do `pyproject`; `uv lock`; os 3 erros (`Row | None`,
`Reminder | None`, `int | None`) consertados de verdade (um `None` possível vira erro explícito,
não `cast`); o passo do CI
`uv run --locked python -m mypy src/lifeos/banco.py src/lifeos/reminders src/lifeos/registro.py src/lifeos/confirmacao.py`;
`tests/test_ci_workflow.py` exige o passo; `AGENTS.md` ganha o comando.
**✅ Checkpoint:** o comando do `mypy` → `Success: no issues found`; `python -m pytest
tests/test_lock.py tests/test_ci_workflow.py -q` verde; `uv lock --check` ok.

**🐞 Previsto → Depurar:** o `test_lock` recusar uma dependência do `mypy` sem wheel para Mac
Intel → `uv tree --package mypy` e a lista de arquivos no PyPI; se recusar, pergunto.

### Fase 3 — migrations (C3)
**Faz:**
- `banco.py`: `Migracao(numero, nome, passo)` (passo = SQL ou função), `MIGRACOES`, `migrar(conn)`
  (ledger criado na mesma transação; `BEGIN IMMEDIATE`; relê; confere checksums; recusa número
  desconhecido; backup se há pendente e o banco tem tabelas; aplica em ordem; `COMMIT`; `ROLLBACK`
  em qualquer erro); `conectar()` chama `migrar` antes de devolver a conexão;
- migrations 1–4: `reminders` + índice (o DDL de `5d0ace4`); `due_at` em UTC (a função de hoje);
  `acoes` + índice; `confirmacoes`. Os `_SCHEMA` e `_migrar` saem dos módulos;
- `tests/test_banco_migracoes.py`, com a fixture `banco_de_5d0ace4`: o DDL literal dos três
  módulos em `5d0ace4`, `user_version` 1, lembretes com `due_at` naive/offset/nulo, ações,
  confirmações:
  - migra, e toda linha de antes está lá, igual (comparação por conteúdo, não por contagem só);
  - migrar duas vezes → o `iterdump()` idêntico;
  - uma migração falsa que falha no meio (depois de um `CREATE`) → o `iterdump()` idêntico ao de
    antes e o ledger sem ela;
  - banco novo (arquivo que não existe) → o mesmo schema que o banco antigo migrado;
  - número desconhecido no ledger → erro com o número; checksum diferente → erro;
  - backup: criado uma vez, com o conteúdo de antes; banco novo não gera backup;
  - dois **processos** abrindo o mesmo banco antigo ao mesmo tempo → os dois abrem, ledger com
    cada número uma vez;
  - os checksums publicados, escritos à mão.
- Conferência extra, fora da suíte: o `data/viking.db` do VPS (formato real de hoje, 132 linhas)
  copiado e migrado.

**✅ Checkpoint:** `python -m pytest tests/test_banco_migracoes.py tests/test_reminders_store.py
tests/test_registro.py tests/test_confirmacao.py -q` verde; a cópia do banco do VPS migra com as
132 linhas e as 2 ações; a suíte inteira passa.

**🐞 Previsto → Depurar:** a transação não cobrir o DDL (o Python fechando a transação sozinho;
classe 5) → o teste da falha no meio **tem de ter ficado vermelho** com a conexão no modo padrão;
confiro isso desfazendo o `isolation_level=None`. Classe 4 (idempotência verde porque nada rodou)
→ o teste afirma o ledger com 4 linhas depois da primeira vez.

### Fase 4 — UUID, interface e contrato (C4)
**Faz:**
- migração 5: `reminders` reconstruída (`id TEXT PRIMARY KEY NOT NULL`, as colunas de hoje e as
  quatro do envio), cópia com `uuid4` por linha, índice de `due_at` e um de pendentes por prazo;
- `reminders/interface.py` (`Protocol`): `add(..., id=None)` (id do cliente = repetir não
  duplica), `get`, `list_open`, `complete`, `vencidos(desde, ate)`, `reservar_envio`,
  `marcar_envio`, `soltar_envio`;
- `store.py` implementa; `naive` recusado; UTC de largura fixa; `service.py` converte o `quando`
  no fuso do dono (a borda);
- chat e MCP: `concluir_lembrete(reminder_id: str)`; o texto ao dono sem `#id` (título e prazo no
  fuso dele); o id vai ao Gemini numa linha que a docstring manda não mostrar;
- `tests/test_reminders_contrato.py` parametrizado pela implementação (hoje, uma), com o teste de
  "o módulo satisfaz o `Protocol`" pelo `mypy`.

**✅ Checkpoint:** a migração 5 no banco de `5d0ace4` → mesmas linhas por conteúdo, cada uma com
UUID único; o contrato verde; `test_assistant_tools` e `test_mcp_server` verdes; o comando do
`mypy` do C2 limpo.

**🐞 Previsto → Depurar:** classe 6 (um vizinho que ainda trata o id como `int`: registro, MCP,
texto) → `grep -rn "reminder_id\|#{r.id}\|#{reminder.id}" src/`. Classe 7 (o `naive` recusado
quebrando quem já passa um `naive` legítimo) → `grep -rn "store.add\|due_at=" src/ tests/`.

### Fase 5 — `viking lembretes --enviar` (C5)
**Faz:** `reminders/envio.py` (novo): `enviar_vencidos(agora)` →
- `store.vencidos(agora - 24 h, agora)` (pendentes, não enviados);
- para cada um: `reservar_envio` (perdeu = pula), `envio.novo("eu", título, corpo com o prazo
  no fuso do dono)`, `marcar_envio` (`enviado`/`incerto`) ou `soltar_envio`; `LimiteDiario` para
  o laço e solta;
- conta os vencidos há mais de 24 h (não enviados, listados pelo título).

Na CLI, `viking lembretes` (lista os pendentes) e `--enviar`, com os códigos 0/2/1.

Testes, com o dublê do Gmail:
- 2 vencidos → 2 e-mails, com o assunto = título;
- de novo → 0;
- um vencido há 25 h → 0 enviados, 1 listado;
- o limite no meio → 2, e o resto solto para a próxima;
- 5xx → `incerto`, não reenvia;
- reserva de outra execução no prazo → pula; reserva vencida → pega;
- dois **processos** ao mesmo tempo com o mesmo banco → 1 e-mail;
- título com controle → recusado e solto;
- a saída não tem endereço;
- o registro tem `gmail.enviar` livre.

**✅ Checkpoint:** `python -m pytest tests/test_lembretes_envio.py -q` verde; a suíte inteira passa.

**🐞 Previsto → Depurar:** classe 4 (o "duas vezes manda uma" verde porque a primeira não mandou)
→ afirmar 1 no dublê depois da primeira. Classe 3 (a janela comparar texto de formatos
diferentes) → um lembrete com `due_at` sem microssegundos no teste.

### Fase 6 — limpeza, mutações e fechamento (C6)
**Faz:**
- `scripts/limpar_lembretes_de_teste.py [--aplicar]`. O critério:
  - título "Pagar conta", corpo vazio, tags `[]`, sem prazo, `source` manual;
  - concluído menos de 1 s depois de criado.

  Sem a flag, só conta. Com ela, apaga numa transação e mostra antes e depois. Teste com o lixo e
  com dois "Pagar conta" legítimos (um aberto e um concluído horas depois).
- Mutações novas em `scripts/mutacoes.py`:
  - sem `BEGIN IMMEDIATE`;
  - sem reler o ledger;
  - sem a recusa do mais novo;
  - sem o checksum;
  - sem o backup;
  - reserva sem o `WHERE` do prazo;
  - janela sem o limite de 24 h;
  - `incerto` soltando a reserva;
  - `autouse` sem o `banco.CAMINHO`.

  Rodada completa em background.
- Portões lidos: `pytest`, `ruff check`, `ruff format --check`, o `mypy`.
- Duas passadas de `referencia/revisao.md`.
- Docs:
  - D56 (fundação de dados) e D57 (o que mora onde);
  - `AGENTS.md` (o `banco.py`, a armadilha "migração aplicada não se edita", o isolamento dos
    testes, `viking lembretes`);
  - `sessoes.md`, diário, barra e erros.
- Commits, push e CI pelo SHA inteiro.

**✅ Checkpoint:** `python scripts/mutacoes.py` → todas mortas (hoje 198, mais as novas); CI
`success` no SHA do push.

### Verificação ponta a ponta (C7, roteiro para o Mac)
`cd ~/LifeOs` → `git pull && git log --oneline -1`.

Depois:
- `cp data/viking.db data/viking.db.antes-da-sessao-9` e `ls -la data/` (o backup existe, com o
  tamanho igual);
- `uv sync --locked --extra dev`, `source .venv/bin/activate`, `which python`;
- `shasum data/viking.db` → `python -m pytest -q` → `shasum data/viking.db` (o mesmo: a suíte não
  toca o banco);
- `viking lembretes` (migra, faz o backup próprio, lista);
- `python scripts/limpar_lembretes_de_teste.py` (conta) → `--aplicar`;
- no `viking chat`, "me lembra de testar o Viking daqui a 2 minutos";
- depois de 2 min, `viking lembretes --enviar` → 1 e-mail na caixa; de novo → 0;
- `viking registro`.

### Riscos e o que é irreversível
- **Migrar o banco do Mac** é irreversível sem cópia: o roteiro copia antes, e a migração copia
  também.
- A migração 5 reconstrói a tabela: um erro no meio é `ROLLBACK` (testado), nunca meia tabela.
- **Apagar o lixo de teste** só com `--aplicar`, depois da contagem. O critério não alcança um
  lembrete que uma pessoa concluiu.
- O envio de lembrete só vai à própria conta: um duplicado, no pior caso, chega só a ele.
- Nada custa dinheiro nesta sessão.

## Plano — Sessão 8b: e-mail formatado, paginação da agenda e as validações ao vivo 4 e 3b (fechada em 2026-09-29)

### O que esta sessão entrega (verificável)
(a) "manda pra mim um e-mail apresentando quem você é" chega no Gmail do dono com **negrito e
lista de verdade** e a linha do Viking em cinza, menor; um texto com `<script>`, `<img onerror>`
ou `<a href>` chega como **texto**, nunca como marcação.
(b) Uma busca na agenda com mais de 250 ocorrências vem inteira até o teto declarado (500), e,
acima dele, a resposta **diz** que a lista está incompleta. O mesmo vale para a lista por data.
(c) No Mac: a página real da Wikipédia com um CPF de exemplo termina com "escondi 1 CPF dos
modelos" (o contador novo); o evento de dia inteiro "Teste Viking 3b" criado **pelo MCP** aparece
no Google Calendar no dia escolhido e só é apagado pelo `viking aprovar`.

### O que ela NÃO faz (e para onde foi)
- Formulários (pedido do dono de 2026-09-29) → **Sessão 11b**, escrita em `sessoes.md`, D55.
- Logo do Viking → backlog (como estava).
- Links clicáveis, imagens, tabelas e títulos grandes no e-mail → fora por construção (o conversor
  não os gera).

### Respostas do dono (2026-09-29)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| Plano do e-mail formatado (reabre a D46 no "só texto") | confirmado | C1; a D46 ganha "HTML só do nosso conversor" |
| A linha do Viking | cinza e menor | só no HTML; no texto puro igual a hoje |
| Validações ao vivo 4 e 3b | no roteiro do Mac no fim | C4 e C6 |
| Formulários: posição | depois da 11 (Sessão 11b) | escrito em `sessoes.md` e D55 (C0) |
| Formulários: dados | pessoais, sem dinheiro | D55 |
| Formulários: envio | o Viking só preenche; o dono clica | D55 |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Conversor em `gmail/formato.py`, só stdlib.** Primeiro divide o texto **cru** em trechos (texto, negrito, itálico) e blocos (parágrafo, lista, título); depois **cada trecho passa por `html.escape`** e só as tags que nós escrevemos ficam sem escape | escapar trecho a trecho, a partir da mesma divisão, faz a parte texto e a HTML mostrarem exatamente as mesmas palavras. Escapar a linha inteira antes e procurar `**` depois faria as duas divergirem num `**a < b**` | um caso real que a divisão não represente |
| **Subconjunto:** `**x**` → `<b>`, `*x*` → `<i>` (sem `*` colado a letra ou número dos dois lados: `2*3*4` fica como está), linhas `- `/`* `/`• ` → `<ul>`, `1. `/`1) ` → `<ol>` (com `start` se não começar em 1, só dígitos), `# x` → parágrafo em negrito, linha em branco → novo `<p>`, quebra simples → `<br>`. Aninhado não existe: o que não casa fica literal nas duas partes | é o que o Gemini escreveu na captura; menos regra, menos superfície | o Mac mostrar um formato comum que sai cru |
| **Propriedade testada:** tirar as nossas tags do HTML e desfazer o escape devolve as mesmas palavras da parte texto, para toda entrada adversarial | uma régua que não depende da lista de ataques que eu lembrei | — |
| **Parte texto:** tira só `**`/`*` de ênfase e o `# `; mantém `- ` e `1. ` das listas (legíveis como estão) | cliente sem HTML lê limpo | — |
| **Terminal:** mostra o texto fonte (o que o código liga) e, quando há formatação, a linha "No Gmail, negrito, itálico e listas saem formatados" | o dono aprova o que o Gemini escreveu; a formatação é derivada | — |
| **Paginação:** `_listar(pedido, teto=500)` segue o `nextPageToken` em páginas de 250, no máximo `teto/250` páginas; devolve `Eventos(lista, completa)`. `buscar` ganha `orderBy="startTime"` (os primeiros são os mais próximos); `por_data` usa o mesmo. `proximos` fica (já tem `maxResults` pedido) | `falha-ruidosa` §2: teto silencioso é interrupção; `por_data` é o vizinho com o mesmo teto de 250 (classe 6) | o Gemini se perder com 500 linhas (medir no Mac) |
| **Contador de redação** no subprocesso do Jev: o envelope conta, por tipo, quantas trocas `_redacao.pagina` fez antes de cada chamada ao modelo (o máximo por página, não a soma dos passos) e o evento final leva `redacoes`; `viking browser` mostra "escondi N CPF dos modelos" | a saída é redigida de novo na volta: sem o contador, um `[CPF]` no fim não separa "o modelo nunca viu" de "viu e a saída escondeu" | — |
| **Roteiro da 3b num script** (`scripts/calendario_mcp_ao_vivo.py DATA`): cliente MCP de verdade em memória, cria o evento de dia inteiro, lista por data, busca, pede para apagar; imprime estado e título, nunca ID | como o `pedido_mcp_de_teste.py` da Sessão 5; repo público | — |

### Medido na abertura (2026-09-29, VPS)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `git rev-parse HEAD origin/master`, `ls .mutacao.lock` | limpo; `70f25ab` = origin; sem trava | ok |
| Suíte | `python -m pytest -q` | `1688 passed in 20.45s` | base |
| CI do HEAD | `gh run list --commit <sha inteiro>` | `completed success` | ok |
| Versões | `uv lock --upgrade --dry-run` | "No lockfile changes detected" | nada a atualizar |
| Leitura de volta | `gmail/service._corpo` | prefere `text/plain` | o Viking relê a parte texto (sem `**`) |
| Vizinho da paginação | `grep events().list src/` | `buscar` e `por_data` sem `maxResults` nem `pageToken` (padrão da API: 250); `proximos` com `maxResults` | os dois entram |
| Página para o CPF | `curl` do artigo "Cadastro de pessoas físicas" da Wikipédia (pt) | `123.456.789-09` em texto; `_redacao.redigir` o troca por `[CPF]` (dígito válido) | página real do C6 |
| Saída redigida de novo | `jev_runner._higienizar` → `_redacao.redigir` | um CPF escrito pelo modelo também vira `[CPF]` na saída | o contador (decisão acima) |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | plano aqui; Sessão 11b e D55 escritas | — | ✅ |
| C1 | `formato.py` + `montar` com duas partes: teste vermelho antes, verde depois; terminal e docstrings; mutações mortas | C0 | ✅ (3 vermelhos + o módulo inexistente → `1776 passed`; 5 mutações mortas) |
| C2 | paginação de `buscar` e `por_data` com `completa`; texto do chat e do MCP diz quando falta | C1 | ✅ (12 vermelhos → `1786 passed`; 4 mutações mortas) |
| C3 | contador de redação no subprocesso e na saída de `viking browser` | C2 | ✅ (11 vermelhos → `1799 passed`; 4 mutações novas mortas, e a antiga do envelope reapontada) |
| C4 | `scripts/calendario_mcp_ao_vivo.py` com teste offline pelo dublê | C3 | ✅ (4 testes; a saída sem ID) |
| C5 | portões, duas passadas de revisão, D46, docs, commits, push, CI pelo SHA | C4 | ✅ (2ª passada: 3 textos velhos; 1ª: o laço de páginas vazias → `MAX_PAGINAS`) |
| C6 | roteiro do Mac: e-mail formatado, CPF, 3b | C5 | ✅ (dono, 2026-09-29: e-mail formatado; 2 CPF escondidos; 3b criada e apagada pelo MCP) |

### Fase 1 — e-mail formatado (C1)
**Faz:** teste antes em `tests/test_gmail_formato.py` (novo) e em `tests/test_gmail_envio.py`:
- o "uma parte só" vira "exatamente `text/plain` + `text/html` em `multipart/alternative`,
  `iter_attachments()` vazio";
- adversarial (`<script>`, `<img src=x onerror=…>`, `"><a href=…>`, `<style>`, `**` sem fechar,
  `***x***`, lista colada num parágrafo, `javascript:` no texto, `&lt;` já escapado): nenhum
  `<a`, `<img`, `<script`, `<style`, `on…=` no HTML; e a propriedade (sem as nossas tags e com
  `html.unescape`, as palavras são as da parte texto);
- parte texto sem `**`; emoji com ZWJ inteiro nas duas; assinatura nas duas, cinza no HTML;
- "sai exatamente o aprovado" confere as duas partes contra o `corpo` aprovado.

Depois `gmail/formato.py`, `envio.montar`, `tools.texto_do_envio` e as docstrings das duas tools.
Mutações: tirar o `html.escape` do trecho; manter `**` na parte texto; montar o HTML de outro
campo que não o aprovado.

**✅ Checkpoint:** `python -m pytest tests/test_gmail_formato.py tests/test_gmail_envio.py
tests/test_gmail_envio_chat.py -q` vermelho antes (conto quantos), verde depois; mutações novas
mortas; suíte inteira verde.

**🐞 Previsto → Depurar:** classe 4 (a propriedade passar porque as duas partes saem da mesma
função errada) → o teste literal com o HTML esperado escrito à mão para um caso; classe 7 (o
itálico pegar `2*3*4` ou um `*` de lista) → vizinhos legítimos listados no teste.

### Fase 2 — paginação (C2)
**Faz:** teste antes com o dublê do calendário devolvendo 300 e 600 ocorrências em páginas de 250
(o dublê passa a respeitar `maxResults` e `pageToken`): 300 vêm inteiras e `completa`; 600 param
em 500 e `completa=False`; o texto de `responder_buscar`/`responder_listar_por_data` diz
"mostrando os primeiros 500 … há mais"; o MCP leva `completa` no conteúdo estruturado.
**✅ Checkpoint:** `python -m pytest tests/test_calendar_service.py tests/test_mcp_server.py -q`
verde; mutação "ignorar o `nextPageToken`" e "`completa` sempre verdadeiro" mortas.
**🐞 Previsto → Depurar:** classe 6 (consertar `buscar` e esquecer `por_data`, ou o texto do MCP)
→ `grep -n "events().list" src/`.

### Fase 3 — contador de redação (C3)
**Faz:** teste antes em `tests/test_jev_subprocess_main.py`: uma página falsa com um CPF válido →
o evento final traz `redacoes == {"CPF": 1}` e o texto que chegou ao `choose` falso não tem o
número; página sem nada → sem a linha. `_redacao` ganha uma contagem (stdlib), o envelope guarda o
máximo por tipo, o runner carrega o campo e `formatar` escreve a linha.
**✅ Checkpoint:** `python -m pytest tests/test_jev_subprocess_main.py tests/test_redacao.py
tests/test_browser_seguranca.py -q` verde; mutação "o contador conta a página já redigida" morta.
**🐞 Previsto → Depurar:** classe 5 (contar `[CPF]` que a página já tinha escrito) → contar a
diferença entre o antes e o depois, com teste de página que contém `[CPF]` literal.

### Fase 4 — script da 3b (C4)
**Faz:** `scripts/calendario_mcp_ao_vivo.py DATA [--conferir]`, com teste offline pelo dublê do
calendário e o `Client(mcp)` em memória: cria, lista, busca, pede para apagar; `--conferir`
só conta quantos "Teste Viking 3b" restam. Nunca imprime ID.
**✅ Checkpoint:** o teste do script verde; saída sem nenhum ID do dublê.

### Fase 5 — fechamento (C5)
Portões lidos; duas passadas de revisão; D46 atualizada; `AGENTS.md`, `docs/fontes/gmail-api.md`,
diário, barra (a Sessão 11b entra na contagem: 28), `sessoes.md`; commits com o porquê; push; CI
pelo SHA inteiro.

### Verificação ponta a ponta (C6, Mac)
`cd ~/LifeOs` → `git pull && git log --oneline -1` → `uv sync --locked --extra dev` → `source
.venv/bin/activate` → `which python` → `python -m pytest -q`. Depois:
1. `viking chat`: "manda pra mim um e-mail apresentando quem você é" → chega com negrito, lista e
   a linha cinza.
2. `viking browser` na página da Wikipédia do CPF → a saída diz "escondi 1 CPF dos modelos" (ou
   mais) e não mostra o número.
3. `python scripts/calendario_mcp_ao_vivo.py <data que ele escolher>` → conferir no Google
   Calendar → `viking aprovar` → `python scripts/calendario_mcp_ao_vivo.py <data> --conferir` →
   0 restantes.

### Riscos e o que é irreversível
- E-mail enviado não se desfaz: o teste do Mac é para a própria conta.
- O evento de teste é criado na agenda real: apagado pelo `viking aprovar` no mesmo roteiro.
- A Wikipédia mudar o artigo: o contador mostra 0 e o roteiro diz o que fazer (trocar a página).
- Custa só tokens do Gemini e do Jev no teste do Mac.

## Plano — Sessão 8: e-mail que sai, mais o furo do bloqueio e a rotina de versões (fechada em 2026-09-28)

### Context
É a primeira sessão do roteiro de 2026-09-28 (D46). O Viking passa a **mandar e-mail**:
- para o dono, sem código;
- para outra pessoa, só com o código que ele digita.

Antes do e-mail, fecha duas dívidas achadas na revisão sênior:
- o furo no bloqueio de banco e e-mail do navegador (D8);
- a atualização do lock (D45).

Com o plano aprovado, o C0 copia este texto para o topo do `PROGRESSO.md`, como nas outras
sessões. Depois disso, execução até o fim sem pedir confirmação a cada fase.

### O que esta sessão entrega (verificável)
(a) Um endereço embrulhado ou disfarçado de banco ou e-mail não abre aba nem chega à página.
- Casos: `view-source:`, `blob:`, `filesystem:`, `https:itau…` sem barras, `\`, `%69`, letras de
  largura dupla, hífen invisível.
- O endereço inicial só aceita `http`, `https`, `data:` e `about:blank`. Um `file:///…` é recusado.

(b) `uv.lock` atualizado em commit próprio, com a suíte antes e depois.

(c) No Mac:
- "manda pra mim um e-mail…" chega **sem código**, com a linha "Escrito pelo Viking (Assistente
  AI)";
- uma resposta a outra pessoa só sai **depois** de `confirma NNNN`, na mesma conversa do Gmail;
- as duas aparecem em `viking registro`;
- um código errado não envia nada.

### O que ela NÃO faz (e para onde foi)
- Disparo de lembrete por e-mail (`viking lembretes --enviar`, com `enviado_em`) → Sessão 9 (já
  escrito lá).
- Logo do Viking no e-mail → backlog. É pedido do dono ("bem depois"); escrevo no C0.
- Anexos, Cc/Cco e HTML → fora, por construção (D46).
- Token separado com `gmail.send` → S10 (já escrito lá).
- **O passo (c) antigo, conferir "Testing" no Console, sai do plano.**
  - O dono já conferiu em 2026-09-26: em produção, externo, só ele de usuário
    (`docs/fontes/gmail-api.md:14`, `sessoes.md:190`). O "D11 nunca conferiu" da seção da 8 é
    erro meu, de classe 2.
  - O que fica: a prova de que o token não vence em 7 dias. O token do Gmail de 2026-09-26 ainda
    tem de renovar depois de 2026-10-03. Entra como primeiro passo da S10, que é onde isso importa.

### Respostas do dono (2026-09-28)
| Pergunta | Resposta | Consequência no plano |
|---|---|---|
| Quem é "você" no envio livre | a conta do Gmail | o endereço vem de `users.getProfile` (o `service.perfil()` que já existe); nada na config, e nenhum endereço no repo |
| Limite por dia sem código | 20 | contado no `registro` numa janela móvel de 24 h (sem depender de fuso); no limite, recusa e diz |
| Resposta cita a original | não | só o texto dele, na mesma conversa |
| Marca para quem recebe | linha visível "Escrito pelo Viking (Assistente AI)", e uma logo bem depois | a linha vai no fim do corpo, mais o cabeçalho próprio; logo no backlog |

### Decisões técnicas minhas (declaradas; o dono pode derrubar)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| **Uma regra para os dois caminhos:** se todos os destinatários são a conta, é livre; se há qualquer outro, vai com código. Vale igual para e-mail novo e para resposta | uma regra só, testada uma vez | o dono querer código também para si |
| **`responder_email(email_id, corpo)` não tem parâmetro de destinatário.** O "Para" sai do cabeçalho da original (`Reply-To`, senão `From`), só os endereços, sem o nome | um e-mail com injeção não consegue escolher para quem vai: não há onde escrever | o Mac mostrar `Reply-To` legítimo que atrapalha |
| **E-mail novo:** só "Para", de 1 a 5 endereços ASCII validados; sem Cc/Cco | D46; endereço não-ASCII é recusado, o que corta sósias de endereço | o dono pedir Cc |
| **O código liga para + assunto + corpo + conversa (`threadId`, `In-Reply-To`, `References`)**, guardados na proposta. O envio monta a mensagem **só desses dados** | o dono aprova exatamente o que sai | — |
| **Corpo e assunto com caractere de controle ou bidi são recusados, não limpos.** O limite é 5000 caracteres, e o terminal mostra o corpo **inteiro** | o que ele lê na tela tem de ser o que sai; um trecho escondido ou cortado seria vazamento aprovado sem ver | — |
| **O código só aparece com terminal interativo** (`liberacao.terminal_interativo`); sem terminal, nenhuma proposta é criada | regra da sessão (D26/D52) | — |
| **4 dígitos, 10 min, uso único**, como as outras aprovações; uma proposta nova substitui a aberta | o mesmo `aprovacao_local` para tudo | — |
| **`send` em uma função só** (`service.enviar`), dentro de `registro.acao("gmail.enviar")`; sem nova tentativa, a não ser em recusa de cota (429/403 de cota: nada foi enviado); 5xx, tempo esgotado ou falha de conexão é `incerta` ("Não sei se enviei…") | um reenvio mandaria duplicado; o padrão é o de `calendar/service.FalhaDaApi(incerta=…)` | — |
| **Mensagem:** `email.message.EmailMessage`, só `text/plain` UTF-8, `From` = a conta, cabeçalho `X-Viking` e a linha visível no fim | sem anexo por construção; o `EmailMessage` recusa CR/LF (medido no 3.12) | o Mac mostrar que o `From` explícito atrapalha |
| **O registro guarda** para, assunto, conversa, `livre` e o id da mensagem. O corpo não, e o código nunca | privacidade; o limite de 20 conta pelas linhas com `livre` que estão `feita`, `incerta` ou `iniciada` | — |
| **E-mail lido de volta com `X-Viking`** continua dentro do bloco de não confiável, com a etiqueta "[enviado pelo Viking]", mesmo com o dono como remetente | D53: a marca informa, nunca dá confiança; um cabeçalho qualquer um forja | — |
| **Bloqueio de domínio:** um canonizador só em `_redacao._host`, usado dos dois lados. Ele desembrulha `view-source:`/`blob:`/`filesystem:` (em laço), trata `\` e barras que faltam nos esquemas especiais, decodifica `%XX` no host, aplica NFKC com casefold, tira caracteres invisíveis e troca o ponto ideográfico por `.` | é a regra de host da especificação que o Chrome segue (WHATWG, não medido no Chrome); o conserto é no ponto único, não nos dois chamadores | um endereço legítimo recusado ao vivo |
| **Esquema do endereço inicial:** `jev_runner` só aceita `http`, `https`, `data:` e `about:blank`; qualquer outro vira o erro novo `endereco_recusado`. `data:` fica porque os testes e a D38 usam | `file:///…/.env` do Mac iria ao OpenRouter e ao Gemini; é a vizinha do mesmo furo (classe 6) | o dono pedir um esquema |

### Medido na abertura (2026-09-28, VPS)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Repositório | `git status`, `git rev-parse HEAD origin/master`, `ls .mutacao.lock` | limpo; `7f1145f` = origin; sem trava | ok |
| Suíte | `python -m pytest -q` | `1553 passed in 19.87s` | base |
| CI do HEAD | `gh run list --commit <sha inteiro>` | `completed success` | ok |
| Versões | `uv lock --upgrade --dry-run` | oauthlib 3.3.1→4.0.0, platformdirs 4.12.0→4.12.1, **pyjwt 2.15.0→2.15.1, sse-starlette 3.4.11→3.5.0** (as duas últimas não estavam no bloco) | as quatro no commit do C2; pyjwt e sse-starlette vêm do `mcp` (`uv tree --invert`) |
| Status OAuth | `docs/fontes/gmail-api.md:14` | já conferido pelo dono em 2026-09-26: em produção | o passo (c) sai; corrigir a S8 e a D11 |
| Envio hoje | `tests/test_gmail_limpeza.py:326` `_PROIBIDAS` | `send` proibido em `gmail/` | vira "permitido só em `service.enviar`" |
| Onde o código aparece | `gmail/tools._ao_dono`, `liberacao.terminal_interativo` | a limpeza imprime sem conferir terminal; a liberação confere | o envio segue a liberação |
| Bloqueio | `_redacao._host` (urlsplit) | nenhum desembrulho nem canonização; runner sem lista de esquemas | Fase 1 |

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | plano no `PROGRESSO.md`; S8/D11 corrigidas; logo no backlog; `erros.md` classe 2 (18) | — | ✅ 2026-09-28 (e classe 5: o hífen invisível no próprio plano) |
| C1 | teste vermelho do bloqueio → conserto → verde; mutações novas mortas; commit 1 | C0 | ✅ 2026-09-28: 17 de 20 disfarces vermelhos antes; `1607 passed` depois; 11/11 mutações `bloqueio`/`view-source` mortas pelo teste esperado |
| C2 | lock atualizado, suíte antes e depois, `test_lock` verde; commit 2 | C1 | ✅ 2026-09-28: **5** pacotes (o `google-auth` 2.59.0 saiu às 21:49Z, depois da abertura: só declara Python 3.15); `1607 passed` antes e depois; lock/MCP `443 passed` |
| C3 | `service.enviar` + `envio.py` (montar, livre, propor, confirmar) com testes; régua do `send` trocada | C2 | ✅ 2026-09-28: `tests/test_gmail_envio.py` (44) |
| C4 | tools no chat, `aprovacao_local`, CLI `--enviar`/`--responder`, leitura de volta com a etiqueta; mutações | C3 | ✅ 2026-09-28: `tests/test_gmail_envio_chat.py` (21); 8 mutações do envio; achados: código inexistente caía no texto da limpeza (`_tipo_aberto`), e responder ao que o dono mandou ia para ele (agora o `To` da original) |
| C5 | portões, duas passadas de revisão, docs, commit(s), push, CI pelo SHA | C4 | ✅ 2026-09-28: `1679 passed`, 183/183 mutações; `/security-review` não disponível para mim nesta sessão (não conferido) |
| C6 | teste do dono no Mac | C5 | ✅ 2026-09-28: tudo passou; achado o "manda pra mim" que perguntava o endereço → `para="eu"` (1686 passed, 9/9 mutações do envio) |

### Fase 1 — o furo do bloqueio (C1)
**Faz:**
- **Teste antes**, em `tests/test_redacao.py`, `test_dominio_bloqueado`:
  - os disfarces: `view-source:https://itau.com.br/`, `blob:https://itau.com.br/uuid`,
    `filesystem:https://itau.com.br/temporary/x`, `VIEW-SOURCE:view-source:https://…`,
    `https:itau.com.br`, `https:/itau.com.br`, `https:\\itau.com.br\x`, `https://%69tau.com.br`,
    `https://ｉｔａｕ.com.br`, `https://it\u00adau.com.br` (gerado por script, erros classe 5) e
    `https://itau。com.br`.
  - O `test_dominio_nao_bloqueado` ganha os vizinhos legítimos:
    - `https://example.com/view-source:https://itau.com.br`;
    - `data:text/html,itau.com.br`;
    - `https://evil.com%40itau.com.br`.

  Esperado: **vermelho** nos disfarces antes do conserto (conto quantos).
- **Conserto** em `src/lifeos/browser/_redacao.py`, só stdlib (`_host` e um `_canonico`), como
  descrito nas decisões.
- **Esquema no runner** (`jev_runner.run_jev`, antes do bloqueio):
  - `_redacao.esquema_permitido(url)`;
  - o código novo `endereco_recusado` em `browser/mensagens.py`;
  - testes em `tests/test_browser_seguranca.py` com `file:///etc/hosts`, `chrome://settings`,
    `javascript:alert(1)` e `view-source:https://example.com`.
- **Mutações** em `scripts/mutacoes.py`:
  - tirar o desembrulho;
  - tirar a decodificação `%`;
  - tirar o NFKC;
  - tirar a lista de esquemas.

  As âncoras vão para `test_mutacoes_ancoras`.

**✅ Checkpoint:**
- `python -m pytest tests/test_redacao.py tests/test_browser_seguranca.py -q`: vermelho → verde;
- `python scripts/mutacoes.py` (background, sem `timeout`): todas mortas;
- a suíte inteira passa.

**🐞 Previsto → Depurar:** classe 7 (regra pelo caso típico: o canonizador recusar um endereço
legítimo) e classe 6 (consertar o runner e esquecer o `_checar` do subprocesso). → `grep -rn
"dominio_bloqueado\|_host(" src/`. Os dois lados chamam a mesma função? Rodar
`tests/test_jev_subprocess_main.py`.

### Fase 2 — versões (C2)
**Faz:**
1. Ler os changelogs das 4 versões, com link e data; oauthlib já foi lido (só quebra o lado
   provedor).
2. `uv lock --upgrade`.
3. `uv sync --locked --extra dev`.
4. A suíte.
5. Commit próprio.

**✅ Checkpoint:** `uv lock --check` ok; `python -m pytest -q` → `N passed` (o mesmo N de antes do
upgrade); `tests/test_lock.py` verde (wheel para Mac Intel e Linux nos dois Pythons).

**🐞 Previsto → Depurar:** o sse-starlette ou o pyjwt mudar algo que o `fastmcp` usa. →
`python -m pytest tests/test_mcp_server.py tests/test_mcp_aprovacao.py -q`; se cair, reverter só
esse pacote (`uv lock --upgrade-package`) e perguntar.

### Fase 3 — o envio no serviço (C3)
**Faz:**
- `gmail/service.py`:
  - `enviar(mensagem, *, thread_id, livre)`: a **única** chamada `.send`, dentro de
    `registro.acao`; 5xx, tempo e conexão são `FalhaDaApi(incerta=True)`;
  - `cabecalhos_para_responder(email_id)`: `get` em metadata com `From`, `Reply-To`, `Subject`,
    `Message-ID`, `References` e o `threadId`; `Message-ID` e `References` validados no formato
    `<…>` e com teto de tamanho;
  - `X-Viking` entra em `_CABECALHOS`, e `Email.do_viking` também.
- `gmail/envio.py` (novo, como `limpeza.py`):
  - `montar()` puro, com `EmailMessage`, a linha visível e o `X-Viking`;
  - `validar()`: endereços, controles, bidi e tamanhos;
  - `enviar_livre()`: destinatário = `perfil()`, limite de 20 em 24 h pelo `registro`;
  - `propor_novo()` e `propor_resposta()`: `confirmacao.propor(GMAIL_ENVIAR, dados)`;
  - `confirmar(codigo)`: `consumir`, monta só dos dados e chama `enviar`.
- `aprovacoes.py`: `GMAIL_ENVIAR`, com janela 0 e `no_chat=True`.
- O dublê em `tests/conftest.py`: `messages().send(userId, body)` decodifica o `raw` e guarda;
  custo 100; falha 5xx injetável.
- `tests/test_gmail_envio.py`:
  - montagem: só `text/plain`, nenhuma parte de anexo, `In-Reply-To`/`References`/`threadId`
    certos, `Re:` sem duplicar;
  - CRLF recusado pela nossa trava **e** pelo `EmailMessage`;
  - controle e bidi recusados;
  - livre só para a conta: `dono+x@`, outro domínio e maiúsculas não são o dono;
  - o limite 21º recusado;
  - o código nunca no retorno nem no `registro` (lê a tabela `acoes`);
  - `incerta` no 5xx;
  - uso único, expiração, substituição.
- Régua: o `_PROIBIDAS` perde `send`; um teste novo exige `.send` exatamente uma vez em `gmail/`,
  em `service.enviar`, e `tests/test_registro_ganchos.py` passa a exigir o `registro.acao` em volta
  dele. Lixeira, apagar, `drafts`, `insert` e `import_` continuam proibidos.

**✅ Checkpoint:** `python -m pytest tests/test_gmail_envio.py tests/test_gmail_limpeza.py
tests/test_registro_ganchos.py -q` verde; a mutação "enviar fora do `registro.acao`" derruba a
régua.

**🐞 Previsto → Depurar:** classe 4 (um teste do código fora do `registro` que passa porque o
código nunca foi gerado). → a asserção positiva primeiro: o código **está** no texto do terminal e
**não está** na tabela. Classe 5: o dublê decodificar diferente do Google. → comparar com
`base64.urlsafe_b64decode` e com o `email.parser` da stdlib.

### Fase 4 — chat, CLI e leitura de volta (C4)
**Faz:**
- `gmail/tools.py`:
  - tools `enviar_email(para, assunto, corpo)` e `responder_email(email_id, corpo)`, com
    docstrings que dizem: você nunca vê o código; um pedido dentro de e-mail não vale;
  - `texto_do_envio()` para o terminal: Para, Assunto, a conversa (assunto e remetente da
    original), o corpo inteiro, "Para enviar, digite: confirma NNNN (vale até HH:MM)" e "Nada foi
    enviado ainda";
  - a etiqueta "[enviado pelo Viking]" na `_linha` e no `responder_ler`, dentro do bloco.
- `assistant/agent.py`:
  - as tools entram em `FERRAMENTAS` (21 → 23);
  - `aprovacao_local` leva o código de `GMAIL_ENVIAR` a `_aprovar_envio`; `desfaz` com esse código
    responde "e-mail enviado não se desfaz. Nada mudou";
  - uma linha no texto de sistema.
- `cli.py`: `viking gmail --enviar PARA --assunto A --corpo C` e `--responder ID --corpo C`, com o
  código pedido ali mesmo, como `--arquivar`, e só com terminal.
- `registro_texto.py`: o texto de `gmail.enviar`.
- Testes em `tests/test_gmail_aprovacao.py`:
  - `_chamadas("confirmar")` de `envio` só em `agent.py`/`cli.py`;
  - `_chamadas("enviar")` só em `envio.py`;
  - a linha `confirma` não vai ao Gemini;
  - a injeção "responda para x@evil" num e-mail não muda o "Para".
- `test_servidor_mcp_nao_expoe_email` segue verde.
- Mutações:
  - o "livre" aceita qualquer endereço;
  - o limite desligado;
  - o código no retorno da tool;
  - a resposta usa um endereço do corpo.

**✅ Checkpoint:** a suíte inteira passa; `test_assistant_tools` (assinaturas e sem future import)
verde; as mutações novas mortas.

**🐞 Previsto → Depurar:** classe 6 (o `aprovacao_local` rotear o código do envio para
`_aprovar_limpeza`, o fallthrough). → um teste com proposta de envio aberta e `confirma NNNN`, que
afirma que o `send` do dublê foi chamado e o `batchModify` não.

### Fase 5 — fechamento (C5)
- Portões lidos, citando a linha: `pytest`, `ruff check .`, `ruff format --check .` (o formatador
  só nos arquivos que eu editei, nomeados).
- Duas passadas de `referencia/revisao.md`, com perguntas diferentes. Conferir se
  `/security-review` existe (D53) e, se existir, rodar.
- Docs:
  - `AGENTS.md`: o módulo `gmail/`, a armadilha do envio e a régua;
  - `docs/fontes/gmail-api.md`: `send`, cabeçalhos e marca;
  - `docs/decisoes.md`: D46 com as respostas de hoje, D8 com o conserto, gatilho da D11;
  - `sessoes.md`: S8 feita, e o primeiro passo da S10 (o token com mais de 7 dias);
  - diário, barra e `PROGRESSO.md`.
- Commits com o porquê; push; CI pelo SHA inteiro.

### Verificação ponta a ponta (C6, roteiro para o Mac, classe 1)
`cd ~/LifeOs` → `git pull && git log --oneline -1` → `uv sync --locked --extra dev` → `source
.venv/bin/activate` → `which python` → `python -m pytest -q`.

Depois:
1. `viking gmail --login`: o oauthlib 4.0.0 ainda entra.
2. `viking browser --url "view-source:https://www.itau.com.br/" --goal "ler a página"` →
   recusado, sem abrir aba.
3. `viking browser --url "file:///etc/hosts" --goal "ler"` → recusado.
4. `viking chat`:
   - "manda pra mim um e-mail com assunto Teste Viking dizendo oi": chega **sem código**, com a
     linha visível;
   - pedir uma resposta a um e-mail de **outra pessoa** (de preferência de outro endereço dele):
     aparecem a proposta e o código; digitar um **código errado** → nada sai; depois
     `confirma NNNN` → sai na mesma conversa.
5. `viking registro` → as duas linhas `gmail.enviar`, sem código.

### Riscos e o que é irreversível
- **E-mail enviado a outra pessoa não se desfaz.** Por isso sempre com código, e o teste do Mac usa
  um endereço dele ou de alguém avisado.
- Envio livre em laço por injeção: para em 20 por dia, e só chega à caixa dele.
- O canonizador recusar site legítimo: aparece como `dominio_bloqueado`, com o domínio nomeado. O
  dono pode liberar por `VIKING_BROWSER_LIBERADOS`.
- Upgrade do MCP: a suíte cobre o protocolo em memória; o `viking mcp-server` ao vivo não é medido
  aqui.
- Nada custa dinheiro nesta sessão além de tokens do Gemini no teste do Mac.

## Plano — Sessão 7: manutenção (versões travadas, CI, scanner, formatação e três consertos pequenos) (fechada em 2026-09-28)

### Context
Sessão 7 de `sessoes.md` (auditoria do Codex §15.1–15.4) mais o achado da 6: a aprovação do MCP
compara `inicio` como texto. Nada aqui é funcionalidade nova. O objetivo é tornar seguro continuar
mexendo:
- a mesma versão de cada pacote em toda máquina;
- os testes rodando no GitHub a cada push;
- aviso de pacote com falha conhecida;
- formatação sem baseline;
- dois testes que provam o que dizem.

Abertura conferida em 2026-09-28, e tudo bate com o bloco de retomada:
- HEAD `b894956` = origin, árvore limpa, sem `.mutacao.lock`;
- `1118 passed`, `7 files would be reformatted`, `ruff check` limpo.

Este plano mora aqui desde o C0; os planos anteriores ficam abaixo, como nas outras sessões.

### O que esta sessão entrega (verificável)
(a) `uv sync --locked --extra dev` no Mac instala exatamente o `uv.lock`, e a suíte passa lá.
(b) O commit do topo no GitHub tem o run do CI **verde, conferido pelo `headSha`**: testes, `ruff check`, `ruff format --check` com zero arquivos a formatar, e `pip-audit` do lock.
(c) Os alertas do Dependabot estão ligados: `gh api …/vulnerability-alerts` → 204.
(d) Uma aprovação do MCP pedida com o dono num fuso e aprovada noutro executa. Um evento que mudou de hora continua recusado.
(e) Nenhum teste importa API privada do google-genai.
(f) O número de erros de tipos está medido e na mão do dono, que decide se ele vira portão.

### O que NÃO faz
- **Bloquear o master** (branch protection) → recusado pelo dono; entra em D45 como recusa, com o motivo.
- **PRs automáticos do Dependabot** → recusado pelo dono (D45).
- **Corrigir todos os erros de tipos:** depende do número medido no C1.
  - Se o dono não quiser na 7, vira item do backlog de `sessoes.md`, escrito na hora com o número.
- **Mutações no CI** → continuam à mão (cerca de 10 min; o `scripts/mutacoes.py` diz "não no CI").

### Respostas do dono (2026-09-28)
| Pergunta | Resposta | Consequência |
|---|---|---|
| Escopo | todos: pequenos + lock + CI + scanner. A 1ª rodada marcou só os pequenos; a 2ª desfez a contradição: "entram todos" | sessão cheia, 2 entregas |
| Checagem de tipos | medir e trazer o número antes de prometer | C1 mede; decisão do dono ali |
| Formatação | commit só de formatação | fim do baseline de 7 e da regra "só os meus trechos do `--diff`" |
| Commits | 2 | reconciliado com "commit só de formatação": entrega 1 = commit 1a (só formatação) + 1b (pequenos), num push só; entrega 2 = commit 2 |
| Instalar no Mac | pelo `uv` (`uv sync`) | `python -m pip install -e` sai da doc; `python -m pytest` fica |
| Scanner | alertas do GitHub + verificação no CI, sem PRs automáticos | eu ligo pelo `gh`, **com o ok do dono na hora** |
| CI vermelho | só marca ❌ e avisa | sem branch protection; push direto no master continua |
| Atualizar versões | quando o scanner avisar + ao abrir cada sessão | rotina de abertura ganha "há versão nova?"; a atualização vai num commit próprio, com a suíte antes e depois |

### Decisões técnicas minhas
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Lock pelo `uv` (`uv lock`), build continua setuptools, sem `[tool.uv]` especial; CI e Mac usam `--locked` | o `uv` já existe nas duas máquinas; `--locked` falha se o lock não bate com o `pyproject` | o `uv` do Mac velho demais para ler o lock (o roteiro mede `uv --version`) |
| CI: `.github/workflows/testes.yml`, `on: push` (todas as branches) + `pull_request` + `workflow_dispatch`, **sem filtro de caminho**, Python 3.12, `permissions: contents: read`, actions fixadas por **SHA de 40 caracteres**, sem nenhum `secrets.` | os testes leem `.md` (âncoras), então filtro de caminho erraria; repo público = log público e cadeia de suprimentos; o CI verifica, não publica (`nuvem-e-deploy` §10) | — |
| Um teste lê o workflow: SHA fixado, `contents: read`, sem `secrets`, sem `pull_request_target`, `--locked`, e os mesmos portões do `AGENTS.md` | estrutura vence disciplina: o workflow não pode afrouxar calado | — |
| `pip-audit` fixado por versão, rodado pelo `uvx` sobre a exportação do lock (`uv export --frozen`), fora das dependências do Viking | audita o que o Viking instala, sem pôr a árvore do `pip-audit` na venv | a medição do C1 mostrar que a exportação não serve ao `pip-audit` |
| No CI, `skipped` esperado = 2 (os contratos com o clone do Jev, `test_jev_subprocess_main.py:699,757`) | "skipped > 0 numa suíte que não pula é vermelho": o número fica escrito e conferido | — |
| Checagem de tipos: medir com `mypy` fixado, modo padrão (não strict), pelo `uvx`, sem instalar na venv | maduro, e mede sem compromisso | — |
| `.md` fora do `ruff format` (`[tool.ruff.format] exclude`) | o único `.md` apontado cita o código do patch do Jev como ele é; o ruff 0.16 formata blocos Python de `.md` | — |
| `.git-blame-ignore-revs` com o SHA do commit 1a (no commit 2, que é quando o SHA existe) | o GitHub esconde a formatação no blame | — |
| §15.2: **trocar** `_parse_schema_from_parameter("VERTEX_AI", …)` por `types.FunctionDeclaration.from_callable_with_api_option(callable=fn, api_option="GEMINI_API")`; `test_anotacoes_sao_tipos_reais` fica | o privado valida contra o backend errado e quebra se o google-genai renomear; o público aceita 21/21 (medido); o do future import é outro teste | — |
| `_REGRAS`: cada regra vira uma frase só, comparada com espaços normalizados dos dois lados | todas as listas de "alternativas" têm 1 item (lido); o `or` da linha 96 some sem perder regra | — |
| `inicio`: `_mesmo_instante(a, b)`. Os dois aware → compara o instante (`datetime ==`); senão (dia inteiro, texto) → compara o texto | recusa falsa com texto falso ("mudou") é defeito; o `etag`/`updated` continuam; nunca afrouxa um evento que mudou | — |
| Rotina de abertura (`sessoes.md` ▶️ e `AGENTS.md`): `uv lock --upgrade --dry-run` (ou `uv tree --outdated`); se houver versão nova → commit próprio `uv lock --upgrade`, suíte antes e depois | resposta do dono | — |

### Medido na abertura (2026-09-28, VPS, HEAD `b894956`)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Arquivos fora da formatação | `ruff format --check --output-format concise .` e `ruff format --diff F \| grep -c '^[-+] '` | 7 arquivos, uns 35 trechos no total (lista abaixo) | um commit só de formatação é pequeno; o `.md` é citação e sai da formatação |
| Ferramentas | `ruff --version`, `pip list` | ruff 0.16.8, pytest 9.1.1, google-genai 2.24.0, 102 pacotes; **nada fixado** | outra máquina pode ter outro ruff e outro número |
| Instalação | `pyproject.toml`, `.venv/pyvenv.cfg` | setuptools; `pip install -e ".[dev]"`; venv por `python3 -m venv`, Python 3.12.3; sem lock, sem `requirements*.txt` | §15.1 procede |
| `uv` | `uv --version` | 0.12.10 no VPS | — |
| Mac | diário (Sessões 4–6) | `uv` existe (o Jev roda por `uv run`); conda `base` ativo junto do venv | versões do Python e do `uv` **não medidas**: o roteiro mede antes de trocar |
| GitHub | `gh api repos/Zbreno11-git/LifeOs …` | ver abaixo | CI e alertas partem do zero |
| Tempo da suíte | `time python -m pytest -q` | `1118 passed in 16.11s` (17,05 s real) | cabe num CI a cada push |
| Tempo das mutações | carimbos de 3 rodadas no transcrito (27–28/09) | 9 min 23 s, 9 min 39 s, 10 min 03 s | ficam à mão |
| API privada do google-genai | `grep` | `tests/test_assistant_tools.py:6,28` usa `"VERTEX_AI"`; o Viking usa a API de desenvolvedor (`agent.py:144`) | o teste confere contra o backend errado |
| API pública | script contra as 21 tools | `from_callable_with_api_option(..., "GEMINI_API")` aceita 21/21; **não** pega anotação-string | complementa o teste do future import, não o substitui |
| `or` em asserção | leitura | `tests/test_assistant_tools.py:96`, de antes da regra; todas as alternativas têm 1 item | conserto no mesmo arquivo |
| `inicio` | `calendar/service.py:608`; `grep` de quem mais lê um início guardado | ver abaixo | defeito latente; conserto pequeno |
| Suíte sem o clone do Jev | `grep skip` | 2 testes pulam | `skipped` = 2 no CI |
| Suíte sem `.env` | — | **não medido** (no plano não copio o repo) | C1 |
| Tipos | `which mypy pyright ty` | nenhum instalado; `src` 8.290 linhas, `tests` 9.286 | C1 mede |

Os 7 arquivos fora da formatação e quantos trechos cada um muda:
- `archive/.../serial_mcp_bridge.py`: 10;
- `docs/arquitetura/browser-automation-stack.md`: bloco Python que **cita** o patch do Jev (4 → 1 linha);
- `agent.py`: 3;
- `calendar/tools.py`: 6;
- `custos.py`: 4;
- `tests/test_assistant_tools.py`: 8;
- `tests/test_browser_jev_runner.py`: 4.

O que o GitHub tem hoje:
- repositório público, sem `.github/`;
- Actions ligado, com todas as actions permitidas;
- secret scanning e push protection **ligados**;
- alertas do Dependabot **desligados** (a API responde 404) e security updates desligados.

O `inicio` na aprovação do MCP:
- os dois lados saem de `no_fuso_do_dono` e são comparados como texto;
- recusa falsa quando o fuso do processo do MCP é diferente do fuso do `viking aprovar`, ou quando a `VIKING_TIMEZONE` muda dentro da 1 h de validade;
- nunca aprova errado, e a mensagem diria "mudou" sem ter mudado;
- é o único lugar que compara um início guardado.

### Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | plano no `PROGRESSO.md` (bloco ▶️ + plano), acima da 6 | — | ✅ |
| C1 | medições que faltaram + número de tipos levado ao dono | C0 | ✅ (resultado abaixo; tipos → backlog, dono) |
| C2 | commit 1a: só formatação, zero a formatar, âncoras de mutação intactas | C1 | ✅ `dd7d4c8` |
| C3 | §15.2 público + `_REGRAS` sem `or` | C2 | ✅ 21 casos + 33 regras |
| C4 | `inicio` por instante | C2 | ✅ `_mesmo_instante`, regra única com o desfazer |
| C5 | mutações, docs, revisão em 2 passadas, commits 1a+1b, push | C3, C4 | ✅ `1149 passed`, 162/162 |
| C6 | `uv.lock` + `uv sync --locked` reproduz a suíte no VPS | C5 | ✅ 103 pacotes; `.venv` do VPS sincronizado, `1158 passed`; cryptography 48.0.1 (D45) |
| C7 | CI (workflow + teste que o lê + `.git-blame-ignore-revs`) | C6 | ✅ 9 testes, 3 mutações 3/3 |
| C8 | alertas do Dependabot ligados (ok do dono na hora) | C7 | ✅ ok do dono; `vulnerability-alerts` → 204 |
| C9 | tipos conforme a decisão do C1 (portão ou backlog escrito) | C1, C7 | ✅ dono: backlog (2026-09-28); escrito no backlog de `sessoes.md` |
| C10 | D45, rotina de abertura, docs, revisão em 2 passadas, commit 2, push, CI do HEAD verde pelo `headSha` | C6–C9 | ✅ `0a1d122`: run 36381073572 `success` (`1156 passed, 2 skipped`, 37 s); grafo lê o lock; 3 alertas = os da D45 |
| C11 | Mac: roteiro abaixo | C10 | ✅ 2º teste em `069fe2a`: `uv sync` ok, `1553 passed`, versões do lock (o 1º achou `no-build` e Python 3.13, consertados) |

### Fase 0 — C1: medir o que faltou (nada commitado)
**Faz (tudo no scratchpad, nada no repo):**
- **Suíte num export limpo, como o CI vê o repo.** `git archive HEAD` → pasta no scratchpad, venv nova com `uv venv` + `uv pip install -e ".[dev]"`, e `env -u GEMINI_API_KEY -u PLUGGY_CLIENT_ID -u PLUGGY_CLIENT_SECRET -u PLUGGY_API python -m pytest -q -rs`, sem `.env` e sem o clone.
- **Tipos:** `uvx mypy==<fixada> src` → número de erros por arquivo.
- **Scanner:** `uv export` do ambiente atual + `uvx pip-audit==<fixada>` → achados.
- **`uv sync` na cópia:** o `pip` sobrevive? (decide se o `python -m pip` some da doc).
- **GitHub:** se o grafo de dependências lê o `uv.lock`, pela documentação e depois por `gh api …/dependency-graph/sbom` no C8.

**✅:**
- `N passed, 2 skipped` no export, com N = 1118 − 2. Se der outro número, a diferença é o achado: teste que dependia do `.env` do VPS **é defeito** e se conserta no commit 1b.
- O número de tipos vai ao dono (pergunta com o dado na mão).

**🐞:**
- **Classe 2:** afirmar "o GitHub lê o `uv.lock`" sem conferir → só a medida do C8 conta.
- **Classe 4:** um teste passando aqui por causa do `.env` do VPS → é justamente o que o export mede.

#### C1 — resultado (2026-09-28, `5dd06a7`, scratchpad)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|
| Suíte num export limpo, sem `.env` e sem o clone | `git archive HEAD` + `uv venv` + `uv pip install -e ".[dev]"` + `env -i PATH HOME TZ=UTC python -m pytest -q -rs` | `1116 passed, 2 skipped in 18.86s`; os 2 são `test_jev_subprocess_main.py:699,757` (clone ausente) | a suíte não depende do `.env` do VPS; `skipped` = 2 no CI |
| Venv criada pelo `uv` | `.venv/bin/python -m pip --version` | `No module named pip` | com `uv sync`, `python -m pip` deixa de funcionar na venv: a doc passa a `uv pip …`; `python -m pytest` fica |
| Versões: instalação de hoje × venv do VPS | `pip freeze` × `uv pip freeze`, nomes normalizados | 18 pacotes diferentes, todos mais novos na instalação limpa (ex.: google-genai 2.24.0 → 2.25.0, fastmcp 4.0.5 → 4.0.10, ruff 0.16.8 → 0.16.9); a suíte passa nas duas | é o §15.1 medido: duas máquinas já instalam coisas diferentes |
| Formatação com o ruff 0.16.9 | `ruff format --check .` | os mesmos `7 files would be reformatted` | — |
| Tipos | `uvx mypy==2.3.1 --python-executable .venv/bin/python src` | `Found 67 errors in 15 files (checked 41 source files)`: 34 em `jev_runner.py` (um padrão só, `**dict` num dataclass), 9 imports do ambiente do Jev, 3 pacotes do Google sem tipos, o resto `None` que o mypy não vê filtrado; nos ~12 que li, nenhum defeito real | decisão do dono |
| Scanner | `uv pip freeze` (97 pacotes) + `uvx pip-audit==2.10.1 -r … --no-deps --disable-pip` | `No known vulnerabilities found` | o CI parte verde |

### Entrega 1 — formatação e consertos pequenos

#### C2 — commit 1a, só formatação
**Faz:**
- `[tool.ruff.format] exclude = ["*.md"]`;
- `ruff format` **só nos 6 `.py` listados** (nome por nome, não `.`).

**✅:**
- `ruff format --check .` → nenhum "would be reformatted";
- `git diff --stat` → exatamente os 6 `.py` + `pyproject.toml`;
- `python -m pytest -q` → 1118 passed;
- `python -m pytest tests/test_mutacoes_ancoras.py -q` verde.

**🐞:**
- **Classe 8:** formatador com alcance maior que a mudança → nomes explícitos e `git status` depois.
- **Classe 5:** âncora de `scripts/mutacoes.py` num trecho reformatado (agent, tools, custos, `test_browser_jev_runner`) → o teste de âncoras primeiro, e depois a rodada **completa**, porque a mudança é ampla.

#### C3 — §15.2 e o `or`
**Faz:** em `tests/test_assistant_tools.py`:
- `test_schema_aceito_pela_api_do_gemini` com a API pública `GEMINI_API`, sem o import privado;
- `_REGRAS` com uma frase por regra, normalizada dos dois lados, numa asserção só.

**✅:**
- `grep -rn '_automatic_function_calling_util' src tests` → 0;
- `grep -n ' or ' tests/test_assistant_tools.py` → só o `(fn.__doc__ or "")`, que é um padrão e não uma asserção;
- os testes parametrizados continuam com 21 tools e 14 regras (contados pelo `-v`).

**🐞:**
- **Classe 4:** a API pública aceita qualquer coisa e o teste fica verde à toa → antes de confiar, medir qual anotação ela **recusa** (por exemplo, um tipo não suportado) e usá-la na mutação.
- **Classe 7:** uma regra com `\n    ` no meio perde o casamento após normalizar → uma asserção por regra, com a mensagem dizendo qual.

#### C4 — `inicio` por instante
**Faz:**
- `calendar/service._mesmo_instante(a, b)`;
- a linha 608 passa a usá-lo;
- docstring com o porquê (fuso do dono em processos diferentes).

**✅:** em `tests/test_mcp_aprovacao.py`, ou onde o dublê de aprovação já vive:
- pedido com o dono em São Paulo, aprovação com o dono em Los Angeles, **mesmo `etag`** → executa (antes: recusava);
- evento que andou 1 h com o `etag` **igual** → recusa (isola a regra do `inicio` da do `etag`);
- dia inteiro igual → executa;
- dia inteiro mudado → recusa.

**🐞:**
- **Classe 4:** o teste de "andou 1 h" passa pela regra do `etag` → o dublê mantém o `etag`, e a mutação `_mesmo_instante → True` tem de derrubar **esse** teste.
- **Classe 6:** outro lugar que compara início guardado → já medido: único (`grep` na abertura).

#### C5 — fechar a entrega 1
**Mutações novas (≥4):**
- `_mesmo_instante` volta a comparar texto → cai o teste de fuso cruzado;
- `_mesmo_instante` devolve sempre `True` → cai o de "andou 1 h";
- anotação de uma tool trocada pelo tipo que o Gemini recusa → cai `test_schema_aceito_pela_api_do_gemini`;
- regra de docstring apagada → cai a regra certa.

Rodada completa de `python scripts/mutacoes.py` **em background, sem timeout** (esperado: `161 · mortas pelo teste esperado: 161`). Antes, a pergunta "qual teste esperaria para sempre?": nenhuma mutação aqui é "recusa → espera".

**Docs:**
- `AGENTS.md`: tirar "baseline de 7 arquivos" e o "só os meus trechos";
- `docs/erros.md`: o antídoto da classe 8 perde a cláusula do baseline, e classe nova só se eu errar;
- `sessoes.md`: §15.2 e §15.4 riscados, com data;
- D45 parcial: formatação;
- diário e `PROGRESSO.md`.

**Revisão, 1ª passada:**
- O diff do 1a é **só** formatação? `git diff -w --stat` e leitura.
- E se o fuso do dono for o mesmo dos dois lados? (o teste antigo continua verde)
- E se um dos dois horários vier sem fuso? (cai no texto)

**Revisão, 2ª passada, "o que isto tornou falso?":**
- as regras de formatação no `AGENTS.md`, no `docs/erros.md`, na memória e no bloco de retomada;
- o número "baseline 7" no `PROGRESSO.md`;
- `sessoes.md` §15.4.

Varredura de caracteres de controle e de dados reais no diff. Commits 1a e 1b, push.

### Entrega 2 — versões travadas, CI e scanner

#### C6 — `uv.lock`
**Faz:**
- `uv lock` com os extras `dev` e `hardware`;
- `README.md`, `AGENTS.md` ("Comandos") e `CLAUDE.md`: instalar com `uv sync --locked --extra dev`, e `python -m pytest` continua. O `python -m pip` fica ou sai conforme o C1.

**✅:**
- `uv lock --check` → ok;
- venv nova no scratchpad com `uv sync --locked --extra dev` → `N passed`;
- `git diff --stat` → `uv.lock` + docs.

**🐞:**
- **Classe 3:** o `uv lock` resolvendo versões diferentes das instaladas hoje (google-genai mais novo) → comparar `uv export` com o `pip freeze` de hoje, e a suíte decide.
- `uv sync` removendo o `pip` → medido no C1.

#### C7 — CI
**Faz:**
- `.github/workflows/testes.yml`, conforme as decisões;
- `tests/test_ci_workflow.py`, que lê o YAML como texto e não precisa de dependência nova. Ele confere:
  - `uses:` com SHA de 40 hex;
  - `permissions: contents: read`;
  - nenhum `secrets.` nem `pull_request_target`;
  - `--locked`;
  - os comandos `pytest`, `ruff check`, `ruff format --check` e `pip-audit`;
- `.git-blame-ignore-revs` com o SHA do 1a.

**✅:**
- `python -m pytest tests/test_ci_workflow.py -q` verde;
- mutações: tirar `--locked`, trocar um SHA por `@v4`, `contents: write` → cada uma cai.

**🐞:**
- **Classe 2:** SHA de action copiado de memória → conferir por `gh api repos/actions/checkout/git/ref/tags/<tag>` e escrever a tag no comentário.
- **Classe 7:** o teste lê o YAML por regex e casa um comentário → recortar as linhas `uses:`.

#### C8 — alertas do Dependabot
**Faz:** eu **peço o ok na hora** e depois `gh api -X PUT repos/Zbreno11-git/LifeOs/vulnerability-alerts`.

**✅:**
- `gh api …/vulnerability-alerts -i` → `204`;
- `gh api …/dependency-graph/sbom` lista pacotes do `uv.lock` (sim/não, anotado com a data).

**🐞:**
- **Classe 2:** o grafo não ler o `uv.lock` → os alertas veem só o `pyproject`, e o `pip-audit` do CI cobre o lock. Isso vai escrito na D45.

#### C9 — tipos
**Faz:** o que o dono decidir no C1.
- **Portão:** consertar e pôr `mypy` no CI.
- **Backlog:** escrever em `sessoes.md` com o número e a data.

**✅ e 🐞:** definidos com o número. Não prometo o portão antes (sem limiar inventado).

#### C10 — fechar a entrega 2
**Mutações novas:** as 3 do C7 (esperado: 164, todas mortas; rodada completa em background, sem timeout).

**Docs:**
- D45 inteira: lock, CI, scanner, atualização, e as recusas (branch protection, PRs automáticos);
- `AGENTS.md`: estrutura (`.github/`, `uv.lock`), comandos, armadilha nova só se houver incidente;
- `sessoes.md`: ▶️ com a rotina de abertura ("há versão nova?"), §15.1 e §15.3 riscados;
- barra de progresso, diário (com "Erros desta sessão") e `PROGRESSO.md`.

**Revisão, 1ª passada:**
- O CI roda os mesmos portões que eu rodo aqui? Ler lado a lado o workflow e o "Comandos".
- O log público do CI mostra algo que não devia? Ler o log do 1º run.
- O que aparece se o lock ficar desatualizado? O `--locked` falha.

**Revisão, 2ª passada, "o que isto tornou falso?":**
- `python -m pip install` em `README.md`, `AGENTS.md`, `CLAUDE.md` e nas armadilhas do conda;
- "sem CI" no `sessoes.md` e no `scripts/mutacoes.py` (que diz "não no CI": continua verdade?);
- o roteiro-padrão do Mac em `docs/erros.md` classe 1.

Commit 2, push. **Fecha só com o run do CI do HEAD verde, conferido pelo `headSha`** (`gh run list --commit <sha>`), não com "a lista está vazia".

### Verificação ponta a ponta — C11, Mac (2º roteiro, depois do 1º teste)
```
cd ~/LifeOs
git pull && git log --oneline -1
source .venv/bin/activate
which python
uv pip list | wc -l
uv sync --locked --extra dev
which python
python --version
uv pip list | wc -l
uv pip list | grep -i -E '^(cryptography|google-genai|ruff) '
python -m pytest -q
viking browser --doctor
viking financas
viking chat
```
Esperado:
- o `uv sync` termina sem erro. Ele pode compilar o cryptography, o que leva alguns minutos, ou
  aproveitar o 50.0.1 já instalado;
- o `which python` é `~/LifeOs/.venv/bin/python` antes e depois, e o Python é o 3.13.5;
- a contagem cai (o `pip` e o que não está no lock saem);
- versões: `cryptography 50.0.1`, `google-genai 2.25.0`, `ruff 0.16.9`;
- `1553 passed`, sem pulados;
- o `--doctor` e o `viking financas` ficam como antes;
- no chat: `o que tenho amanhã?`, `/custos`, `sair`.

No GitHub (site): o commit do topo com ✅ nos dois Pythons; Security → Dependabot sem alerta aberto.

### Riscos e o que é irreversível
- **`uv sync` no Mac remove pacote que não está no lock** (exato por padrão). O que alguém instalou à mão na venv some. A contagem antes/depois mostra, e reinstalar é possível. O Jev tem venv própria e não é tocado.
- **O `.venv` do Mac pode ter sido criado pelo Python do conda,** e o `uv` pode recriá-lo. O `which python` e o `python --version` antes e depois mostram.
- **Ligar os alertas do Dependabot** muda uma configuração da conta do dono, embora reversível. Só com o ok na hora.
- **O log do CI é público** (repo público): nada de segredo no CI, nenhum `secrets.`, e o teste do C7 prende isso.
- **Custo:** Actions em repo público com runner padrão é de graça, segundo a documentação do GitHub (não medido aqui). Nenhum outro gasto.
- **`.env` do dono:** nunca tocado. Nenhuma variável nova nesta sessão.

## Plano — Sessão 6: o navegador com duas tarefas ao mesmo tempo (trava, protocolo, chaves, versão do Jev) (fechada em 2026-09-28)

### Context

**O que é a Sessão 6** (`sessoes.md`, auditoria do Codex §10.7, §10.10, §11.1, §11.2):
1. **Trava só dentro do processo** (`jev_runner._EXECUCAO = threading.Lock()`): dois `viking`
   (chat + `viking browser`, ou dois terminais) dirigem o mesmo Chrome ao mesmo tempo, e o
   `preparar_navegador` de um pode **reiniciar o daemon** no meio da tarefa do outro.
2. **Protocolo frouxo**: `parse_event` aceita qualquer dict com `"type"` no stdout.
3. **O Jev herda todo o ambiente do Viking** (`Popen` sem `env=`, `jev_runner.py:357`; e
   `cli._doctor` com `subprocess.call`) — inclusive `GEMINI_API_KEY` e `PLUGGY_CLIENT_SECRET`, que o
   `config.py:20` carrega do `.env` para `os.environ`.
4. **Nada confere a versão do clone do Jev** (o patch OpenRouter é um commit do fork).
+ o **primeiro passo adiado da 5**: no Mac, desfazer um reagendamento; e conferir o conserto do fuso.

**Entrega verificável (Mac):** (a) uma segunda tarefa (ou `--doctor`) com outra em curso é recusada
na hora dizendo "ocupado por … desde … (tarefa: «…»)"; (b) o daemon do Browser Harness, reiniciado
uma vez, **não** tem `GEMINI_API_KEY` no ambiente (contagem 1 antes, 0 depois — só o nome, nunca o
valor); (c) `viking browser --doctor` mostra ramo, commit, mudanças não salvas e "patch OpenRouter:
presente"; (d) `desfaz` de um reagendamento volta o horário exato; (e) "amanhã às 10h" cria às 10:00.

### Respostas do dono (2026-09-27)
| Pergunta | Resposta | Consequência |
|---|---|---|
| Outra tarefa rodando | recusar na hora, dizendo quem usa | trava sem espera (`LOCK_NB`), mensagem com origem, hora e objetivo |
| Chaves ao Jev | lista do que pode passar | allowlist; o resto não passa |
| Versão do Jev diferente | avisar, não bloquear | `--doctor` detalha; cada tarefa avisa 1 linha no stderr se o patch falta ou há mudança não salva |
| Teste adiado | só o reagendamento | convidado segue "não medido" |
| Tamanho | os 4, em 2 commits | commit 1 = trava + protocolo; commit 2 = ambiente + versão |
| `--doctor` com tarefa em curso | recusar, dizendo quem | o doctor pega a mesma trava |
| Objetivo na mensagem | sim, curto (~60), marcado não confiável | redigido, `neutralizar`, dentro de «» |

### Medido na abertura (2026-09-27, código em `cafe704`; levantamento lendo o clone e o `uv` daqui)
| O quê | Resultado | Consequência |
|---|---|---|
| Variável do ambiente do pai × `--env-file` (uv 0.12.10) | **o ambiente do pai vence** (`TYPESAFE_MODEL=FROM_PARENT` prevaleceu) | allowlist **não** passa `OPENROUTER_API_KEY`/`TYPESAFE_*`/`TEXT_MODEL*`: vêm só do `.env` do Jev (D7) |
| Daemon do Browser Harness | processo separado, `{**os.environ}` (BH/admin.py:562-588), sobrevive às tarefas | no Mac ele guarda o ambiente da 1ª tarefa: **reiniciar uma vez** e medir |
| Chrome no Mac | `open -a` (não herda ambiente); no Linux, Popen herda | allowlist leva `DISPLAY`/`WAYLAND_DISPLAY`/`XAUTHORITY`/`DBUS_SESSION_BUS_ADDRESS` |
| Variáveis que o Jev/harness leem | `BH_*`, `BU_*`, `BROWSER_HARNESS_HOME`, `XDG_*`, `HOME`, `PATH`, `CHROME_PATH`; httpx lê `HTTP(S)_PROXY`/`ALL_PROXY`/`NO_PROXY`/`SSL_CERT_FILE`/`SSL_CERT_DIR` | allowlist exata abaixo |
| stdout no caminho do runner | só `emit()`; Jev e harness: 0 escritas no caminho usado | protocolo estrito = defesa, não conserto: schema + nonce, sem canal dedicado |
| `.venv` do clone aqui | binário do Mac, não roda no VPS | tudo testado com dublês; o Jev real só no Mac |
| Testes que usam `_fake_cmd` | 7 em `test_browser_jev_runner.py` (baseline de formatação) | precisam emitir o nonce (previsto) |

### Decisões técnicas minhas
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Trava = `fcntl.flock(LOCK_EX\|LOCK_NB)` em `data/navegador.lock`, mantendo o `threading.Lock` antes (testes e rapidez) | o kernel solta a trava se o processo morrer: sem trava velha, sem limpeza | Windows: sem `fcntl` → só a trava do processo (trilha pausada), com aviso na doc |
| Dono da trava escrito **dentro** do arquivo (JSON: pid, origem, desde, objetivo redigido ≤60); o arquivo nunca é apagado | apagar abre corrida; o conteúdo só vale se a trava está presa | JSON lido pela metade → "outro processo do Viking (sem detalhes)" |
| O filho **não** herda a trava (`close_fds` padrão) | o daemon é filho do filho e a herdaria para sempre | se o Viking morrer por `SIGKILL`, o filho segue até o próprio `--timeout` (180 s): aceito e escrito |
| `busy` passa a mostrar o detalhe (`_COM_DETALHE`), neutralizado | o objetivo pode ter vindo de uma página via Gemini | — |
| Nonce por execução (`secrets.token_hex(8)`) via **variável de ambiente** `VIKING_JEV_NONCE` (não argv); todo `emit` o carrega; o pai descarta evento sem `schema == 1`, nonce igual, `type` conhecido e campos mínimos (`result.status`, `error.code` texto) | não aparece no `ps`; o fake de teste lê do mesmo jeito | — |
| Allowlist: `PATH HOME USER LOGNAME SHELL TMPDIR LANG TZ` + prefixos `LC_ XDG_ UV_ BH_ BU_ BROWSER_HARNESS_` + `CHROME_PATH` + proxy/certificado (`HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY` e minúsculas, `SSL_CERT_FILE SSL_CERT_DIR`) + Linux gráfico (`DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS`) + `VIKING_JEV_NONCE`. **Fora**: `VIKING_*` (exceto o nonce), `GEMINI_*`, `PLUGGY_*`, `GOOGLE_*`, `OPENROUTER_*`, `TYPESAFE_*`, `TEXT_MODEL*`, `VIRTUAL_ENV`, `CONDA_*`, `PYTHON*` | chave nova no futuro nasce bloqueada; `PYTHONPATH`/`VIRTUAL_ENV` do Viking não confundem o `uv` do Jev | o Mac mostrar que falta algo → acrescentar com o incidente |
| Versão do Jev: o que decide é o **conteúdo** (`jev_ultrafast/model.py` contém `openrouter.ai/api/alpha/decisions`), não o hash (um rebase do fork mudaria o hash); ramo/commit/"mudanças não salvas" são informativos | robusto a rebase | — |
| Sem `git` ou fora de repositório → "não consegui conferir a versão do Jev", nunca exceção | o aviso não pode derrubar a tarefa | — |

### Mapa de checkpoints
| C | Fecha quando | Estado |
|---|---|---|
| C0 | este plano no `PROGRESSO.md` (bloco ▶️ + plano), acima do da 5 | ✅ |
| C1 | trava entre processos + `--doctor` com a trava + mensagem "ocupado" | ✅ |
| C2 | protocolo estrito (schema + nonce + campos mínimos) | ✅ |
| C3 | mutações, docs, revisão em 2 passadas, **commit 1 + push** | ✅ |
| C4 | ambiente allowlisted no Jev e no `--doctor` | ✅ |
| C5 | versão do Jev no `--doctor` + aviso por tarefa | ✅ |
| C6 | mutações, docs, revisão em 2 passadas, **commit 2 + push** | ✅ |
| C7 | Mac: roteiro abaixo | ✅ (menos a data das finanças, adiada para a 7) |

### Commit 1 — trava e protocolo

#### C1 — trava entre processos
**Faz:** `src/lifeos/browser/trava.py` (novo; stdlib + `config.DATA_DIR`): `TRAVA_PATH`,
`Ocupado(pid, origem, desde, objetivo)`, gerenciador `ocupar(objetivo) -> Iterator[Ocupado | None]`
(None = é nossa; `Ocupado` = de outro, sem esperar), `descrever(Ocupado) -> str` ("ocupado por
viking chat desde 10:02 (tarefa: «…»)"). Escreve o dono **depois** de travar (truncate + write +
flush); objetivo com `_redacao.redigir` + `limpar_controles`, ≤60. `jev_runner.run_jev`: depois do
`dominio_bloqueado` e do `_EXECUCAO`, `with trava.ocupar(goals[0])` em volta de tudo que abre
subprocesso; ocupado → `_erro("busy", descrever(o), goals)`. `cli._doctor`: mesma trava; ocupado →
imprime e sai 2. `mensagens`: `busy` em `_COM_DETALHE`; texto novo ("Outra tarefa de navegador está
usando o Chrome agora… Não repita: espere ela terminar"). `conftest.py`: `TRAVA_PATH` em
`tmp_path` (autouse).
**✅:** `tests/test_browser_trava.py`:
- um **segundo processo de verdade** (`subprocess` com `python -c` que trava e dorme) segurando →
  `run_jev` devolve `busy` com "ocupado por cli desde" e o objetivo, e **nenhum** `Popen` do Jev;
- o processo que segurava é morto (`kill`) → a próxima tarefa roda (o kernel soltou);
- arquivo com JSON pela metade/lixo e trava presa → "sem detalhes", sem exceção;
- trava livre com conteúdo velho no arquivo → roda (o conteúdo não decide nada);
- objetivo com token/CPF e controle/bidi → redigido e limpo no arquivo e na mensagem;
- `--doctor` com trava presa → sai 2 sem chamar o `uv`;
- a trava é solta depois de exceção dentro do `with` e depois de `KeyboardInterrupt`;
- o subprocesso do Jev não herda o descritor da trava (`Popen` sem `pass_fds`; conferir `close_fds`).
Testes existentes de `busy` (`_EXECUCAO`) seguem verdes.
**🐞 Previsto → Depurar:** (classe 4) teste de concorrência com thread no mesmo processo
"passa" por outro motivo → usar **processo** separado; (classe 7) rótulo "origem" vazio quando
`registro.ORIGEM` não foi marcada (`desconhecida`) → mensagem "outro processo do Viking";
`data/` inexistente num clone novo → `mkdir(parents=True, exist_ok=True)`; fuso da hora "desde" →
`config.TIMEZONE` e teste com Brasília fixado.

#### C2 — protocolo estrito
**Faz:** `_jev_subprocess.emit` inclui `"nonce": os.environ.get("VIKING_JEV_NONCE", "")`.
`jev_runner`: `run_jev` sorteia o nonce e o põe no `env` do `Popen` (em C4 isso entra na allowlist;
em C1–C3, `{**os.environ, "VIKING_JEV_NONCE": n}`); `parse_event(linha, nonce)` exige dict,
`schema == 1`, `nonce` igual, `type` em `{start, health, step, liberado, result, error}`, e
`result.status`/`error.code` texto. Evento inválido é ignorado (conta como lixo; sem terminal válido →
`runner_crash`/`bad_output`, como hoje).
**✅:** `test_browser_jev_runner.py`: terminal forjado sem nonce, com nonce errado, com `schema: 2`,
com `type` desconhecido ou `error` sem `code` → ignorado; um `result` forjado **antes** do terminal
real não vence; os 7 testes com `_fake_cmd` passam a emitir pelo helper que lê o nonce do ambiente.
`test_jev_subprocess_main.py`: todo evento emitido carrega o nonce da variável.
**🐞:** os 7 `_fake_cmd` quebram de uma vez (previsto) → helper único `_evento(**campos)` no
prelúdio do script; `test_browser_jev_runner.py` está no **baseline de formatação** → só os meus
trechos do `ruff format --diff`; âncoras de mutação em `jev_runner` (`--goal=` e a URL redigida) →
`python -m pytest tests/test_mutacoes_ancoras.py` logo depois.

#### C3 — fechar o commit 1
Mutações (≥5): trava só intraprocesso (flock removido); `LOCK_NB` removido (esperaria — o teste com
processo real precisa de limite curto **no teste**, não no script); `--doctor` sem trava; nonce não
conferido; `schema` não conferido. `python scripts/mutacoes.py` em **background, sem timeout**.
Docs: D40 (trava e protocolo), `AGENTS.md` (estrutura `trava.py`; armadilha "a trava é do kernel,
não apague o arquivo"), `docs/fontes/jev-typesafe.md`/`browser-automation-stack.md` (concorrência),
diário, `PROGRESSO.md`. **Revisão pontual 1ª passada** — perguntas: *e se o processo morrer
segurando? e se dois abrirem no mesmo milissegundo? e se o arquivo tiver lixo?* (cada uma com o
teste que responde). **2ª passada:** *o que isto tornou falso?* — o texto `busy` antigo, docstring de
`run_jev` ("lock"), `AGENTS.md` sobre `_EXECUCAO`. Varredura de controles e de dados reais. Commit +
push.

### Commit 2 — ambiente e versão do Jev

#### C4 — ambiente allowlisted
**Faz:** `jev_runner.ambiente_do_jev(nonce="") -> dict` (allowlist da tabela; fonte única);
`_rodar` passa `env=`; `cli._doctor` também (e passa `--env-file` quando o arquivo existe, como o
`build_command`). Docstring com o porquê medido (o pai vence o `--env-file`).
**✅:** `tests/test_browser_ambiente.py`: com `GEMINI_API_KEY`, `PLUGGY_CLIENT_SECRET`,
`OPENROUTER_API_KEY`, `TEXT_MODEL_API_KEY`, `VIRTUAL_ENV`, `PYTHONPATH`, `CONDA_PREFIX`,
`VIKING_DB_PATH` no ambiente → nenhum no resultado; `PATH`, `HOME`, `LC_ALL`, `HTTPS_PROXY`,
`https_proxy`, `NO_PROXY`, `BU_NAME`, `BH_HOME`, `UV_CACHE_DIR`, `XDG_CONFIG_HOME`, `DISPLAY`,
`CHROME_PATH` → passam iguais; o `Popen` do runner recebe `env=` (dublê de `Popen` capturando
kwargs) e o `subprocess.call` do doctor também; um fake script que imprime **os nomes** das variáveis
que recebeu confirma de ponta a ponta (sem valores).
**🐞:** (classe 7) prefixo casando demais — `UV_` pega `UV_…` legítimo, mas `BU_` não pode pegar
`BUDGET_KEY`: casar `BU_` exato no começo, e teste com `BUDGET_SECRET` fora; lista de proxy só em
maiúsculas → minúsculas também (httpx lê as duas); no Mac falta algo → o roteiro C7 mede e eu
acrescento com o incidente.

#### C5 — versão do Jev
**Faz:** `src/lifeos/browser/versao_jev.py` (novo): `conferir(jev_dir) -> Versao(ramo, commit,
nao_salvas: int, patch: bool | None, erro: str)` via `git -C … rev-parse --abbrev-ref HEAD`,
`rev-parse --short HEAD`, `status --porcelain` (conta linhas), e leitura de
`jev_ultrafast/model.py` procurando `openrouter.ai/api/alpha/decisions`; `git` ausente/timeout
(5 s)/fora de repo → `erro`. `texto(v)` para o doctor; `aviso(v) -> str` (vazio se tudo certo; uma
linha se patch ausente, mudanças não salvas ou erro). `cli._doctor` imprime `texto` antes do doctor
do harness; `executar_no_navegador` (não silencioso) e `cli._browser` imprimem `aviso` no **stderr**.
Os `git` rodam com o ambiente allowlisted.
**✅:** `tests/test_browser_versao_jev.py` com um repositório git **de verdade** em `tmp_path`
(`git init`, commit com um `model.py` com e sem a URL): patch presente/ausente; arquivo alterado →
`nao_salvas == 1`; sem `.git` → erro legível; `git` fora do PATH (monkeypatch `shutil.which`/PATH) →
erro legível; `aviso` vazio no caso limpo; o aviso **não** vai para o texto do Gemini (sai no stderr).
**🐞:** `git status` listando o `.env`/`.venv` do clone como não salvo no Mac (se o `.gitignore` do
fork não os cobre) → o Mac mostra; se for ruído, contar só arquivos rastreados (`--untracked-files=no`)
— decidir com a saída real; `git` pedindo "safe.directory" (dono diferente) → cai em `erro`, texto
claro.

#### C6 — fechar o commit 2
Mutações (≥4): `GEMINI_` passa; `env=` removido do `Popen`; `env=` removido do doctor; patch
conferido por hash em vez de conteúdo não (substituir a leitura por `True`). D41 (ambiente e versão),
`AGENTS.md` (armadilha "o ambiente do pai vence o `--env-file`" e "o daemon guarda o ambiente da
primeira tarefa"), `docs/fontes/jev-typesafe.md` ("Egress": o que o Jev recebe), diário, erros,
barra, `sessoes.md`, `PROGRESSO.md`. **Revisão pontual 1ª passada:** *o que ainda chega ao Jev e ao
daemon?* (a lista inteira contra o levantamento); *o que quebra no Mac se faltar?* (uv, cache,
Chrome, proxy). **2ª passada:** *o que isto tornou falso?* — `docs/fontes/jev-typesafe.md` (egress),
`AGENTS.md` (D7 e chaves), `browser --doctor` na doc. Commit + push.

### Verificação ponta a ponta (C7, Mac)
```
cd ~/LifeOs
git pull && git log --oneline -1
pgrep -f browser_harness.daemon
ps -wwE -o command= -p "$(pgrep -f browser_harness.daemon | head -1)" | tr ' ' '\n' | grep -c '^HOME='
ps -wwE -o command= -p "$(pgrep -f browser_harness.daemon | head -1)" | tr ' ' '\n' | grep -c '^GEMINI_API_KEY='
source .venv/bin/activate
which python
python -m pytest -q
pkill -f browser_harness.daemon
viking browser --doctor
viking browser --url https://example.com --goal 'abrir a página'
ps -wwE -o command= -p "$(pgrep -f browser_harness.daemon | head -1)" | tr ' ' '\n' | grep -c '^HOME='
ps -wwE -o command= -p "$(pgrep -f browser_harness.daemon | head -1)" | tr ' ' '\n' | grep -c '^GEMINI_API_KEY='
viking browser --url 'https://www.youtube.com/results?search_query=lofi' --goal 'abrir o primeiro resultado' &
sleep 4
viking browser --doctor
wait
viking chat
```
(Revisto no C6, 2026-09-27: o `git pull` vem antes de qualquer medida — classe 1; `ps -wwE` e não
`ps eww`: no macOS `-e` é "todos os processos" e o ambiente é `-E`, então o `eww` daria 0 de
qualquer jeito — classe 4. O `HOME=` é o controle: tem de dar `1` nas duas medidas; se der `0`, o
`ps` não está mostrando o ambiente e a contagem do `GEMINI_API_KEY` não vale. URL com `?` entre
aspas. Se o primeiro `pgrep` não mostrar nada, o daemon não está de pé e o "antes" não se mede.)
Esperado: `HOME` `1`/`1`; `GEMINI_API_KEY` `1` antes e `0` depois (só o nome, nunca o valor); o
`--doctor` mostra "Jev em …", ramo, commit, "mudanças não salvas" e "patch OpenRouter: presente" antes
do diagnóstico do harness; nenhuma tarefa mostra linha "⚠️  Jev:" (se mostrar, colar: é a medida do
`git status` do clone do Mac); o segundo `--doctor` (com o YouTube rodando) diz "Não rodei o
diagnóstico: o navegador está sendo usado pelo terminal (viking browser) desde … (tarefa: «abrir o
primeiro resultado»)". No chat: `cria um evento Teste Viking amanhã às 10h` (conferir **10:00**) →
`muda o Teste Viking para as 11h` → `desfaz` (voltou às 10:00?) → `apaga o Teste Viking` → `sair`.

### Riscos e o que é irreversível
- `pkill` do daemon: inofensivo (a próxima tarefa o sobe de novo); o Chrome pode pedir "Allow remote
  debugging" de novo — clique do dono, como sempre.
- Allowlist estreita demais quebra o navegador no Mac → o roteiro mede na primeira tarefa; conserto
  é acrescentar a variável com o incidente.
- Nada escreve em conta de terceiros; o evento de teste é só "Teste Viking".

## Plano — Sessão 5: confirmação mecânica (registro de ações, MCP com aprovação, liberar um clique) (fechada em 2026-09-27)

### Context

**O que é a Sessão 5.** Três coisas do Viking agem hoje sem trava mecânica (auditoria do Codex §5
e §7; `sessoes.md`):
1. **O servidor MCP** apaga e reagenda eventos direto, a pedido de qualquer app ligado nele (§5.3).
2. **O freio de cliques** do navegador só bloqueia; D18 prometeu a liberação para esta sessão.
3. **Nada registra o que foi feito.** Uma ação acontece, a chamada seguinte ao Gemini falha, o
   dono vê só "❌ Erro", pede de novo — e a ação acontece duas vezes (§7, P0/P1).

A peça é a mesma da limpeza do Gmail (D26/D30): código que só o dono vê, ligado aos dados exatos,
uso único — mais um registro local do que foi pedido e feito, com desfazer.

**Entrega verificável (Mac):** (a) um app pelo MCP pede para apagar um evento e ele continua lá até
`viking aprovar`; (b) um "Sair" recusado pelo freio é liberado com `confirma NNNN` e o Viking faz
só aquele clique, uma vez; (c) um evento apagado no chat volta com `desfaz`; (d) `viking registro`
e "o que você fez hoje?" listam as ações, e um erro do Gemini depois de uma ação diz o que já foi
(ou pode ter sido) feito.

### O que NÃO faz
- Código no chat para apagar/reagendar/criar (dono: "exagero"); segue a trava do título + desfazer.
- Liberar clique de **dinheiro** (dono: sempre à mão).
- Idempotência automática (devolver "já criado"): cortada na revisão — responder do registro sem
  reler o Google mostraria evento fantasma; o aviso pós-erro + registro no chat cobrem o §7.
- Aprovação por elicitation do MCP / web; migrations formais (§12.6) → backlog.

### Respostas do dono (2026-09-27)
| Pergunta | Resposta | Consequência |
|---|---|---|
| Tamanho | as três partes, 2 commits | commit 1 = registro + calendário + MCP; commit 2 = navegador |
| Código no calendário (chat) | não ("exagero") | trava do título + desfazer |
| MCP apagar/reagendar | só propõe; aprova no terminal | `viking aprovar` |
| Chat × MCP | MCP mais rígido, confirmado | D36 |
| Desfazer | sim, `desfaz` recria/volta | cópia bruta do evento no registro |
| Registro | 30 dias; também no chat | purga automática; tool de leitura `acoes_recentes(dias)` |
| Liberar clique | com código | proposta na recusa |
| Categorias | sair e conta; dinheiro nunca | sem sinal de dinheiro em **lugar nenhum** do botão |
| Refazer | só aquele clique | abre a página da recusa e o Viking escreve o objetivo "clicar em «rótulo»" |
| Validade MCP | 1 hora | `propor(..., validade=)`; chat segue 10 min |

### Decisões técnicas minhas
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Código reservado só entre propostas que **ainda agem** (abertas válidas ou consumidas dentro da janela da ação), em todas as ações | 4 tipos de ação; reservar tudo por 8 dias vira negação de serviço | — |
| `vivo`/`acao_do_codigo` com a janela **de cada ação** (MCP: só aberta; navegador: sem desfazer) | "confirma 1234" não pode casar com dois | — |
| Tabela pequena `aprovacoes.TIPOS = {acao: (confirmar, desfazer, janela, so_terminal)}`; o **despacho** fica em `agent.py` e `cli.py` | mantém o sentido de `test_so_o_laco_do_chat_e_a_cli_confirmam` | — |
| `desfaz` sozinho tratado pelo laço (não pelo Gemini): desfaz a última ação de calendário **desta sessão do chat**; com limpeza do Gmail desfazível também, mostra as duas opções; `desfaz NNNN` segue Gmail | um e-mail com injeção não induz desfazer; é a palavra do dono | — |
| Registro = um gerenciador de contexto `with registro.acao(op, params, desfazer=bruto) as r:` com estados `iniciada → feita/falhou/incerta`; exceção ambígua (timeout/5xx depois do envio) ou linha `iniciada` sobrando = `incerta` ("pode ter sido feito") | um erro nem sempre é falha (o Google pode ter aplicado) | — |
| Tabela `acoes` no `viking.db`, `CREATE TABLE IF NOT EXISTS` + índice em `criada_em`, sem `PRAGMA user_version` (é dos lembretes) | colisão de versão | migrations formais |
| `ORIGEM`/`TURNO` por `contextvars`; no MCP, definido **por chamada**; padrão barulhento (`desconhecida`, e um teste proíbe) | AFC do google-genai roda no mesmo thread; FastMCP copia o contexto para o thread | — |
| `parametros` redigidos (`_redacao`); `desfazer` bruto, nunca mostrado nem mandado ao Gemini; código de confirmação **nunca** entra no registro | o registro alimenta a nota ao Gemini | — |
| Cópia para desfazer = item bruto do `events.get` (não o `Evento`, que perde descrição, fuso, `date`×`dateTime`) | restaurar fiel | — |
| Desfazer apagar: reler; se `cancelled` e o dono é organizador → `patch status=confirmed` (a doc do Google fala em restaurar cancelados); senão recriar cópia **sem convidados** e `sendUpdates="none"`, avisando "ID novo"; evento recorrente/instância ou de outro organizador → recusa explicada. Desfazer reagendamento só se o horário atual ainda é o que o Viking pôs, restaurando `start`/`end` exatos. Reivindicação atômica (`UPDATE … WHERE desfeita_em IS NULL`) | reconvidar manda e-mail em nome do dono; não medido | a medida no Mac (C10) |
| MCP: várias propostas abertas (não substitui), no máximo 5 abertas e 20 por hora | "aguardando" não pode sumir em silêncio | — |
| `viking aprovar` exige terminal interativo (stdin e stdout TTY) | um app com terminal (Claude Code) rodaria o comando e leria o código | D36 escreve o limite: protege de app sem terminal; para agente local é barreira de intenção |
| Liberação casa por `{esquema+host, categoria, rótulo normalizado (≤80)}`, produzida **pelo subprocesso** na recusa; cópia bruta só no banco/argv, cópia limpa para mostrar | normalização única; `data:` tem host vazio | — |
| Sem reproposta automática: se não chegou no botão, diz isso; uma nova recusa gera nova proposta | reproposta ampla demais | — |
| `build_command` com `--goal=…`/`--url=…` e `allow_abbrev=False` no subprocesso | texto do Gemini nunca vira `--liberar-uma` | — |

### Medido na abertura (2026-09-27, código em `34d680f`)
| O quê | Resultado | Consequência |
|---|---|---|
| Jev pausa na recusa? | não: `AcaoSensivel` encerra `run()`; nova execução abre aba nova | liberar = nova execução curta |
| Id da ação entre execuções | posicional; decisão do OpenRouter não determinística | casar por host+categoria+rótulo |
| Ordem das categorias no freio | sair → conta → dinheiro (`_acoes_sensiveis.py:260-269,298-302`) | "Sair e pagar" seria "sair": checar dinheiro à parte |
| stdout do MCP | canal JSON-RPC | nunca imprimir no `server.py` |
| `propor` | substitui abertas da mesma ação; reserva 8 dias | parâmetros `validade=`, `substituir=` |
| `store.complete` | chamado direto de `agent.py:106` e `server.py:156` | criar `reminders/service.concluir` |
| `nota_pendente = nota or nota_pendente` (`agent.py:294`) | guarda uma nota só | juntar notas |
| Âncoras de mutação atingidas | `agent.py` ×6, `confirmacao.py` ×5, `calendar/service.py` ×2, MCP ×1, freio ×6 | reescrever no mesmo passo |

### Mapa de checkpoints
| C | Fecha quando | Estado |
|---|---|---|
| C0 | adiados no backlog; linha em branco quebrada em `docs/erros.md` (classe 7); `docs/fontes/google-calendar-api.md` com o que a doc diz sobre restaurar evento ("não medido; validar no Mac") | ✅ |
| C1 | confirmação genérica + `desfaz` local + notas juntas; Gmail igual | ✅ |
| C2 | registro (gerenciador de contexto, estados, purga, redação) + ganchos nos serviços + `reminders/service.concluir` | ✅ |
| C3 | chat: aviso pós-erro, `desfaz` do calendário, `acoes_recentes`; `viking registro [--desfazer ID]` | ✅ |
| C4 | MCP propõe; `viking aprovar` (TTY, releitura, 1 h, limites) | ✅ |
| C5 | mutações, docs, revisão em 2 passadas, **commit 1 + push** | ✅ |
| C6 | subprocesso: recusa estruturada, `--liberar-uma` de uso único, dinheiro recusado em qualquer sinal | ✅ |
| C7 | pai: proposta, código só ao dono (TTY), aprovação no chat e no `viking browser`, execução curta | ✅ |
| C8 | mutações, docs, revisão em 2 passadas, **commit 2 + push** | ✅ |
| C9 | Mac: roteiro abaixo | ✅ 2026-09-27 (e o conserto do fuso, D39) |

### Commit 1 — registro, calendário e MCP

#### C1 — confirmação genérica
**Faz:** `confirmacao.propor(acao, dados, *, validade=VALIDADE, substituir=True)`; reserva de
código só entre propostas que ainda agem; `acao_do_codigo(codigo)`; `vivo` pela janela da ação.
`src/lifeos/aprovacoes.py` (`TIPOS`). `agent.aprovacao_local` itera os tipos do chat; código de
proposta do MCP digitado no chat → "esse código é do `viking aprovar`", sem ir ao Gemini; `desfaz`
sozinho → desfaz do calendário (C3) ou as duas opções. `nota_pendente` junta notas.
**✅:** `python -m pytest -q tests/test_confirmacao.py tests/test_gmail_aprovacao.py` verde; só
`test_so_a_palavra_ganha_a_instrucao_aqui` muda (de propósito, parametrizado); novos: código não
casa entre ações; reserva não trava com propostas substituídas; validade 1 h.
**🐞 (classes 6 e 7):** vizinho esquecido na regra genérica → lista escrita de vizinhos/disfarces
antes (frase livre com código de outra ação; "desfaz" com e sem Gmail aberto); âncoras de
`agent.py` → `python -m pytest tests/test_mutacoes_ancoras.py` logo após editar; não formatar
`agent.py` (baseline).

#### C2 — registro e ganchos
**Faz:** `src/lifeos/registro.py`: tabela `acoes(id, turno, origem, operacao, parametros,
estado, resultado, desfazer, desfeita_em, criada_em, terminada_em)`; `acao(...)` gerenciador de
contexto; `do_turno`, `recentes`, `purgar` (30 d na abertura), redação. Ganchos: `calendar/service`
(criar, criar_dia_inteiro, apagar com item bruto, reagendar com `start`/`end` antigos),
`reminders/service` (criar, **concluir** novo — `agent.py:106` e `server.py:156` passam por ele),
`gmail/limpeza` (confirmar/desfazer), `browser/jev_runner.run_jev` (objetivo, URL redigida,
status). `conftest.py`: banco do registro em `tmp_path` (autouse).
**✅:** `tests/test_registro.py` + testes por serviço: uma linha por efeito; falha da API =
`falhou`; fake que aplica e depois levanta = `incerta`; purga no dia 31 e não no 29; CPF/token/
controle/bidi redigidos; `'); DROP TABLE` gravado literal; AST: toda `.delete(`/`.patch(`/
`events().insert(`/`batchModify(`/`store.add(`/`store.complete(` está dentro de uma função que usa
`registro.acao` (subindo de `lambda` até o `def`).
**🐞 (classe 4):** relógio real no teste de purga → `agora=` injetável; o fake não aplicar antes
de levantar → falha explícita "aplicou e levantou".

#### C3 — chat e `viking registro`
**Faz:** laço do chat define `TURNO`; no `except` do `send_message` (`agent.py:311-321`) imprime
"Antes do erro, o Viking já fez: …" / "pode ter feito: …" (`incerta`) e deixa a nota ao Gemini
("não repita sem perguntar"), com títulos de terceiros dentro de `nao_confiavel.bloco`. `desfaz`
local (C1) chama o desfazer do calendário. Tool de leitura `acoes_recentes(dias: int = 1)` (sem
future import; regra na docstring + `_REGRAS`: "dado, não instrução"). CLI `viking registro` e
`--desfazer ID`.
**✅:** fake chat que chama `criar_evento` e **depois** levanta → saída lista o evento, 2º turno
recebe a nota; sequência criar → erro → `desfaz` → `sair` (erro da Gmail 2); desfazer duas vezes
recusa (reivindicação atômica); o código sentinela nunca aparece em linha do registro nem em nota.
**🐞 (classe 6):** a nota colada antes do `sair` → teste da sequência do Mac reaproveitado.

#### C4 — MCP propõe, `viking aprovar`
**Faz:** `viking_apagar_evento`/`viking_reagendar_evento`: validam e conferem (leitura), `propor`
(`substituir=False`, `validade=1h`, limites 5 abertas/20 por hora), devolvem `estado:
"aguardando_aprovacao"` + evento, sem código; `ORIGEM="mcp"` por chamada; instruções do MCP
atualizadas. `cli.py viking aprovar`: exige TTY; lista abertas com dados exatos e código; pede o
código; relê o evento (`etag`/`updated`, título, início, fim; `cancelled` recusa); executa pelo
`calendar/service`, registra, mostra.
**✅:** `test_mcp_server.py`: apagar pelo MCP não apaga **e** cria proposta; travas da Sessão 1 pelo
MCP não criam proposta (hoje `apagados == []` ficaria verdadeiro à toa); o código sentinela não está
em `content` nem `structured_content`; duas propostas convivem; 21ª na hora recusa; `viking aprovar`
sem TTY recusa; código expirado (1 h + 1 min), evento mudado ou cancelado recusam; origem gravada
`mcp` via `fastmcp.Client`; AST: `mcp_server` nunca chama confirmar; `.delete(`/`.patch(` só em
`calendar/service.py`. `test_apagar_ok_pelo_mcp` muda de sentido (documentado no commit).
**🐞 (classe 2):** `print` no `server.py` corrompe o protocolo → teste em memória pega; nunca
imprimir lá.

#### C5 — fechar o commit 1
Mutações novas (≥10): MCP apaga direto; código de outra ação aprova; reserva conta substituídas;
validade ignorada; evento mudado aprovado; `aprovar` sem TTY; registro sem redação; purga cedo;
`incerta` vira `feita`; pós-erro não lista; desfazer duas vezes; nota perdida. `python
scripts/mutacoes.py` sem `timeout` → todas pelo teste esperado. Docs: D36 (chat×MCP + limite do
TTY), D37 (registro 30 d, desfazer, sem idempotência automática), D30 com gatilho novo;
`AGENTS.md` (estrutura, `viking aprovar`/`viking registro`, armadilha "stdout do MCP"),
`docs/fontes/fastmcp.md`, diário, erros, `sessoes.md`, `PROGRESSO.md`. Revisão (roteiro
`referencia/revisao.md`): 1ª "e se esta escrita chegar duas vezes?" em cada uma; 2ª "o que isto
tornou falso?" (âncoras, textos do MCP, docstrings, `_REGRAS`). Varreduras de controles e de dados
reais. Commit + push.

### Commit 2 — liberar um clique

#### C6 — subprocesso
**Faz:** `_acoes_sensiveis.sinais(acao, guard) -> set[str]` (todas as categorias que casam, no
rótulo, no contêiner e no `href`), `motivo` inalterado por fora. `_frear`: `AcaoSensivel` leva
`{esquema_host, categoria, rotulo}`; o evento `error` ganha o campo `acao_sensivel`.
`--liberar-uma=JSON`: o primeiro clique recusado que casa **exato** e sem nenhum sinal de
`dinheiro` passa, emite `liberado`, a liberação acaba; `dinheiro` no argumento, JSON malformado ou
host vazio fora de `data:` → `protecao-indisponivel` antes de navegar. `allow_abbrev=False`.
**✅:** `test_jev_subprocess_main.py`: clica uma vez; segundo sensível recusa; outro host/porta/
esquema, outro rótulo ("Sair" × "Sair de todos os dispositivos"), outra categoria → recusa;
"Sair e pagar" e contêiner de checkout → recusa; primeiro sensível não casa → recusa e liberação
gasta; contratos com o Jev real verdes (suíte com o clone).
**🐞 (classe 7):** normalização divergente → a impressão digital sai do subprocesso e volta intacta.

#### C7 — pai
**Faz:** `jev_runner`: `--goal=`/`--url=`; `result_from` lê `acao_sensivel` (cópia limpa passa por
`_higienizar`). `executar_no_navegador`: na recusa liberável e com terminal interativo,
`propor("navegador.clique", {url_da_recusa, esquema_host, categoria, rotulo})` e mostra ao dono
(`_ao_dono`) site, botão, categoria e "vou abrir esta página e clicar só neste botão"; ao Gemini, o
texto sem código. `dinheiro` e `--json`/sem TTY → sem proposta. Aprovar (laço do chat ou
`viking browser`, molde `_arquivar`) = `run_jev(url_da_recusa, ["clicar no botão «rótulo»"],
liberar=...)` — objetivo escrito pelo Viking; se não achar o botão, diz isso. Registro da execução.
**✅:** `tests/test_browser_liberacao.py`: código nunca no texto da tool nem no fake Gemini;
argv com `--liberar-uma` exato e objetivo do Viking (nada do objetivo original); objetivo/URL
iguais a `--liberar-uma=…` não liberam; AST: só o caminho de aprovação passa `liberar=`; sem TTY,
nenhuma proposta.
**🐞 (classe 6):** nota/`sair` depois da aprovação → reusar o teste da sequência do Mac.

#### C8 — fechar o commit 2
Mutações (≥7): outro host/rótulo/duas vezes; sinal de dinheiro ignorado quando a categoria é
sair; `--goal` sem `=`; código ao Gemini; objetivo original na reexecução; proposta sem TTY. D38
(liberação; D18 reescrita). Docs (`jev-typesafe.md`, freio), diário, erros, barra, `sessoes.md`,
`PROGRESSO.md`. Revisão em 2 passadas. Commit + push.

### Verificação ponta a ponta (C9, Mac)
```
git pull && git log --oneline -1
source .venv/bin/activate
which python
python -m pytest -q
viking chat
```
No chat: criar "Teste Viking" amanhã 10h → apagar → `desfaz` (voltou com o mesmo ID?) → "o que
você fez hoje?" → `sair`. Depois `viking registro`. MCP: um `python -c` com `fastmcp.Client`
chamando `viking_apagar_evento` no evento de teste (colado pronto) → evento continua →
`viking aprovar` → código → apagado. Navegador: `viking browser` numa página `data:` com um botão
"Sair" → recusa com código → digitar → clica uma vez. Medir no Mac: `get` depois do delete dá
`cancelled`? `patch status=confirmed` devolve o mesmo ID? (decide D37).

### Riscos e o que é irreversível
- Apagar evento no Mac: só "Teste Viking".
- Clique liberado: só em página `data:`, nunca numa conta real.
- Restaurar evento pela API: não medido → fallback recria sem convidados e diz "ID novo".

## Plano — Sessão Pluggy: finanças no chat, só leitura (fechada em 2026-09-27)

### O que entrega
No `viking chat`: "quanto tenho?", "quanto gastei este mês e em quê?", "paguei o aluguel?",
"quanto está a fatura?" — respondidos com dados da Pluggy consultados na hora, sempre dizendo de
quando é a última sincronização. `viking financas --saldo/--gastos/--buscar/--fatura` faz o
mesmo sem o Gemini.

### O que NÃO faz
Cópia local e RAG (decisão do dono: consultar toda vez); MCP (decisão do dono); categorização
própria ou pela Enrichment API; alertas; qualquer escrita (PIX, mudar categoria).

### Respostas do dono (2026-09-27)
| Pergunta | Resposta | Consequência |
|---|---|---|
| O que perguntar | saldo, gastos do período, buscar transação, fatura | 4 tools |
| O que vai ao Gemini | valores e descrições | descrição redigida (regra das páginas) e no bloco de não confiável; nunca `paymentData`, número de conta, CPF do titular |
| Onde fica | consultar toda vez | nada financeiro gravado em disco |
| Acesso | só no chat | teste que o MCP não expõe |

### Decisões técnicas minhas
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Sentido pela `type`, valor sempre positivo | o sinal muda entre conta e cartão (medido) | — |
| Movimento entre contas próprias e investimentos fora do "gasto", mostrado à parte | senão a fatura paga conta duas vezes (medido) | o dono querer ver tudo junto |
| PIX/transferência para outros conta como gasto, em linha própria | é dinheiro que saiu; separado para não parecer compra | o dono decidir que não é gasto |
| Data depois de hoje fora do "gasto do mês", contada à parte ("parcelas futuras") | 45 parcelas pendentes até 2027 (medido) | — |
| Dia da transação no fuso do Viking | a data vem em UTC | — |
| Categoria em português por `/categories` (`descriptionTranslated`), guardada no processo | a taxonomia é da Pluggy, não dado do dono | — |
| `lifeos/financas/service.py` (dados) + `tools.py` (texto do Gemini), como o Gmail | fonte única e testável | — |

### Checkpoints
| C | Fecha quando | Estado |
|---|---|---|
| C1 | `service.py`: contas, transações (cursor, período), normalização e classificação + fake no formato medido + testes | ✅ 54 testes |
| C2 | respostas: saldo, gastos, busca, fatura (`tools.py`) + testes de conta (sinal, parcelas, dobra) | ✅ 43 testes |
| C3 | 4 tools no chat (sem future import, regras nas docstrings) + testes de segurança (sem documento/número, injeção na descrição no bloco, MCP sem finanças) | ✅ |
| C4 | `viking financas --saldo/--gastos/--buscar/--fatura` + testes | ✅ |
| C5 | mutações novas mortas; suíte; ruff; baseline 7 | ✅ 71/71 |
| C6 | docs + revisão em duas passadas + commit + push | ✅ |
| C7 | Mac: as quatro perguntas no CLI e no chat, conferidas com o app do banco | ✅ |

### 🐞 Previsto → Depurar
- Total de gasto que não bate com o app do banco → primeiro o sinal por tipo, depois fatura paga
  em dobro, depois parcela futura (as três armadilhas medidas).
- Mês "errado" nas bordas → data em UTC; converter para o fuso antes de agrupar.
- Categoria vazia → "sem categoria", nunca some da soma.

## Plano — Sessão Gmail 2: limpar a caixa (só arquivar, lista aprovada)

### O que entrega (verificável)
No `viking chat`, o dono pede "arquiva tudo do remetente X e Y"; o Viking imprime **direto no
terminal** a lista exata (quantos de cada remetente, quantos protegidos e por quê) e um código;
o dono digita `confirma NNNN` e só então os e-mails saem da caixa de entrada. `desfaz NNNN`
devolve exatamente os mesmos por 7 dias. O Gemini nunca vê o código e não tem ferramenta que
arquive.

### O que NÃO faz
- Lixeira, apagar, marcar como lido, descadastrar → fora por decisão do dono (D23).
- Regra automática / filtro do Gmail → fora (D25: por remetente).
- Expor pelo MCP → fora (D21).
- Liberar o freio de cliques e o token de exclusão do calendário → Sessão 5 (já escrito lá); esta
  sessão entrega o mecanismo de confirmação que a Sessão 5 reaproveita.

### Respostas do dono
| Pergunta | Resposta | Consequência |
|---|---|---|
| Como escolher | por remetente, a partir do raio-x | tool recebe endereços exatos, não consulta livre |
| O que sai | todos da caixa de entrada, lidos ou não | seleção `from:X in:inbox`, sem filtro de data |
| O que nunca sai | estrela, importante, anexo | filtrado na consulta **e** conferido de novo no cliente |
| Como aprovar | digitando código mostrado no terminal, fora do Gemini | interceptação da linha no laço do chat; nenhuma tool de confirmar |
| Desfazer | sim, por 7 dias | registro local dos IDs arquivados |
| Teto por aprovação | **250** (D28, revista: era 1000; cota do Gmail) | uma chamada `batchModify`; acima disso, os mais antigos de cada remetente, na ordem pedida, e o texto diz quantos sobraram |
| Permissão maior | seguir com `gmail.modify` sabendo que ele autoriza enviar/lixeira (D29) | teste que proíbe essas chamadas no código |

### Decisões técnicas minhas
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Escopo `gmail.modify` no lugar de `readonly`, mesmo token | modify cobre leitura; a conferência de escopo de `google_auth` já força o login novo | — |
| Nunca `https://mail.google.com/` (acesso total, apaga de vez) | o Viking não precisa apagar | — |
| `lifeos/confirmacao.py` genérico (SQLite em `viking.db`, tabela `confirmacoes`): código de 4 dígitos (`secrets`), ligado à ação + dados, expira em 10 min, consumido uma vez; proposta nova invalida as abertas | é o mecanismo que a Sessão 5 reaproveita; uma proposta nova no meio do turno não deixa um código velho valer para outra lista | o dono querer várias propostas abertas |
| A tool `preparar_limpeza` imprime a lista e o código **no terminal** e devolve ao Gemini só a contagem e "o usuário confirma no terminal" | e-mail com injeção pode fazer o Gemini propor, nunca aprovar | — |
| `confirma NNNN` / `desfaz NNNN` interceptados no laço do chat **antes** do Gemini, executados localmente; o resultado vai ao Gemini como nota no próximo turno, sem o código | não existe caminho do Gemini até a escrita | — |
| Endereço validado por regex estrita antes de montar a consulta; e o remetente de cada e-mail conferido **igual** ao endereço no cliente | a busca `from:` do Gmail casa por pedaço; `a@b.com OR in:anywhere` ampliaria a seleção | — |
| Proteções conferidas duas vezes: `-is:starred -is:important -has:attachment` na consulta + rótulos `STARRED`/`IMPORTANT` e a lista de `has:attachment` no cliente | uma camada falhar não arquiva o protegido | — |
| Na confirmação, refazer a seleção e **intersectar** com os IDs aprovados | ganhou estrela depois → fica; chegou depois → não entra | — |
| `users.messages.batchModify` com **só** `removeLabelIds: ["INBOX"]`, em lotes de ≤ 1000; desfazer = `addLabelIds: ["INBOX"]` nos IDs registrados | é o "arquivar" do Gmail; reversível | — |
| `viking gmail --arquivar END[,END]` (pede o código no próprio terminal) e `--desfazer CODIGO` | validar no Mac sem o Gemini | — |
| A lista impressa mostra, por remetente: quantos saem, quantos ficam e por quê, e até 3 assuntos recentes | o dono lê a lista inteira sem ler 500 linhas | o dono pedir linha por e-mail |

### Medido na abertura (2026-09-26)
| O quê | Como | Resultado | Consequência |
|---|---|---|---|
| Laço do chat | `assistant/agent.py:182-200` | toda linha vai para `chat.send_message` | a interceptação entra antes da linha 194 |
| Fake do Gmail | `tests/conftest.py:150` | `list` ignora `q` | o fake ganha um avaliador mínimo (`from:`, `in:inbox`, `has:attachment`, `is:starred`, `is:important`, negação) e `batchModify` |
| Escopo atual | `gmail/oauth.py:12` | `gmail.readonly` | troca na Etapa 1.1 |
| Caixa real | raio-x no Mac | 200 (piso) de 91 remetentes em 30 dias | a primeira limpeza real sai dessa lista |

### Mapa de checkpoints
| C | Fecha quando | Estado |
|---|---|---|
| C0 | teto respondido e escrito aqui e em `docs/decisoes.md` — D28, D29; Pluggy logo depois da Gmail 2 | ✅ |
| C1 | escopo `modify` + textos "só leitura" ajustados; suíte 530+ verde — suíte 547 | ✅ |
| C2 | `confirmacao.py` + `tests/test_confirmacao.py` (código único, expira, consumido uma vez, proposta nova invalida a velha) — 17 passed | ✅ |
| C3 | `service.selecionar/arquivar/desfazer` + fake com consulta e `batchModify` + `tests/test_gmail_limpeza.py` — 31 passed, suíte 578 | ✅ |
| C4 | tool `preparar_limpeza` + interceptação no chat + testes de segurança (código nunca no texto do Gemini; injeção no remetente; nada sai sem código) — 24 testes em `test_gmail_aprovacao.py` | ✅ |
| C5 | `viking gmail --arquivar/--desfazer` + testes de CLI — 5 testes de CLI no mesmo arquivo; suíte 606 | ✅ |
| C6 | mutações novas mortas; suíte, `ruff`, baseline 7, varredura de controles — 41/41 mortas; ruff limpo; baseline 7; varredura 0 | ✅ |
| C7 | docs + revisão em duas passadas + commit + push — 3 achados na 1ª passada, docs velhos na 2ª | ✅ |
| C8 | Mac: arquivar, desfazer e aprovar pelo chat — 71 arquivados, 71 devolvidos, 71 arquivados de novo; código nunca no Gemini (2316f25) | ✅ |

### Fase 1 — escopo e confirmação
**1.1** `gmail/oauth.py` → `gmail.modify`; `cli.py` e docstrings deixam de dizer "só leitura";
tool `raio_x_da_caixa` deixa de dizer "não ofereça limpar". ✅ suíte verde; teste novo
`SCOPES == [gmail.modify]` e nenhum `mail.google.com`. 🐞 teste de login antigo falha por texto
"só leitura" → ajustar a mensagem, não o teste de escopo (classe 4).

**1.2** `lifeos/confirmacao.py`: `propor(acao, dados) -> Proposta(codigo, expira)`,
`consumir(codigo, acao) -> dados` (erros `CodigoInvalido`/`Expirado`/`JaUsado`),
`registrar(codigo, resultado)`, `buscar_executada(codigo)` para o desfazer. ✅
`test_confirmacao.py` verde. 🐞 relógio: injetar `agora` nos testes, nunca `sleep`.

### Fase 2 — serviço
**2.1** `service.selecionar(enderecos) -> Selecao(por_remetente, protegidos por motivo, ids)`:
valida endereços, uma consulta por remetente, metadados em lote (reaproveita `_metadados`,
`Email` ganha `estrela`/`importante`), remetente exato, lista de `has:attachment`.
**2.2** `service.arquivar(ids)` / `service.desfazer(ids)` via `batchModify`, em lotes de ≤ 1000;
falha no meio → diz quantos foram e quantos não (nunca "arquivei" parcial em silêncio).
✅ `test_gmail_limpeza.py` verde. 🐞 fake ignorando a consulta faria o teste de proteção passar
à toa → o fake avalia a consulta e o teste confere o corpo de cada `batchModify` (classe 4).

### Fase 3 — chat e CLI
**3.1** `tools.preparar_limpeza(remetentes: str)` (sem future import) → imprime a proposta e o
código; devolve a contagem sem o código. **3.2** `agent.py`: `confirma NNNN`/`desfaz NNNN` antes
do `send_message`. **3.3** `viking gmail --arquivar/--desfazer`. ✅ testes de segurança e de CLI.
🐞 print da tool indo para o Gemini: não vai (AFC só lê o retorno), mas o teste prova com um
código sentinela ausente do retorno e presente no stdout.

### Riscos e o que é irreversível
- Arquivar é reversível (desfazer por 7 dias e, depois disso, "Todos os e-mails"). Nada apaga.
- É a primeira escrita do Viking na conta do dono: a validação no Mac começa com **um**
  remetente de newsletter escolhido por ele, conferido no Gmail antes do chat.
- Login novo com permissão maior. **Medido em 2026-09-26** na descrição `gmail.v1.json` instalada:
  `gmail.modify` é descrito como "Read, compose, and send emails from your Gmail account" e
  autoriza `send`, `trash`, `import`, `insert` e `drafts.send`; não autoriza `delete` nem
  `batchDelete` (apagar de vez). Não há escopo menor que tire e-mail da caixa. O Viking não chama
  nada disso: a Etapa 1.1 ganha um teste que lê o código de `gmail/` e falha se aparecer chamada
  a `send`, `trash`, `import`, `insert`, `delete` ou `drafts`. Dizer isso ao dono antes do login.
