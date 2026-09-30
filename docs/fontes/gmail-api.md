# Gmail API (Sessão Gmail, 2026-09-26)

- **API:** Gmail API v1 via `googleapiclient` (a descrição `gmail.v1.json` já vem no pacote
  instalado; nenhuma dependência nova). `users.messages.list`, `users.messages.get`,
  `users.getProfile` e, só para arquivar/desarquivar, `users.messages.batchModify` — sempre com
  `userId="me"`.
- **Escopo:** `gmail.modify` desde a Sessão Gmail 2 (antes, `gmail.readonly`). Medido em
  2026-09-26 no `gmail.v1.json` instalado: o Google o descreve como "Read, compose, and send
  emails from your Gmail account" e ele autoriza `send`, `trash`, `import`, `insert` e
  `drafts.send`; não autoriza `delete`/`batchDelete` (apagar de vez). É o menor escopo que tira
  e-mail da caixa. O Viking não chama lixeira, importar nem apagar (teste que lê o código de `gmail/`; D29); desde a Sessão 8, envia por uma função só (`service.enviar`, D46). Os dois
  são escopos **restritos** do Google. Trocar o escopo força **um login novo** (a conferência de
  `google_auth` vê que o token salvo é de `readonly`).
- **App OAuth:** o mesmo do calendário (`secrets/google_credentials.json`). Conferido pelo dono
  em 2026-09-26: em produção, tipo externo, só ele de usuário. Pela documentação do Google (não
  medido): em produção o login não vence em 7 dias (isso é do modo "Testing"), e um app não
  verificado com escopo restrito mostra a tela "O Google não verificou este app" no login e
  aceita até 100 usuários — sem bloqueio para uso pessoal.
- **Token próprio:** `secrets/google_token_gmail.json` (`VIKING_GMAIL_TOKEN_PATH`), separado do
  do calendário: um login do Gmail que falhe ou seja revogado não derruba a agenda.

## Login compartilhado (`lifeos/google_auth.py`)

Calendário e Gmail passam pelo mesmo fluxo. Duas coisas que a biblioteca **não** faz sozinha,
medidas em 2026-09-26 no `google-auth` instalado:

- `Credentials.from_authorized_user_file(caminho, scopes)` guarda os escopos **pedidos**, e
  `has_scopes()` compara com eles — daria sempre verdadeiro. O Viking lê o campo `scopes` gravado
  no próprio arquivo do token; token de outro escopo vira login novo, não erro 403 mudo.
- Na tela do Google dá para desmarcar a permissão e concluir o login. O Viking confere
  `granted_scopes` e, faltando o escopo, falha alto sem gravar token (`PermissaoNaoConcedida`).

O token é gravado com permissão 600 (o refresh token dá acesso à conta).

## Formato das mensagens (o que o código espera)

- `messages.list` → `{"messages": [{"id", "threadId"}], "nextPageToken"}`; paginamos até o teto.
- `messages.get(format="metadata", metadataHeaders=[From, Subject, Date, List-Unsubscribe,
  List-Id])` para listas; `format="full"` para ler um e-mail.
- `labelIds` traz `UNREAD`, `INBOX` e as abas (`CATEGORY_PROMOTIONS`, `_UPDATES`, `_SOCIAL`,
  `_FORUMS`). `List-Unsubscribe`/`List-Id` marcam newsletter e lista de envio.
- `snippet` vem com entidade HTML (`&#39;`); `internalDate` em milissegundos desde a época.
- `payload.parts[].body.data` é **base64url sem padding**, com os bytes no charset da parte
  (`Content-Type`). Preferimos `text/plain`; sem ele, o `text/html` vira texto (sem `script`/
  `style`). Parte com `filename` é anexo: contado, nunca aberto.
- "Hoje" é `after:<segundos desde a época>` da meia-noite no fuso do Viking — a data escrita
  (`after:2026/09/26`) o Gmail interpreta num fuso que não é o nosso.

O fake de `tests/conftest.py` (`gmail`) segue este formato. **Conferido contra a caixa real do
dono em 2026-09-26** (não lidos + raio-x): bateu, com uma exceção que o fake não tinha — prévias
(`snippet`) de newsletter feitas só de enchimento invisível (ZWNJ U+200C, CGJ U+034F, espaço sem
quebra), agora removido do trecho e do corpo.

O app OAuth aparece para o Google com o nome **"n8n"** (tela de consentimento e alerta de
segurança do login) — é o mesmo app, criado antes do Viking.

## O que chega ao Gemini

Só pelo `viking chat` (o MCP não expõe e-mail — decisão do dono). Remetente, assunto, trecho e
corpo passam pela redação das páginas (`_redacao.redigir` + `redigir_url` nos links; e-mails e
códigos de verificação ficam, decisão do dono) e vão dentro do bloco de não confiável
(`lifeos/nao_confiavel.py`). Busca com e-mails que não puderam ser lidos diz quantos; raio-x que
bateu no teto (200) diz que os números são piso.

**Residual:** token de link que vai no **caminho** (`/login/abc123...`), não num parâmetro, não é
redigido; o objetivo da busca (escrito pelo usuário/Gemini) não é redigido.

## Raio-x e lotes

O raio-x lê metadados de até 200 e-mails da caixa de entrada em lotes de 25
(`new_batch_http_request`), dentro da cota (abaixo). Quem falha por outro motivo ganha uma nova
tentativa depois de 1 s; quem falha de novo é contado e aparece no texto.

## Cota (lida em 2026-09-26, depois de estourar no Mac)

`developers.google.com/workspace/gmail/api/reference/quota`: **6.000 unidades por minuto por
usuário**; `messages.get` = **20**, `messages.list` = 5, `batchModify` = 50. Ou seja, no máximo
300 e-mails lidos por minuto — o raio-x (200) sozinho gasta 4.000. **Medido no Mac:** a primeira
versão da limpeza leu 207 e-mails na proposta e de novo na confirmação, em menos de um minuto, e
recebeu `403` com motivo `rateLimitExceeded` (não é 429). Hoje: orçamento de 4.800/min por
processo (`service._Cota`), espera crescente de 2 a 64 s em qualquer recusa de cota (o orçamento
não enxerga outro processo), e a confirmação só faz buscas. O fake do `conftest` cobra a mesma
cota num relógio falso. O corpo do erro traz o número do projeto OAuth: não sai do serviço
(`_descrever`).

## Limpeza da caixa (Sessão Gmail 2)

- **Arquivar** = `batchModify` com `removeLabelIds: ["INBOX"]` (até 1000 IDs por chamada); o e-mail
  continua em "Todos os e-mails". **Desfazer** = `addLabelIds: ["INBOX"]` nos mesmos IDs, por 7
  dias, a partir do registro em `viking.db` (tabela `confirmacoes`).
- **Seleção por remetente:** `from:<endereço> in:inbox -is:starred -is:important -has:attachment`.
  O `from:` do Gmail casa **por pedaço** (um `ofertas@loja.example.golpe.example` também casa), então
  o remetente de cada e-mail é conferido igual ao endereço nos metadados. As proteções também são
  conferidas de novo no cliente (rótulos `STARRED`/`IMPORTANT` e a lista de `has:attachment`).
- **Endereço estrito antes da consulta:** `a@b.com OR in:anywhere` viraria uma busca na conta
  inteira; qualquer pedido fora do formato recusa tudo, sem consultar.
- **Teto 250 por aprovação (D28):** acima disso, os mais antigos de cada remetente, na ordem pedida.
  250 conferidos = 5.000 unidades, cerca de 1 minuto na cota.
- **A confirmação não relê** e-mail por e-mail: refaz as buscas (a que exclui os protegidos e as
  que os listam) e intersecta com os aprovados. O remetente exato foi conferido na proposta.

## Enviar (Sessão 8, 2026-09-28)

- **Chamada:** `users.messages.send(userId="me", body={"raw": <base64url da mensagem>, "threadId":
  <da original, na resposta>})`, com o escopo `gmail.modify` que já temos (ele autoriza `send`,
  medido em 2026-09-26). Custa **100 unidades** da cota (a tabela de cota lida em 2026-09-26; o
  dublê cobra o mesmo). Uma só chamada no código, dentro de `registro.acao("gmail.enviar")`.
- **Mensagem:** `email.message.EmailMessage` com a política SMTP (linhas em CRLF no fio),
  `From` = a conta (`users.getProfile`), cabeçalho `X-Viking: enviado-pelo-viking` e, no fim, "—
  Escrito pelo Viking (Assistente AI)". O `EmailMessage` recusa CR/LF num cabeçalho (medido no
  Python 3.12.3); a nossa validação recusa antes, com mensagem clara.
- **Duas versões do mesmo texto (Sessão 8b, 2026-09-29):** até a 8 saía só `text/plain`, e o
  markdown do Gemini aparecia cru no Gmail do dono (`**Gestão de Calendário:**`). Agora é
  `multipart/alternative`: `text/plain` sem os marcadores e `text/html` de `gmail/formato.py`
  (negrito, itálico, listas; assinatura em cinza e menor), as duas saídas do texto que o dono
  aprovou. O conversor divide o texto cru e escapa cada trecho antes de formatar: nada do
  Gemini vira link, imagem ou script. Medido no Python 3.12.3: `iter_attachments()` vazio e
  `get_body(("html", "plain"))` escolhe o HTML. A leitura de volta (`service._corpo`) prefere o
  `text/plain`. **Não medido aqui:** como o Gmail mostra o HTML (o teste é no Mac).
- **Resposta na conversa:** `threadId` da original, `In-Reply-To` = o `Message-ID` dela e
  `References` = as dela + o `Message-ID` (só o que tem a forma `<…>`; até 20), e o `Subject` com
  "Re: " (sem duplicar) — https://developers.google.com/workspace/gmail/api/guides/threads.
  Destinatário: `Reply-To`, senão `From`, só os endereços; se quem escreveu a original foi o
  próprio dono, o `To` dela sem ele. Nunca `Cc`/`Cco`.
- **Falha:** recusa por cota (429, ou 403 `rateLimitExceeded`) é certeza de que não saiu e se
  repete com espera; 4xx é "não enviei"; 5xx, tempo esgotado ou conexão é `incerta` ("Não sei se
  o e-mail saiu… confira em Enviados"), sem nova tentativa.
- **Não medido aqui (VPS):** o envio de verdade (o teste é no Mac); se o Gmail mantém o `From`
  explícito; como a marca `X-Viking` aparece ao ler de volta pela API (esperado: nos `headers`).

## Na nuvem (Sessão 10c, 2026-09-30; no ar só depois da prova de 04/10)

- **O token:** o do Mac (`secrets/google_token_gmail.json`, escopo `gmail.modify`) sobe para o
  Secret Manager (`viking-gmail`) **do Mac**, por `python scripts/nuvem.py segredo viking-gmail
  --executar`, pela entrada padrão; o VPS não guarda token do Gmail (D57). O motor o lê como
  arquivo de volume (`VIKING_GMAIL_TOKEN_ARQUIVO`) e renova o acesso **em memória**
  (`google_auth.credenciais_da_nuvem`): o login nunca abre lá. Se o Google recusar renovar, a
  mensagem diz de onde subir de novo.
- **O prazo:** o `googleapiclient` 2.200.0 espera até 60 s por operação de rede
  (`DEFAULT_HTTP_TIMEOUT_SEC`, lido em 2026-09-30) e as esperas de cota somam 126 s por chamada.
  Sem prazo, uma chamada podia passar de 500 s, e o Cloud Run mata o pedido em 300 s. O turno da
  nuvem tem 220 s (`lifeos/prazo.py`): antes de cada espera e de cada pedido, o serviço confere
  se ela e um pedido inteiro (`REDE_S` = 60 s) cabem; se não, `LimiteDoGmail("não deu tempo…")`,
  com certeza de que nada foi feito naquela chamada. No Mac não há prazo.
- **O aviso de espera** ("⏳ Esperando N s") sai só no terminal do Mac: no motor o stderr é o log.
- **A cota** é por usuário, não por processo: o Mac e o motor gastam da mesma (6.000/min), e o
  orçamento de cada um não enxerga o outro. A espera no erro continua sendo a rede de segurança.
- **O limite de 20 envios em 24 h** conta separado no Mac e na nuvem (o registro mora onde a ação
  roda, D57); unificar é da S11.

