---
name: evidencia
description: Disciplina para afirmar coisas — um número, uma causa, um estado ("está no ar", "funciona", "está verde"), uma ausência ("não existe", "não temos acesso") ou uma existência ("o recurso suporta X"). Separa fato medido, inferência e hipótese; trata documentação nossa como registro de medição passada; ensina a ler saída de ferramenta sem se enganar e a relatar com a prova junto. Use antes de escrever qualquer número ou causa num relatório, documento, commit ou resposta, ao decidir com base em um documento, e ao contradizer alguém.
---

# Evidência — o que eu sei, e como eu sei

## Quando usar

- Antes de escrever um número, uma causa ou um estado em qualquer lugar que
  alguém vai ler: resposta, relatório, documento, comentário, mensagem de
  commit, log.
- Ao decidir com base num documento, num comentário ou num resumo.
- Ao afirmar que algo **não** existe ou **não** é possível.
- Ao corrigir alguém.

## Quando não usar

- Em exploração privada, antes de concluir qualquer coisa. Ali a hipótese pode
  ser solta, desde que não saia dali com cara de fato.

## O princípio

A falha mais repetida em trinta sessões não foi de código. Foi aceitar como
medição algo que era **registro de uma medição passada**, ou nem isso. Um
comentário no YAML dizia "o alvo devolve 15 anúncios", e ele tinha 1.633. Cinco
documentos afirmavam que a imagem no ar era uma, e era outra. Uma citação entre
aspas "da sessão anterior" tinha sido inventada horas antes pelo próprio agente.

Um texto nosso não é uma fonte independente. Quando ele concorda com o que você
ia concluir, isso é **uma** testemunha, e é a menos confiável das duas.

---

## As regras

### 1. Documentação nossa é registro, não evidência

Isso vale para README, comentário, docstring, anotação de tipo, texto de `help`
de uma flag, mensagem de commit, resumo de conversa, log velho em `/tmp` e o
seu próprio texto de dez minutos atrás.

**A pergunta:** *quem mediu isto, quando e com qual comando?* Se a resposta
não está escrita ali, é hipótese e vale zero como confirmação.

- **A anotação de tipo é uma promessa.** `list[str]` e `help="repetível"` dizem
  o que o autor pretendia. *Caso real:* `-t a -t b` virava o literal `{a,b}`
  numa comparação SQL. Resultado: zero linhas, nenhum erro, e "nada pendente"
  sobre uma fila de 8.549.
- **Uma citação entre aspas ganha procedência que não tem.** Antes de repetir
  uma citação, faça `grep` nela. *Caso real:* a frase existia só em dois
  arquivos escritos no mesmo dia pelo mesmo agente, e o registro original dizia
  o contrário.
- **Um log de execução passada não é medição atual.** Pergunte: *este log é de
  qual execução, e ela é posterior à última mudança que mexeria nele?*
- **Um hash, um id ou um estado escrito num documento** é o registro de um
  `describe` de algum dia. Antes de repetir, rode o `describe`.

### 2. Hipótese se escreve como hipótese

O vocabulário separa as coisas, e ele precisa ser usado de forma consistente:

| Palavra | Quer dizer |
|---|---|
| **medido** | um comando rodou agora (ou na data citada), e o resultado está aqui |
| **inferido** | segue logicamente de algo medido; diga de quê |
| **hipótese** | plausível e não testada |
| **não confirmado / requer verificação externa** | fora do seu alcance (painel de fornecedor, produção sem credencial) |

*Caso real:* *"é propagação da API recém-habilitada"* foi escrito como causa, e
o `apply` foi repetido com base nisso. Falhou igual. O log de auditoria dizia
outra coisa: os Termos de Serviço nunca aceitos, com a permissão **concedida**
na linha ao lado.

**Uma frase que explica um problema real é a mais difícil de duvidar**, porque
o problema confirma a explicação todo dia. O topo de um feed estava cheio de
lixo, e "é erro de parse de área" parecia óbvio. Dois dos casos citados eram
fazendas reais de 210 hectares.

### 3. Fontes precisam ser independentes

- **Duas fontes que concordam não são duas quando uma copiou a outra.**
- **Concordância entre execuções do mesmo código prova determinismo, não
  acerto.** *Caso real:* três dry-runs do estimador deram a mesma taxa de custo
  e foram chamados de "três medições independentes". O custo real era 3,7×
  menor.
- **Pergunte:** *estas fontes são independentes, ou é o mesmo código
  respondendo?*

### 4. Afirmar ausência ou existência é afirmação como qualquer outra

Essas são as afirmações mais fáceis de fazer sem procurar, porque não achar
nada parece confirmação.

- *"Não existe canal de alerta"*: existiam cinco, no fim de um arquivo que não
  foi lido até o fim.
- *"Esta sessão não tem acesso ao banco"*: tinha, e o arquivo de ambiente não
  tinha sido aberto. **Afirmar ausência de acesso é pior que afirmar ausência de
  fato:** um fato errado alguém contesta, e um acesso "inexistente" ninguém
  tenta usar. O custo foi trabalho não feito.
- *"O recurso existe na nossa região"*: não existia, e ninguém tinha perguntado.
- *"Não dá para saber a causa"*, declarado depois de olhar **uma** fonte. A
  pergunta que faltou: *que outra tabela sabe quando isto mudou?*

**Antes de afirmar que algo existe ou não existe, abra o lugar onde estaria.**
Para uma capacidade de fornecedor, isso é a lista de regiões ou de
funcionalidades dele, não o fato de o comando existir.

### 5. Pergunte quanto deveria ser

Antes de aceitar um número extraído, estime a ordem de grandeza. Se você não
sabe estimar, não sabe se a extração funcionou.

- **Zero é implausível** para um push sem nenhum run de CI, para uma fila medida
  de manhã, para um grupo que já tem membros contados.
- **O número plausível é o perigoso.** "19 passed" onde deviam ser 21. "151
  testes" onde eram 232, porque um corte por índice apagou 1.641 linhas e a
  suíte menor continuou verde.
- **`passed + failed + skipped` tem de bater com o total,** e um `skipped` novo
  é notícia.

### 6. Compare só o que é comparável

Antes de acreditar numa comparação, pergunte:

- **São contemporâneas?** Um preço extraído comparado com o payload **mais
  recente** "acusou" 167 erros. Eram 43; os outros eram preços que mudaram
  depois.
- **Estou comparando com a fonte, ou com a minha aproximação dela?** O primeiro
  `R$` do texto não é o preço de venda.
- **As duas pontas devolvem o mesmo número de linhas? O mesmo plano?** Um
  `count(*)` em volta de uma consulta muda o plano, não só o tempo.
- **É estimativa ou contagem?** Uma estatística do planejador não conta linhas.
  Em documento, contagem sai de `count(*)`.
- **Se esta régua ficar verde, quantas explicações isso admite?** Se admitir
  mais de uma, ela não é a régua.

### 7. Ler saída de ferramenta

| Armadilha | Antídoto |
|---|---|
| Códigos de cor entre a chave e o valor | remover as sequências ANSI antes do `grep` |
| Numa cascata, a primeira linha é a estratégia que **falhou** | ler a última, ou o campo que o manifesto declara como usado |
| Nome de campo não é semântica (`Completed` é o nome da condição; `failedCount` conta saída ≠ 0, inclusive a parcial deliberada) | ler a documentação do campo |
| `tail` corta o topo, que é onde muitas ferramentas põem o que recusam | saída inteira em arquivo; ler do topo |
| Pipe troca o código de saída pelo do último comando | redirecionar para arquivo, não para `tail` |
| Filtro que devolve lista vazia sem erro (um vigia mudo) | o laço deve **reclamar** quando não acha nada |
| Terminal corta colunas | identificador (URL, hash, id) se copia **da fonte**, nunca completado de memória |

**No relatório, cite a linha literal da ferramenta**, não a sua leitura dela.
*Caso real:* a primeira linha dizia `ancoras ruins: 1`, e o relatório disse
"0 órfãs", porque a leitura procurou no fim a frase que esperava.

### 8. Medir antes de virar regra; o limiar de "bom" é do dono

- Uma regra que reprova, apaga ou funde **nasce desligada**, gravando o número.
  Ela só passa a cobrar depois de medida. Alarme mal calibrado é ignorado, e
  alarme ignorado também falha no dia em que está certo.
- **Um piso declarado sai de um número medido**, com a data e o comando no
  comentário.
- **O número que define "bom o bastante" é do dono.** Meça, reporte e pergunte.
  Não anuncie um limiar e depois o trate como combinado.

### 9. Fato não é intenção

`charges_enabled: false` é fato. *"Portanto alguém precisa ativar"* é uma
inferência sobre a intenção de alguém, e estava errada: era sandbox **por
escolha**. A ausência de uma configuração pode ser esquecimento ou decisão, e as
duas são indistinguíveis pela API. Quem responde é o dono, com uma pergunta de
uma linha.

### 10. Contradizer exige medição completa e de agora

Para corrigir um fato registrado, a medição parcial serve para investigar, não
para corrigir. *Caso real:* a correção disse "são três, não cinco" com 8 de 15
medidos. Eram cinco.

---

## Como relatar

```
**Medido** (<data hora>, `<comando>`): <resultado literal>
**Inferido** de <o quê>: <conclusão>
**Hipótese**: <o que ainda não testei> — o teste que decide: <comando>
**Não confirmado / requer verificação externa**: <item> — porque <motivo>
```

- Todo número com a data. Amanhã ele é registro.
- A linha literal da ferramenta junto do veredito.
- Rede instável durante a medição → a medição é suspeita, inclusive a que
  confirma o que você achava.

## Testes de falha

Você está errando se:

- escreveu "conferido" ou "medido" ao lado de um número que copiou de um
  documento;
- a sua fonte e a sua conclusão foram escritas pela mesma pessoa no mesmo dia;
- afirmou que algo não existe sem abrir o lugar onde estaria;
- um relatório seu diz "verde" e você não consegue colar a linha que diz isso;
- você usou o vocabulário do antídoto ("o medido, não o documento") para
  justificar um número que era um log velho.

## Critério de conclusão

Cada afirmação do texto tem uma destas etiquetas, explícita ou evidente pelo
contexto: medido (com comando e data), inferido (de quê), hipótese (e o teste
que decide) ou não confirmado.
