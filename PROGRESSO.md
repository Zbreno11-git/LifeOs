# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-29, Sessão 10 em curso (C0)

**Estado:** `git log --oneline -3` e `git status --short` · travas: nenhuma · background: nenhum.
Base da abertura (2026-09-29): `1884 passed`, CI de `26ddc71` verde.

**Onde parou:** plano da 10 aprovado pelo dono (abaixo); C0 em curso.

**Próximo passo exato:** o primeiro checkpoint ⬜ do mapa abaixo.

**Reler, nesta ordem:** `CLAUDE.md`/`AGENTS.md`; este bloco e o plano abaixo; `sessoes.md` (10 e
10b); `docs/decisoes.md` D47 (revista) e D58; skills `nuvem-e-deploy`, `seguranca`,
`dados-e-banco`.

**Não pode ser esquecido:**
- o VPS tem o `gcloud` logado com a conta do dono (decisão dele: usar), então **todo** comando do
  `gcloud` leva `--project` do Viking; nunca o projeto padrão da configuração, que é outro projeto
  dele;
- o ADC do dono está vivo no VPS: nenhum teste constrói cliente de nuvem sem o emulador;
- criar recurso ou gastar = pedir o ok do dono naquele passo; o local do Firestore é irreversível;
- nenhum ID de projeto, URL ou conta de serviço no repo (vão no `.env`);
- migração publicada não se edita;
- mutações em background, sem timeout;
- nunca presumir o fuso: o dono volta ao Brasil em ~1 mês.

**Depende do dono:** os ok's de C2 (repo privado), C3 (cada recurso) e C6 (deploy); o teste do
Mac (C9); a prova do token do Gmail depois de 2026-10-03 (primeiro passo da 10b).

## Plano — Sessão 10: nuvem 1, o motor (a 10b leva o chat para a nuvem)

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
| C2 | gitleaks no CI e no hook, limpo no histórico, canário reprovado; **ok do dono** → repo privado, conferido pela API | C1 | ⬜ |
| C3 | `scripts/nuvem.py` só-leitura mostra tudo "a criar"; **ok** → projeto, faturamento, APIs, orçamento, Firestore em SP, registry, contas de serviço e índices; o só-leitura mostra "nada a criar" | C2 | ⬜ |
| C4 | store Firestore passa o contrato no emulador (VPS e CI), sem pulado; mutações novas mortas | C1 | ⬜ |
| C5 | motor (Starlette) com testes de 401/403/identidade e sem conteúdo em log; Dockerfile; imagem constrói | C4 | ⬜ |
| C6 | **ok** → primeiro deploy; `describe` = SHA; sem login → 403 do Google; fumaça com o `cli@` exerce `/versao` e `/lembretes` (e `vencidos` na produção) | C3, C5 | ⬜ |
| C7 | `viking lembretes --nuvem` (cliente com `IDTokenCredentials`), testes offline; roteiro do Mac | C6 | ⬜ |
| C8 | portões, duas passadas de revisão, docs, commits, push, CI pelo SHA | C7 | ⬜ |
| C9 | teste do dono no Mac | C8 | ⬜ |

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
