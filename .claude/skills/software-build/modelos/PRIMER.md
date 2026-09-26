# <Projeto> — instruções para o agente

> Leia isto primeiro, em toda sessão. É curto de propósito: o conhecimento
> profundo está nas skills e nos documentos listados abaixo. Este arquivo
> carrega **o que não está em nenhum lugar do código**.
>
> Teto: a narrativa da sessão atual e da anterior. Ao fechar a seguinte, a mais
> velha desce para `docs/HISTORICO-DO-PRIMER.md` — corte **por tipo**: o que
> ainda decide algo sobe para "Fronteiras", lição vai para o catálogo de erros,
> só narrativa desce.

## O que é

<Duas a quatro frases: o produto, para quem, o estado hoje, com data.>

## O requisito que decide empates

> <A frase do dono que resolve conflitos de prioridade. Exemplo real: "prefiro
> que o sistema erre alto a coletar mais".>

## Regras invioláveis

<Poucas. Cada uma com o incidente que a criou, em uma linha. Exemplos:>

- **Consertar primeiro.** Não se constrói sobre defeito conhecido sem
  autorização do dono pedida na hora.
- **Escrita em produção** (migration, deploy, dado, segredo) só com autorização
  na hora.
- **Nunca desfazer com comando destrutivo** trabalho não commitado; backup por
  cópia.
- **Medir antes de virar regra; não afirmar causa que não se mediu.**

## Sessão atual

⚠️ **Sessão N (data): <título>.** <O que decide algo agora.>

Contexto anterior (data): <a sessão anterior, resumida>.

## Fronteiras e gatilhos em vigor

| Fronteira | A regra, em uma linha (e o gatilho que a reabre) |
|---|---|
| <nome> | <regra> |

## Onde está o quê

| | |
|---|---|
| `docs/SESSOES.md` | roadmap, com o bloco "▶️ Começar a próxima sessão por aqui" |
| `PROGRESSO.md` | estado agora e "retomar aqui" |
| `docs/DIARIO.md` | uma entrada por sessão |
| `docs/ERROS.md` | catálogo de erros por classe — abrir ao achar um defeito |
| `docs/DECISOES.md` | decisões com gatilho de reabertura |

## Comandos

```bash
# portões
<teste> && <lint> && <typecheck>
# o que está no ar
<comando de describe>
```

## Protocolo

- Abrir: leitura obrigatória → `git status` → estado do mundo.
- Execuções longas em background; esperar não é trabalho.
- Fechar: portões lidos → duas passadas de revisão → documentos → commit com o
  porquê → no ar?
- Ao achar um defeito: abrir o catálogo de erros antes — *de que classe isto é
  uma instância?*
