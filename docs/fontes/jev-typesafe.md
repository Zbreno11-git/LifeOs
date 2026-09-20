# Jev (TypeSafe)

- **Projeto (agente):** https://github.com/browser-use/jev-ultrafast — vendorizado neste repo em
  `jev-ultrafast/` (clone externo, gitignored, próprio `.git`; ver risco abaixo)
- **O que é "Jev":** modelo de decisão de baixo custo/latência da TypeSafe (acessado hoje via
  **OpenRouter Decisions API**, `POST https://openrouter.ai/api/alpha/decisions`, modelo
  `typesafe/jev-latest`/`jev-1.13-*`), que recebe um espaço de ação limitado
  (`CLICK, TYPE_TEXT, SELECT, SCROLL_UP/DOWN, WAIT, DONE, BLOCKED`) e uma lista numerada de elementos da
  página, e devolve `{operation, target}` — em vez de um LLM generalista raciocinar antes de cada
  clique.
- **Docs oficiais:** https://docs.typesafe.ai/introduction
- **Papel no projeto:** é o "executor rápido" da automação de navegador — o LLM planejador (Gemini/Claude/
  GPT) decide o quê fazer em alto nível; o Jev decide qual ação/elemento clicar a seguir. Ver
  `docs/arquitetura/browser-automation-stack.md` seções 1, 8, 18.
- **Custo observado:** ~US$ 0,0000137/chamada, latência de centenas de ms (medido em 2026-09-19).
- **Risco em aberto:** o clone local em `jev-ultrafast/` tem `origin` apontando direto para o upstream
  (`browser-use/jev-ultrafast`), não para um fork pessoal — diferente do padrão usado em `windows-mcp/`.
  Os 3 commits locais (incluindo o patch que troca a chamada direta à TypeSafe pelo endpoint Decisions
  da OpenRouter, com fallback de env var) não têm remote próprio. Recomendado criar um fork pessoal
  (ex.: `Zbreno11-git/jev-ultrafast`) antes de depender disso a longo prazo.
