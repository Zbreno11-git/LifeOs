# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-26, Gmail 2 feita no VPS; falta o Mac (C8)

**Estado do repositório:** o commit de fechamento da Gmail 2 (conferir com `git log -1`) · igual
ao remoto · travas: nenhuma · execuções em background: nenhuma.

**Próximo passo exato:** o dono roda o roteiro abaixo no Mac e cola a saída; com ela, fechar C8
(diário + barra: Gmail 2 de parcial para fechada). Depois, abrir a Sessão Pluggy
(`sessoes.md`), que depende de o dono pôr os IDs das conexões no `.env`.

**Antes de confiar neste bloco:** `git status --short` vazio; `ls .mutacao.lock` → não existe;
`python -m pytest -q` → `607 passed`.

**Não pode ser esquecido:** repo público (nada de remetente real nem `project_id` em commit — nem
o endereço que o dono escolher para o teste); formatar só os arquivos editados (baseline 7);
roteiro do Mac começa com `git pull && git log --oneline -1`; escapes Unicode por `chr()`; a
aprovação mora no laço do chat e não pode virar tool (D30, `AGENTS.md`).

**Roteiro para o Mac (C8)** — trocar `REMETENTE` pelo endereço de uma newsletter do raio-x:

```bash
cd ~/LifeOs
git pull && git log --oneline -1
source .venv/bin/activate
which python
python -m pytest -q
viking gmail --login
viking gmail --arquivar REMETENTE
```

Esperado: `607 passed`; o `--login` abre o navegador **de novo** (permissão nova: o Google a
descreve como ler, escrever e enviar — ver D29) e termina em `✅ Login do Gmail ok (ler e
arquivar)`; o `--arquivar` mostra a lista e pede o código — digitar o código; conferir no Gmail
(web) que os e-mails saíram da Caixa de entrada e estão em "Todos os e-mails". Depois:

```bash
viking gmail --desfazer CODIGO
viking chat
```

No chat: "quem mais me manda e-mail que eu não abro?" → "arquiva tudo do REMETENTE" → digitar
`confirma` e o código mostrado → "e agora?". Colar a saída (sem o endereço, se preferir).

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
| Teto por aprovação | **1000** (D28) | uma chamada `batchModify`; acima disso, os mais antigos de cada remetente, na ordem pedida, e o texto diz quantos sobraram |
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
| C8 | Mac: login novo com modify, arquivar um remetente escolhido pelo dono, conferir no Gmail, desfazer, e o mesmo pelo chat | ⬜ |

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
