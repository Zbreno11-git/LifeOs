# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-28, Sessão 6: fusos medidos e consertados; falta o dono pôr o fuso e conferir

**Estado do repositório:** o commit "Sessão 6: o dono não está em Brasília" (conferir com `git log -1`;
o anterior é `b52b3b8`) · igual ao remoto · travas: nenhuma · background: nenhum.

**Onde parou:** C0–C6 ✅; C7 rodado no Mac (2026-09-27) e o C7-bis (2026-09-28) mediu os fusos:
relógio do Mac em -08:00, agenda do Google em `America/Sao_Paulo`, sem `VIKING_TIMEZONE`, e o dono
**não** está em Brasília (ver memória do Claude, "Fuso do dono"; a cidade não vai para o repo).
Consertado: D42 revista, D43, D44. `1118 passed`; `ruff` limpo; baseline 7; mutações 157/157.

**Próximo passo exato (C7-ter, depende do dono):** o roteiro da resposta de 2026-09-28 (segunda
parte). Conferir: (1) a linha "⚠️  Fuso: sem VIKING_TIMEZONE…" aparece no chat **antes** de ele pôr a
variável; (2) depois de `VIKING_TIMEZONE` no `.env` dele, `python -c` mostra o fuso dele e o aviso
some; (3) "amanhã às 10h" → o Viking diz 10:00, a busca seguinte diz 10:00 (convertida), e a agenda
do Google (em São Paulo) mostra o horário correspondente de Brasília; (4) as datas de
`viking financas --gastos` batem com o app do banco (ele confere e diz, sem colar valores). Com
tudo certo: fechar a Sessão 6 — diário, barra de progresso, `sessoes.md` (▶️ para a 7), este bloco.

**Medido no Mac (2026-09-28, `4d5e48b`, `1118 passed`):** com `VIKING_TIMEZONE` no `.env`, o fuso
do Viking é `America/Los_Angeles …-07:00` e "amanhã às 10h" caiu às 14:00 da agenda (-03:00) = 10:00
do dono ✅; `VIKING_TIMEZONE= viking chat` mostrou "⚠️  Fuso: sem VIKING_TIMEZONE… (-08:00)… agenda
em America/Sao_Paulo (-03:00)" ✅ (o token renovado em silêncio); "eventos de amanhã" trouxe a reunião
das 13:00 da agenda às **09:00** ✅. A listagem que tinha dito "14:00" era do Mac ainda em
`b52b3b8` (confirmado pelo `git pull` desta rodada). **Falta só:** o dono comparar as datas de
`viking financas --gastos` com o app do banco.

**Reler, nesta ordem:** `CLAUDE.md`/`AGENTS.md` (armadilha "Três fusos"); este bloco;
`docs/decisoes.md` (D39 revista, D40–D44); `docs/erros.md` (classes 2 e 4, 2026-09-28);
`calendar/service.no_fuso_do_dono`, `calendar/tools.aviso_de_fuso`, `financas/service.FUSO_DOS_BANCOS`,
`google_auth.credenciais_sem_login`, `_jev_subprocess._revisitando`.

**Não pode ser esquecido:**
- Nunca presumir o fuso do dono; "criei às 10:00" do Gemini não é medida (conferir na busca/agenda).
- Repo público: nada de cidade, conta ou valor real; o `.env` é do dono (ele acrescenta a linha).
- Roteiro do Mac começa com `cd ~/LifeOs` e `git pull && git log --oneline -1`; URL com `?` entre aspas.
- Mutações em background, sem `timeout`; baseline 7 (`agent.py`, `calendar/tools.py` nele).

**Depende do dono:** o roteiro e a conferência das datas no app do banco.

**Antes de confiar neste bloco:** `git status --short` vazio; `ls .mutacao.lock` → não existe;
`python -m pytest -q` → `1118 passed`; `python -m ruff format --check . | tail -1` → `7 files would
be reformatted`.

## Plano — Sessão 6: o navegador com duas tarefas ao mesmo tempo (trava, protocolo, chaves, versão do Jev)

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
| C7 | Mac: roteiro abaixo | ⬜ |

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
