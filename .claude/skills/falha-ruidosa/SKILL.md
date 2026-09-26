---
name: falha-ruidosa
description: Confiabilidade e observabilidade — desenhar sistemas que erram ALTO em vez de entregar um resultado plausível e errado. Falha nunca como valor vazio, número que carrega se está completo, código de saída para resultado parcial, execução não confiável que não muta estado, veredito com camadas (proveniência, expectativa, linha de base, canário), registro de execução que nasce no início, alerta sobre ausência, falha transitória versus definitiva, e o raio de uma falha externa. Use ao desenhar job, pipeline, agendamento, tratamento de erro, alerta, painel de operação, ou ao revisar qualquer caminho que possa terminar "com sucesso" tendo feito menos do que devia.
---

# Falha ruidosa — errar alto, nunca plausível

## Quando usar

- Ao desenhar qualquer coisa que roda sem ninguém olhando: job, agendador,
  pipeline, webhook, sincronização.
- Ao escrever um `catch`, um valor padrão, um `return []`, um `?? 0`.
- Ao montar alerta, painel de operação ou métrica.
- Ao revisar: *"se isto estivesse errado, o que apareceria?"*

## Quando não usar

- Em protótipo descartável sem consumidor. Mas escreva que é descartável:
  o dia em que alguém passar a ler o resultado muda tudo, e nada no código
  avisa.

## O princípio

> Entre **fazer mais** e **errar mais alto**, errar mais alto ganha.

O que faz alguém depurar o sistema toda semana não é o timeout, porque o timeout
avisa. É a falha que devolve um número pequeno e plausível. Um processo que
entrega 40% e **diz** que entregou 40% é um problema agendado. Um processo que
entrega 40% e parece saudável é uma dívida que cresce em silêncio, e a conta
chega meses depois, quando alguém confia no número.

---

## Os padrões

### 1. Falha nunca se representa com valor vazio

Uma função que pode falhar devolve `None` (ou um tipo com motivo) para **"não
consegui"**, e `[]`/`""`/`0` só para **"consegui, e não havia nada"**.

*Casos reais:* um render que estourou o tempo devolveu 200 com HTML vazio, e
"não deu tempo" virou "o site não tem anúncios". Um sitemap que era, na
verdade, a home em HTML passou como "sitemap lido, zero imóveis". Uma paginação
bloqueada no meio virou "fim do catálogo".

**Pergunte:** *este vazio significa "nada" ou "não sei"? Quem lê consegue
distinguir?*

### 2. Todo número que chega a um humano carrega se está completo

Se parte da varredura foi interrompida, o total é **piso, não medida**, e a
saída diz isso (`completo: false`, `motivo`). Um número que perdeu a informação
de como foi obtido produz conclusões erradas mesmo sendo tecnicamente correto.

**Um teto silencioso é uma interrupção.** *Caso real:* seis fontes paravam em
exatamente 1.000 itens numa listagem, e o que ficava de fora era dado como
"saiu" e apagado do produto. Quem bate num teto conhecido não está completo.

### 3. Resultado parcial sai com código diferente de zero

Sem isso, um agendador não distingue uma execução pela metade de uma execução
boa. Documente o que cada código quer dizer **por processo**. Numa casa, `exit 2`
era "parcial" (uma fonte reprovada) para os jobs de coleta e "falha" para a
auditoria de segurança. A tabela de exceções é um campo por processo, não um
`if` espalhado.

### 4. Execução não confiável não muta estado autoritativo

- Não marca nada como morto, não sobrescreve valor bom, não alimenta série
  histórica.
- **Não entra na linha de base.** Se entrasse, a próxima execução igualmente
  ruim passaria, e a degradação viraria o normal.
- Quando a decisão depende de duas perguntas diferentes ("a execução foi boa?"
  e "a lista estava completa?"), exija as duas. Não troque uma pela outra.

Coletar a menos é um problema. Apagar o que estava certo por causa de uma
execução ruim é pior e é irreversível.

### 5. Veredito com dentes, em camadas

Cada camada pega um modo de falha que as outras não pegam:

| Camada | Pega |
|---|---|
| **Proveniência** (de onde veio cada dado; se usou fallback) | "não consegui ler" virando "veio vazio" |
| **Expectativas absolutas** (piso, teto de sanidade) | volume absurdo para cima ou para baixo |
| **Linha de base histórica** (mediana das últimas N execuções **confiáveis**) | degradação lenta, que regra absoluta nenhuma pega |
| **Canários** (fixture real conferida contra a config) | a nossa configuração deixar de casar com o mundo |
| **Disjuntor** (para depois de N recusas seguidas) | resposta de recusa contada como resposta vazia |

Use **mediana** e não média na linha de base, para que uma execução
catastrófica não puxe o histórico para baixo. Quando um canário falhar,
recapture a fixture e confira à mão antes de mexer no número esperado. Baixar o
esperado sem olhar transforma o canário em decoração.

### 6. Ausência nunca é verde

- A tela de operação parte do conjunto **esperado** (a lista de jobs
  declarada), não do que o banco devolveu. Derivar do banco faz sumir da tela o
  job que **nunca rodou**.
- Sem registro, a célula diz **"sem registro"** com o mesmo peso visual de um
  problema, nunca num cinza discreto.
- **Um alerta cuja ausência é o defeito também existe.** Se um aviso de
  auditoria é esperado por desenho, o dia em que ele some sem ninguém ter mexido
  é o dia em que algo quebrou.

### 7. O registro da execução nasce no início

Escreva a linha na **entrada** (`fim = NULL`) e feche na saída. Gravar só no fim
reproduz a cegueira: um `SIGKILL` não passa por `finally`, e o job que morre no
meio não grava nada. Linha aberta e velha = **travado**, nunca "rodando".

**Ambiente interativo não escreve no registro de produção.** *Caso real:* a
guarda era "sem URL de banco, não grava". O `.env` local tinha a URL de
produção, e a suíte de testes escreveu 30 linhas no registro de produção. A
condição certa é o **ambiente** (agendado ou interativo), não a presença de uma
credencial.

### 8. Alertas: evento → métrica → e-mail, com o contrato testado

- O código emite um **evento estruturado** com nome estável; a infraestrutura
  transforma em métrica de log; a métrica dispara o alerta.
- **O nome do evento é um contrato entre duas pontas** (código e filtro do
  alerta). Um teste lê as duas do disco e reprova se divergirem. Mudar a frase
  no código sem mudar o filtro desliga o alerta em silêncio.
- **Uma segunda testemunha que sobrevive ao seu log quebrar:** a métrica nativa
  da plataforma para "execução falhou" ou "agendador falhou".
- **Não alerte a operação normal.** Um cartão recusado é operação, e ele não
  pode usar o prefixo que o alerta de falha definitiva casa. Alarme que dispara
  à toa ensina a ignorar alarmes.
- **Filtre o log pelo campo que o seu código escreve**, não pela severidade que
  a plataforma infere. Um filtro por `severity` que não casa devolve zero, e
  zero parece "nenhum problema".
- Todo serviço que mexe em dinheiro ou acesso tem **pelo menos um** alerta
  próprio. *Caso real:* as cinco políticas de alerta eram todas sobre o job de
  coleta. Uma tempestade de 500 no webhook de pagamento seria invisível.

### 9. Calibrar antes de cobrar

Uma verificação nova nasce como **observação** (mede, grava e não reprova). Ela
vira **divergência** (reprova) depois de uma rodada limpa em produção ter
mostrado a distribuição. Mantenha as duas listas separadas **por estrutura**:
quem produz observação nunca produz divergência, e um teste prende isso. Ligar
uma verificação é mover o campo de uma lista para a outra.

### 10. Transitória ou definitiva — e o padrão é transitória

Num `catch` que responde a um terceiro (fila, webhook, agendador), pergunte:
*desta lista de erros que eu capturo, quais a retentativa conserta?*

- **Transitória** (rede, banco fora, terceiro fora): falhe com o código que
  provoca a retentativa (5xx).
- **Definitiva** (configuração errada, referência inexistente, contrato
  violado): marque o estado como `falhou` com o motivo, deixe visível e alerte.
  Um 500 eterno repete o mesmo erro até o terceiro desistir, e o log acusa a
  rede quando o defeito é seu.
- **A classe é um tipo** (`FalhaDefinitiva`), lançado onde a causa é conhecida.
  O `catch` bifurca por tipo. Do banco, a classe atravessa como **código de
  erro**, não como texto de mensagem.
- **O que você não entende continua transitório.** Reentregar algo não
  entendido é seguro; engolir com 200 é perder.
- **`200` faz o terceiro parar de reentregar.** Nunca responda 200 para "eu
  reconheço este evento como meu e não consegui processá-lo".

### 11. O raio da falha

Toda dependência externa vai falhar por alguns minutos algum dia; isso é
operação, não hipótese. A pergunta de revisão não é *"isto pode falhar?"*, é
**"quando isto falhar, o que mais para de funcionar junto?"** A resposta boa é
"só isto", e isso exige uma **cerca por seção**, não uma no fim do mundo.

*Caso real:* o fornecedor recusou por uns dois minutos um token de sessão
válido (a causa ficou do lado dele e não foi medida), uma leitura de lista
falhou, e a página inteira caiu, levando junto as tarefas do usuário, que
vinham de outra tabela.

### 12. Mensagens que dizem a causa certa

- 4xx do terceiro é **nosso pedido** errado; 5xx e transporte são **deles**.
  Não escreva "o serviço não respondeu" para um 400: ele respondeu e disse que o
  pedido não serve.
- Não retente o que nunca vai dar certo (4xx, exceto 429).
- *"Tente novamente em instantes"* só é verdade quando a retentativa resolve.
  Uma frase genérica não envelhece junto com as causas que ela cobre.

### 13. Tabela derivada tem duas lacunas

Toda tabela projetada a partir de outra precisa de duas medições:

1. **Presença:** o produto enxerga tudo o que a base tem?
2. **Validade:** o produto mostra algo que a base já sabe que não vale mais?

*Caso real:* 384 itens marcados como mortos na origem continuaram buscáveis por
semanas, porque a projeção era upsert puro e a verificação só media presença.

Uma rotina de reconciliação (por exemplo, semanal) mede as duas e sai ≠ 0 quando
sobra lacuna.

### 14. Etapa recorrente nunca fica manual

Se uma etapa precisa acontecer toda semana, ela é **agendada e alertada**, não
anotada para alguém lembrar. *"É delicado"* é motivo para mais guarda
(transação, conferência, código de saída), não para deixar manual. A
alternativa real a automatizar não é "alguém decide com calma", é "ninguém roda
e ninguém percebe".

---

## As duas perguntas de revisão

1. **Se isto estivesse errado, o que apareceria?** Quando a resposta honesta é
   "nada", é ali que está o trabalho.
2. **Quando isto reprovar, dá para saber o porquê sem abrir o banco?** Um
   alerta que obriga a investigar para distinguir incêndio de fumaça gasta a
   confiança que existe para proteger.

## Testes de falha

O desenho está falhando se:

- existe `catch` que loga e segue, num caminho que decide dinheiro, acesso ou
  apagamento;
- um job pode terminar com código 0 tendo processado menos do que devia;
- o painel de operação é gerado a partir do que o banco devolveu;
- um alerta depende de uma string que nenhum teste amarra ao código;
- você não sabe dizer qual evento dispara cada alerta, nem se esse evento ainda
  é emitido;
- "sem dados" e "zero" aparecem iguais na tela.

## Critério de conclusão

- [ ] Cada caminho de falha tem um sinal: código de saída, evento ou estado
      visível.
- [ ] Parcial e ausência são distinguíveis de sucesso, na tela e no alerta.
- [ ] O contrato evento↔alerta está preso por teste.
- [ ] Transitório e definitivo são tipos diferentes, e o padrão é transitório.
- [ ] Uma mutação que remove a guarda derruba um teste.
