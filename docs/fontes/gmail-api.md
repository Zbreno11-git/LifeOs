# Gmail API (Sessão Gmail, 2026-09-26)

- **API:** Gmail API v1 via `googleapiclient` (a descrição `gmail.v1.json` já vem no pacote
  instalado; nenhuma dependência nova). Só `users.messages.list`, `users.messages.get` e
  `users.getProfile`, sempre com `userId="me"`.
- **Escopo:** `gmail.readonly` — o Viking **só lê**. Limpar a caixa (arquivar) é a Sessão Gmail 2,
  que troca o escopo por `gmail.modify`. Os dois são escopos **restritos** do Google.
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

O fake de `tests/conftest.py` (`gmail`) segue este formato. **Não verificado contra payload
real** até a validação no Mac: o contrato só se prova quando a requisição sai.

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
(`new_batch_http_request`). Quem falha (ex.: 429 por rajada) ganha uma nova tentativa depois de
1 s; quem falha de novo é contado e aparece no texto. Latência e taxa de 429 **não medidas** —
medir no Mac antes de mexer em `LOTE`/`MAX_RAIO_X`.
