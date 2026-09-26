# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-26, entre sessões — antes de um compact

**Estado do repositório:** árvore limpa · HEAD `6cfa269` antes deste checkpoint (o commit de
checkpoint vem logo depois; conferir com `git log -1`) · igual ao remoto · travas: nenhuma
(`.mutacao.lock` ausente) · execuções em background: nenhuma.

**Estado do mundo (Mac do dono, medido pela saída colada em 2026-09-26):** código até `9841595`
puxado e validado (528 testes; Gmail real lido; chat ok). Os commits `520a404` e `6cfa269`
(enchimento das prévias, frase do raio-x) **ainda não foram puxados no Mac** — entram no próximo
`git pull`, sem validação ao vivo pendente além de rodar a suíte.

**Objetivo em curso:** nenhum código em andamento. Sessão Gmail 2 (limpar a caixa) **aberta só
com as perguntas**: o dono respondeu e pediu para **não começar ainda** ("mas calma não começa
ainda").

**Próximo passo exato:** esperar o dono dizer para começar a Gmail 2. Quando disser: escrever o
plano no formato de `.claude/skills/software-build/referencia/plano-de-sessao.md` a partir de
`sessoes.md` → "Sessão Gmail 2" (respostas + desenho proposto), perguntar o teto de e-mails por
aprovação, e só então codar.

**Reler, nesta ordem:**
1. `CLAUDE.md` e `AGENTS.md` — regras, fronteiras, armadilhas.
2. Este bloco.
3. `sessoes.md`, seção "Sessão Gmail 2" — as respostas do dono e o desenho proposto.
4. `docs/decisoes.md` (D21–D27) e `docs/erros.md` (índice).
5. Skills `software-build` (abrir/planejar), `seguranca` (ação irreversível, injeção) e
   `testes-que-provam`.
6. `src/lifeos/gmail/service.py`, `gmail/tools.py`, `google_auth.py` — onde a limpeza encaixa.

**Decisões desta conversa (e onde ficaram escritas):**
- Freio de cliques: sair/conta/dinheiro, para e avisa, sem liberação até a Sessão 5 — dono — D18,
  `sessoes.md` (4b e 5).
- Gmail só no chat, redação das páginas, plano pago do Gemini — dono — D21, D22.
- Limpeza: sessão própria, só arquivar, lista aprovada — dono — D23.
- Limpeza por remetente, todos da caixa, proteções estrela/importante/anexo — dono — D25.
- Aprovação digitando código fora do Gemini; desfazer por 7 dias — dono — D26, D27.

**Não pode ser esquecido (só existe aqui ou é fácil de perder):**
- O repo é **público**: nem o `project_id` do OAuth nem nome de remetente/assunto da caixa do
  dono entram em doc ou commit.
- O app OAuth aparece no Google como **"n8n"** — o alerta de segurança de login é o nosso.
- Baseline do `ruff format --check`: 7 arquivos pré-existentes (2026-09-26). Formatar **só os
  arquivos editados** (`docs/erros.md`, classe 8).
- Roteiro para o Mac começa com `git pull && git log --oneline -1` e só segue com o commit
  certo (classe 1).
- Escape Unicode em parâmetro de ferramenta vira caractere literal (classe 5, 3 ocorrências):
  gerar por script com `chr()`.
- Números de 2026-09-26 no VPS: `530 passed`; mutações `28` (26 na última rodada completa + 2
  reprovadas isoladas depois); raio-x real do dono: 200 e-mails (piso) de 91 remetentes em 30 dias.

**Depende do dono:**
- O "pode começar" da Gmail 2.
- No plano: o teto de e-mails por aprovação (o que muda: uma aprovação grande limpa tudo de uma
  vez; uma pequena obriga várias rodadas, mas cada lista é lida inteira).
- Opcional: renomear o app OAuth "n8n" para "Viking" na tela de marca do Google Cloud.

**Riscos do próximo passo:** a Gmail 2 é a primeira escrita na conta do dono pelo Viking. É
reversível (arquivar e desfazer), mas exige o login novo com `gmail.modify` e cuidado com
injeção: o código de aprovação nunca pode passar pelo Gemini.

**Antes de confiar neste bloco, confira:**
- `git status --short` vazio e `git log --oneline -1` = o commit de checkpoint deste bloco;
- `ls .mutacao.lock` → não existe;
- `python -m pytest -q` → `530 passed`.

> O plano da Sessão Gmail (leitura) fica abaixo como registro até a Gmail 2 abrir o dela.

## Plano — Sessão Gmail: leitura via API

**Entrega (verificável):** no `viking chat`, o dono pergunta "o que chegou hoje?", "busca e-mail
do X", "lê esse" e "quem mais me manda coisa que eu não abro?", e o Viking responde lendo o Gmail
pela API, com o conteúdo redigido e delimitado como não confiável. Nada muda na caixa.

**Não faz:** limpar/arquivar (→ Sessão Gmail 2, já escrita no `sessoes.md`); expor e-mail pelo
MCP (decisão do dono); anexos; enviar e-mail.

**Respostas do dono (2026-09-26):**
| Pergunta | Resposta | Consequência |
|---|---|---|
| Por onde lê | só `viking chat` | tools só em `FERRAMENTAS`; teste prova que o MCP não as expõe |
| Redação | regra das páginas | `_redacao.redigir` + URLs do corpo por `redigir_url`; e-mails e códigos 2FA visíveis |
| Ferramentas | buscar, ler, não lidos de hoje + limpar | limpar vira a Sessão Gmail 2; aqui, raio-x só leitura |
| Limpeza | sessão própria; só arquivar; lista aprovada | escrito no `sessoes.md` |
| Plano do Gemini | pago | conteúdo não é usado para treino (termos do Google, não verificado por mim) |
| App OAuth | produção, externo, só ele | login não vence em 7 dias; aviso "app não verificado" no login é esperado |

**Medido na abertura (2026-09-26):**
- `calendar/oauth.py`: `SCOPES` só de calendário e **nenhuma** conferência de escopo no token
  salvo — um token sem a permissão pedida passaria como válido.
- `googleapiclient` instalado traz `gmail.v1.json`: sem dependência nova.
- `tests/conftest.py` só trava o Google **Calendar** de verdade.

**Decisões técnicas minhas:**
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Token do Gmail em arquivo próprio (`google_token_gmail.json`) | falha ou revogação do Gmail não derruba o calendário (raio da falha) | o dono preferir um login só para os dois |
| `lifeos/google_auth.py` compartilhado pelo calendário e pelo Gmail, conferindo `has_scopes` e gravando o token com permissão 600 | segundo consumidor do mesmo fluxo; um token sem o escopo vira login novo, não erro 403 mudo | — |
| Pacote `lifeos/gmail/` (não `email/`, que colide com a stdlib) | — | — |
| `lifeos/nao_confiavel.py` com `neutralizar`/`bloco`, usado pelo navegador e pelo Gmail | a regra do delimitador passaria a ter duas cópias | — |
| `_redacao` continua em `browser/` (D13: o gatilho, terceiro consumidor, disparou; reavaliado) | ele precisa ser vizinho do subprocesso do Jev, que o importa pelo caminho | uma forma de o subprocesso importá-lo sem `lifeos` e sem mexer em `sys.path` |
| Raio-x lê metadados em lotes (`new_batch_http_request`), teto de 200 e-mails, 1 nova tentativa para quem falhar | 200 chamadas uma a uma seriam lentas; teto e falha aparecem no texto como "piso"/"incompleto" | latência ou 429 medidos no Mac |
| `viking gmail --login/--buscar/--raio-x` | validar no Mac sem gastar Gemini, como o `viking browser` | — |

**Checkpoints:**
| C | Fecha quando | Estado |
|---|---|---|
| C1 | `google_auth.py` + calendário delegando + `tests/test_google_auth.py` verdes — 10 passed, suíte 454 | ✅ |
| C2 | `nao_confiavel.py` + `mensagens.py` usando; suíte do navegador igual — 454, mutação do delimitador morta no endereço novo | ✅ |
| C3 | `gmail/service.py` (buscar, ler, não lidos de hoje, raio-x) + `tests/test_gmail_service.py` — 33 passed | ✅ |
| C4 | `gmail/tools.py` + registro no chat + testes de segurança (injeção, redação, controles, MCP sem Gmail) — 20 passed | ✅ |
| C5 | `viking gmail` na CLI + trava do `conftest` para o Gmail — 5 testes de CLI; trava ampliada; suíte 527 | ✅ |
| C6 | mutações novas mortas; suíte, `ruff`, baseline 7, varredura de controles — 26/26 + a 27ª isolada; suíte 528; ruff limpo; baseline 7 | ✅ |
| C7 | docs + revisão em duas passadas + commit + push | ✅ |
| C8 | Mac: login (aviso de não verificado), `--raio-x`, pergunta no chat — tudo validado, ver diário | ✅ |

**🐞 Previsto → Depurar:**
- Teste do calendário quebrando depois de mover o OAuth → a trava do `conftest` mira
  `lifeos.calendar.oauth.get_calendar_service`; manter esse nome.
- Corpo do e-mail ilegível: `body.data` é base64url **sem padding** e nos bytes do charset da
  parte → completar `=` e decodificar pelo `charset` do `Content-Type`, com `replace`.
- E-mail só em HTML → texto por `html.parser` da stdlib, sem `<script>`/`<style>`.
- `snippet` vem com entidade HTML (`&#39;`) → `html.unescape`.
- 429 no lote do raio-x → contar e dizer "incompleto", nunca devolver menos sem avisar.
- Escape Unicode em parâmetro de ferramenta vira caractere literal (classe 5) → `chr()`.
