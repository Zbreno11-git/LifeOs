# Dispositivo de pulso + controle local de PC — PAUSADO

> **STATUS: PAUSADO (2026-09-20).** Esta trilha (assistente físico de pulso, controle local do PC via
> Windows-MCP) não é a prioridade atual. Foi substituída, como caminho principal de execução, pela
> automação de navegador (Jev + Browser Harness) — ver `docs/arquitetura/viking-visao-e-arquitetura.md`,
> seções 4.2 e 5. O código e os testes já feitos ficam preservados em `archive/wristband-fail-test/`;
> nada aqui foi descontinuado de vez, apenas despriorizado. Este documento condensa a arquitetura e o
> roadmap que antes viviam inline em `CLAUDE.md`.

## Arquitetura (alvo, conforme o doc de referência v1)

Fluxo proposto: botão/gesto → captura no ESP32 (XIAO ESP32-S3) → HTTPS → Life OS API (FastAPI) → STT →
roteamento de intenção → execução → resposta estruturada → TTS quando útil → playback no wristband.
Comandos conhecidos/simples podem pular o LLM no roteador.

Três destinos de execução, cada um com um dono distinto:
- **Cloud** (Life OS API): notas, lembretes, dados persistidos do usuário.
- **Windows PC / Bosgame** (via o *Life OS Windows Agent*, componente ainda a construir): ações locais
  no PC. (O doc de referência original chama isso de "Mac Agent" agindo no "Mac" — leia esses termos
  como este PC Windows agora; ver `docs/fontes/mac-control-mcp-dead-end.md`.)
- **Firmware** (no dispositivo): mudanças de volume/estado locais ao próprio wristband.

**Design do Windows Agent** — a decisão arquitetural a preservar (adaptada do Mac Agent do doc original):
- [`Windows-MCP`](https://github.com/CursorTouch/Windows-MCP) (externo, Python, MIT, roda no PC via a
  árvore de UI Automation, sem visão computacional) roda **no PC Windows**. Fork:
  https://github.com/Zbreno11-git/Windows-MCP. Ver `docs/fontes/windows-mcp.md`.
- O Life OS Windows Agent inicia esse servidor como um **cliente MCP local via stdio**
  (`uv run windows-mcp serve`) — MCP é usado só para esse salto local, nunca entre wristband/cloud e o PC.
- O Windows Agent mantém uma conexão **outbound**, autenticada, com o backend (WebSocket como escolha
  inicial, não validada) — nunca abre porta inbound/pública no PC.
- O backend nunca deve encaminhar um nome de tool arbitrário gerado por modelo para o Windows Agent. Ele
  emite uma intenção tipada, allow-listed; o Agent é quem traduz isso numa sequência de chamadas MCP
  locais (ex.: `PowerShell` com um comando específico e conhecido — não um arbitrário).
- Um fork do `Windows-MCP` só se justifica modificar se houver uma *necessidade comprovada*. Forkar para
  build a partir do source / fixar versão (prática atual) não é isso.

Envelope mínimo de comando (backend → Windows Agent): `request_id, device_id, target, action,
parameters, issued_at, expires_at, confirmation_required`. Resposta: `request_id, status, result|error,
completed_at`. `request_id` deduplica retentativas; `expires_at` evita disparar um comando obsoleto
quando o PC reconecta.

### Restrições de segurança/operação

- Autenticar wristband, usuário e PC separadamente; parear o PC à conta antes de aceitar comandos
  remotos. TLS + credenciais de curta duração/rotacionáveis; nunca embutir chaves de serviços de IA no
  firmware.
- MVP mantém a allow-list de ações remotas pequena. Leitura de tela, clipboard, envio de mensagens,
  execução de código e operações irreversíveis precisam de regras próprias e confirmação explícita antes
  de serem habilitadas. As tools `PowerShell`/`Registry`/`FileSystem` do `Windows-MCP` são amplas por
  design — o Windows Agent, não o servidor MCP cru, é quem deve aplicar a allow-list.
- Tratar transcrições e conteúdo de tela como dados não confiáveis — texto visto na tela nunca deve
  conceder ao agente novas permissões.
- Distinguir *recebido*, *executado* e *confirmado*: um HTTP 200 da API não é conclusão; só o próprio
  resultado do Windows Agent confirma. Mostrar "pendente" em vez de falso sucesso.
- Se o PC estiver dormindo/travado/desconectado/sem permissões, retornar um sinal claro de
  indisponibilidade em vez de travar ou falhar silenciosamente.

## Roadmap (pausado, como estava documentado)

1. **Fase 1 — Fail test** (feito): Arduino → Serial → Python (no Bosgame) → comando MCP local. Critério
   de saída: botão dispara uma vez; sucesso/erro observável. Não valida Wi-Fi, MCP-por-rede, nem voz.
2. **MVP 0.5 — Canal remoto**: ESP32 → API autenticada → Windows Agent → MCP local → play/pause. Critério
   de saída: resultado ponta a ponta, reconexão e tratamento de comando duplicado testados; LED de status
   reflete o resultado real.
3. **MVP 1 — Áudio de entrada**: XIAO + INMP441 → upload via Wi-Fi → STT → nota/ação.
4. **MVP 2 — Resposta e ergonomia**: adicionar sensor ToF, saída de áudio MAX98357A, botões, TTS.
5. **Produto**: case, pareamento, updates, observabilidade, catálogo de ações.

## Perguntas em aberto (herdadas, ainda não respondidas)

Conectividade da wristband fora de redes conhecidas; quais comandos precisam de confirmação explícita vs.
execução direta; provisionamento/atualização do Windows Agent e recuperação de permissões (nenhuma
auditoria equivalente ao TCC do macOS foi feita); metas mensuráveis de latência/bateria/precisão de
STT/custo; se notas/lembretes ou controle de PC deveriam ser a prioridade de usuário inicial (hoje
respondido para o milestone atual do Viking: nenhum dos dois — o milestone atual é
calendário+navegador+lembretes, ver `docs/arquitetura/viking-visao-e-arquitetura.md`).
