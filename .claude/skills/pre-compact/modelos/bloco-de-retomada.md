# Modelo — bloco de retomada

Copie para o **topo** do documento de progresso. Apague as linhas que não se
aplicam, mas não os títulos: um título vazio com "nenhum" é informação, e um
título ausente é dúvida.

```markdown
## ▶️ RETOMAR AQUI — <data>, <hora> <fuso> — antes de um <compact | conversa nova | handoff>

**Estado do repositório:** árvore limpa · HEAD `<sha>` (igual ao remoto: sim) ·
travas: nenhuma · execuções em background: <nenhuma | "<o quê>", saída em
`<caminho>`, fazer <x> com o resultado>

**Estado do mundo (medido às <hora>):** <serviço A> no ar = `<tag>` ·
<banco> migrations aplicadas = <n> · CI do HEAD: <verde/vermelho/não rodou —
de propósito?>

**Objetivo em curso:** <uma frase verificável>

**Próximo passo exato:** <arquivo · comando · resultado esperado>

**Checkpoints:**
| C | Fecha quando | Estado |
|---|---|---|
| C1 | … | ✅ |
| C2 | … | 🔵 |
| C3 | … | ⬜ |

**Reler, nesta ordem:**
1. `<primer>` — regras e fronteiras
2. este bloco
3. `<plano>` — fase <n>, etapas <n.m>
4. skill `<área>`
5. `<arquivo de código>` — <por quê>

**Decisões desta conversa (e onde ficaram escritas):**
- <decisão> — <quem> — escrita em `<arquivo>`

**Não pode ser esquecido (só existe aqui):**
- <gotcha medido, com data> — <o que ele faz se esquecido>
- <número de base para comparação, com data e comando>

**Depende do dono:**
- <pergunta> — o que muda com cada resposta

**Riscos do próximo passo:** <irreversível? custa dinheiro? em produção?>

**Antes de confiar neste bloco, confira:**
- `git status` limpo e HEAD = `<sha>`
- `<comando que confere o estado do mundo>` → esperado `<valor>`
- `<execução em background>` terminou? resultado literal:
```
