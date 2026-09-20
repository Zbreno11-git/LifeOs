# Pluggy (Open Finance)

- **Serviço:** https://pluggy.ai — agregador de open finance/open banking brasileiro.
- **Status no projeto:** referência para a fase futura de finanças (não implementado ainda). Ver
  `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 6.
- **Por que Pluggy e não entrada manual:** decisão explícita do dono do projeto — adicionar
  gastos/lançamentos manualmente (texto ou voz) não é confiável o suficiente para um controle financeiro
  real. Dados vindos de uma conta bancária conectada via open finance são a única forma considerada
  confiável.
- **Estado da conta:** já existe uma conta Pluggy conectada (fora deste repo).
- **A avaliar antes de implementar:** custo da API (plano gratuito vs. pago), quais endpoints são
  necessários só para leitura de transações, limites de uso, e se dá para operar de forma sustentável
  sem pagar o tier completo.
- **Gancho de compatibilidade já preparado:** o schema de `src/lifeos/reminders/models.py` tem campos
  genéricos (`type`, `source`, `external_id`, `metadata`) pensados para acomodar, no futuro, registros
  como `type="finance_transaction", source="pluggy", external_id=<id da transação>` sem precisar de
  migração de schema.
