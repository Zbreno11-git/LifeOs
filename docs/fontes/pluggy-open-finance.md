# Pluggy (Open Finance)

- **Serviço:** https://pluggy.ai — agregador de open finance/open banking brasileiro.
- **Status no projeto:** medido em 2026-09-26, ainda sem código. A sessão está em `sessoes.md`
  ("Sessão Pluggy"). Visão: `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 6.
- **Por que Pluggy e não entrada manual:** decisão explícita do dono do projeto — adicionar
  gastos/lançamentos manualmente (texto ou voz) não é confiável o suficiente para um controle financeiro
  real. Dados vindos de uma conta bancária conectada via open finance são a única forma considerada
  confiável.
- **Gancho de compatibilidade já preparado:** o schema de `src/lifeos/reminders/models.py` tem campos
  genéricos (`type`, `source`, `external_id`, `metadata`) pensados para acomodar, no futuro, registros
  como `type="finance_transaction", source="pluggy", external_id=<id da transação>` sem precisar de
  migração de schema.

## Custo e caminho de uso pessoal (medido em 2026-09-26)

Fonte: o MCP de documentação da Pluggy (`https://mcp.pluggy.ai/mcp`, ferramentas `query` e
`search_qa`) e o guia `https://meu.pluggy.ai/api-guide`. Não é contrato: é o que a documentação
dizia nessa data.

- **Uso pessoal é gratuito pelo Meu Pluggy**, sem prazo: até **5 conexões ativas**, todas do
  **mesmo titular**, sem uso comercial. O trial de 15 dias e os planos pagos (dados a partir de
  R$ 2.500/mês) são para uso comercial e não se aplicam aqui. Isso responde a pergunta aberta
  de D5 ("custo real").
- **Caminho:** (1) conectar os bancos em `meu.pluggy.ai` (onde acontece a autorização do banco);
  (2) no Dashboard da Pluggy, com a mesma conta, entrar na aplicação e conectar o conector
  **MeuPluggy (id 200)**, **uma autorização por banco** (banco adicionado depois precisa da dele);
  (3) usar o Client ID/Secret dessa aplicação na API.
- **Atualização:** o Meu Pluggy sincroniza cada banco **a cada 24 h**. O item proxy na nossa
  aplicação reflete essa sincronização, mas **não sincroniza sozinho e não pode ser atualizado
  manualmente**. Consequência: o Viking sempre responde com dados de até ~1 dia atrás, e precisa
  dizer isso (`lastUpdatedAt`).
- **Histórico:** até os últimos **365 dias** depois da primeira sincronização.
- **Consentimento:** a documentação consultada não diz quando expira. Não medido.

## API (o que o Viking usaria, conferido na OpenAPI pelo MCP em 2026-09-26)

- `POST /auth` com `clientId`/`clientSecret` → `apiKey`, válida por **2 h**; vai no cabeçalho
  `X-API-KEY`.
- `GET /accounts?itemId=` → contas do item (corrente, cartão).
- `GET /v2/transactions?accountId=` (cursor `after`; `dateFrom`/`dateTo` em `aaaa-mm-dd`) →
  campos `amount`, `date`, `description`, `category`, `type`, `status`, `merchant`,
  `paymentData`, `creditCardMetadata`, entre outros. O `GET /transactions` paginado está
  **deprecated**.
- `GET /items/{id}` → estado e `lastUpdatedAt` de uma conexão.
- **Limites:** 360 requisições/min por IP nos `GET` de contas e transações e no `/auth`.
- `GET /v2/items` (listar conexões) vem **desligado** por padrão: medido nas credenciais do dono,
  **403 `LIST_ITEMS_FEATURE_NOT_ENABLED`**. Os IDs dos itens saem do Dashboard.
- ⚠️ **A mesma chave alcança escrita:** `POST /payments/requests` (inclusive PIX), `PATCH
  /transactions/{id}`, `DELETE /items/{id}`, webhooks. O Viking só lê: o cliente precisa ser
  **só `GET` por construção** (lista fechada de caminhos), com teste que prove isso.

## Medido nas credenciais do dono (2026-09-26, VPS, sem imprimir valor)

- `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` no `.env` da raiz (que é gitignored).
- `POST /auth` → **200**, com `apiKey`.
- `GET /connectors?ids=200` → **200**, `MeuPluggy` do tipo `PERSONAL_BANK`: o conector proxy está
  disponível para a aplicação.
- Se já existem itens MeuPluggy conectados nessa aplicação: **não deu para saber** (listagem
  desligada). Depende do dono olhar no Dashboard.
- **Os IDs de `meu.pluggy.ai/connections/<id>` não servem** (medido em 2026-09-26 com as duas
  conexões do dono, Nubank e Itaú): `GET /items/<id>` → **404 `ITEM_NOT_FOUND`**. São itens da
  aplicação do próprio Meu Pluggy; a nossa precisa do item "espelho" criado pelo conector
  MeuPluggy, que tem **outro** ID.
- **Por que o dono não achou o conector** (base de suporte verificada da Pluggy, via MCP
  `search_qa`): o MeuPluggy só aparece no seletor depois de **habilitado uma vez** nas
  configurações de conectores da aplicação, no Dashboard; antes disso aparecem só o Sandbox e os
  bancos. Depois: criar conexão → escolher "MeuPluggy" (não o banco) → entrar com a conta do Meu
  Pluggy → autorizar **um banco por vez**. Nomes exatos dos botões do Dashboard: não conferidos.
- **O dono não achou nada do MeuPluggy no Dashboard** (2026-09-26): foi feito o plano B,
  `viking financas --conectar` (`lifeos/financas/conectar.py`). `POST /connect_token` → token
  (campo `accessToken`, conferido na OpenAPI) → página em `127.0.0.1`, num caminho aleatório, com
  o widget `PluggyConnect` (script `cdn.pluggy.ai/pluggy-connect/v2.7.0`, conferido que existe)
  já em `connectorIds: [200]`/`selectedConnectorId: 200`, sem sandbox → no `onSuccess`, o ID
  volta ao processo, que o confere com `GET /items/{id}`. Medido em `GET /connectors/200`: o
  MeuPluggy é **OAuth** (sem campos de credencial), então o widget abre o login do Meu Pluggy.
  **Medido no Mac (2026-09-27):** o OAuth do widget funciona com a página em `http://127.0.0.1`,
  sem `oauthRedirectUri` — duas rodadas, uma por banco (Nubank e Itaú), cada uma voltou com o ID
  e `status: UPDATED`; cada conexão traz uma conta corrente (`BANK/CHECKING_ACCOUNT`) e um cartão
  (`CREDIT/CREDIT_CARD`). O `lastUpdatedAt` era o da hora da conexão (19:44 e 19:51 UTC de
  2026-09-26). IDs e nomes das contas ficam só no `.env` do dono.

## Pagamentos: o que a chave alcança (medido em 2026-10-06, a D51)

Medido na abertura da Sessão 11c, no VPS, com o ok do dono naquele passo. Foram só dois `GET`
pelo cliente de `lifeos/financas/pluggy.py` (que recusa escrita antes da rede), mostrando o
código HTTP e a contagem, nunca o conteúdo:
- `GET /smart-transfers/preauthorizations` → **403 `PAYMENT_INITIATION_NOT_ALLOWED`**. Segundo a
  documentação ("Creating a preauthorization"), as Smart Transfers servem "to do payments without
  user interaction" depois de um consentimento único. É o único caminho em que um pagamento
  sairia sem o dono, e a aplicação dele não o alcança.
- `GET /payments/requests` → **200**, `{page, results, total, totalPages}` com 0 pedidos. A
  listagem abre. Se **criar** um pedido seria recusado não foi medido: só se mede escrevendo, e
  escrever é proibido.

Lido na mesma data (o MCP de documentação; `payments/overview` e o Q&A verificado):
- "Payments must be enabled specifically for your client. If you're interested in using it,
  please get in touch with our Sales team!"
- "O produto de pagamentos é exclusivo para clientes com assinatura" (Q&A); os planos de
  pagamentos começam em R$ 500/mês, separados dos de dados.
- **Todo PIX avulso exige o pagador no banco:** criar um pedido devolve um link
  (`pay.pluggy.ai`), e a tentativa nasce `CONSENT_AWAITING_AUTHORIZATION` ("the user needs to
  authorize it in the institution"), com um `consentUrl` do banco que vence em 5 minutos.
- A resposta gerada pela ferramenta `query` do MCP ("sim, exige autorização") é texto de modelo e
  não conta como fonte; as frases acima vêm do guia e do Q&A.

Consequência (D51): as duas condições se cumprem, e as finanças podem ir à nuvem num serviço
isolado só de leitura. A mudança é a Sessão 11d.

## MCP de documentação

`claude mcp add --transport http pluggy-docs https://mcp.pluggy.ai/mcp` (adicionado no Claude Code
do VPS em 2026-09-26). As ferramentas de documentação (`query`, `search_docs`, `search_qa`,
`list_endpoints`, `get_api_endpoint`) funcionam sem login. O mesmo servidor tem ferramentas
**autenticadas que escrevem** (`create_request`, `update_request`, `delete_request`, que apaga
item de verdade): não autenticar esse MCP numa sessão de agente sem necessidade.

## Formato real dos dados (medido nas conexões do dono, 2026-09-27; só estrutura, sem valores)

- **Sinal do `amount` muda por tipo de conta:** conta corrente, `DEBIT` vem **negativo**; cartão,
  `DEBIT` vem **positivo**. O sentido sai de `type` (`DEBIT`/`CREDIT`), nunca do sinal.
- **Parcelas no futuro:** no cartão, 144 transações parceladas (`creditCardMetadata` com
  `installmentNumber`/`totalInstallments`/`purchaseDate`/`billId`) e 45 parcelas `PENDING` com data
  até 2027. "Gasto do mês" não pode somar data depois de hoje.
- **O mesmo dinheiro aparece duas vezes:** pagar a fatura é `Credit card payment` na conta
  corrente e de novo no cartão; há também `Same person transfer`, `Transfer - Internal`,
  investimentos (`Investments`, `Fixed income`, `Variable income`, `Proceeds interests and
  dividends`) e `operationType` `RESGATE_APLIC_FINANCEIRA`/`RENDIMENTO_APLIC_FINANCEIRA`/
  `PAGAMENTO_FATURA`/`TRANSFERENCIA_MESMA_INSTITUICAO`. Nada disso é gasto.
- **Pagamento de fatura nem sempre vem categorizado:** na conta do Nubank, os 33 do histórico
  vêm como `Transfers`/`OUTROS`, com a descrição exata "Pagamento de fatura" (no Itaú, 13 de 13
  como `Credit card payment`). No lado do cartão, os créditos de pagamento começam todos por
  "pagamento" ("pagamento recebido" em 34+6, "pagamento com…" 13, "pagamento debito…" 6), e 19
  do Itaú vêm `Transfers` ou sem categoria (medido em 2026-09-27, contagens). Achado no primeiro
  `--gastos` do dono: o pagamento do Nubank entrava como gasto.
- **Taxonomia de transferências (`/categories`, 2026-09-27):** `04…` é "Same person transfer" com
  filhas (CASH, PIX, TED); `05…` é "Transfers": boleto (`05010000`), dinheiro, cheque, DOC,
  câmbio (`05050000`), mesma instituição (`05060000`), PIX (`05070000`), TED, "para terceiros"
  (`05090000` e filhas) e pagamento de cartão (`05100000`). No histórico do dono: `05000000`
  147, `05100000` 53, `04000000` 21, `05070000` 18, `05060000` 7, `05050000` 1.
- **Categoria:** em inglês (`category`), com `categoryId`; `/categories` tem 130, com
  `descriptionTranslated`. Faltam em parte: 6 de 65 numa conta, 31 de 265 num cartão.
- **`merchant` sempre vazio**; quem diz o que foi é `description`.
- **`paymentData` traz o CPF/CNPJ da contraparte** (`payer`/`receiver.documentNumber`) e dados
  de conta: não vai ao Gemini. `account.number`/`taxNumber`/`owner` também não.
- **Uma página de `/v2/transactions` sem filtro trouxe tudo** (até 351 itens, `next` vazio); o
  cursor existe mesmo assim.
- **Cartão:** `creditData` tem `creditLimit`, `availableCreditLimit`, `balanceCloseDate`,
  `balanceDueDate`, `minimumPayment`; `/bills` devolve as faturas fechadas (`totalAmount`,
  `dueDate`, `billClosingDate`).
- **Datas de fatura são datas, não instantes:** `dueDate` e `billClosingDate` vêm sempre às
  `T00:00:00.000Z` (25 de 25 faturas, medido em 2026-09-27; só a hora foi lida). Convertidas para
  Brasília, cairiam no dia anterior; `balanceDueDate` vem já sem hora. As transações, ao
  contrário, são instantes (`03:00Z` é meia-noite em Brasília) e se convertem — para Brasília,
  o fuso do banco, e não para o do dono (2026-09-28: ele não está nesse fuso).
- **`balance` do cartão é o limite usado, não a fatura do mês:** nos dois cartões,
  `balance == creditLimit − availableCreditLimit` (medido em 2026-09-27, só a comparação). A
  documentação diz o mesmo para conectores Open Finance. Inclui as parcelas futuras.
- **`balanceDueDate` é o vencimento da última fatura fechada**, já passado (igual ao `dueDate`
  mais recente de `/bills` nos dois cartões): não serve como "próximo vencimento".
- **Por que a fatura mais nova não vem (documentação, "Open Finance › Considerations & FAQ ›
  Bills", lida em 2026-09-27):** "open bills are not returned until the bills are closed or
  overdue (This depends on the FI)"; e o ciclo de uma compra de cartão: `PENDING` sem `billId`
  até a fatura vencer, quando a Pluggy acha a fatura e liga as compras. Nas do dono, a de
  setembro do Itaú fechou e não veio até o vencimento.
- **A última fatura de `/bills` pode estar atrasada:** fechou há 33 e 39 dias nos dois cartões, e
  vence 7 dias depois de fechar — uma fatura mais nova já fechou e ainda não veio.
- **Cada compra diz sua fatura:** `creditCardMetadata.billId` (não há `billId` no topo) está em
  333 de 336 e 219 de 219 transações até o último fechamento; depois dele, 8 e 7 sem `billId`
  (uma com); parcelas futuras sem `billId`. Sem `billId` e depois do fechamento: tipos `DEBIT`
  (compras), `CREDIT` de pagamento e `CREDIT` de estorno.

