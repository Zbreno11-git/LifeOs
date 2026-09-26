# Um arranjo de teste por mutação que não mente

Ferramentas prontas de mutação (Stryker, mutmut, PIT) geram milhares de mutações
cegas. O que funcionou melhor foi uma **lista curada**, onde cada mutação é o
defeito que um conserto impede, escrito como troca de texto, com o nome do teste
que deve cair. É lenta de escrever e barata de ler: cada linha é uma afirmação
sobre o que o teste protege.

## A forma de uma mutação

```python
Mutacao(
    nome="webhook: fatura sem tentativa interna é aceita em silêncio",
    arquivo="src/pagamento/webhook.ts",
    velho="if (!linha) throw new FalhaDefinitiva(",
    novo="if (false) throw new FalhaDefinitiva(",
    esperado="fatura sem tentativa interna devolve 500",   # fragmento do nome do teste
)
```

## O que o arranjo tem de fazer, e o incidente que ensinou cada item

| Requisito | Por quê |
|---|---|
| **Conferir todas as âncoras antes de rodar qualquer uma**: cada `velho` casa **exatamente uma vez**; abortar se alguma não casar | um formatador requebrou uma linha, e "26 passed" era mutação que não aplicou |
| **Recusar mutação que só altera comentário**, comparando o texto sem comentários com um **tokenizador** | a mutação acertou a primeira ocorrência, que estava no comentário que documentava a linha |
| **Para arquivo de dados, comparar o valor carregado** | uma chave YAML duplicada tornou a mutação inerte |
| **Exigir uma partida verde** (suíte sem mutação, zero `skipped`) | medir vermelho sobre uma suíte já vermelha não prova nada |
| **Exigir que caia o teste esperado**, não qualquer um | "caiu, mas não o teste esperado" costuma ser rótulo desatualizado; às vezes é defeito pego por acidente |
| **Restaurar em `finally` e conferir byte a byte**, incluindo os arquivos derivados | o gerenciador de pacotes regravou o lockfile, e o conserto de 6 CVEs foi commitado desfeito |
| **Trava no disco** (arquivo com PID e hora) enquanto roda; outras ferramentas param se ela existe | editar durante a rodada é ler código mutado, ou ter a edição apagada pela restauração |
| **Rodar subconjunto por fragmento do nome** (um `remut`) | quando o CI aponta 1–3 mutações, prova-se cada uma isolada em vez de pagar outra rodada inteira |
| **Relatório com as recusas no TOPO**, e saída inteira em arquivo | um `tail` cortou exatamente a linha `ancoras ruins: 1` |
| **Sem timeout externo** | `SIGTERM` não passa pelo `finally`: fica código mutado e trava no disco |
| **Mutação de migration aplicada muda de arquivo junto** quando uma migration nova redefine a função | a mutação mirava o texto velho, o teste lia o novo, e os dois deixaram de se falar |
| **Estado fora do arquivo derrubado entre rodadas** (função no banco de teste, cache do typecheck) | uma sobrecarga de função sobreviveu entre rodadas e mascarou a mutação |

## Onde uma lista curada ganha de uma ferramenta cega

- Cada mutação **é** a documentação do que o teste protege.
- O custo é proporcional ao risco: regras que decidem dinheiro, acesso e
  apagamento ganham mutação; texto de tela, não.
- Ela sobrevive a refatoração: a âncora quebra alto (casa 0 vezes), e isso
  obriga a reler a regra.

## Custo

Uma lista de mais de mil mutações levou ~1h30 de CI por push. Se o CI é pago,
isso é decisão de gasto: agrupe commits, rode localmente os portões que o CI
rodaria e reverifique só o que mudou. Uma rodada completa por push só se
justifica se a mudança toca o que as mutações miram.
