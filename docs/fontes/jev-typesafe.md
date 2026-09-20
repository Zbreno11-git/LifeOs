# Jev (TypeSafe)

- **Upstream:** https://github.com/browser-use/jev-ultrafast
- **Fork usado neste projeto:** https://github.com/Zbreno11-git/jev-ultrafast, branch
  `viking-openrouter` (commit `afbee69`). O clone local em `jev-ultrafast/` aponta pra ele
  (`origin`), com `upstream` no repo original — mesmo padrão do `windows-mcp/`.
- **O que é "Jev":** modelo de decisão de baixo custo/latência da TypeSafe que recebe um espaço de
  ação limitado (`CLICK, TYPE_TEXT, SELECT, SCROLL_UP/DOWN, WAIT, DONE, BLOCKED`) e uma lista
  numerada de elementos da página, e devolve `{operation, target}` — em vez de um LLM generalista
  raciocinar antes de cada clique. Docs: https://docs.typesafe.ai/introduction
- **Papel no projeto:** é o executor das "mãos" do Viking. O Viking o chama **por subprocesso**
  (`uv run --directory <jev>`), nunca por import — ver
  `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 4.2.

## O patch do OpenRouter (nosso, não do upstream)

O upstream fala direto com a TypeSafe: `POST https://api.typesafe.ai/v1/systemone` autenticado com
`TYPESAFE_API_KEY`. **Nosso fork troca isso** pelo endpoint alpha de decisões da OpenRouter
(`POST https://openrouter.ai/api/alpha/decisions`), aceitando `OPENROUTER_API_KEY` com fallback
para `TYPESAFE_API_KEY`, porque a chave que temos é da OpenRouter. O mesmo commit passa a incluir o
corpo da resposta na mensagem de erro HTTP — sem isso, um 4xx do endpoint alpha é indiagnosticável.

> **Histórico:** até 2026-09-20 esse patch existia **apenas como modificação não commitada** no
> working tree de uma pasta gitignorada — qualquer `git checkout`/`clean`/re-clone o apagaria.
> (Uma versão anterior deste documento dizia que havia "3 commits locais incluindo o patch"; era
> falso: os 3 commits eram todos do upstream.) Resolvido com o fork acima.

## Configuração que funciona

No `.env` do **próprio Jev** (não no do Viking):

| Variável | Valor em uso |
|---|---|
| `OPENROUTER_API_KEY` | chave OpenRouter (a mesma serve os dois modelos) |
| `TYPESAFE_MODEL` | `~typesafe/jev-latest` — **com o til**, forma namespaced da OpenRouter |
| `TEXT_MODEL_API_KEY` | mesma chave OpenRouter |
| `TEXT_MODEL_BASE_URL` | `https://openrouter.ai/api/v1` |
| `TEXT_MODEL` | `inception/mercury-2.5` |
| `TEXT_MODEL_REASONING` | `none` |

Sem `OPENROUTER_API_KEY` **nem** `TYPESAFE_API_KEY`, o código levanta um `KeyError` cru (daí o
código de erro `model_key_missing` no nosso runner). `TEXT_MODEL_API_KEY` só é exigida quando a
tarefa precisa digitar texto.

- **Custo observado:** ~US$ 0,0000137/chamada de decisão, latência de centenas de ms (2026-09-19).
- **Risco em aberto:** o endpoint de decisões da OpenRouter é **alpha** e assumimos que ele aceita o
  corpo no formato da TypeSafe. Se falhar, aparece como erro HTTP (código `model_http`) e o primeiro
  suspeito é a string `~typesafe/jev-latest`.
