---
name: dados-e-banco
description: Banco e dados — migrations numeradas e imutáveis depois de aplicadas, ordem entre migration e código, escritas que aguentam reenvio, chaves de unicidade tiradas de quem produz o dado, tabelas derivadas com presença e validade, fotografia versus acúmulo, máquinas de estado com saída, "quem espera este objeto sumir?", unidades no nome da coluna, armadilhas de tipo (float4, date vs timestamp), medir com count(*) e com o plano real, cortes por percentil, amostragem, e réplica com controle antes de mudar uma regra sobre dado de produção. Use ao escrever migration, schema, escrita concorrente ou idempotente, projeção ou agregado, consulta de medição, ou ao mudar uma regra que reescreve dados.
---

# Dados e banco

## Quando usar

- Ao criar ou mudar schema, função, policy ou índice.
- Ao escrever qualquer `INSERT`/`UPDATE` que pode ser repetido.
- Ao construir uma tabela derivada, um agregado ou uma fotografia periódica.
- Ao medir algo sobre os dados para decidir.
- Antes de mudar uma regra que reescreve dados em produção.

## Quando não usar

- Para a fronteira de autorização no banco (RLS, grants, funções privilegiadas):
  isso está em `seguranca`. Aqui fica só o que toca integridade e medição.

## O princípio

O dado errado não quebra nada. Ele é lido por tudo o que vem depois e se
propaga em silêncio: uma mediana calculada sobre a população errada contamina
todo número que a usa. Por isso o trabalho de dado tem prioridade sobre
acabamento de tela e não espera lançamento: a isenção de "ninguém está usando
ainda" vale para experiência, não para dado.

---

## 1. Migrations

- **Numeradas, num diretório, com um ledger** que guarda o que foi aplicado e o
  checksum.
- **Uma migration aplicada não se edita, nem o comentário.** O checksum é do
  arquivo, e comentário é arquivo. *Caso real:* onze linhas de comentário
  acrescentadas a uma migration aplicada armaram uma falha que só disparou no
  job semanal seguinte, três dias depois, de madrugada. Criar uma migration
  nova é a regra que a própria mensagem de erro já dizia.
- **Compare os checksums do disco com os ledgers de produção no fechamento da
  sessão.** Nenhum teste compara o disco com produção: a suíte aplica tudo do
  zero num schema descartável, onde não existe checksum antigo para divergir. E
  cada diretório pode ter a sua regra de checksum (com ou sem substituição de
  schema); usar a regra errada devolve um resultado plausível.
- **Toda tabela nasce dentro de uma migration numerada.** *Caso real:* uma
  tabela de controle criada fora ficou de fora de todos os `REVOKE`, e o papel
  anônimo tinha todos os privilégios nela, inclusive `DELETE`.
- **Para redefinir uma função, a base é a ÚLTIMA definição aplicada**, não a
  primeira. A primeira é a mais tentadora, porque tem o cabeçalho que explica o
  desenho. Reescrever a partir dela desfaz em silêncio os consertos das
  versões seguintes. Use `grep` pelo nome em todas as migrations e leia a de
  número mais alto, ou leia a definição no banco (`pg_get_functiondef`).
- **Para policies, o `grep` pelo nome não basta.** O conserto pode estar noutra
  tabela, com outro nome. A pergunta é: *que regra vale para toda tabela desta
  família, e qual foi a última migration que mexeu nela?*
- **Uma ferramenta de migration genérica ao lado do seu ledger** (a CLI do
  fornecedor, uma ferramenta MCP de "aplicar migration") cria um terceiro
  histórico divergente. Use as ferramentas genéricas só para ler e auditar.

### A ordem entre migration e código

- **Código novo que LÊ um objeto novo:** a migration vai antes, ou o código
  nasce tolerante à ausência. *Caso real:* o código passou a ler uma coluna que
  ainda não existia em produção, e quem estava usando o ambiente entrou num
  laço de login, com 70 erros no log antes de alguém olhar.
- **Uma auditoria que MEDE o que a migration cria:** a régua da auditoria sobe
  antes da migration, ou a próxima execução mede o mundo novo com a régua velha
  e dispara um alarme falso.

## 2. Toda escrita tem de aguentar ser reenviada

- **Antes de escrever `SET x = x + 1`, pergunte o que acontece se o statement
  chegar duas vezes.** Uma retentativa de conexão pode reenviar algo que o
  servidor já aplicou. Contadores que decidem estado (quantas ausências até
  declarar morto) não podem inflar.
- **A chave de unicidade não sai do caso que motivou a guarda. Ela sai de
  enumerar os produtores** daquelas colunas: *quem escreve nesta tabela, e com
  que chave?* *Caso real:* uma guarda contra duplicata usou `(url, execução,
  preço)`, e o reprocessamento, que reusa o mesmo id de execução, voltava a um
  preço já visto e **engolia a transição**, dizendo que tinha gravado. Uma
  duplicata dá para ver; um descarte não.
- **Conhecer o padrão não basta.** O mesmo defeito foi repetido no dia seguinte
  ao conserto, num contador pior. A pergunta escrita é o que protege; lembrar do
  episódio, não.

## 3. Tabelas derivadas e fotografias

- **Duas perguntas, sempre:** *quem escreve esta linha?* e **o que faz esta
  linha deixar de ser verdade, e quem escreve ISSO?** A resposta da segunda
  quase nunca está na mesma tabela (é o `status` de outra, escrito por outro
  módulo).
- **Presença e validade são duas medições** (ver `falha-ruidosa`). E o conserto
  tem uma armadilha: apagar da derivada faz a régua de presença acusar as mesmas
  linhas como faltantes. O `DELETE` e o ajuste da régua vão no mesmo commit.
- **Uma fotografia é upsert e poda.** `ON CONFLICT DO UPDATE` sabe atualizar a
  linha que continua e não sabe nada da linha que sumiu. Sem a poda, a linha
  velha fica viva com o número antigo e a data de hoje. **A poda alcança só o
  período corrente:** o anterior é memória, e apagá-lo reescreve o passado que a
  variação compara.
- **Por partição, nunca pelo máximo global.** "A semana mais recente" se resolve
  por cidade (`DISTINCT ON`), não por um `max(semana)` global. No dia em que uma
  cidade não gravar, o global a faz sumir da tela.
- **Um valor que a tela sempre mostra é calculado pelo pipeline e gravado**,
  não recalculado a cada abertura. Gravado, ele fica conferível por SQL,
  vigiável por uma reconciliação e alertável. O custo é ficar velho entre
  execuções, o que é aceitável quando a fonte só muda na execução.
- **Materializar ou resolver por consulta se decide medindo.** *Caso real:*
  resolver uma regra de bairro por consulta custou +2.185% na busca, e a regra
  virou coluna materializada por gatilho.
- **O acumulado se calcula da série do banco**, nunca de uma resposta de API com
  janela deslizante. E "12 meses" são 12 competências **consecutivas**, não os
  últimos 12 pontos.

## 4. Ciclo de vida

- **Todo estado precisa de uma transição de saída e de quem a dispara.** Um
  estado com entrada e sem saída, dentro de um índice único que bloqueia a
  próxima operação, tranca a porta numa data. *Caso real:* uma assinatura
  `ativa` que nunca saía de `ativa` impediria qualquer assinatura nova depois do
  primeiro mês não renovado.
- **Quando o estado espelha um objeto de terceiro, a transição é do terceiro.**
  Não use o seu relógio: expirar localmente uma assinatura que o terceiro
  continua renovando libera uma segunda compra e cobra duas vezes. Pergunte
  também: *este estado é terminal para nós ou para o dono do objeto?* Uma
  recusa de cartão não é terminal para o processador; o mesmo pagamento pode
  aprovar com outro cartão.
- **Quem espera este objeto sumir?** `ON DELETE CASCADE`, regras de ciclo de
  vida de bucket, limpezas agendadas e **promessas em texto público**. Tornar um
  objeto permanente desliga tudo o que dependia do fim dele. *Caso real:* um
  `CASCADE` correto ficou inalcançável quando se decidiu que a linha-mãe nunca
  seria apagada, e a promessa de retenção da política de privacidade passou a
  não ser cumprida por nada.
- **Toda promessa de retenção tem um dono no código** e um teste que amarra as
  duas pontas (o texto e o mecanismo).
- **Ledger é só inserção.** Correção se faz com um lançamento oposto, nunca
  sobrescrevendo.

## 5. Tipos e unidades

- **A unidade vai no nome da coluna** (`preco_centavos`, `duracao_ms`).
  *Caso real:* duas colunas `bigint`, uma em centavos e outra em reais,
  produziram um "divergência de preço (218316800 > 2672383)" que seria falso em
  toda publicação, o alarme que ensina a ignorar alarme.
- **`real` (float4) contra parâmetro float8:** `WHERE col = %s` com o valor que
  o próprio banco imprimiu (`37.16`) não casa com o que o float4 guarda. Deu 4 de
  5 grupos sem membro nenhum, sem erro. Use `%s::real`.
- **Alargar float4 na saída** imprime o lixo binário na tela (`0.97` →
  `0.9700000286102295`). Declare o tipo exato no retorno.
- **`date` não tem fuso.** Formatá-lo como timestamp em UTC-3 mostra o dia
  anterior. Leia `date` pelo texto.
- **Dinheiro anunciado arredonda a favor do cliente** (desconto com `floor`).
  Arredondar para cima anuncia mais do que se entrega.
- **Um portão de acesso sobre um agregado devolve zero linhas, nunca uma linha
  com "0".** Zero é um dado; ausência é a recusa.

## 6. Medir sobre os dados

- **Contagem sai de `count(*)`**, não de estatística do planejador.
- **Conte antes de agrupar.** Agregar por chave descarta cardinalidade, e a
  cardinalidade costuma ser a pergunta.
- **Pergunte "relativo a quê?".** Um corte de "X% abaixo da mediana" seleciona
  metade da base por definição (uma mediana tem metade abaixo dela). Para
  raridade, use percentil (posição), com uma segunda cláusula de magnitude,
  porque as duas erram em direções opostas. **Antídoto de dez segundos:** quantos
  itens o corte seleciona, e quantos o corte trivial (`< mediana`, `> 0`)
  selecionaria? Se os números são da mesma ordem, o limiar não trabalha.
- **Leia as dez primeiras e as dez últimas linhas de toda ordenação nova.** Um
  ranking por "quão extremo" é, por construção, um ranking dos dados mais
  improváveis da base: achou em minutos preços lidos em centavos (fator 100
  exato) e áreas de terreno usadas como área construída. **A guarda mira o
  mecanismo** (razão ≥ 9,5×, a assinatura de uma casa decimal perdida), não o
  tamanho (um teto de −50% morderia uma queda real de 60%).
- **Correlações de preço são associações medidas, não ajustes.** Um atributo
  associado a preço mais alto numa amostra não autoriza somar um percentual.
- **Plano real, não raciocínio.** `EXPLAIN (ANALYZE, BUFFERS)` das duas pontas.
  Uma bancada que simplifica a consulta para medir (um `count(*)` em volta)
  mede outra consulta: o planejador poda colunas e troca o acesso ao heap por
  índice. E as duas pontas têm de devolver o mesmo número de linhas.
- **Amostragem:** `DISTINCT ON` obriga o `ORDER BY` a começar pelas colunas
  distintas. Com o `LIMIT` no mesmo `SELECT`, a amostra vira os menores ids.
  Sorteie num CTE separado. Pares X→Y e Y→X não são dois pares.
- **`FULL OUTER JOIN` para comparar conjuntos**, com o filtro do período dentro
  do CTE; no `ON`, ele deixa passar como não casada. Duas contagens iguais não
  provam chaves iguais.

## 7. Mudar uma regra que reescreve dados de produção

1. **Réplica local das entradas** (cópia binária, só leitura em produção).
2. **Controle:** o código **atual** rodando na réplica tem de reproduzir
   produção **linha a linha** antes de qualquer diff. Se o controle não fecha,
   o diff não significa nada. *Caso real:* o controle só fechou com
   `extra_float_digits = 3`; sem isso, o banco devolvia 15 dígitos e fabricava
   27 mil diferenças.
3. **Diff** entre o controle e o código novo, e amostra conferida na fonte
   (a página, o documento) nos casos de dúvida.
4. `--dry-run` em produção, comparado ao diff.
5. Escrita com autorização na hora, apontando o irreversível.
6. Medição depois, contra o previsto.

## 8. Ambientes

- **A URL de produção nunca vai na variável da suíte de testes.** Uma suíte que
  cria e derruba schemas precisa de banco separado e variável separada, para não
  ter caminho até produção.
- **`DROP`/`TRUNCATE` fora do prefixo descartável** (`teste_<uuid>`) param e
  perguntam.
- **Duas implementações do mesmo store** (um banco local, outro de produção):
  método novo nas duas, com teste de contrato parametrizado. A semântica diverge
  onde o SQL parece igual (contar por subtração ou por `rowcount`, `NULL` na
  ordenação). Uma divergência intencional se declara (`NotImplementedError` com
  o motivo), não se finge.

---

## Testes de falha

Você está criando dado ruim se:

- editou uma migration que já está num ledger;
- escreveu `x = x + 1` sem pensar no reenvio;
- a tabela derivada só sabe acrescentar;
- o estado novo não tem transição de saída;
- a coluna nova de dinheiro ou tempo não tem a unidade no nome;
- o número do relatório veio de uma estimativa ou de uma bancada que muda o
  plano;
- vai reescrever produção sem um controle que reproduza produção.

## Critério de conclusão

- [ ] Migration nova (não editada); checksums do disco = ledger de produção.
- [ ] Ordem migration × código × auditoria decidida e escrita.
- [ ] Toda escrita repetível foi pensada para o reenvio, e a chave saiu dos
      produtores.
- [ ] Derivadas com presença e validade; fotografias com poda do período
      corrente.
- [ ] Mudança de regra em produção com réplica, controle e diff antes.
