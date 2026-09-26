---
name: integracoes
description: Integrações com terceiros — APIs externas, webhooks, pagamentos, LLMs, e-mail transacional e dependências. Contrato provado com requisição real, limites e erros do terceiro como constantes, retry por classe, idempotência, releitura do que se configurou na conta do fornecedor, capacidade da região/conta/plano, taxonomia de falha de webhook, modo declarado versus deduzido (teste/produção), ordem de investigação de saída de LLM, links de e-mail que não agem, e medir a árvore de uma dependência antes de aceitá-la. Use ao integrar ou revisar qualquer chamada a terceiro, webhook, cobrança, modelo de IA, envio de e-mail, ou ao adicionar dependência.
---

# Integrações — o contrato só se prova quando a requisição sai

## Quando usar

- Nova chamada a API externa, novo webhook, nova etapa de cobrança.
- Integração com LLM (extração, busca, geração).
- Envio de e-mail com link.
- Adição ou atualização de dependência.
- Uso de uma capacidade de fornecedor pela primeira vez (região, recurso,
  plano, modo).

## Quando não usar

- Para a infraestrutura em que o seu código roda: ver `nuvem-e-deploy`.

## O princípio

> **A fixture devolve o que você escreveu, não o que o terceiro aceita.**

Todo teste que substitui o terceiro por uma função sua prova a sua aritmética,
e essa distinção fica invisível até alguém chamar o serviço de verdade. Os
defeitos mais caros de integração passaram por suítes verdes: um limite da API,
dois parâmetros que a API recusa juntos, a referência de um evento que mudou de
lugar numa versão nova, a moeda exibida ao cliente diferente da cobrada.

---

## 1. Qualquer terceiro

- **Capture um payload real e teste contra ele.** Evento, resposta, erro.
  Quando o contrato muda (versão de API), capture de novo.
- **Limites do terceiro são constantes próprias, com o erro citado ao lado.**
  Exemplo: `TETO_DA_API = 20  # 400: "A quantidade máxima de valores deve ser
  20"`, com um teste que afirma `PEDIDO <= TETO`. Um número medido que vive só
  num comentário volta a 24 na próxima vez que alguém quiser mais histórico.
- **Retry por classe:** 4xx é pedido nosso e não se repete (menos 429, que pede
  espera); 5xx e erro de transporte são deles, e se repetem com backoff. A
  mensagem diz de quem é a culpa.
- **Toda chamada tem teto de tempo.** Uma chamada sem teto pendura o processo
  inteiro no pior dia do fornecedor.
- **Operação que custa ou que muda estado leva chave de idempotência**, derivada
  do evento que a causou (não aleatória), para que a reentrega não repita a
  cobrança, o estorno ou o e-mail.
- **Cliente que devolve `{ data, error }` em vez de lançar exige o retorno
  examinado.** `await cliente.rpc(...)` sem `const` é a forma mais comum de
  escrever "faça isto" e de perder o erro.
- **O que você configurou na conta do fornecedor não viaja com o git.** Endpoint
  de webhook, lista de eventos, configuração de portal, regras de domínio. Crie
  um instrumento no repositório que lê o **código** como fonte e compara com o
  objeto **vivo, relido**. Criar sem reler prova que a requisição não deu erro,
  não que o fornecedor guardou o que você pediu. E filtre pelo modo certo
  (teste/produção), senão ele confere o objeto de teste e diz ✓ enquanto o de
  produção está torto.

### Antes de usar uma capacidade pela primeira vez

Três perguntas, e as três já custaram caro:

1. **Existe na MINHA região/plano?** O comando da CLI existe em toda região; quem
   recusa é a API, e só na hora (`501 UNIMPLEMENTED`).
2. **A MINHA conta está apta hoje, e qual campo responde?** Um plano de seis
   passos para ativar a cobrança real pressupunha uma conta ativada que não
   existia. E a ausência pode ser **escolha** do dono, não esquecimento:
   pergunte.
3. **O que esta ferramenta faz com aquilo de que o meu produto depende?**
   Cookies, streaming, WebSocket, upload grande, cabeçalho customizado, CORS.
   *Caso real:* uma camada de hosting que funcionava na região certa **remove os
   cookies** da requisição, e o login nunca fechava. A fumaça passou 13 de 13,
   porque nenhum teste exercia uma sessão. Outro: uma URL assinada provada pelo
   servidor (sem `Origin`, sem preflight) falhou no navegador por falta de CORS.

## 2. Webhooks

- **Assinatura verificada sobre o corpo cru**, antes de qualquer parse.
- **Taxonomia de falha** (ver `falha-ruidosa`): transitória → 5xx para o
  fornecedor reentregar; definitiva → marca `falhou` com o motivo, alerta e fica
  visível. Um único `catch` que chama tudo de "transitória" deixa dinheiro
  cobrado, acesso nunca concedido e o log culpando a rede por três dias.
- **O padrão do que não se entende é transitório.** E **200 faz o fornecedor
  parar de reentregar**. Então:
  - evento reconhecido como **nosso** e não interpretado → 5xx, não 200;
  - referência interna ausente → não é sucesso;
  - uma trava de segurança (por exemplo, "recuso eventos de produção durante os
    testes") que responde 200 é uma mina: no dia em que produção ligar, o
    primeiro evento real some.
- **Um passo que consome a própria entrada vai por último.** Se o passo 3
  apaga o que o passo 4 (que pode falhar) precisa, a reentrega encontra o vazio,
  classifica como definitivo e desfaz um pagamento bom. Copie, grave, e só então
  limpe; e a limpeza que falha vira log, não exceção.
- **Índices e ids saem do nome do objeto, não da posição numa lista**, porque a
  lista muda entre reentregas.
- **A lógica de dinheiro sai da rota para um módulo importável.** A rota é a
  única coisa que nenhum teste consegue importar, e é atrás dela que o erro de
  retorno descartado se esconde.

## 3. Pagamentos

- **O modo é declarado, não deduzido, e a conferência vale nos dois sentidos.**
  Uma variável `MODO=teste|live` (ausente = teste; presente e ilegível =
  **lança**) contra a qual se confere o prefixo da chave, o `livemode` do preço,
  do portal e do evento. O sentido esquecido é o silencioso: uma chave de teste
  sob o modo de produção faz o checkout abrir, o acesso ser concedido e
  **nenhum dinheiro entrar**.
- **Confira o que o cliente VÊ**, não só a API. O preço era na moeda local na API
  e na sessão, e o checkout exibiu outra moeda para um IP estrangeiro, por uma
  opção padrão da conta ("preço adaptativo").
- **A vigência de uma assinatura é decidida pelo processador**, por webhook e
  por releitura, nunca pelo seu relógio (ver `dados-e-banco`, ciclo de vida).
- **Falha definitiva num fluxo de assinatura não estorna sozinha.** Estornar sem
  cancelar deixa o processador cobrando no mês seguinte, e você sem acesso para
  dar. No fluxo em que o produto **não pode ser entregue**, o estorno automático
  é o certo. A decisão depende de a falha ser sua (configuração) ou do produto.
- **Receita no painel soma só eventos de produção**; os de teste são contados,
  nunca somados. Ajustes manuais (reembolso que o processador não avisa) entram
  como lançamentos com sinal e motivo.
- **Na conta real, leitura é livre e escrita é o combinado:** cobrança,
  reembolso, cancelamento, apagar objeto, dados da conta e chaves só com o dono
  autorizando na hora.

## 4. LLM

- **Quando a saída parece ruim, investigue nesta ordem: o schema que enviamos →
  o prompt exato → a normalização da resposta → e só então o modelo.** Imprima
  o schema; não o leia. *Caso real:* dois campos do schema eram o mesmo objeto
  em memória, o enum de um vazou para o outro, e o modelo não conseguia
  responder. Parecia "o modelo se abstém".
- **Uma ausência no contexto é preenchida com o texto mais próximo, e o mais
  próximo é a pergunta do usuário.** Se o resumo de dados não tem o bairro e a
  pergunta tem, o modelo afirma o bairro. Instrução de sistema não substitui
  dado: **para cada afirmação que a saída pode fazer, o contexto carrega o
  campo.**
- **O teto de saída inclui o raciocínio** em modelos que pensam. Uma guarda
  contra o caso patológico (repetição infinita) cortou o caso normal: 477 de 500
  tokens pensando, JSON truncado na posição 5. **Meça a guarda no caso comum,
  não só no raro.**
- **Teto de custo verificado antes de gastar**, na entrada do pedido, não numa
  contagem posterior. Uma estimativa de custo é um estimador: confira contra a
  fatura real.
- **Cache por usuário:** guarde o que é igual para todos (intenção, vetor,
  explicação do resumo), nunca o resultado filtrado por permissão.
- **Mostre o resultado sem esperar a frase gerada**, se a frase é enfeite do
  resultado.
- **O modelo aponta; a regra decide.** Deixe o número que decide dinheiro fora
  do alcance do modelo, e o modelo com o que ele faz bem (ler texto, apontar
  argumentos).
- **Espelhos em duas linguagens** (o prompt em TS e em Python) comparam-se pela
  **saída** montada, não pelas constantes.
- **Descarte silencioso de resposta paga** é a pior falha possível aqui: conte
  e registre cada descarte.

## 5. E-mail transacional

- **Nenhum link de e-mail AGE.** Varredores de provedores abrem os links antes
  do humano. O link abre uma página, e a ação é um botão lá.
- **Token no fragmento (`#t=`)**, fora do log do servidor e do `Referer`; hash
  no banco; `noindex` e `no-referrer` na página. Token errado → zero linhas, sem
  erro (um erro seria oráculo).
- **Rastreamento de clique desligado:** ele reescreve o link do token por um
  redirecionador de terceiro.
- **Idempotência** por pedido (marca de "avisado em" + chave determinística).
- **DNS de e-mail** (DKIM, SPF, DMARC, MX) conferido nos servidores
  autoritativos.
- Girar o segredo do token invalida todo link já enviado. Escreva isso ao lado
  do segredo.

## 6. Dependências

- **Meça a árvore, não o pacote.** `install` → quantos pacotes entraram →
  `audit`, olhando **de onde** vem a vulnerabilidade transitiva (muitas vezes é
  uma cópia velha de algo que já existe na árvore em versão sã).
- **Um override precisa ser conferido no lock.** Um override que não pegou é
  indistinguível de um que pegou, se ninguém olhar.
- **Dependência que chega com dívida é recusada, mesmo sendo a oficial.** Ao
  recusar, diga o que se perde (a implementação passa a ser sua) e o que precisa
  ser exercido de verdade no lugar.
- **Restaure conferindo:** um backup tirado **depois** do install já contém a
  dependência.
- **Auditoria de dependências agendada** (semanal) e a cada mudança de manifesto.

## 7. Dado de terceiro e postura

- **Coletar de um terceiro exige postura identificável:** User-Agent com
  contato, `robots.txt` respeitado, limite de taxa por domínio, sem proxy nem
  disfarce. Contra um bloqueio, a resposta é ir mais devagar e continuar se
  identificando.
- **Ler o dado estruturado que o site publica para o próprio front-end** impõe
  menos carga que renderizar a página.
- **Comprar dado de um fornecedor é outra relação** e não afrouxa a postura com
  quem você coleta.
- **Dado pago se guarda inteiro, cru**, junto com o processado. Reingerir custa
  dinheiro, e o campo que você não usou hoje pode ser a matéria-prima de amanhã.
- **Número de terceiro carrega a procedência até a tela** (fonte, período).

---

## Testes de falha

A integração está frágil se:

- todos os testes dela usam uma fixture escrita à mão;
- existe um caminho em que o seu servidor responde 200 sem ter gravado;
- o modo (teste/produção) é deduzido da chave, e ninguém confere o oposto;
- a configuração da conta do fornecedor só existe no painel;
- a primeira vez que uma capacidade do fornecedor é usada é o deploy;
- a saída do LLM "melhorou" depois de trocar de modelo, sem ninguém ter impresso
  o que era enviado.

## Critério de conclusão

- [ ] Contrato exercido contra o terceiro de verdade, ou contra payload real
      capturado.
- [ ] Teto de tempo, retry por classe, idempotência onde há custo.
- [ ] Transitório e definitivo separados; nenhum 200 sem gravação.
- [ ] Configuração da conta conferida por releitura, no modo certo.
- [ ] Capacidade, região e conta conferidas antes do passo que depende delas.
