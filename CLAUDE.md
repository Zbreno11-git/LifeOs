# CLAUDE.md

Guia técnico deste repositório: @AGENTS.md

O conteúdo canônico (arquitetura, comandos, armadilhas, segredos) fica em `AGENTS.md`, compartilhado
com o Codex e qualquer outro agente — não duplique nada aqui. Abaixo só o que é específico de
trabalhar neste repo a partir de uma sessão do Claude Code.

## Como o trabalho acontece aqui

O ambiente do Claude Code neste projeto é um **VPS Linux sem tela e sem as chaves de API**. Isso
significa que há uma classe inteira de coisas que **não dá para validar aqui**, só escrever:

- qualquer chamada ao Gemini ou ao OpenRouter (as chaves vivem no Mac do dono);
- qualquer coisa que toque um Chrome de verdade (o Browser Harness exige um clique humano em "Allow
  remote debugging" na primeira vez, e aqui não há display);
- o fluxo OAuth do Google Calendar.

O ciclo real é: escrever e testar aqui o que é testável (lógica pura, parsing, timeout, mensagens) →
commitar e dar push → o dono faz `git pull` no Mac e roda. **Por isso "terminei" só é verdade depois
do push**: até lá o trabalho não chegou na máquina onde ele roda.

Quando algo precisar de validação ao vivo, monte o comando completo para o dono colar no terminal do
Mac e peça a saída — não presuma o resultado. Vários bugs desta base só apareceram assim.

## Ao propor comandos para o dono rodar

Ele usa zsh no macOS, com conda base ativo junto do venv. Consequências práticas estão em
`AGENTS.md` ("Armadilhas já pagas"): sem comentário `#` na mesma linha do comando, sempre
`python -m pip`/`python -m pytest`, e nunca mandar imprimir arquivo de segredo.

## Skills do projeto (`.claude/skills/`)

O `README.md` de lá diz quando usar cada uma. As que valem sempre aqui:

- **`software-build`** ao abrir, planejar e fechar uma sessão de `sessoes.md`. O formato do plano
  está em `referencia/plano-de-sessao.md`, e a revisão em duas passadas em `referencia/revisao.md`.
- **`pre-compact`** assim que o dono avisar de um `/compact`, de uma conversa nova ou de parar por
  hoje: fechar a etapa num ponto seguro, atualizar o bloco de `PROGRESSO.md`, commit e push, e
  entregar o prompt pós-compact. Logo **depois** de um compact vale a seção "Depois do compact":
  ler e conferir antes de executar qualquer coisa. O dono usa isso muito.
- **`evidencia`** e **`testes-que-provam`** antes de escrever um número ou dizer "testado".

## Memória entre sessões

Há memória em `/root/.claude/projects/-root-LifeOs/memory/` com preferências de trabalho do dono
(fluxo de entrega, estilo de resumo, decisões de produto do Viking). Vale reler antes de assumir
como ele prefere trabalhar — ela existe justamente porque este repo atravessa várias sessões.
