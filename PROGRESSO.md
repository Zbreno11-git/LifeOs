# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-26, entre sessões (4b fechada)

**Estado:** Sessão 4b validada no Mac do dono (444 testes, 16/16 mutações, freio recusando na
Chrome real — ver diário). Execuções em background: nenhuma. Travas: nenhuma.

**Próximo passo exato:** Sessão Gmail (`sessoes.md`, bloco ▶️) — o primeiro passo é do dono:
conferir no Google Cloud Console se o app OAuth está em "Testing" ou "In production".

**Não esquecer:**
- O repo é **público**. Citar a Altiva está liberado pelo dono (2026-09-26).
- Baseline do `ruff format --check`: 7 arquivos pré-existentes (2026-09-26). Formatar só os
  arquivos editados (`docs/erros.md`, classe 8).

> O plano da 4b fica abaixo como registro até a próxima sessão abrir o dela.

## Plano — Sessão 4b: freio de ação que age sobre a conta + mutações curadas

**Entrega (verificável):** um clique do Jev em "Sair", em mexer na conta ou em gastar dinheiro é
recusado **antes** de acontecer, com código `acao_sensivel`, e `scripts/mutacoes.py` prova que os
testes das regras de apagar/acessar/egress caem quando a regra some.

**Não faz:** liberar alguma categoria (decisão do dono: só pela confirmação em duas etapas da
Sessão 5, já escrita lá); "publicar em seu nome" (recusado pelo dono: alarme falso demais).

**Respostas do dono (2026-09-26):**
| Pergunta | Resposta | Consequência |
|---|---|---|
| O que o freio recusa | Sair; mexer na conta; dinheiro | 3 categorias; "Enviar/Publicar" fica livre |
| Reação | Para e avisa | `RuntimeError` no envelope → erro classificado, aba aberta, rótulo na mensagem |
| Liberação | Não, só Sessão 5 | nenhuma env nova; até lá o Viking não compra sozinho |

**Medido na abertura (2026-09-26, lendo o clone `afbee69`):**
- `choose()` devolve `{"choice": "<id>"}`; `act()` executa `next(a for a in page["actions"] if
  a["id"] == selected)` → o envelope vê a ação antes do clique.
- `act()` não aperta Enter após digitar; no `select` dispara `input`/`change` (corrigido na
  revisão: o plano dizia que só `click` enviava).
- `page["guards"][str(node)]` = lista de 14 itens (`snapshot.js`, `cache.guard`): [12] = `href`,
  [13] = texto do contêiner (form/dialog/li...). Link só com ícone chega com rótulo `"link"`.

**Decisões técnicas minhas:**
| Decisão | Por quê | O que me faria mudar |
|---|---|---|
| Freio em `choose_protegido`, depois do `choose` | único caminho até o clique | o Jev passar a executar sem passar por `choose` (teste de contrato pega) |
| Módulo irmão `_acoes_sensiveis.py`, só stdlib | roda dentro do ambiente do Jev, como `_redacao` | — |
| `click` e `select` são freados; `fill` não | o `select` dispara `change`, que o site pode usar para enviar; o `fill` não aperta Enter | o Jev passar a submeter no `fill` |
| Três sinais: rótulo, `href` (sair) e texto do contêiner para botões genéricos ("Excluir", "Confirmar") | "Tem certeza? [Excluir]" passaria só pelo rótulo | alarme falso medido alto |
| Freio ligado desde já, sem fase de observação | falso positivo custa uma tarefa parada; falso negativo, a conta | — |
| Layout de `guards` diferente do esperado → `protecao_indisponivel` | fecha em falha, como o envelope | — |

**Checkpoints:**
| C | Fecha quando | Estado |
|---|---|---|
| C1 | `_acoes_sensiveis.py` + `tests/test_acoes_sensiveis.py` verdes (`pytest tests/test_acoes_sensiveis.py`) — 93 passed | ✅ |
| C2 | freio no envelope + `classificar` + testes em `test_jev_subprocess_main.py`, incluindo contrato com o Jev real (`agent.py` e `snapshot.js`) — 29 passed; contrato cai em 3 quebras | ✅ |
| C3 | mensagem `acao_sensivel` em `mensagens.py` + teste — 58 passed + frase na tool do Gemini | ✅ |
| C4 | `scripts/mutacoes.py` roda todas as mutações e cada uma derruba o teste esperado — 16/16 mortas (1 viva achou teste faltando) | ✅ |
| C5 | suíte inteira, `ruff check`, `ruff format --check` (baseline 7), varredura de controles — 444 passed, ruff limpo, format 7, 0 controles | ✅ |
| C6 | docs (jev-typesafe, AGENTS, decisoes, erros, sessoes, diário, barra) + revisão em duas passadas + commit + push | ✅ |
| C7 | validado no Mac — saída colada pelo dono, ver diário | ✅ |

**🐞 Previsto → Depurar:**
- Os testes antigos do envelope quebram porque o `choose` falso devolve `None` → o falso passa a
  devolver `{"choice": "wait"}` (classe 4 de `docs/erros.md`: fixture sem o que o código novo exige).
- Rótulo com caractere invisível escapando do freio (`Sa` + zero-width + `ir`) → normalizar tirando
  a categoria Unicode `Cf` antes de casar.
- Mutação inerte por âncora que casa em comentário → o script compara os tokens sem comentário.
- Um escape Unicode escrito em parâmetro de ferramenta vira caractere literal (classe 5,
  3 ocorrências) → nos testes, gerar por `chr()`.

**Não esquecer:**
- O repo é **público**. Citar a Altiva está liberado pelo dono (2026-09-26).
- Baseline do `ruff format --check`: 7 arquivos pré-existentes (2026-09-26).
