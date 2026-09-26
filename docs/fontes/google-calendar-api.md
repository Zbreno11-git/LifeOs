# Google Calendar API

- **API:** Google Calendar API v3, via `googleapiclient` (`google-api-python-client`)
- **Auth:** OAuth 2.0 via `google-auth-oauthlib` — fluxo `InstalledAppFlow.from_client_secrets_file`
  com servidor local para o redirect; token cacheado em disco e renovado automaticamente.
- **Escopo usado:** operações sobre `calendarId='primary'` — listar próximos eventos, listar por
  data/intervalo (no fuso civil configurado por `VIKING_TIMEZONE`), criar evento (com hora ou dia
  inteiro), deletar por ID (com conferência de título), reagendar por ID (idem).
- **Origem no repo:** portado do protótipo `calendar-bot/` (`oauth.py`, `calendar_tools.py`) para
  `src/lifeos/calendar/`. Ver `docs/arquitetura/viking-visao-e-arquitetura.md`, seção 4.1.
- **Credenciais:** `credentials.json` (client secret OAuth) e `token.json` (refresh token) vivem em
  `secrets/` (gitignored) — nunca commitar. Ver `AGENTS.md`, seção de segredos.
- **Setup:** criar um projeto no Google Cloud Console, habilitar a Calendar API, gerar credenciais OAuth
  "Desktop app", baixar o `credentials.json` para `secrets/google_credentials.json`.

## Camadas no Viking (Sessão 3b, 2026-09-26)

- `calendar/service.py` — lógica e travas, sem texto. Devolve `Evento` (id, título, início, fim,
  dia inteiro, link) ou levanta um erro de domínio com `codigo`: `entrada_invalida` (com
  `campo`: `event_id`, `titulo_esperado`, `data`, `horario`, `intervalo`), `nao_encontrado`,
  `titulo_divergente` (com `titulo_real`) ou `falha_api`. Toda chamada ao Google passa por
  `_executar`, que envolve a *montagem* da requisição e o `.execute()` — antes, falha da API em
  criar/reagendar/listar subia como exceção crua.
- `calendar/tools.py` — o texto. Cada `responder_*` devolve `Resposta(texto, dados, erro)`; as
  tools do Gemini devolvem só o `texto` (idêntico ao de antes — docstrings e assinaturas
  conferidas contra um retrato do código anterior).
- `mcp_server/server.py` — mesmo `texto` + `structured_content` (`{"eventos": [...]}` nas
  leituras, o evento afetado nas mutações). Recusa de trava e falha da API viram `is_error=True`
  com `{"erro": codigo, ...}`.
- Títulos passam por `limpar_controles`: vêm de convites de terceiros.
- Testes nunca falam com o Google de verdade: `tests/conftest.py` troca `get_calendar_service` por
  uma função que falha alto, e o fake (`calendario`) entra por cima. No Mac, onde o token existe,
  um teste que escapasse do fake criaria evento na agenda real.
