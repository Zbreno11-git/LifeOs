# Google Calendar API

- **API:** Google Calendar API v3, via `googleapiclient` (`google-api-python-client`)
- **Auth:** OAuth 2.0 via `google-auth-oauthlib` — fluxo `InstalledAppFlow.from_client_secrets_file`
  com servidor local para o redirect; token cacheado em disco e renovado automaticamente. Desde a
  Sessão Gmail o fluxo mora em `lifeos/google_auth.py`, compartilhado com o Gmail (que tem token
  próprio) — ver `docs/fontes/gmail-api.md`, "Login compartilhado".
  Desde a Sessão 11c (D63), o backup tem o terceiro token, o do Drive
  (`secrets/google_token_drive.json`, escopo `drive.file`, que só enxerga os arquivos que o Viking
  cria e não é escopo sensível), feito no Mac por `viking backup --login`. O cliente OAuth mora
  noutro projeto do dono, e a API do Drive já estava ligada lá (medido em 2026-10-06, `gcloud
  services list --enabled`). O token da agenda de 2026-09-20 ainda renovava em 2026-10-06: o app
  não está no modo "teste", que venceria os tokens em 7 dias.
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
- **Paginação (Sessão 8b, 2026-09-29):** o `events.list` devolve até 250 por página se não se
  pede outro número, e o resto por `nextPageToken`. `buscar` e `por_data` seguem as páginas até
  `service.TETO_EVENTOS` (500) e devolvem `Eventos` com `completa`; quem para no teto diz "há
  mais" no texto. `proximos` pede N e é completa por definição. A referência diz que uma página
  pode vir com menos que o pedido, "or none at all, even if there are more events" (lida em
  2026-09-29): por isso há também `MAX_PAGINAS` (10), achado na revisão — sem ele, páginas
  vazias com `nextPageToken` fariam o laço girar para sempre.
- `mcp_server/server.py` — mesmo `texto` + `structured_content` (`{"eventos": [...],
  "completa": bool}` nas leituras, o evento afetado nas mutações). Recusa de trava e falha da API viram `is_error=True`
  com `{"erro": codigo, ...}`.
- Títulos passam por `limpar_controles`: vêm de convites de terceiros.
- Testes nunca falam com o Google de verdade: `tests/conftest.py` troca `get_calendar_service` por
  uma função que falha alto, e o fake (`calendario`) entra por cima. No Mac, onde o token existe,
  um teste que escapasse do fake criaria evento na agenda real.

## Restaurar um evento apagado (lido em 2026-09-27 para a Sessão 5; restaurar **medido** no Mac no mesmo dia)

A referência do recurso `Events` diz que, no calendário do organizador, um evento cancelado
(`events.delete`) continua expondo os detalhes "so that they can be restored (undeleted)", e que
esses eventos "will eventually disappear". O método não é nomeado; o caminho provável é
`events.patch` com `{"status": "confirmed"}` no mesmo ID. Para evento em que o dono é só
convidado, os detalhes não ficam. Um `insert` com o ID antigo tende a dar 409 (cópia precisa de ID
novo).

**Como o Viking faz (Sessão 5, `calendar/service.restaurar`):** reivindica a ação no registro (uma
vez só) e relê o evento; `confirmed` → nada a fazer; `cancelled` → `patch {"status": "confirmed"}`
com `sendUpdates="none"`; sumiu → cópia sem convidados. Reagendamento volta só se o horário atual
é o que o Viking pôs, com o campo que não vale anulado (`{"date": d, "dateTime": null}`: um
`patch` em `start` mescla). Falha ambígua do desfazer deixa a ação desfeita (não recria duas
vezes). Não medido: a mescla com `null` e o `patch` de status — validar no Mac.

A validar no Mac (C9 da Sessão 5), no evento "Teste Viking": `get` depois do `delete` devolve
`status=cancelled`?; o `patch` volta o mesmo ID e ele reaparece no `list`?; convidados recebem
aviso (`sendUpdates`)?. Até medir, o desfazer do Viking tenta restaurar e, se não der, recria uma
cópia **sem convidados** e com `sendUpdates="none"` (reconvidar mandaria e-mail em nome do dono),
avisando "ID novo"; recusa evento recorrente e de outro organizador.

**Medido no Mac em 2026-09-27 (C9), evento "Teste Viking" sem convidados:** criar → apagar pelo
chat → `desfaz` respondeu "voltou ao calendário" — o caminho `restaurado`: o `get` depois do
`delete` deu `cancelled` e o `patch {"status": "confirmed"}` no mesmo ID funcionou; a busca
seguinte (pelo MCP) achou o evento e o apagou. **Não medido:** aviso a convidados (o evento não
tinha) e a mescla com `null` do desfazer de um reagendamento (não houve reagendamento).
