# GCP: Cloud Run, Firestore e o deploy do Viking

Referência curta do que a Sessão 10 mediu (2026-09-29/30) ao pôr o motor no ar, e a 10b
(2026-09-30) ao pôr o chat nele. Cada linha diz de onde veio: **medido** (comando nosso, com
data) ou **lido** (documentação, com data). As decisões estão na D47 (revista), na D58 e na D59;
o código em `scripts/nuvem.py`, `src/lifeos/nuvem/`, `src/lifeos/assistant/na_nuvem.py`,
`src/lifeos/registro_firestore.py` e `src/lifeos/reminders/store_firestore.py`.

## Onde está

- Um projeto só do Viking (o ID em `VIKING_NUVEM_PROJETO`), região `southamerica-east1` (a casa do dono; o local do Firestore não
  muda depois de criado). O ID e a URL ficam no `.env`, não no repo.
- `python scripts/nuvem.py` mede os 10 passos da infraestrutura (8 da Sessão 10; `segredos` e
  `ttl` da 10b); `python scripts/nuvem.py deploy` mostra o que está no ar e roda as provas. Nada
  muda sem `--executar`.

## Custo e cota

- **Lido (2026-09-29):** Firestore Standard grátis por dia: 50 mil leituras, 20 mil gravações,
  20 mil exclusões, 1 GiB guardado, 10 GiB de saída por mês; **um banco grátis por projeto** (o
  primeiro criado). `docs.cloud.google.com/firestore/quotas`, atualizada em 2026-09-28.
- **Lido (2026-09-29):** Cloud Run: "requests denied by IAM policy are not billed"; a cota grátis
  é um desconto a preço da faixa 1, e `southamerica-east1` é faixa 2. `cloud.google.com/run/pricing`.
- **Medido (2026-09-29):** a conta de faturamento do dono é em BRL (o orçamento tem de ser na
  moeda dela: 105 BRL = US$ 20 na PTAX de venda de 5,2204) e tinha o limite de 9 projetos
  ligados ("Cloud billing quota exceeded", que o `gcloud` só mostra com `--verbosity=debug`).
- **Medido (2026-09-30):** a imagem do motor tem 512 MB descomprimida e 97 MB comprimida; o
  registro guarda as 5 últimas (0,5 GB grátis).

## Log

- **Lido (2026-09-29):** o log de pedidos do Cloud Run (`HttpRequest`) guarda método, **URL**,
  tamanhos, status, user-agent, IP, referer e latência; **não guarda o corpo** nem outros
  cabeçalhos. Por isso nada de conteúdo na URL. O motor roda com `--no-access-log` e não loga
  título nem e-mail.

## Identidade e token

- **Lido (2026-09-29):** pelo `X-Serverless-Authorization`, o Cloud Run tira a assinatura do
  token antes de passá-lo ao contêiner; pelo `Authorization`, o motor recebe o token inteiro e
  verifica a assinatura (medido ao vivo: o token pessoal do dono passou pelo IAM e o motor o
  recusou com 401, pela audience).
- **Medido (2026-09-30):** o `status.url` do serviço é a URL antiga, com hash; a determinística
  (`https://motor-<número do projeto>.<região>.run.app`), que é a audience, está na anotação
  `run.googleapis.com/urls`.
- **Medido (2026-09-30, no Mac):** `gcloud auth application-default login` grava como projeto
  de cota o padrão do gcloud (lá, outro projeto do dono); sem `with_quota_project`, a chamada de
  impersonação seria cobrada e limitada por aquele projeto. O cliente troca pela do Viking.
- **Medido (2026-09-30):** a permissão `run.invoker` recém-dada ao `viking-cli@` levou menos de
  1 min para valer (403 do Google, depois 200).
- **Medido (2026-09-29):** o ID de uma conta de serviço tem de 6 a 30 caracteres ("motor" foi
  recusado); criada agora, ela demora alguns segundos para o IAM aceitar papel nela.
- **Lido (2026-09-29, `gcloud` 583):** `print-access-token --lifetime` vale 3600 s por padrão (até
  12 h só com política de organização); o `gcloud` lê token de arquivo por `--access-token-file`.
  Não usado: o dono decidiu usar o login do VPS (D47 revista).

## Firestore

- **Medido (2026-09-29, emulador 1.22.0):** a transação trava o documento para cada leitor; com
  16 execuções disputando a mesma reserva, as escritas se esperavam até "Transaction lock
  timeout" e a biblioteca desistia em 5 tentativas (`ValueError`), e em 5 de 10 rodadas quem
  desistia não achava vencedor. O store usa comparar e trocar (`last_update_time`) e relê
  quando perde; o emulador também responde `Aborted` a escritas simples juntas (não aplicadas:
  relê depois de uma espera sorteada). 0 de 40 rodadas caíram depois.
- **Lido:** `== None` não casa campo ausente: todo documento nasce inteiro.
- **Medido (2026-09-30):** o índice composto dos vencidos (`completed_at`, `enviado_em`,
  `due_at`) ficou pronto em poucos minutos; criar com espera passou de 300 s (`--async`). O
  emulador não exige índice; a rota `/fumaca/vencidos` exerce a consulta na produção.
- **Medido:** o emulador é o jar do firebase-tools (v1.22.0, sha256 fixado em
  `scripts/emulador_firestore.sh`), com Java 21 (no CI, o `JAVA_HOME_21_X64` do runner).

## Segredos, prazo e TTL (Sessão 10b)

- **Lido (2026-09-30):** Secret Manager grátis por mês: 6 versões ativas, 10 mil acessos e 3
  notificações de rotação. No Cloud Run, um segredo **montado como volume** é buscado ao ler o
  arquivo e acompanha a versão `latest`; como **variável de ambiente**, é lido na partida da
  instância e o Google manda fixar a versão. A conta que roda o serviço precisa de
  `roles/secretmanager.secretAccessor` (dado **em cada segredo**, não no projeto). Cada volume
  num diretório próprio (`/segredos/gemini/chave`, `/segredos/agenda/token.json`).
- **Medido (2026-09-30):** os dois segredos com 1 versão cada; no ar, `/fumaca/segredos` →
  `{'gemini': True, 'agenda': True}` (a chave lê e o token da agenda do VPS, de 2026-09-20,
  renova no motor, em memória). O `describe` mostra só as variáveis de caminho e os volumes.
- **Lido (2026-09-30):** o prazo de um pedido no Cloud Run é de 300 s por padrão e até 3600 s.
  O motor usa 300 s; o cliente do Mac espera 320 s.
- **Medido (2026-09-30):** a TTL de `acoes.expira_em` levou alguns minutos de `CREATING` a
  `ACTIVE`; o índice composto novo (`acoes`: `operacao`, `criada_em`) ficou pronto no mesmo
  intervalo. Criar um índice que já existe devolve `ALREADY_EXISTS`: o script cria só os que
  faltam.
- **Medido (2026-09-30 05:21Z, `scripts/nuvem.py prova-chat`):** um turno real no ar ("o que
  tenho amanhã na agenda?"), logo depois do deploy, levou 4,9 s de ponta a ponta (do VPS), com
  3.986 tokens (3.842 de entrada, 144 de saída) e ~US$ 0,0015 pela estimativa das tarifas do
  `config`; o teto gravou o gasto no Firestore. No VPS (C0), os turnos levaram de 0,9 a 3,0 s.
  O log do motor depois do turno: 28 entradas, nenhuma com a pergunta, a resposta ou o
  histórico.

## As mãos e o envio de lembretes (Sessão 11, D61)

- **Lido (2026-10-01, a página de preços do Cloud Scheduler):** US$ 0,10 por tarefa por mês, e 3
  tarefas grátis por conta de faturamento. O Viking usa uma (`viking-lembretes`, `* * * * *`):
  de US$ 0 a 0,10 por mês. O token da chamada é OIDC do `viking-agendador@`, com a audience = a
  URL do motor; o motor só deixa essa conta em `/tarefas/lembretes`.
- **Conta, não medição (2026-10-01):** o `viking maos` ligado 8 h por dia pergunta a cada 5 s:
  ≈ 5,8 mil pedidos e ≈ 5,8 mil leituras do Firestore por dia, dentro do grátis do Cloud Run (2
  milhões de pedidos por mês) e do Firestore (50 mil leituras por dia). A rodada do envio por
  minuto não relê os atrasados: ≈ 1,5 mil leituras por dia com poucos lembretes; relendo 20
  atrasados seriam ≈ 29 mil. Medir no ar depois de 24 h com o agendador ligado.
- **Medido (2026-10-07, as 24 h de 2026-10-06 17:00Z a 2026-10-07 17:00Z, a API do Cloud
  Monitoring, `ALIGN_SUM` em 86400 s):** 163 documentos lidos, 1.481 gravados, 0 apagados; 1.491
  pedidos 2xx e 26 4xx no Cloud Run (os 26 são as recusas que as provas do `deploy` exercem,
  conferido pelo log). A conta de cima errou de lado: o ~1,5 mil por dia aparece nas
  **gravações** (o `estado` do envio, uma por rodada), e as leituras ficam na casa das centenas.
  Não medido: se a cobrança soma uma leitura mínima por consulta vazia (não achei a frase na
  documentação em 2026-10-07); se somar, ~+1,5 mil por dia.
- **Medido (2026-10-06, ~16:53Z):** o Cloud Scheduler **aceita `southamerica-east1`** (o `jobs
  create` passou de primeira). 4 min depois: a tarefa `ENABLED`, última execução sem erro, e o
  `/versao` com `envio_de_lembretes: True`; o `run.invoker` do `agendador@` não precisou esperar
  propagação visível. A prova: um lembrete para 17:02:00Z saiu às 17:02:02.9Z (o `enviado_em` do
  Firestore).
- **O turno com o Gmail no ar (2026-10-06):** "quantos e-mails não lidos chegaram hoje?" → HTTP
  200 em 6,1 s, 9.969 tokens, ~US$ 0,0034 (a 10c estimava um teto de ~+5.000 tokens pelas 7
  tools do Gmail: a pergunta da agenda na 10b deu 3.982).

## O backup no Drive (Sessão 11c, D63)

- **Uma 2ª tarefa do Scheduler** (`viking-backup`, `0 9 * * *` em `Etc/UTC`, como o
  `viking-agendador@`, só na rota `/tarefas/backup`). O preço lido em 2026-10-01 vale: US$ 0,10
  por tarefa por mês, com 3 grátis por **conta de faturamento**. Quantas os outros projetos do
  dono usam na mesma conta não foi medido, então a conta vai de US$ 0 a 0,10/mês.
- **O segredo `viking-drive`** é o 4º com versão ativa (6 grátis por mês, lido em 2026-09-30).
- **Leituras:** uma rodada lê os lembretes, as ações dos 30 dias e os meses de gasto: centenas de
  documentos por dia, contra as 50 mil grátis. Não medido no ar ainda.

## Comandos do gcloud que dizem "não existe" de jeitos diferentes

`NOT_FOUND`, "was not found", "may not exist" e, no `run services describe`, "Cannot find
service" (medido em 2026-09-30). `scripts/nuvem.py` trata esses como ausência e qualquer outro
erro como erro.
