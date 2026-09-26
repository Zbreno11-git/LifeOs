# Viking — progresso em curso

> Arquivo de trabalho: descreve a sessão **atual** e é atualizado a cada etapa fechada, não só no
> fim. É o que sobrevive a um `/compact` ou a uma conversa nova (skill `pre-compact`). Quando a
> sessão fecha, o que era narrativa vai para o diário, lição para `docs/erros.md`, decisão para
> `docs/decisoes.md`, e este bloco passa a apontar para a próxima sessão.

## ▶️ RETOMAR AQUI — 2026-09-26, entre sessões

**Estado:** nenhuma sessão em curso. Último trabalho: instalação das skills e organização dos
documentos (commit "Instalar skills de trabalho e organizar a continuidade", conferir com
`git log -1`). Execuções em background: nenhuma. Travas: nenhuma.

**Próximo passo exato:** abrir a Sessão 4b — ler em `jev-ultrafast/jev_ultrafast/agent.py` o que
`choose` devolve (a ação escolhida antes de rodar) e perguntar ao dono a lista de ações que o freio
recusa (proposta em `sessoes.md`, Sessão 4b).

**Checkpoints da próxima sessão:** ainda não planejada (o plano sai na abertura, no formato de
`.claude/skills/software-build/referencia/plano-de-sessao.md`).

**Não esquecer:**
- O repo é **público** (`gh repo view`, 2026-09-26): nada com nome de outro projeto do dono, dado
  pessoal ou segredo entra em commit.
- Baseline do `ruff format --check`: 7 arquivos pré-existentes fora do padrão (2026-09-26); a
  pasta `.claude/` está excluída de propósito.

**Depende do dono:** a lista do freio de clique (Sessão 4b).

## Antes de confiar neste bloco, confira

```bash
git status --short
git log --oneline -3
python -m pytest -q
```

Esperado: árvore limpa; `324 passed`. Se o disco divergir deste bloco, o disco ganha — e a
divergência é notícia.
