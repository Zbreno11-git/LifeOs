# Viking (Life OS)

Assistente pessoal unificado — calendário, navegação web e lembretes via chat. Workspace Python 3.12.
Ver `AGENTS.md` para o guia técnico completo e `docs/arquitetura/viking-visao-e-arquitetura.md` para a
visão de produto.

## Setup

```bash
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # preencher GEMINI_API_KEY
# credenciais do Google Calendar em secrets/ — ver docs/fontes/google-calendar-api.md
```

## Uso

```bash
viking chat         # assistente de chat (calendário + navegador + lembretes)
viking mcp-server    # servidor MCP do Viking
```

## Estrutura

- `src/lifeos/` — pacote do Viking (`calendar/`, `browser/`, `reminders/`, `assistant/`, `mcp_server/`)
- `tests/` — testes (pytest)
- `docs/` — `diario-de-bordo.md` (log de progresso), `arquitetura/` (visão/arquitetura), `fontes/`
  (referências técnicas externas)
- `archive/` — trilhas pausadas mas preservadas (ex.: dispositivo de pulso)
- `secrets/` — credenciais locais reais, gitignored
- `data/` — dados locais (ignorado pelo git, exceto `.gitkeep`)
