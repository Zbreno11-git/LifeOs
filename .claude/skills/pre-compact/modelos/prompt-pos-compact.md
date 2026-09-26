# Modelo — prompt para a primeira mensagem depois do compact

Preencha e entregue no chat, pronto para colar. Ele é curto de propósito: o
conteúdo está no disco, e o prompt só diz **onde ler, o que conferir e por onde
começar**. Um prompt que tenta carregar o estado inteiro vira uma segunda fonte,
que diverge do disco.

```text
Retomando depois de um compact. Não comece pelo trabalho — comece pela leitura.

1. Leia, nesta ordem: <primer>, o bloco "▶️ RETOMAR AQUI" no topo de
   <arquivo de progresso>, <plano> (fase <n>), e a skill <área>.
2. Antes de confiar no bloco, confira:
   - git status limpo e HEAD = <sha>;
   - <trava/processo> não existe;
   - <comando de estado do mundo> → esperado <valor>;
   - <execução em background>: terminou? leia a saída literal em <caminho>.
   Se algo divergir do bloco, o disco ganha — me diga o que divergiu antes de
   seguir.
3. O próximo passo é: <etapa n.m — arquivo, comando, resultado esperado>.
4. Regras que valem nesta etapa: <2–3 fronteiras que o próximo passo pode
   quebrar sem perceber>.
5. Depende de mim: <pergunta pendente | nada>.

Quando terminar a leitura e as conferências, me diga em uma linha o que achou e
siga com o passo 3.
```

## Por que ele pede uma linha de volta

A linha de volta é a prova barata de que a leitura aconteceu e de que o estado
bate. Sem ela, o primeiro sinal de que o contexto novo leu errado é um commit
errado.
