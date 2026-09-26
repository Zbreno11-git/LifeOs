# O formato do plano de sessão

O plano é o único artefato que atravessa um compact intacto. Um plano vago
obriga a próxima encarnação do agente a redescobrir o que já foi decidido, e
redescobrir errado é pior do que não saber.

## Esqueleto

```markdown
# Plano — Sessão N: <nome>

## O que esta sessão entrega (em uma frase verificável)

## O que ela NÃO faz (e para onde foi)
- <item> → sessão M (já escrito lá: sim/não)

## Respostas do dono
| Pergunta | Resposta | Consequência no plano |
|---|---|---|

## Decisões técnicas minhas (declaradas, para a próxima sessão saber o que é herdado)
| Decisão | Por quê | O que me faria mudar |
|---|---|---|

## Medido na abertura (com data)
| O quê | Comando | Resultado | Consequência |
|---|---|---|---|

## Mapa de checkpoints
| C | Fecha quando | Depende de | Estado |
|---|---|---|---|
| C0 | adiados escritos nas sessões de destino | — | ⬜ |
| C1 | … | C0 | ⬜ |

## Fase 1 — <nome>

### Etapa 1.1 — <nome>
**Faz:** <o que muda, em quais arquivos>
**✅ Checkpoint:** <afirmação que um comando confere> — `<comando>` → <número esperado>
**🐞 Previsto → Depurar:** <o defeito provável desta etapa, ligado à classe do
catálogo de erros> → <o primeiro comando para investigar>

### Etapa 1.2 — …

## Verificação ponta a ponta
<o caminho completo, do jeito que o usuário faria, e o que precisa aparecer>

## Riscos e o que é irreversível
- <passo> — irreversível/custa dinheiro? — como conferir antes
```

## Por que cada parte existe

- **"Não faz"** existe porque o escopo que não está escrito volta como
  suposição. E o destino tem de estar escrito **antes**, na sessão que recebe o
  item.
- **Decisões técnicas declaradas** separam o que o dono escolheu do que você
  escolheu. A sessão seguinte precisa saber o que pode reabrir sem perguntar.
- **"Medido na abertura", com data:** uma medição sem data vira um fato eterno
  no documento seguinte.
- **O checkpoint é uma afirmação com comando e número esperado.** *"Fase
  concluída"* não se confere. *"`count(*)` de X devolve 1.354"* se confere. Sem
  o número esperado, você não percebe quando a extração do resultado mentiu.
- **"🐞 Previsto → Depurar"** obriga a abrir o catálogo de erros antes de
  construir, e deixa escrito o primeiro passo de investigação para quando o
  defeito previsto aparecer.
- **O estado dos checkpoints vai para o topo do progresso** a cada fase, para
  que a retomada comece pelo primeiro não marcado.

## Perguntas antes do plano

- Em rodadas de até quatro, agrupadas por assunto: primeiro as que decidem o
  **tamanho** da sessão, depois as de borda.
- Cada opção com a consequência escrita, e a recomendada em primeiro.
- Só o que é do dono. Decisão técnica você toma e declara.
- **Some as respostas** e devolva a combinação quando ela produzir algo que
  nenhuma resposta isolada mostra.
- Pare de perguntar quando tiver **confiança de implementação**, não depois de
  um número fixo de perguntas.
