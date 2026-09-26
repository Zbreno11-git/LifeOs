# Decisões — Viking

> Decisões que moldam o sistema: o quê, por quê, quem decidiu e o **gatilho** que as reabre. Não
> se reabre uma decisão sem que o gatilho tenha disparado. Decisão de produto, de dinheiro, de
> limiar ou de adiamento é do dono; a técnica o agente toma e declara, e o dono pode derrubar.
> Uma proposta **recusada** também entra, com o motivo, para não ser proposta de novo.
>
> Criado em 2026-09-26 juntando o que estava espalhado (`AGENTS.md`, `sessoes.md`, diário e a
> memória local do Claude no VPS, que o Codex e o Mac não veem). Onde a decisão já tem
> detalhe em outro doc, a coluna "Onde" aponta para ele — o detalhe continua lá.

| # | Decisão | Por quê | Quem, quando | Recusado e por quê | Gatilho para reabrir | Onde |
|---|---|---|---|---|---|---|
| D1 | **Viking** é a marca; **Life OS** é o codinome técnico (pacote `lifeos`, comando `viking`) | — | dono, 2026-09-20 | — | — | `AGENTS.md` |
| D2 | Trilha de hardware (pulso → ESP32 → Windows-MCP) **pausada, não descontinuada** | o assistente CLI entrega valor antes | dono, 2026-09-20 | expandir o Windows Agent agora | o dono reativar a trilha, ou o Bosgame voltar | `docs/arquitetura/wristband-hardware-pausado.md` |
| D3 | Navegador (Jev + Browser Harness numa Chrome real) é o mecanismo de execução padrão | substitui o controle local de PC | dono, 2026-09-20 | Windows-MCP como mecanismo principal | D2 reabrir | `docs/arquitetura/browser-automation-stack.md` |
| D4 | `mac-control-mcp` fora | exige macOS 14+; o Mac é um 2017 Intel em Ventura 13, sem upgrade (bloqueio de plataforma) | medido, 2026-09-20 | — | Mac com macOS 14+ | `docs/fontes/mac-control-mcp-dead-end.md` |
| D5 | Finanças via **Pluggy** (open finance), não entrada manual | entrada manual não é confiável | dono, 2026-09-20 | entrada manual de transações | custo real do Pluggy medido e inviável (pergunta aberta) | `docs/fontes/pluggy-open-finance.md` |
| D6 | Código escrito no VPS, validado no Mac do dono (`git pull`) | o Browser Harness exige um clique humano em "Allow remote debugging"; o VPS não tem tela nem chaves | dono, 2026-09-20 | — | outra máquina com tela e chaves passar a ser a de teste | `CLAUDE.md` |
| D7 | Chaves do Jev (`OPENROUTER_API_KEY`, `TEXT_MODEL_*`) só no `.env` do clone do Jev; o Viking guarda só `VIKING_JEV_DIR` | duas cópias da chave divergem na rotação | agente, 2026-09-20 | duplicar no `.env` do Viking | — | `AGENTS.md` |
| D8 | Navegador **bloqueia banco e e-mail por padrão**; libera por domínio no `.env` | a página vai para OpenRouter e Gemini | dono, 2026-09-26 | só redigir, sem bloquear | o dono pedir um site bancário específico (já é possível por `VIKING_BROWSER_LIBERADOS`) | `docs/fontes/jev-typesafe.md` |
| D9 | E-mails na página **não** são redigidos | o dono quer vê-los | dono, 2026-09-26 | redigir e-mail junto com CPF/cartão | um e-mail de terceiro vazar para onde não devia (caso medido) | `docs/fontes/jev-typesafe.md` |
| D10 | Proteção do caminho OpenRouter **sem editar o fork**, por envelope em `choose`/`field_context` | mesma cobertura, zero conflito com o upstream, uma cópia só da regra | dono pediu "patchar o fork"; agente propôs o envelope; dono aprovou, 2026-09-26 | editar o fork | `test_contrato_com_o_jev_real` falhar (o Jev mudou como chama as duas funções) | `AGENTS.md`, armadilhas |
| D11 | Gmail pela **API oficial** (OAuth do calendário + `gmail.readonly`), nunca pelo navegador | dado estruturado, permissão mínima, nada passa pelo OpenRouter | dono, 2026-09-26 | abrir o Gmail no navegador (segue bloqueado por D8) | o app OAuth não conseguir o escopo (status "Testing" não conferido) | `sessoes.md`, Sessão Gmail |
| D12 | Erro de tool do MCP é erro de verdade (`is_error=True`), com `structured_content` | cliente MCP distingue falha de sucesso | dono, 2026-09-20 (Sessão 3) | devolver erro como texto de sucesso | — | `docs/fontes/fastmcp.md` |
| D13 | `_redacao.py` fica em `browser/`, mesmo o calendário usando | tem de ser vizinho de `_jev_subprocess.py`, que o importa pelo caminho dentro do ambiente do Jev | agente, 2026-09-26 | mover para um módulo neutro agora | a Sessão Gmail (terceiro consumidor) — extrair sem quebrar o import do subprocesso | `calendar/service.py`, comentário |
| D14 | Não redigir o valor atual dos campos da página | hipótese **não medida**: o Jev acharia o campo vazio e repreencheria em loop | agente, 2026-09-26 | redigir `current_value` | observar ao vivo que não há loop, ou dado sensível vazando por ali | `docs/fontes/jev-typesafe.md` |
| D15 | Skills de trabalho em `.claude/skills/`, commitadas, sem o nome do projeto de origem | viajam com o repo até o Mac; o repo é **público** | dono, 2026-09-26 | só no VPS (`~/.claude/skills/`); commitar com o nome | — | `.claude/skills/README.md` |
| D16 | Freio de clique destrutivo antes do Gmail (Sessão 4b) | o Jev dirige a Chrome logada; era o maior risco aberto e estava sem sessão | dono, 2026-09-26 | deixar na Sessão 5 | — | `sessoes.md` |
| D17 | Verificação automática no GitHub (pytest + ruff) junto com o lockfile, na Sessão 7 | grátis em repo público; segunda máquina conferindo | dono, 2026-09-26 | adiantar agora; não ter | — | `sessoes.md`, Sessão 7 |

## Formato de um gatilho bom

Mensurável e com quem mede ("o teste de contrato falhar", "o dono pedir X"). Nunca "quando der"
ou "no futuro": isso é esquecimento agendado.
