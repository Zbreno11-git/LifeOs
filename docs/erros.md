# Catálogo de erros — Viking

> Erros que **o agente** cometeu neste repo e consegue citar, com o caso real. Não é lista de boas
> práticas. Organizado **por classe**, a que mais se repete no topo; uma ocorrência nova entra na
> classe existente, com o que ela tem de diferente. Sem incidente, não entra.
>
> **Ao achar um defeito, abra este arquivo antes de atacar:** *de que classe daqui isto é uma
> instância?* Se for de alguma, o antídoto já está escrito.
>
> Diferença para "Armadilhas já pagas" do `AGENTS.md`: lá ficam as regras do **ambiente** que
> continuam valendo (conda no Mac, future import, C1 no `json.dumps`); aqui, o **meu modo de
> errar**. Criado em 2026-09-26 com as ocorrências registradas no diário, no `AGENTS.md` e na
> memória do Claude.

## Índice

| Nº | Classe | Ocorrências | Antídoto em uma linha |
|---|---|---|---|
| 1 | Comando para o Mac que não roda como escrito | 4 | caminho real `~/LifeOs`, `which python` depois do `source`, sem `#` na linha, `python -m`, nunca imprimir segredo |
| 2 | Afirmei sem abrir o lugar onde estaria | 3 | *quem mediu isto, quando, com qual comando?* — e `grep`/`git log` antes de afirmar |
| 3 | Estimei em vez de medir | 3 | medir no mesmo processo; nunca régua de caractere por token; medir a linha antes de quebrar |
| 4 | Teste que não separava o certo do errado | 3 | desfazer o conserto e ver **o** teste cair; dimensionar a entrada pela diferença, não pelo caso |
| 5 | A ferramenta fez outra coisa do que eu li | 3 | escapes gerados por script; varredura de caracteres de controle antes do commit |
| 6 | Conserto que cobriu um ponto e não o vizinho | 2 | *onde mais esta falha pode nascer?* antes de dar por pronto |

---

### 1. Comando para o Mac que não roda como escrito

**Antes de 2026-09-20 — `cat .env` num passo a passo.** Vazou a chave OpenRouter do dono para a
conversa. Virou regra no `AGENTS.md`: conferir variáveis com `grep -o '^[A-Z_]*=' .env`.

**2026-09-20 — `#` na mesma linha do comando.** O zsh interativo passou o comentário como
argumento (`git log -1 # commit` deu erro).

**2026-09-20 — placeholder no roteiro.** Mandei `cd ~/caminho/para/LifeOs`; o dono colou literal.

**2026-09-20 — sem `which python`.** O primeiro `pytest` do roteiro rodou no Python do conda
(`ModuleNotFoundError: No module named 'lifeos'`), porque o `.venv` não estava ativo naquele shell.

> **Um comando para o dono é código que roda numa máquina que eu não vejo.** Ele tem de funcionar
> colado sem edição, no zsh com conda ativo.

**O antídoto, concreto:** todo roteiro começa com `cd ~/LifeOs`, `source .venv/bin/activate` e
`which python`; `python -m pip`/`python -m pytest`; nenhum `#` na linha; nenhum `cat` de arquivo
com segredo.

### 2. Afirmei sem abrir o lugar onde estaria

**2026-09-20 — "3 commits locais com o patch".** `docs/fontes/jev-typesafe.md` afirmou isso a
partir de um relatório; `git log` mostrava que os 3 eram do upstream e o patch nem estava
commitado. O risco real era maior que o documentado.

**2026-09-26 — "o Jev da TypeSafe quase certamente não é o do `jev-ultrafast`".** Errado: o `.env`
do Jev usa `TYPESAFE_MODEL=~typesafe/jev-latest`, e isso estava escrito em `jev-typesafe.md`.

**2026-09-26 — armadilha não medida no `AGENTS.md`.** Quase registrei como "já paga" que redigir o
valor dos campos faz o Jev repreencher em loop. Nunca foi observado; foi para `jev-typesafe.md`
como hipótese.

> **Um texto nosso é registro de uma medição passada, ou nem isso.** Afirmar ausência ("não é o
> mesmo", "não existe") é a afirmação mais fácil de fazer sem procurar.

**O antídoto, concreto:** antes de afirmar estado de repositório, `git log`/`git status`; antes de
afirmar que algo é ou não é, abrir o arquivo onde estaria; "Armadilhas já pagas" só com incidente.

### 3. Estimei em vez de medir

**2026-09-20 — tokens por caractere.** A régua "4 caracteres por token" errou por 6×. E medir em
duas conversas ao vivo deu -80 onde o real, no mesmo processo, era -477.

**2026-09-20 — "ordens de grandeza mais barato".** Afirmei a partir do `example.com` (~500 tokens);
o YouTube gastou 24.507 tokens em 6 chamadas.

**2026-09-20 — comprimento de linha (Sessão 3).** Estimei a largura na indentação errada, quebrei
uma string, e o `ruff format` juntou de volta.

> **Um número sem comando é hipótese, mesmo quando parece óbvio.**

**O antídoto, concreto:** o procedimento de medição de tokens do `AGENTS.md`; para linha, medir a
linha real antes de quebrar; todo número no chat vem com "medido"/"estimado".

### 4. Teste que não separava o certo do errado

**2026-09-20 — tools do Gemini sem argumento.** O `from __future__ import annotations` quebrava
toda chamada **com** argumento; os testes/usos sem argumento passavam e mascaravam o bug. Hoje há
teste por tool que passa argumento.

**2026-09-26 — ReDoS pequeno demais (Sessão 4).** 5 mil blocos davam 2,6 s na regex vulnerável,
perto do teto de 2 s: num Mac rápido a regressão passaria. Pego pela mutação; 10 mil blocos dão
10,5 s na vulnerável contra 0,43 s na certa.

**2026-09-26 — fixture sem o módulo que o código novo exige (Sessão 4).** A fixture `jev_falso`
não injetava `jev_ultrafast.agent`; todos os testes do subprocesso cairiam em
`protecao_indisponivel` pelo motivo errado. Previsto no plano e corrigido antes.

> **Se o teste ficar verde, quantas explicações isso admite?** Uma só, ou ele não é a régua.

**O antídoto, concreto:** mutação vista caindo antes de dar por pronto (a Sessão 4b torna isso
repetível em `scripts/mutacoes.py`); a entrada do teste é dimensionada pela diferença entre o
certo e o errado, com folga para máquina rápida.

### 5. A ferramenta fez outra coisa do que eu li

**2026-09-26 — `\u202e` pela ferramenta de escrita (Sessão 4).** O parâmetro é JSON: o escape virou
o caractere bidi literal no código-fonte (Trojan Source). O `ruff` pegou (`PLE2502`). Reincidi no
mesmo dia escrevendo o item no diário pelo terminal; pego pela varredura de caracteres de controle.

**2026-09-26 — terceira vez, escrevendo este catálogo.** Criei este arquivo pela ferramenta de
escrita e citei o escape no item acima: virou o caractere literal de novo, na linha que descreve o
erro. O que ela tem de novo: saber da armadilha não protegeu, porque o texto era **sobre** ela, não
um teste. A varredura antes do commit pegou (1 achado em 37 arquivos); trocado por script.

**2026-09-26 — `cat > arquivo` sem entrada (Sessão 4).** O comando esperou stdin e travou até o
timeout.

> **A ferramenta interpreta o que eu escrevo antes de o arquivo receber.**

**O antídoto, concreto:** nunca escrever uma sequência de escape Unicode em parâmetro de
ferramenta, nem em prosa; gerar por script (`chr(92)`); varredura de C0/C1/bidi em todo arquivo
alterado antes do commit, sempre, inclusive em commit só de documentação; nada de `cat >` para
criar arquivo.

### 6. Conserto que cobriu um ponto e não o vizinho

**2026-09-26 — `_executar` só no `.execute()` (Sessão 3b).** A falha da API também nasce ao montar
a requisição; o teste antigo de falha no `delete` pegou. `_executar` passou a receber a montagem.

**2026-09-20 — `fastmcp.md` fora do formato (Sessão 3).** Rodei o `ruff format` só nos `.py`; ele
também formata o Python dentro dos `.md`. Formatado na Sessão 4.

> **O que este conserto tornou falso, e onde mais a mesma falha nasce?** É a segunda passada de
> revisão.

**O antídoto, concreto:** na revisão, listar todos os pontos por onde a falha entra antes de
fechar; rodar os portões no repo inteiro, não só nos arquivos que eu lembro de ter tocado.
