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

## MCP de documentação

`claude mcp add --transport http pluggy-docs https://mcp.pluggy.ai/mcp` (adicionado no Claude Code
do VPS em 2026-09-26). As ferramentas de documentação (`query`, `search_docs`, `search_qa`,
`list_endpoints`, `get_api_endpoint`) funcionam sem login. O mesmo servidor tem ferramentas
**autenticadas que escrevem** (`create_request`, `update_request`, `delete_request`, que apaga
item de verdade): não autenticar esse MCP numa sessão de agente sem necessidade.
