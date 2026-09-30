# GCP: Cloud Run, Firestore e o deploy do Viking

Referência curta do que a Sessão 10 mediu (2026-09-29/30) ao pôr o motor no ar. Cada linha diz
de onde veio: **medido** (comando nosso, com data) ou **lido** (documentação, com data). As
decisões estão na D47 (revista) e na D58; o código em `scripts/nuvem.py`, `src/lifeos/nuvem/`
e `src/lifeos/reminders/store_firestore.py`.

## Onde está

- Um projeto só do Viking (o ID em `VIKING_NUVEM_PROJETO`), região `southamerica-east1` (a casa do dono; o local do Firestore não
  muda depois de criado). O ID e a URL ficam no `.env`, não no repo.
- `python scripts/nuvem.py` mede os 8 passos da infraestrutura; `python scripts/nuvem.py deploy`
  mostra o que está no ar e roda as provas. Nada muda sem `--executar`.

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

## Comandos do gcloud que dizem "não existe" de jeitos diferentes

`NOT_FOUND`, "was not found", "may not exist" e, no `run services describe`, "Cannot find
service" (medido em 2026-09-30). `scripts/nuvem.py` trata esses como ausência e qualquer outro
erro como erro.
