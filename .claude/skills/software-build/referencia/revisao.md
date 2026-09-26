# O roteiro de revisão

Revisão não é releitura. Cada passo abaixo pega uma classe diferente de defeito,
e a ordem importa, porque os primeiros são baratos e mecânicos e os últimos
exigem pensar.

## Passada 1 — o diff contra a intenção

1. **Rode os portões e leia o resultado** (a linha literal, do topo: muitas
   ferramentas põem o que recusam na primeira linha, não na última).
2. **Rode o comando de verdade** contra dados reais ou populados, não só a
   suíte. Suítes começam de banco vazio e não veem o que só existe em base velha.
3. **Leia lado a lado tudo o que tem espelho:** duas implementações do mesmo
   contrato, o mesmo cálculo em duas linguagens, o esquema e o tipo gerado. Uma
   divergência de semântica passa por qualquer teste de contrato que compare
   constantes.
4. **Para cada escrita, pergunte: e se ela chegar duas vezes?** (reenvio, retry,
   reentrega do webhook, reprocessamento).
5. **Para cada caminho de falha, pergunte: se isto estivesse errado, o que
   apareceria?** Quando a resposta honesta é "nada", esse é o item que precisa
   de trabalho.

## Passada 2 — depois do conserto, com perguntas novas

1. **O que este conserto tornou falso?** Teste que mirava a linha antiga,
   comentário que descrevia o comportamento anterior, âncora de mutação, número
   num documento, invariante que dependia do valor que mudou.
2. **Quem mais produz este estado?** Enumere quem escreve a linha **e** quem
   muda o estado dela (status, flag, exclusão). A resposta raramente está na
   mesma tabela.
3. **O que a segunda execução encontra?** Um passo que consome a própria
   entrada desarma a retentativa. *Caso real:* apagar os arquivos temporários
   antes do passo que podia falhar fez a reentrega estornar um pagamento bom.
4. **Que transição tira uma linha deste estado, e quem a dispara?** Um estado
   com entrada e sem saída tranca a porta numa data.
5. **Quem espera este objeto sumir?** `CASCADE`, regras de ciclo de vida,
   limpezas agendadas e promessas em texto público. Tornar algo permanente
   desliga tudo que dependia do fim dele.
6. **A condição que eu escrevi é a mesma coisa que a frase ao lado dela?** O
   comentário certo em cima da condição errada é o que mais desarma a releitura.
7. **Consertei o visível e pus um silencioso no lugar?** Duplicata virou
   descarte? Alarme virou alarme eterno sobre um sistema saudável?

## Passada de produção — antes de algo irreversível

1. Releia o que vai ser aplicado **na versão do disco**.
2. `--dry-run`/`plan` e compare com o que você espera, item por item.
3. Aponte em voz alta o irreversível (`DROP`, `TRUNCATE`, `DELETE`, sobrescrita
   por upsert) e o que custa dinheiro.
4. Leia **o que entra no build**: o que o Dockerfile copia, o que os arquivos de
   ignore excluem, `git status` limpo e sem trava de processo que reescreve
   fontes.
5. Diga ao dono o que cada comando vai mudar, **antes**.

## Sobre revisor e implementador

Se há dois agentes (ou duas pessoas), um implementa e o outro revisa. **Nunca os
dois ao mesmo tempo no mesmo escopo.** O revisor não redesenha o que só faria
diferente. O implementador volta para a validação final. O ciclo tem fim:
implementação → revisão → validação → próxima tarefa.
