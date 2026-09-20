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
