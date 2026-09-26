---
name: software-build
description: Inicia, conduz e mede um projeto de software trabalhado em sessões com uma pessoa dona das decisões — documentos de continuidade (primer, roadmap, progresso, diário, catálogo de erros, decisões), plano por fases com checkpoints, definição de pronto em degraus, regra de dívida, quem decide o quê, revisão em duas passadas e quando parar, revisar ou refatorar. Também avalia a MATURIDADE de um projeto existente. Use ao começar um projeto, ao abrir, planejar ou fechar uma sessão, quando perguntarem "como está o projeto?", e sempre que for declarar algo "pronto".
---

# Software build — construir em sessões sem perder o fio

## Quando usar

- **Projeto novo:** antes da primeira linha de código (modo iniciar).
- **Projeto existente:** para saber onde ele está e o que falta (modo avaliar,
  ver [`referencia/maturidade.md`](referencia/maturidade.md)).
- **Toda sessão:** ao abrir, ao planejar, ao fechar.
- **Antes de dizer "pronto"**, "fechado", "resolvido" ou "no ar".

## Quando não usar

- Para uma pergunta pontual ou um script de uso único, que não criam estado
  para carregar.
- Para decidir **como** fazer algo técnico: isso é das skills técnicas. Esta
  decide **em que ordem, com que prova e com quem**.

## O princípio

Um projeto longo feito com um agente de IA falha de um jeito previsível. Ele
não quebra: **esquece**. Esquece a decisão da semana passada, a dívida que
ficou "para depois", o gotcha que já custou uma tarde. E declara pronto o que
só está pronto no repositório.

Esta skill troca memória por estrutura. São documentos com dono e prazo, sessões
com fim verificável e uma definição de pronto que não se cumpre só com um
commit.

---

## 0. Os dois modos de entrada

### Iniciar um projeto

1. **Entenda o projeto antes de escrever.** Pergunte o que o produto faz, para
   quem, qual o prazo e qual a frase que decide empates (exemplo real:
   *"prefiro que erre alto a coletar mais"*). Pergunte também o que é
   irreversível e o que custa dinheiro. Escreva as respostas com as palavras do
   dono.
2. **Crie os documentos** a partir de [`modelos/`](modelos/). Comece pelo
   primer, pelo roadmap e pelo progresso. Diário, catálogo de erros e decisões
   nascem vazios, com o cabeçalho que diz para que servem.
3. **Quebre o trabalho em sessões de 1–2 h**, cada uma com um entregável
   verificável. Ordene por **dependência de dado**, não por vitrine: o que é
   mais importante na comunicação não é necessariamente o primeiro a ser
   construído. Escreva essa distinção, para ela não ser confundida depois.
4. **Declare os portões** (testes, lint, typecheck, CI) e o que fecha uma
   sessão. Declare também o que é decisão do dono (seção 4).
5. **Desenhe a falha antes do código** (`falha-ruidosa`) e a fronteira de
   autorização antes da primeira tabela (`seguranca`). Reformar depois custa
   mais.
6. **Abra a sessão 1** com o protocolo da seção 2.

### Avaliar um projeto existente

Siga [`referencia/maturidade.md`](referencia/maturidade.md): dez dimensões, cada
uma com uma sonda (um comando ou arquivo) e critérios observáveis. O relatório
começa pelas três faltas mais caras e termina pelo que está bom e não deve ser
mexido. Não crie documentos novos antes de o dono ver o relatório.

---

## 1. Os documentos que sustentam a continuidade

São sete, cada um com um único trabalho. Os modelos estão em
[`modelos/`](modelos/).

| Documento | Trabalho | Quem lê | Regra que o mantém útil |
|---|---|---|---|
| **Primer** (`CLAUDE.md`/`AGENTS.md`) | Orientar rápido e carregar **o que não está no código**: regras invioláveis, fronteiras em vigor, gatilhos de reabertura | Todo agente, toda sessão | **Tem teto.** Carrega a sessão atual e a anterior; a mais velha desce para um histórico. O corte é **por tipo**, não por idade (ver abaixo) |
| **Roadmap** (`SESSOES.md`) | O que vai ser construído, em sessões de 1–2 h com fim verificável | Quem planeja | Adiar algo = escrever a etapa **na sessão que a recebe**, como primeiro passo do plano |
| **Progresso** (`PROGRESSO.md`) | O estado **agora** e o bloco "▶️ retomar aqui" | O próximo agente, o próximo você | Descreve a sessão em curso; atualizado **a cada etapa**, não no fim |
| **Diário** | Uma entrada por sessão: o que foi feito, o que foi decidido e por quê, o que se aprendeu | Quem precisa do porquê | Entrada nova no topo, com data; narrativa, não estado |
| **Catálogo de erros** | Erros que **você** cometeu, com o incidente concreto e o antídoto | Todo agente, ao achar um defeito | Organizado **por classe**; uma ocorrência nova entra na classe existente. Sem incidente, não entra |
| **Decisões** | O que foi decidido, por quê e **o gatilho que reabre** | Quem pensa em mudar algo | Decisão sem gatilho escrito tende a ser reaberta por impulso |
| **Barra de progresso** | O estado para o dono ler **sem abrir código** | O dono | Zero jargão, números conferidos na hora e com data |

**Uma fonte por fato.** Se dois agentes precisam da mesma lista, ela mora num
arquivo só: um lado importa, o outro aponta. Duas cópias de instrução não
quebram build nenhum. Elas produzem um agente trabalhando com a versão velha, e
o sintoma aparece semanas depois como *"por que ele fez assim?"*. Um teste pode
reprovar a cópia: procure uma frase-âncora em todos os `.md`.

**O corte é por tipo, não por idade.** Antes de descer um bloco velho para o
histórico, separe o que há nele:

| Conteúdo | Destino |
|---|---|
| Restrição que ainda decide algo (fronteira, gatilho, portão, decisão do dono com efeito futuro) | **Sobe** para o primer e fica |
| Lição com incidente concreto | Catálogo de erros |
| Narrativa do que aconteceu | Desce para o histórico |

Um corte só por idade apaga uma regra junto com a história de como ela foi
descoberta, e a sessão seguinte quebra a regra sem nunca ter sabido dela. **Antes
de podar, pergunte: "se este bloco sumisse agora, o que eu perderia?"**

**Mudar documentação de lugar se explica no próprio documento.** Diga o que
saiu, para onde foi e o que ficou de propósito. Um ponteiro seco diz onde está
o texto, não qual é a regra.

---

## 2. A sessão como unidade

### Abrir

1. **Leitura obrigatória, antes de qualquer trabalho.** Primer, o bloco
   "retomar aqui", o trecho do roadmap e a skill da área que vai ser tocada.
   Vale também depois de um compact (ver `pre-compact`): o resumo da conversa
   registra uma leitura passada e não substitui a leitura.
2. **Estado do repositório:** `git status`, branch, últimos commits, travas de
   processos longos. Mudança que você não reconhece: pare e descubra de quem é
   antes de tocar.
3. **Estado do mundo**, quando houver produção: o que está no ar, o que entrou
   no código desde então e o que foi aplicado no banco. Medido com comando, não
   copiado de documento (ver `evidencia`).

### Planejar

- **Pergunte antes de planejar**, em rodadas pequenas e agrupadas por assunto.
  Comece pelas perguntas que decidem o **tamanho** da sessão e termine pelas de
  borda. Cada opção vem com a consequência escrita, e a recomendada fica em
  primeiro. Pergunte só o que é decisão do dono (seção 4).
- **Some as respostas antes de construir.** Respostas razoáveis uma a uma podem
  se anular juntas. *Caso real:* três escolhas independentes sobre um indicador
  de seta produziam, somadas, só setas verdes, e a seta virava enfeite. Uma
  pergunta a mais, mostrando a combinação, mudou a decisão.
- **Escreva o plano por fases e etapas**, denso o bastante para sobreviver a um
  compact. O formato está em [`referencia/plano-de-sessao.md`](referencia/plano-de-sessao.md):
  mapa de checkpoints no topo, e cada etapa com **Faz**, **✅ Checkpoint** (uma
  afirmação que um comando confere, com o número esperado) e **🐞 Previsto →
  Depurar**.
- **Tudo que for adiado vai primeiro para a sessão que o recebe.** É o primeiro
  passo do plano, antes de qualquer código. Uma etapa que só existe na conversa
  não chega à sessão seguinte.
- **Medições da abertura entram no plano com data.** No dia seguinte elas são
  registro de uma medição, não o estado.

### Executar

- **O documento de progresso se atualiza a cada etapa fechada.** Um documento
  de estado parado é um estado plausível e errado em tela cheia.
- **Execuções longas (CI, build, suíte grande, mutação) vão para o background,
  e esperar por elas não é trabalho.** Pergunte o que dá para adiantar
  enquanto rodam. Um laço `until … sleep` depois de mandar para o background é
  o mesmo desperdício com outra roupa. Se não há nada a adiantar, devolva a
  resposta e espere a notificação.
- **Teste no caminho onde a decisão acontece** (a função do banco, o webhook,
  a ação do servidor), não numa cópia da regra que o teste alcança com mais
  facilidade. *Caso real:* uma função pura estava testada, e a produção rodava
  uma cópia da mesma regra dentro de outra função. Ver `testes-que-provam`.
- **Todo caminho novo responde "se isto estivesse errado, o que apareceria?"**
  antes de ser dado por pronto. Ver `falha-ruidosa`.
- **Toda afirmação escrita separa o medido da hipótese.** Ver `evidencia`.
- **Com o plano aprovado, siga até o fim sem pedir confirmação a cada fase.**
  Faça você mesmo a revisão de fim de fase. Pare apenas para o que é decisão do
  dono.

### Fechar

Nesta ordem, porque cada passo pega uma classe diferente de defeito:

1. Portões verdes, **lidos** (citando a linha literal da ferramenta, não a sua
   leitura dela).
2. **Revisão em duas passadas** (seção 6).
3. Documentos: entrada no diário, progresso, roadmap e barra de progresso com os
   números de hoje.
4. Commit com o **porquê** na mensagem, não só o quê.
5. Se o trabalho muda produção: o conserto está **no ar**? (seção 3)

---

## 3. A definição de pronto é uma escada

| Degrau | Pergunta que ele responde |
|---|---|
| 1. Código escrito | Existe? |
| 2. Portões verdes, lidos | Passa no que eu sei cobrar? |
| 3. Teste que **cai** com o defeito (mutação verificada) | O teste prova o que diz provar? |
| 4. Defeito **explicado** | O que era, por que passou, e o que agora impede que volte? |
| 5. **No ar / aplicado** | O defeito parou de acontecer? |
| 6. Conferido por quem usa (quando é tela ou fluxo) | Faz o que a pessoa queria? |

Commit, push e CI verde param no degrau 3. **Uma dívida só está fechada no
degrau 5.** Oferecer o deploy como "próximo passo opcional" é deixar a dívida
aberta com outra aparência. Se subir depende de autorização, peça a autorização
na hora, como pergunta.

*Caso real:* um conserto commitado e verde ficou dias sem subir. Enquanto isso,
uma decisão do dono que dependia dele ("deixa o inventário velho morrer em três
semanas") estava parada sem sintoma, porque o relógio só começava com o
conserto no ar.

**Folga não é resolução.** *"Isto só dói no dia 15"* responde **quando dói**. Não
responde **se está resolvido**.

---

## 4. Dívida e decisões

### Dívida achada na sessão fecha na sessão

"Não está no plano aprovado" não isenta nada. O plano diz o que vai ser
**construído**, não o que pode ficar quebrado. Adiar existe, mas é decisão do
dono, **pedida na hora**. Escrever num `.md` que a dívida existe não é tratá-la.

**Gatilho mecânico:** ao escrever "fora do escopo", "para uma sessão futura" ou
"decisão para depois", pare e pergunte: *isto é dívida?* Se for, conserte ou
pergunte.

A exceção tem prazo. Um defeito que **só um usuário final veria** pode esperar
enquanto não há usuário final, **se o dono decidir** e se a premissa ficar
escrita junto (*"ninguém usa ainda"*). No dia em que houver usuário, a isenção
acaba. Dado errado não entra nessa exceção, porque contamina tudo que o lê.

### Quem decide o quê

| Decide o dono (você pergunta, com o dado na mão) | Decide você (você recomenda, e ele pode derrubar) |
|---|---|
| Domínio: nomes, agrupamentos, o que o mercado entende | Como separar falha transitória de definitiva |
| O limiar de "bom o bastante" para um portão ou uma latência | Que estrutura impede uma classe de defeito de voltar |
| Preço, prazo, escopo, o que entra em cada sessão | Qual precedente do projeto vale para um caso novo |
| Adiar uma dívida | Se algo **é** dívida |
| Qualquer escrita irreversível em produção (autorização na hora) | Como conferir essa escrita antes |

A pergunta que separa as colunas: *a resposta depende de algo que só ele sabe?*

**Um achado seu chega com recomendação, não com um menu.** Você leu o código e
mediu o modo de falha. Três opções apresentadas como equivalentes devolvem a ele
o custo de refazer o seu raciocínio. O formato é: a recomendação, o porquê e o
que faria você mudar de ideia.

**Não invente um limiar e depois trate como portão.** Anunciar *"se passar de
10 s, a decisão volta para a mesa"* antes de medir faz o número parecer
combinado. *Caso real:* deu 11,3 s, começaram gastos de API para decompor a
latência, e o dono respondeu *"calma, 11 segundos tá bom"*. Meça, reporte e
pergunte.

**O aval para escrever em produção é condicional à sua conferência.** Se o dono
aprova *"se você estiver confiante"*, a confiança tem de vir **antes** da
escrita. Isso significa:

- reler o que vai ser aplicado, na versão do disco;
- rodar o `--dry-run` e comparar com o esperado;
- apontar o que é irreversível e o que custa dinheiro;
- ler o código e os arquivos que vão subir, com olho de revisor.

Se a conferência não fecha, diga que não está confiante.

**Pergunte antes de construir o que foi descrito com palavras do dono**,
sobretudo em tela: uma rodada de perguntas, com opções concretas, e depois siga
até o fim. *Caso real:* a "seta" pedida já existia com outro significado, e os
dois sentidos se contradiziam num caso medido.

### Decisões de arquitetura

- **Nenhuma peça nova sem o gatilho que a justifica, escrito antes:** um
  segundo consumidor para um pacote compartilhado, uma latência que o runtime
  atual não serve para um serviço novo, dois usuários compartilhando dados para
  uma entidade de "organização". Sem gatilho, a abstração é especulativa.
- **Toda decisão registrada leva o gatilho que a reabre** (modelo em
  [`modelos/DECISOES.md`](modelos/DECISOES.md)). Não se reabre uma decisão sem
  que o gatilho tenha disparado. Uma decisão proposta e **recusada** também se
  registra, com o motivo, para não ser proposta de novo.
- **Estrutura vence disciplina.** Quando duas coisas precisam concordar (duas
  listas, dois idiomas, código e configuração de deploy, texto público e
  mecanismo), prefira uma forma em que elas **não possam** divergir: fonte
  única, valor derivado, tipo, ou teste que lê as duas pontas.
- **Uma decisão sobre dados que se comporta diferente por contexto** (fundir
  dois tipos na busca, mas não no cálculo de preço) fica escrita com a medição
  que a sustenta, porque a próxima pessoa vai querer "simplificar".

---

## 5. Medir progresso real

- **A barra é auditável.** Mostre a conta: quantos itens fechados, quantos
  parciais, de quantos. Um item parcial conta como parcial, para o número não
  inflar.
- **Progresso é degrau da escada (seção 3), não número de commits.**
- **Números para o dono são conferidos no momento de escrever**, contra a fonte
  (`count(*)`, `describe`), com data. Um número copiado de um documento anterior
  é o erro mais repetido que existe (ver `evidencia`).
- **Validar a implementação contra o plano:** no fim de cada fase, releia os
  checkpoints do plano e rode os comandos deles. *"Implementei a fase"* não é
  *"a fase passou nos checkpoints dela"*.
- **Tela e texto contra o mecanismo:** quando o plano descreve mecanismo **e**
  texto de interface, os dois entram no mesmo commit ou nenhum entra. O texto é
  barato de escrever e chega sozinho se ninguém segurar.

---

## 6. Revisar duas vezes

O conserto é código novo, escrito rápido e sob a pressão de já ter achado o
defeito. É ali que nasce o defeito seguinte. Por isso existe uma passada de
revisão marcada para **depois** do conserto.

**A segunda passada muda a pergunta.** Repetir a mesma verificação é olhar uma
vez com mais confiança, e isso é pior, porque a segunda leitura valida a
primeira em vez de desafiá-la.

| Primeira pergunta | Segunda, que é outra |
|---|---|
| A imagem no ar é o HEAD? | O que entrou no código desde a imagem no ar? |
| A guarda está certa? | O que este conserto tornou falso? (teste que mirava a linha antiga, comentário, âncora, número num documento) |
| O teste passa? | Se ele ficar verde, quantas explicações isso admite? |
| Quem escreve nesta tabela? | O que faz uma linha daqui deixar de ser verdade, e quem escreve **isso**? |

Se você não consegue formular uma segunda pergunta diferente, você não revisou:
só releu. O roteiro completo está em [`referencia/revisao.md`](referencia/revisao.md).

---

## 7. Quando parar, revisar ou refatorar

**Parar** (e perguntar ou avisar):

- quando a próxima ação é irreversível, custa dinheiro ou escreve em produção;
- quando existe uma trava de processo longo (mutação, migração) na árvore;
- quando o `git status` mostra mudança que você não fez;
- quando um portão falha e a explicação ainda não existe. Consertar primeiro é
  regra: não se constrói sobre um defeito conhecido sem autorização explícita;
- quando você se pega investigando a hipótese mais cara antes da mais barata
  (ver `depuracao`).

**Revisar:**

- ao fim de cada fase e depois de cada conserto (seção 6);
- quando um documento seu concorda com o que você ia concluir. Isso abre a
  questão, não fecha (ver `evidencia`);
- quando uma ferramenta nova acusa algo na primeira execução: a primeira
  suspeita é a ferramenta.

**Refatorar**, só com motivo concreto:

- a mesma classe de defeito apareceu duas vezes. É hora de trocar disciplina
  por estrutura: derivar a lista, criar o tipo, a fonte única ou o teste que
  compara as duas pontas;
- duas listas precisam concordar e nada as compara;
- uma regra existe em N cópias;
- um código não pode ser importado por teste. Isso é sintoma, e a correção é
  tirar a peça pura para onde o teste a alcança;
- **nunca** por preferência de estilo, nem como efeito colateral de uma tarefa
  pequena.

---

## Testes de falha

Você está errando se:

- o documento de progresso diz uma coisa e o `git log` diz outra;
- existe "para depois" escrito sem o "ok" do dono;
- você disse "pronto" e o conserto não está no ar;
- a mesma verificação rodou duas vezes e isso foi chamado de revisão;
- você apresentou um menu de opções equivalentes para um achado seu;
- um número no relatório não tem comando nem data de origem;
- a sessão seguinte precisaria da conversa de hoje para continuar.

## Critério de conclusão (de uma sessão)

- [ ] Portões verdes, lidos, com a linha literal citada.
- [ ] Duas passadas de revisão, com perguntas diferentes.
- [ ] Nenhuma dívida aberta sem autorização registrada.
- [ ] O que muda produção está no ar e foi conferido por comando.
- [ ] Diário, progresso, roadmap e barra atualizados, com números de hoje.
- [ ] O "retomar aqui" tem um próximo passo que cabe numa linha com comando.

## Combina com

`pre-compact` (o fechamento vira retomada), `evidencia` (todo número e toda
causa), `testes-que-provam` (degraus 2 e 3), `nuvem-e-deploy` (degrau 5).
