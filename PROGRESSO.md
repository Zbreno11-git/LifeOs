# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-26, entre sessões (Sessão Gmail fechada)

**Estado:** Sessão Gmail validada no Mac do dono, inclusive as perguntas no `viking chat` (ver
diário). Execuções em background: nenhuma. Travas: nenhuma.

**Próximo passo exato:** abrir a Sessão Gmail 2 (`sessoes.md`) — rodada de perguntas ao dono
sobre como escolher o que arquivar, antes do plano.

**Não esquecer:**
- O repo é **público**: nem o `project_id` do OAuth nem nome de remetente da caixa do dono entram
  em doc nenhum.
- Baseline do `ruff format --check`: 7 arquivos pré-existentes. Formatar **só os arquivos
  editados** (`docs/erros.md`, classe 8).
- Roteiro para o Mac começa com `git pull && git log --oneline -1` e só segue com o commit certo
  (`docs/erros.md`, classe 1).

> O plano da Sessão Gmail fica abaixo como registro até a próxima sessão abrir o dela.

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
