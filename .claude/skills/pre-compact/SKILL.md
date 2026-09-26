---
name: pre-compact
description: Prepara o trabalho para sobreviver a um /compact, a uma conversa nova ou a uma troca de agente — fecha a unidade em curso num ponto seguro, revisa objetivo, decisões, pendências e riscos, escreve o bloco "retomar aqui" no disco, lista o que reler, e gera o prompt pronto para a primeira mensagem depois do compact. Também diz como RETOMAR — o que ler e conferir antes de confiar no bloco. Use quando alguém disser que vai compactar, abrir outra conversa, parar por hoje, passar o trabalho a outro agente, ou logo depois de um compact.
---

# Pre-compact — tornar o compact transparente

## Quando usar

- Alguém avisou que vai rodar `/compact`, ou o contexto está perto do limite.
- Vai abrir uma **conversa nova** (nada sobrevive além do repositório).
- Fim do dia, ou handoff para outro agente ou pessoa.
- **Logo depois** de um compact: siga a seção "Depois do compact".

## Quando não usar

- No meio de uma medição ou experimento cujo resultado decide uma linha de
  código. Termine primeiro (passo 0). Parar no meio joga fora justamente o que
  não está escrito em lugar nenhum.
- Para "resumir a conversa". O produto desta skill é um estado no disco que
  outra instância consegue continuar, não um resumo.

## O princípio

Depois de um compact, **só o que está no disco sobrevive de verdade**: o
documento de progresso, o plano, o `git log` e o código. O resumo da conversa
é escrito por quem já tinha o contexto e por isso omite o que parecia óbvio:
fronteiras em vigor, decisões que não se reabrem, o gotcha que custou uma
tarde. Um aviso de compact não é pedido para parar já. É pedido para **fechar
a unidade atual num ponto seguro** e só então parar.

---

## Procedimento

### 0. Termine o que é importante, não abra nada novo

Se há uma etapa quase fechada, ou uma medição em curso que decide código,
termine. Não comece a etapa grande seguinte. "Termina primeiro" é ordem de
prioridade, não licença para apressar.

### 1. Estado do repositório

```bash
git status --short                 # tem de estar limpo no fim
git log --oneline -5
git rev-parse HEAD                 # e conferir se o remoto tem o mesmo
ls <travas conhecidas>             # ex.: arquivo de lock de mutação/migração
```

- Existe execução em background? Liste o que é, onde está a saída e o que
  fazer com o resultado. **Não deixe execução órfã sem registro.**
- Existe trava de processo longo? Nesse caso não é ponto seguro: o disco pode
  ter código mutado.

### 2. Estado do mundo (se há produção)

- O que está no ar, medido agora por comando (não copiado).
- CI do HEAD: conferido pelo SHA do commit, não por "a lista está vazia, deve
  estar rodando".
- O que depende de um evento futuro (agendamento, janela de coleta, resposta
  do dono), com data e hora **e fuso**.

### 3. Revisão do estado

Escreva, curto, para você mesmo:

| Item | Pergunta |
|---|---|
| Objetivo | O que esta sessão ou plano entrega, em uma frase verificável? |
| Arquitetura em jogo | Quais peças esta etapa toca, e como se ligam? (uma ou duas linhas) |
| Decisões | O que foi decidido nesta conversa, **por quem**, e já está escrito em algum documento durável? |
| Pendências | O que falta, separado em **dívida** (conserta ou tem adiamento autorizado) e **trabalho futuro** |
| Riscos | O que pode dar errado no próximo passo; o que é irreversível ou custa dinheiro |
| Não pode ser esquecido | Gotchas medidos nesta sessão, números com data, frases do dono que decidem algo |

⚠️ **Toda decisão tomada só no chat vai agora para um documento durável**
(roadmap, decisões, primer). O bloco de retomada aponta para ela, mas não pode
ser o único lugar onde ela existe.

### 4. Onde o trabalho parou, exatamente

O próximo passo é **concreto**: arquivo, comando e o resultado esperado.

| Ruim | Bom |
|---|---|
| "Continuar a fase 4" | "Etapa 4.2: acrescentar o teste de reentrega em `tests/test_webhook.py`; esperado 1 vermelho antes do conserto em `webhook.py:88`" |
| "Ver o CI" | "Conferir o run do SHA `abc123` pelo `headSha`; se verde, fechar C5" |
| "Esperar a coleta" | "Segunda 28/09 depois das 04:00 BRT: `SELECT … FROM runs WHERE …`; base de comparação: 280" |

### 5. O que reler, em ordem

Liste os arquivos que o contexto novo precisa ler, **na ordem**, com o motivo
de cada um. Sempre primeiro: as instruções do projeto (primer), depois o
bloco de retomada, depois o plano, depois a skill da área, e por fim os arquivos
de código da etapa em curso.

### 6. Escreva o bloco de retomada no disco

No topo do documento de progresso, a partir de
[`modelos/bloco-de-retomada.md`](modelos/bloco-de-retomada.md). Ele contém o
estado, o próximo passo exato, os checkpoints, a lista do que reler, o que não
pode ser esquecido, o que depende do dono e as verificações que o contexto novo
deve rodar antes de confiar no bloco.

**Teste do bloco:** um agente que só tem o disco consegue continuar sem
perguntar nada que já foi respondido? Se não, falta algo.

### 7. Commit, push, confira

Os portões que o projeto exige já passaram antes deste ponto. Commit com a
mensagem dizendo que é um checkpoint. Push. `git status` limpo. Se o projeto
paga pela execução de CI, o commit de checkpoint segue a regra de economia dele
(por exemplo, a marca de pular CI no commit do **topo** do push).

### 8. Entregue duas coisas no chat

1. **Um resumo para o dono decidir no intervalo:** onde estamos, o que fechou
   (com números medidos), o que falta em ordem, e **o que depende dele**. Esse
   resumo não substitui o documento, e o documento não substitui o resumo: o
   documento é para o próximo agente; o resumo é para o dono saber se o rumo
   está certo.
2. **O prompt pós-compact**, pronto para colar, a partir de
   [`modelos/prompt-pos-compact.md`](modelos/prompt-pos-compact.md).

---

## Variante: conversa nova (nada sobrevive)

Depois de um compact sobra um resumo. Numa conversa nova não sobra nada. Além
dos passos acima:

- **Revise todos os documentos**, não só o progresso: roadmap, diário, primer.
- **O handoff é narrativo e detalhado sobre as últimas sessões:** o que mudou e
  em quais arquivos, o que o diff não conta, os portões medidos, o que **não**
  foi verificado, onde você desconfiaria se fosse o revisor, e os erros que
  cometeu na rodada.

## Variante: handoff para outro agente

Some ao bloco: papel de cada um (quem implementou, quem revisa), o escopo
exato do que pode ser tocado, e **o que o revisor não deve redesenhar**. Um
agente de cada vez no mesmo escopo.

---

## Depois do compact

O compact é uma sessão nova com um resumo no lugar do contexto, não uma
continuação transparente. **A rotina de abertura vale de novo, inteira, antes do
trabalho.**

1. **Leia o que o bloco manda reler, na ordem**, incluindo o primer e a skill
   da área, mesmo que o próximo passo pareça óbvio. O item "próximo passo" diz
   onde o trabalho parou, não o que precisa ser lido antes de recomeçar.
2. **Rode as verificações do bloco antes de confiar nele.** O bloco é o registro
   de uma medição passada: `git status`, HEAD igual ao anotado, travas, estado
   do que está no ar, execuções em background (terminaram? qual foi o
   resultado **literal**?).
3. **Divergência entre o bloco e o disco: o disco ganha.** E a divergência é
   notícia. Registre-a antes de seguir.
4. **Só então** execute o próximo passo.

---

## Testes de falha

O preparo falhou se:

- `git status` não está limpo, ou há trava ou execução em background não
  mencionada;
- o próximo passo não cabe numa linha com comando e resultado esperado;
- existe decisão do dono que só está no chat;
- um número no bloco não tem data;
- o bloco manda "ver o CI" sem dizer qual SHA;
- depois do compact, o primeiro gesto foi executar o próximo passo sem ler nem
  conferir nada.

## Critério de conclusão

- [ ] Unidade em curso fechada, ou parada num ponto explicitamente seguro.
- [ ] Bloco de retomada no topo do progresso, commitado e no remoto.
- [ ] Decisões do chat transferidas para documentos duráveis.
- [ ] Árvore limpa, sem trava, execuções em background registradas.
- [ ] Resumo para o dono e prompt pós-compact entregues no chat.
