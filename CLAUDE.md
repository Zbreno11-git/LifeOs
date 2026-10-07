# CLAUDE.md

Guia técnico deste repositório: @AGENTS.md

O conteúdo canônico (arquitetura, comandos, armadilhas, segredos) fica em `AGENTS.md`, compartilhado
com o Codex e qualquer outro agente — não duplique nada aqui. Abaixo só o que é específico de
trabalhar neste repo a partir de uma sessão do Claude Code.

## Como o trabalho acontece aqui

O ambiente do Claude Code neste projeto é um **VPS Linux sem tela**. Isso significa que há uma
classe inteira de coisas que **não dá para validar aqui**, só escrever:

- qualquer chamada ao OpenRouter (a chave do Jev vive no Mac do dono);
- qualquer coisa que toque um Chrome de verdade (o Browser Harness exige um clique humano em "Allow
  remote debugging" na primeira vez, e aqui não há display);
- o fluxo OAuth do Google (Calendar e Gmail).

**Mas o VPS tem o cliente OAuth do Google** (`secrets/google_credentials.json`, e o token da agenda
desde 2026-09-20). Um comando que toca o Google aqui abre o login, e o VS Code do dono abre a aba
no navegador dele: aprovado, age na conta real. Em 2026-09-29 isso mandou um e-mail de verdade e
deixou um token `gmail.modify` no VPS; o dono mandou apagá-lo (o VPS não guarda token do Gmail).
Antes de rodar um `viking …` que fala com o Google, `ls secrets/`, e nada que envie, apague ou
arquive por aqui (`docs/erros.md`, classe 2).

**O `.env` do VPS tem as chaves do Gemini e da Pluggy** (desde 2026-09-26; medido na abertura da
Sessão 10, e o `CLAUDE.md` dizia o contrário). O dono decidiu mantê-las: são a fonte do que a nuvem
vai usar. Nada daqui as usa sem pedido: um `viking chat` ou `viking financas` no VPS gastaria
tokens de verdade e leria o banco de verdade. A da Pluggy alcança PIX: na nuvem ela mora só no
serviço de finanças (D64, Sessão 11d), e o segredo `viking-pluggy` sobe do Mac (os IDs das
conexões só existem lá).

**E o VPS tem o `gcloud` logado com a conta do dono** (desde 2026-09-07, de propósito, para os
projetos dele; o ADC junto). O projeto padrão da configuração é **outro** projeto dele: todo
comando de nuvem do Viking leva `--project` explícito (D47 revista, D58), e nenhum teste constrói
cliente de nuvem sem o emulador.

O ciclo real é: escrever e testar aqui o que é testável (lógica pura, parsing, timeout, mensagens) →
commitar e dar push → o dono faz `git pull` no Mac e roda. **Por isso "terminei" só é verdade depois
do push**: até lá o trabalho não chegou na máquina onde ele roda.

Quando algo precisar de validação ao vivo, monte o comando completo para o dono colar no terminal do
Mac e peça a saída — não presuma o resultado. Vários bugs desta base só apareceram assim.

## Ao propor comandos para o dono rodar

Ele usa zsh no macOS, com conda base ativo junto do venv. Consequências práticas estão em
`AGENTS.md` ("Armadilhas já pagas"): sem comentário `#` na mesma linha do comando, instalar com
`uv sync --locked --extra dev`, testar com `python -m pytest` (e `uv pip`, não `python -m pip`, para
mexer na venv), e nunca mandar imprimir arquivo de segredo.

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
