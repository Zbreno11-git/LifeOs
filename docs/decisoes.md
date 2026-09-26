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
| D11 | Gmail pela **API oficial** (feito, só leitura, 2026-09-26) (OAuth do calendário + `gmail.readonly`), nunca pelo navegador | dado estruturado, permissão mínima, nada passa pelo OpenRouter | dono, 2026-09-26 | abrir o Gmail no navegador (segue bloqueado por D8) | o app OAuth não conseguir o escopo (status "Testing" não conferido) | `sessoes.md`, Sessão Gmail |
| D12 | Erro de tool do MCP é erro de verdade (`is_error=True`), com `structured_content` | cliente MCP distingue falha de sucesso | dono, 2026-09-20 (Sessão 3) | devolver erro como texto de sucesso | — | `docs/fontes/fastmcp.md` |
| D13 | `_redacao.py` fica em `browser/`, mesmo o calendário e o Gmail usando | tem de ser vizinho de `_jev_subprocess.py`, que o importa pelo caminho dentro do ambiente do Jev. O gatilho (terceiro consumidor, o Gmail) disparou em 2026-09-26 e a decisão foi reavaliada: mantida | agente, 2026-09-26 | mover para um módulo neutro (quebraria o import do subprocesso ou exigiria mexer em `sys.path`) | uma forma de o subprocesso importá-lo sem `lifeos` e sem mexer em `sys.path` | `calendar/service.py`, comentário |
| D14 | Não redigir o valor atual dos campos da página | hipótese **não medida**: o Jev acharia o campo vazio e repreencheria em loop | agente, 2026-09-26 | redigir `current_value` | observar ao vivo que não há loop, ou dado sensível vazando por ali | `docs/fontes/jev-typesafe.md` |
| D15 | Skills de trabalho em `.claude/skills/`, commitadas, sem o nome do projeto de origem | viajam com o repo até o Mac; o repo é **público**. Citar a Altiva em outros docs não é problema (dono esclareceu no mesmo dia) | dono, 2026-09-26 | só no VPS (`~/.claude/skills/`); commitar com o nome | — | `.claude/skills/README.md` |
| D16 | Freio de clique destrutivo antes do Gmail (Sessão 4b) | o Jev dirige a Chrome logada; era o maior risco aberto e estava sem sessão | dono, 2026-09-26 | deixar na Sessão 5 | — | `sessoes.md` |
| D17 | Verificação automática no GitHub (pytest + ruff) junto com o lockfile, na Sessão 7 | grátis em repo público; segunda máquina conferindo | dono, 2026-09-26 | adiantar agora; não ter | — | `sessoes.md`, Sessão 7 |
| D18 | Freio de cliques: recusa **sair**, **mexer na conta** e **dinheiro**; a tarefa **para e avisa** (aba aberta, botão nomeado); **sem liberação** até a Sessão 5 | o Jev dirige a Chrome logada; um clique desses é irreversível ou desloga em todos os aparelhos | dono, 2026-09-26 (Sessão 4b) | "publicar em seu nome" (alarme falso demais); pedir outra ação ao Jev (pode chegar ao mesmo lugar por outro caminho); liberar por categoria no `.env` | a Sessão 5 entregar a confirmação em duas etapas | `docs/fontes/jev-typesafe.md` |
| D19 | O freio nasce ligado, sem fase de só observar | falso positivo custa uma tarefa parada com o botão nomeado; falso negativo, a conta | agente, 2026-09-26 | medir antes de cobrar (regra geral da skill `evidencia` §8) | alarme falso medido atrapalhando uso real no Mac | `_acoes_sensiveis.py` |
| D20 | Mutações curadas em `scripts/mutacoes.py`, à mão; a suíte normal só confere as âncoras | 16 mutações levam ~40 s; a conferência de âncora pega a lista apodrecendo no mesmo dia | agente, 2026-09-26 | rodar mutação no `pytest`/CI a cada push (caro, e o custo gerou erros no projeto de origem) | a Sessão 7 ligar o CI e sobrar folga para uma rodada agendada | `AGENTS.md`, Comandos |
| D21 | Gmail só no `viking chat`, não pelo servidor MCP | o MCP ainda não tem autenticação: qualquer app ligado nele leria a caixa inteira | dono, 2026-09-26 (Sessão Gmail) | expor pelo MCP | o MCP ganhar autenticação e o dono pedir | `gmail/tools.py`; teste `test_servidor_mcp_nao_expoe_email` |
| D22 | E-mail passa pela redação das páginas: somem CPF/CNPJ/cartão/chaves e o token de links; endereços de e-mail e códigos de verificação ficam | o dono quer poder perguntar "qual o código que chegou?" | dono, 2026-09-26 | redigir também códigos; não redigir nada | — | `docs/fontes/gmail-api.md` |
| D23 | Limpar a caixa = só **arquivar**, numa sessão própria, sempre com a lista exata aprovada pelo dono | o Viking nunca tem mais permissão do que usa (`gmail.readonly` agora, `gmail.modify` só na limpeza); arquivar é sempre reversível | dono, 2026-09-26 | lixeira, marcar como lido, descadastrar; regra automática; tudo nesta sessão | — | `sessoes.md`, Sessão Gmail 2 |
| D24 | Token do Gmail em arquivo próprio, fluxo de login compartilhado (`google_auth.py`) | falha ou revogação do Gmail não derruba o calendário | agente, 2026-09-26 | um token com os dois escopos | o dono preferir um login só | `docs/fontes/gmail-api.md` |
| D25 | Limpeza escolhida **por remetente**; saem todos os e-mails dele da caixa de entrada (lidos ou não); nunca saem os com estrela, importantes ou com anexo | previsível; arquivar é reversível | dono, 2026-09-26 (abertura da Gmail 2) | por regra do Gmail; só não lidos; proteger os de hoje | — | `sessoes.md`, Sessão Gmail 2 |
| D26 | Aprovação da limpeza **digitando um código** mostrado direto no terminal, fora do Gemini | e-mail com prompt injection não consegue fazer o Gemini se autoaprovar | dono, 2026-09-26 | "sim" no chat | — | `sessoes.md`, Sessão Gmail 2 |
| D27 | **Desfazer** um arquivamento por 7 dias, devolvendo exatamente os mesmos e-mails | — | dono, 2026-09-26 | depender só de "Todos os e-mails" | — | `sessoes.md`, Sessão Gmail 2 |

## Formato de um gatilho bom

Mensurável e com quem mede ("o teste de contrato falhar", "o dono pedir X"). Nunca "quando der"
ou "no futuro": isso é esquecimento agendado.
