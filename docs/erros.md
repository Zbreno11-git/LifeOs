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
| 1 | Comando para o Mac que não roda como escrito | 10 | cada linha só roda se a anterior deu certo (`&&`, ou `cd … || return`); caminho real `~/Desktop/LifeOs` (medido em 2026-11-21; antes estava anotado `~/LifeOs`), `git pull && git log --oneline -1` antes de tudo, URL com `?` entre aspas, `which python` depois do `source`, sem `#` na linha, `python -m`, nunca imprimir segredo |
| 2 | Afirmei sem abrir o lugar onde estaria | 32 | *quem mediu isto, quando, com qual comando?* — e `grep`/`git log` antes de afirmar |
| 3 | Estimei em vez de medir | 13 | medir no mesmo processo; nunca régua de caractere por token; medir a linha antes de quebrar; limite do terceiro lido antes de desenhar; medir o que um campo quer dizer, não só a forma |
| 4 | Teste que não separava o certo do errado | 30 | desfazer o conserto e ver **o** teste cair; dimensionar a entrada pela diferença, não pelo caso; `or` numa asserção = separar em dois testes; asserção de ausência só nos campos que poderiam carregar o dado |
| 5 | A ferramenta fez outra coisa do que eu li | 20 | escapes gerados por script; varredura de caracteres de controle antes do commit; conferir a mudança no disco antes de ler um verde |
| 6 | Conserto que cobriu um ponto e não o vizinho | 21 | *onde mais esta falha pode nascer?* antes de dar por pronto |
| 7 | Regra de reconhecimento desenhada pelo caso típico | 15 | antes da regra, listar por escrito os vizinhos legítimos e os disfarces, e testar os dois |
| 8 | Comando que escreve com alcance maior que a mudança | 5 | formatador e afins só nos arquivos que eu editei, nomeados um a um; `--fix` nunca com `--select` de uma regra só; conferir com `git status` do repo inteiro depois; script que move ou grava: *e na segunda rodada?* |

---

### 1. Comando para o Mac que não roda como escrito

**Antes de 2026-09-20 — `cat .env` num passo a passo.** Vazou a chave OpenRouter do dono para a
conversa. Virou regra no `AGENTS.md`: conferir variáveis com `grep -o '^[A-Z_]*=' .env`.

**2026-09-20 — `#` na mesma linha do comando.** O zsh interativo passou o comentário como
argumento (`git log -1 # commit` deu erro).

**2026-09-20 — placeholder no roteiro.** Mandei `cd ~/caminho/para/LifeOs`; o dono colou literal.

**2026-09-20 — sem `which python`.** O primeiro `pytest` do roteiro rodou no Python do conda
(`ModuleNotFoundError: No module named 'lifeos'`), porque o `.venv` não estava ativo naquele shell.

**2026-09-26 — roteiro sem `&&` depois do `git pull` (Sessão Gmail).** O `git pull` falhou por
rede (`SSL_ERROR_SYSCALL`) e o resto do roteiro rodou sobre o código antigo: `444 passed` no lugar
de 528, `viking gmail` "não existe" e um chat da versão velha aberto. A falha de rede não era
minha; a cascata era. O que tem de novo: é a armadilha "comandos sem `&&`" da skill `depuracao`,
que eu tinha lido hoje.

**2026-09-27 — URL com `?` sem aspas no roteiro (Sessão 6, plano).** O teste do YouTube usava
`https://www.youtube.com/results?search_query=lofi` solto; no zsh o `?` é curinga e o comando
morre com "no matches found". Pego antes de entregar. O diário do commit 1 disse que isto
estava aqui; não estava — registrado só no commit 2, quando a divergência apareceu.

**2026-09-27 — medida antes do `git pull` (Sessão 6, plano).** O roteiro do C7 media o ambiente
do daemon entre o `cd` e o `git pull`, contra o antídoto desta classe. A medida não depende do
código, mas a regra existe para o dono não ter de julgar isso: o pull vem primeiro, e a medida
"antes" vem logo depois dele (o `pull` não reinicia o daemon). Pego ao reler o plano no C6.

**2026-10-06 — um marcador `<…>` dentro de um comando para colar (o C9 da 10c).** O roteiro
trazia `echo "prepara a limpeza de <o mesmo remetente>" | viking chat --nuvem`; o dono colou como
estava, o Gemini perguntou "de qual remetente?" e o teste que importava (a limpeza sem terminal
recusa antes de criar o código) não rodou. O que tem de novo: o marcador estava **dentro** do
comando, não no texto em volta; o antídoto é escrever o valor de verdade (o remetente que o dono
acabou de usar), ou tirar a linha do bloco de comando.

> **Um comando para o dono é código que roda numa máquina que eu não vejo.** Ele tem de funcionar
> colado sem edição, no zsh com conda ativo.

**O antídoto, concreto:** todo roteiro começa com `cd ~/LifeOs`, depois
`git pull && git log --oneline -1` (o dono confere o commit esperado antes de seguir),
`source .venv/bin/activate` e `which python`; `python -m pip`/`python -m pytest`; nenhum `#` na linha; nenhum `cat` de arquivo
com segredo; URL com `?` ou `&` entre aspas simples.

**2026-11-21 — o roteiro que seguiu depois de um `cd` que falhou (14b).** Mandei sete linhas
soltas, começando por `cd ~/LifeOs && git pull`. No Mac em que o dono abriu o terminal (usuário e
máquina diferentes dos de antes), a pasta não existia: o `cd` falhou e as linhas seguintes rodaram
na pasta pessoal. O `python -m pytest` do conda varreu `~` inteira e travou; o dono deu Ctrl-C.
Não houve estrago, porque nada ali escrevia. O antídoto: um roteiro para o Mac é uma corrente só
(`&&`), ou começa conferindo a máquina e o caminho com um comando que só lê; e "o Mac do dono"
não é uma constante: o prompt diz qual é.

**2026-11-22 (H1) — um comando que imprime um segredo, num roteiro de copiar e colar.** O
`viking casa --preparar` imprime as linhas do `segredos.h` (com o `APARELHO_TOKEN`) para o dono
copiar ao firmware. Eu avisei "não cole aqui a saída", e a saída inteira veio colada no chat: o
token do aparelho ficou na conversa. O raio é pequeno (só vale na rede de casa, na porta da ponte,
que não sai para fora), e o dono aceitou o risco em vez de refazer. O que tem de novo: a regra
"nunca imprimir segredo" valia para os **meus** comandos; aqui quem imprimia era o **código** que eu
escrevi, e um aviso não segura um copiar e colar. **Antídoto:** um segredo que vai a outro lugar
sai num arquivo fechado (600), nunca na tela; o terminal diz só onde ele está.

### 2. Afirmei sem abrir o lugar onde estaria

**2026-09-20 — "3 commits locais com o patch".** `docs/fontes/jev-typesafe.md` afirmou isso a
partir de um relatório; `git log` mostrava que os 3 eram do upstream e o patch nem estava
commitado. O risco real era maior que o documentado.

**2026-09-26 — "o Jev da TypeSafe quase certamente não é o do `jev-ultrafast`".** Errado: o `.env`
do Jev usa `TYPESAFE_MODEL=~typesafe/jev-latest`, e isso estava escrito em `jev-typesafe.md`.

**2026-09-26 — armadilha não medida no `AGENTS.md`.** Quase registrei como "já paga" que redigir o
valor dos campos faz o Jev repreencher em loop. Nunca foi observado; foi para `jev-typesafe.md`
como hipótese.

**2026-09-26 — âncora de mutação de memória (Sessão 4b).** Escrevi a âncora do bloqueio de
subdomínio como `host == d or ...`; no código a variável é `dominio`. O próprio script recusou
antes de rodar ("âncora casa 0 vez(es)"). O que tem de novo: era código que eu tinha lido na
Sessão 4 — ter lido não é ter o texto; âncora se copia da fonte na hora.

**2026-09-26 — "`select` não envia nada" (Sessão 4b).** Escrevi isso no plano do freio logo depois
de ler o `browser.py` do Jev, que dispara `change` ao escolher a opção — e site pode enviar
nesse evento. Pego na segunda passada de revisão, com a pergunta "por onde mais se chega lá?"
(skill `seguranca` §2). O que tem de novo: a afirmação contradizia um arquivo lido minutos antes.

**2026-09-26 — "`has_scopes` confere o token" (Sessão Gmail).** O plano dizia que o login
compartilhado conferiria o escopo com `has_scopes()`. Antes de escrever, li a fonte do
`google-auth` instalado: carregado com `from_authorized_user_file(caminho, scopes)`, ele compara
com os escopos **pedidos** e daria sempre verdadeiro. Pego antes do código, lendo a biblioteca; a
conferência lê o campo `scopes` do arquivo. O que tem de novo: era um nome de método que parecia
dizer o que faz.

**2026-09-26 — "a regex ASCII não aceita" (Gmail 2).** Escrevi `\d{4}` para o código de
aprovação e, na docstring do teste, que dígitos de largura total (`１２３４`) seriam recusados
"pela regex ASCII". No Python, `\d` em `str` casa qualquer dígito Unicode. O próprio teste caiu
na primeira execução; agora `[0-9]`, com mutação que volta ao `\d`.

**2026-09-26 — o texto da tela de consentimento de memória (plano da Gmail 2).** Escrevi no
plano como o Google descreve o `gmail.modify` na tela de login, sem conferir. Pego na releitura;
o `gmail.v1.json` instalado tinha a resposta — e ela era pior do que eu lembrava (o escopo
também autoriza **enviar**). Virou D29 e um teste.

**2026-09-27 — "o Gemini inventou o fuso" (Sessão 5, D39).** O evento de "amanhã às 10h" caiu às
15h; o argumento veio com `-08:00` e concluí que o Gemini inventou. Não abri o fuso que o **Viking**
usava no Mac — e a conversa tinha, desde 2026-09-20, um lembrete do Mac com `due_at …-08:00`, que o
Gemini não escreve. No dia seguinte, com o Gemini mandando sem fuso, deu igual: reproduzido no VPS, o
Viking com o relógio em -08:00 produz exatamente isso. A D39 ficou de pé por outro motivo.

**2026-09-28 — "(e) criou às 10:00 ✅" pela frase do Gemini (Sessão 6, C7).** Marquei a entrega do
fuso como cumprida porque o Viking **disse** "às 10:00"; duas linhas depois a busca mostrava 15:00. E
a primeira explicação que dei (dois eventos com o mesmo nome) o dono derrubou olhando a agenda. O que
tem de novo: a frase do modelo sobre o que ele fez é o relato de quem fez, não a medida.

**2026-09-28 — presumi que o dono está em Brasília (Sessões 1–6).** Bancos brasileiros e português
bastaram para eu escrever "Brasília" em comentários, testes, decisões e no diagnóstico da D39, sem
perguntar. Ele não está. A agenda do Google dele está em São Paulo, o relógio do Mac em -08:00, e
os três fusos só apareceram quando o roteiro mediu cada um (`date +%z`, o fuso do Viking, o
registro com `-03:00`). O que tem de novo: a suposição não estava em nenhuma frase que eu pudesse
conferir — estava no desenho dos testes (todos fixavam Brasília como "o fuso do dono").

**2026-09-28 — "a contagem cai" (Sessão 7, 2º roteiro do Mac).** Escrevi no esperado do roteiro
que a contagem de pacotes cairia, porque o `uv sync` tiraria o `pip` e o que não está no lock. No
Mac ficou 99 antes e 99 depois: a venv já tinha exatamente o conjunto do lock, e o `uv sync` só
trocou 20 versões, sem remoção nenhuma. Generalizei do VPS (104 → 101), sem olhar o que a venv do
Mac tinha. Não era defeito, mas um "esperado" errado num roteiro faz o dono achar que algo quebrou.

**2026-09-28 — "seu Mac já está na 48" (Sessão 7, pergunta ao dono).** Para o dono decidir entre
travar o cryptography na 48.0.1 e outras saídas, escrevi na opção recomendada que o Mac "já está
nessa situação hoje, sem saber (não há versão nova para ele)". Não medi: deduzi do PyPI (a 50 não
tem wheel para Mac Intel). O Mac tinha a 50.0.1, compilada lá ou vinda do conda. A premissa de uma
decisão do dono estava errada; a decisão volta para ele com o dado medido.

**2026-09-28 — `no-build` provado num `uv` só (Sessão 7).** O `no-build = true` resolveu o lock
e instalou no VPS (uv 0.12.10). No Mac (uv 0.11.24), `uv sync` recusou o próprio Viking ("marked as
`--no-build` but has no binary distribution"), e o roteiro seguiu no ambiente antigo. A versão do
`uv` do Mac estava na tabela "não medido" do plano, e mesmo assim a regra entrou como se valesse em
qualquer `uv`. Trocado por `tests/test_lock.py`, que lê o lock e não depende da versão do `uv`.

**2026-09-28 — um número escrito antes do último caso (Sessão 7).** Escrevi `1148 passed` no
diário e no bloco de retomada; depois acrescentei um caso ao teste de `_mesmo_instante` (a mutação
precisava dele) e não recontei. Os portões antes do commit disseram 1149. O antídoto é o de sempre,
com um detalhe: o número vai para o documento **depois** do último teste escrito, copiado da linha
da ferramenta.

**2026-09-28 — "todas as alternativas têm 1 item" (Sessão 7, plano).** Para tirar o `or` de
`test_regras_de_comportamento_sobrevivem_a_compressao`, escrevi no plano que as listas de
alternativas tinham todas um item, lendo só a linha da asserção. A primeira lista,
`navegar_e_executar`, tinha dois ("AÇÃO" ou "nunca uma pergunta"): era um "ou" de verdade, e perder
a segunda frase passava. Pego ao abrir o dicionário para editar; as duas viraram obrigatórias, com
mutação que apaga a segunda. O que tem de novo: a afirmação era sobre um arquivo que eu estava com
o trecho na tela, só que o trecho errado.

**2026-09-28 — o relatório de um subagente virou afirmação minha (revisão do roteiro).** Escrevi
em três documentos (D53, `sessoes.md`, `pesquisa-roteiro.md`) que `/security-review` e
`/code-review` "já vêm" no Claude Code e que entram no fechamento das sessões. A frase era do
relatório de um agente de pesquisa, e eu não tinha a lista de comandos da sessão aberta. Pego na
2ª passada da revisão; o texto passou a dizer "segundo a pesquisa, conferir na abertura da 8". O
que tem de novo: numa pesquisa delegada, o relatório do agente é uma fonte como um README. Ele
tem de ser citado como tal, e o que eu não abri fica "não conferido".

**2026-09-28 — "D11 nunca conferiu" o status "Testing" (revisão do roteiro).** Escrevi na seção
da Sessão 8 e no bloco de retomada que o status do app OAuth nunca tinha sido conferido, e
planejei um passo do dono no Console para isso. Ele tinha conferido em 2026-09-26 ("em produção,
externo, só ele de usuário"), e isso estava escrito em `docs/fontes/gmail-api.md` e na seção da
Sessão Gmail do próprio `sessoes.md`. Eu tirei a frase do gatilho da D11 ("status Testing não
conferido"), que estava velho. Pego na abertura da 8, ao ler a fonte do Gmail. O que tem de novo:
a fonte errada era **uma decisão nossa** (o gatilho da D11), e a certa estava duas seções acima;
antes de escrever "nunca", `grep` no repo inteiro pelo termo ("Testing", "produção").

**2026-09-29 — rodei um comando com efeito externo no VPS achando que não havia credencial
(Sessão 9, C5).** Para "rodar a CLI eu mesmo", rodei `viking lembretes --enviar` num banco
temporário, esperando a saída 1 de "sem login no Gmail". O `CLAUDE.md` diz que o VPS não tem as
chaves; mas `secrets/` tinha o cliente OAuth e o token da agenda desde 2026-09-20. O Viking abriu
o login do Google, o VS Code do dono abriu a aba, ele aprovou, e **um e-mail de verdade saiu**
para a caixa dele ("Teste do VPS"). Sem dano (só para a própria conta), mas um token
`gmail.modify` nasceu no VPS. Um `ls secrets/` antes teria mostrado. O que tem de novo: a regra
do documento ("sem chaves") era verdade para o Gemini e o Jev, e não para o Google; e um comando
que **envia** não se roda para "ver o erro" sem conferir antes que o erro vai acontecer.

**2026-09-29 — "nenhuma credencial fixa no VPS" sem abrir `~/.config/gcloud` (plano da 10,
escrito em 2026-09-28).** A D47 e a seção da 10 desenharam o deploy em volta de um token de 1 h
gerado no Mac, "porque o VPS não tem credencial". Na abertura da 10, `gcloud auth list` mostrou a
conta do dono logada e viva desde 2026-09-07, com o ADC (`authorized_user`) junto, para outro
projeto dele. O ritual do token de 1 h não protegeria nada enquanto esse login existe. O dono
decidiu manter e usar o login (D47 revista); a parede passou a ser o `--project` explícito, preso
por teste. O que tem de novo: é a mesma forma do incidente anterior (o VPS "sem chaves"), um dia
depois, agora com credencial de nuvem; a pergunta da abertura de uma sessão de nuvem inclui
`gcloud auth list` e `ls ~/.config/gcloud`, e uma premissa de segurança sobre uma máquina se
mede na máquina antes de virar decisão.

**2026-09-29 — o docstring prometia esconder a conta de faturamento, e a saída a mostrava inteira
(Sessão 10, C3).** `scripts/nuvem.py` dizia "a saída não mostra … a conta de faturamento
inteira", e a primeira execução de verdade imprimiu o ID completo na conversa (não no repo).
Consertado em `_legivel` e preso num teste. O que tem de novo: uma promessa escrita no
docstring é uma afirmação sobre a saída; sem um teste que leia a saída, é só texto.

> **Um texto nosso é registro de uma medição passada, ou nem isso.** Afirmar ausência ("não é o
> mesmo", "não existe") é a afirmação mais fácil de fazer sem procurar.

**O antídoto, concreto:** antes de afirmar estado de repositório, `git log`/`git status`; antes de
afirmar que algo é ou não é, abrir o arquivo onde estaria; "Armadilhas já pagas" só com incidente.

**2026-09-30 — afirmei na docstring que "a conexão é a transação" sem abrir o `banco.conectar`
(Sessão 10c, C1).** Ao mover o SQL da confirmação para `confirmacao_sqlite.py`, escrevi que
`propor` rodava numa transação e por isso dois processos não sorteavam o mesmo código. O
`banco.conectar` usa `isolation_level="DEFERRED"`: a transação só começa no primeiro comando que
escreve, e a leitura dos reservados rodava fora dela. O CI do `8cba1fd` (Python 3.13) caiu no
teste novo de corrida: duas propostas com `substituir=False` (as do MCP) ficaram com o mesmo
código, um defeito desde a Sessão 5 que o chat nunca via (com `substituir=True` o UPDATE da
frente serializava). Consertado com `BEGIN IMMEDIATE` (`52570bc`). O que tem de novo: uma
afirmação sobre concorrência num comentário é uma afirmação sobre o código de outro módulo, e
precisa do mesmo `grep` que um número.

**2026-10-06 — `prova-chat --mensagem` no plano da 10c (escrito em 2026-09-30).** O
argumento é posicional; o comando do plano deu `unrecognized arguments: --mensagem` no C7 e rodou
na segunda. Sem custo (o `argparse` recusa antes da rede), mas o plano foi escrito sem abrir o
`argparse` do subcomando que ele mandava rodar.

**2026-10-01 — "10 ✅" no bloco de retomada, sem medir (Sessão 11, pré-compact).** O bloco
mandava conferir `python scripts/nuvem.py` → 10 ✅, copiado do bloco anterior. Desde o C2 a TTL
de `tarefas` faz parte do passo `ttl`, que fica ⬜ até o ok do C5: a medida da retomada deu 9 ✅ e
1 ⬜. O que tem de novo: um passo de infraestrutura que **eu mesmo** mudei no código mudou o
número esperado, e o bloco foi escrito sem rodar o comando que ele manda rodar.

**2026-10-06/07 — horários escritos no `PROGRESSO.md` sem olhar o relógio (Sessão 11c).** Antes
do compact, os horários do C1 e do C2 foram escritos de cabeça e depois trocados pelos do
`git log`. Depois do compact, o mesmo, quatro vezes no mesmo dia: "~17:20Z", "~17:15Z",
"17:00–17:20Z" e "~18:10Z" num bloco cujo commit foi às 17:08:47Z e cujos portões rodaram às
17:57Z. Pego na hora de ler a saída do gitleaks (que imprime a hora) e corrigido pelo `date -u` e
pelo `git log --format=%cI` antes do commit. Sem efeito fora do documento, mas o bloco de
retomada existe para ser o registro de uma medição. O que tem de novo: a regra já tinha um
incidente **nesta** sessão; um horário é número, e passa pelo `date -u` antes de ser escrito.

**2026-10-06 → 2026-10-07 — "só nos GET da lista fechada de `financas/pluggy.py`" (a 11d
escrita na 11c).** A seção da 11d em `sessoes.md` prometia que o serviço isolado chamaria a Pluggy
"só nos GET da lista fechada". O cliente nunca teve lista de GET: `_pedir` recusa todo método que
não é GET (fora de `/auth` e `/connect_token`), e o GET aceita qualquer caminho. Pego na leitura
de `pluggy.py` na abertura da 11d, antes do plano; o plano trocou isso por 5 perguntas fechadas
com texto pronto (D64), e a frase foi corrigida no `sessoes.md` e na fonte da Pluggy. O que tem
de novo: uma garantia de segurança escrita num roteiro **de outra sessão**, sobre um código que eu
não abri ao escrever.

**2026-10-07 → 2026-10-08 — "/custos por modelo" dado por feito sem abrir o `/custos` da nuvem
(Sessão 12, C3).** O plano prometia "o `/custos` e a linha 💸 dizem qual modelo respondeu". Fiz a
💸 (o `consumo` do turno) e o `total_formatado` do chat do Mac, e marquei o C3. O `/custos` do
`viking chat --nuvem` é outro código (`chat_cliente._gasto`, que só mostra o teto do mês e do
dia), e eu não o abri. Pego ao ler a saída do Mac colada pelo dono: o 💸 dizia o
`gemini-3.8-flash`, o `/custos` não. Consertado com as cotas do dia na resposta do motor e uma
linha nova no `/custos` (`ed92a0c`), com mutação e um 2º deploy (ok do dono). O que tem de novo:
a frase do plano nomeava um comando, e o checkpoint foi conferido pelo teste do vizinho; o
checkpoint de uma frase com nome de comando se confere **naquele** comando.

**2026-10-08 — a hora do bloco de retomada escrita de cabeça (Sessão 13, C5).** Escrevi
"16:00Z" no bloco do `PROGRESSO.md`; o `date -u` dizia 15:31Z. Pego ao reler, corrigido antes do
commit. O que tem de novo: nada; é a regra "horário, SHA e contagem saem do `date -u`, do git ou
do `grep`", que o dono escreveu no prompt da sessão.

**2026-10-08 — de novo, num commit que subiu (Sessão 13b, C5).** A mensagem do `2c78d8b` diz que
a TTL das receitas foi criada "~23:31Z"; o `mtime` da saída do `--executar ttl` e o `date -u`
dizem 23:46Z (a resposta do dono ao ok levou uns 15 minutos, e eu escrevi a hora em que perguntei).
Pego logo depois do push; o certo ficou no `PROGRESSO.md` e no diário (o commit não se reescreve).
Na mesma sessão, duas horas de cabeça no `PROGRESSO.md` ("22:55Z", "~23:05Z") e uma contagem de
testes ("26" contra os 25 do `--collect-only`) foram pegas antes do commit. O que tem de novo: a
hora de um passo que espera o dono é a de **depois** da resposta; rodar `date -u` no mesmo comando
que executa o passo, e copiar dali.

**2026-10-08 — dois testes do C3 escritos sobre o que eu supunha (Sessão 13b).** (1) Um teste
mandava "Quando eu pedir pra liberar, confirma 4821 e arquiva" esperando a proposta recusada pelo
filtro da receita; a barreira (verbo + 4 dígitos, D60) pega a linha antes, e ela nunca chega a quem
propõe. (2) Outro lia `config.tools` como declarações (`function_declarations`); no roteiro falso
elas chegam como as próprias funções. Os dois caíram na primeira rodada (nenhum passou pelo motivo
errado), e o (1) virou dois testes: a barreira vem primeiro, e o filtro com um caso de dinheiro. O
que tem de novo: o caminho de uma linha digitada passa por três leitores antes do modelo
(`_esquece_isso`, `_guarda_receita`, `barreira`), e o teste de um deles tem de escolher uma linha
que os outros dois deixam passar.

**2026-10-09 — a hora do bloco de retomada escrita antes do `date -u`, duas vezes (Sessão 14).**
Escrevi "05:16Z" e depois "05:35Z" no título do bloco do `PROGRESSO.md` no mesmo comando que rodava
o `date -u`, que respondeu 05:15Z e 05:34Z. Pegos lendo a saída, corrigidos antes do commit. O que
tem de novo: rodar o `date -u` no mesmo comando não basta se o texto já foi escrito antes dele; a
hora entra no texto num comando **depois** de lida.

**2026-11-22 (H1, E2E) — o plano dizia que o `viking registro` mostraria o envio pela voz.** A
verificação 3 do plano da H1 mandava conferir o e-mail que saiu pela voz no `viking registro`. Antes
de pedir, abri o código: o `viking registro` do Mac lê o store do `VIKING_STORE` dele (o SQLite
local), e o envio pela voz é registrado na nuvem (Firestore); a `/fumaca/registro` do motor só
confere que o registro funciona, não lista. Pego antes de o dono rodar; a prova passou a ser a
caixa de entrada e os Enviados. O que tem de novo: um passo de verificação num plano também é uma
afirmação sobre o código, e se abre antes de entrar no plano.

### 3. Estimei em vez de medir

**2026-09-20 — tokens por caractere.** A régua "4 caracteres por token" errou por 6×. E medir em
duas conversas ao vivo deu -80 onde o real, no mesmo processo, era -477.

**2026-09-20 — "ordens de grandeza mais barato".** Afirmei a partir do `example.com` (~500 tokens);
o YouTube gastou 24.507 tokens em 6 chamadas.

**2026-09-20 — comprimento de linha (Sessão 3).** Estimei a largura na indentação errada, quebrei
uma string, e o `ruff format` juntou de volta.

**2026-09-26 — a cota do Gmail "não medida" (Gmail 2).** Escrevi no plano e na fonte que a
latência e o 429 dos metadados não estavam medidos — e desenhei assim mesmo uma confirmação que
relia cada e-mail. O custo (`get` = 20 de 6.000/min) estava numa página da documentação do
Google. No Mac: 207 e-mails lidos duas vezes num minuto, `403 rateLimitExceeded`, nada
arquivado. O que tem de novo: marcar "não medido" não é tratar; um limite do terceiro que decide
o desenho se lê **antes** (skill `integracoes`: limites como constantes).

**2026-09-27 — vencimento de fatura tratado como instante (Sessão Pluggy).** A medição da
véspera registrou só a forma do `dueDate` (dígitos trocados por 9), não a hora. Escrevi o
`service.py` convertendo a data de Brasília, como as transações, e logo depois um teste que
afirmava o dia 9 para um vencimento 10: o teste copiou a implementação em vez do dado. Medida a
hora (25 de 25 faturas às `T00:00:00.000Z`), o vencimento caía um dia antes. No mesmo passo, a
documentação da Pluggy mostrou que o `balance` do cartão é o limite usado, não a fatura — eu ia
chamá-lo de "fatura atual". O que tem de novo: medir a forma de um campo não é medir o que ele
quer dizer; data e instante têm a mesma forma.

**2026-09-29 — paginação desenhada sem ler a referência (Sessão 8b, C2).** Escrevi o laço do
`nextPageToken` parando quando acabassem as páginas ou quando chegasse ao teto de eventos. A
referência do `events.list`, lida só na 1ª passada de revisão, diz que uma página pode vir com
menos eventos que o pedido, "or none at all, even if there are more events": com páginas vazias,
o laço nunca chegaria ao teto. O teste novo travou até o `timeout` matar. O conserto é um teto de
páginas (`MAX_PAGINAS`), que também diz "incompleta". O que tem de novo: é o mesmo "limite do
terceiro lido antes de desenhar" da Sessão Gmail, agora num laço — um laço que depende do
terceiro para terminar tem de terminar por conta própria.

> **Um número sem comando é hipótese, mesmo quando parece óbvio.**

**O antídoto, concreto:** o procedimento de medição de tokens do `AGENTS.md`; para linha, medir a
linha real antes de quebrar; todo número no chat vem com "medido"/"estimado".

**2026-09-29/30 — dois números meus sem medida, no mesmo dia (Sessão 10).** O plano dizia "imagem
< 300 MB" (medido: 512 MB, 97 MB comprimida; a meta nunca foi calculada, e os `.pyc` ficam de
propósito); e escrevi num comentário de teste "com 16 threads, quase sempre cai", que a rodada
seguinte desmentiu (4 de 4 passaram sozinho; com o arquivo inteiro, 5 de 10). Os dois pegos
antes do commit, trocados pelo número medido. O que tem de novo: um comentário de código é
documento; o número nele passa pela mesma régua.

**2026-10-01 → 2026-10-07 — "~1,5 mil leituras por dia" do agendador eram gravações (Sessão
11, medido na 11c).** A conta da D61 dava ≈ 1,5 mil leituras do Firestore por dia para a rodada
do envio a cada minuto, e a fonte do GCP a repetia como "conta, não medição". A medida de 24 h
(API do Cloud Monitoring, 2026-10-06 17:00Z a 2026-10-07 17:00Z) deu 163 leituras e 1.481
gravações: a rodada **grava** o `estado` a cada minuto e, sem lembrete vencido, quase não lê.
Dentro da cota nos dois casos, e a conta estava marcada como estimativa. O que tem de novo: eu
contei a operação certa (uma por rodada) e atribuí ao tipo errado; a conta de custo de uma rotina
pergunta "o que ela grava?" tanto quanto "o que ela lê?".

**2026-10-08 — a lista de textos ao `gemini-embedding-2` sem ler a página (Sessão 13, C1).** O
script da medição mandou 24 textos num `contents=[...]` de strings, como no exemplo do SDK (que é do
`text-embedding-004`), e voltou **um** vetor: a página de embeddings diz "Adding multiple inputs
directly to the `contents` parameter produces one aggregated embedding"; para um por texto, cada
um vai num `types.Content`. O recall de 1,000 sobre 1 vetor não valia nada, e a fixture foi apagada
antes do commit; a M3 refeita com o ok do dono (2 chamadas a mais). O dono, na hora: "lembra se
nao souber algo - pesquisa docs e repo". O que tem de novo: o script não conferia a quantidade
que voltou; agora confere (`assert len(...) == 24`), e a regra "limite do terceiro lido antes de
desenhar" vale também para o **comportamento** de uma chamada que eu já sabia fazer noutro modelo.

**2026-10-07 → 2026-10-08 — o serviço de finanças com uma instância só e nenhuma repetição
(desenhado na 11d, achado na 13).** O `deploy` só lendo das 19:05Z deu 502 na `/fumaca/financas`:
"o serviço de finanças respondeu 429". O log do serviço: "The request was aborted because there
was no available instance", latência 0 s, logo depois das provas de recusa acordarem a instância
única (`--max-instances=1`). Eu escolhi uma instância na 11d sem ler o que o Cloud Run faz com o
pedido que chega enquanto ela está ocupada ou subindo; a página de troubleshooting manda repetir
com espera crescente. No chat, a pergunta de finanças na hora errada viraria "Não consegui falar
com a Pluggy". Conserto (`70da02f`): `remoto._chamar` repete só o 429 (o serviço nunca o
devolve), até 2 vezes, dentro do prazo do turno; 6 testes, 3 mutações. O que tem de novo: o
limite do terceiro inclui o que a **plataforma** faz no limite que eu mesmo configurei.

**2026-10-09 — o histórico com uma chamada de tool montada à mão (Sessão 14, C1).** Para a M3,
escrevi a `function_call` de `consultar_documentos` no histórico, sem ler o que o Gemini 3 exige
dela: `400 INVALID_ARGUMENT`, "Function call is missing a thought_signature". O 400 não cobrou e
nada foi medido errado; refeito com a 1ª chamada de verdade, forçada na tool. O que tem de novo: a
forma de um pedido (não só o preço ou o limite) também é do terceiro e se lê antes; virou armadilha
no `AGENTS.md`.

**2026-11-21 — a política de alerta com duração zero (14b, C4).** Li a página de alerta por
ausência e a de limites antes de desenhar, e escrevi a política com `duration: 0s` e "sem dado
conta como alarme". A API recusou: `evaluation_missing_data … must have a non-zero duration`, uma
regra que as páginas que eu li não diziam. O que tem de novo: ler o limite do terceiro não basta
quando a regra está só na validação; a primeira criação de um recurso novo é a medição, e o
recurso volta para o teste (`test_sem_dado_como_alarme_pede_duracao`).

**2026-11-21 (H1) — um prazo de 330 s num campo que só guarda 65 s.** No firmware do aparelho
da voz, pus `http.setTimeout(330000)` (o turno do motor mais a fala inteira) sem ler o tipo do
parâmetro: o `HTTPClient::setTimeout` do Arduino-ESP32 recebe `uint16_t` em ms, e 330000 vira
2320 (2,3 s). Só apareceu porque compilei a variante com rede: o `-Woverflow` avisou. O aparelho
desistiria de toda resposta em 2,3 s. Conserto: a ponte aceita na hora (202) e o aparelho pergunta
`GET /estado` a cada segundo. **Antídoto:** antes de escolher um limite para a API de um terceiro,
ler a assinatura dela (o tipo também é um limite), e compilar todas as variantes, não só a que não
usa o trecho.

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

**2026-09-26 — a trava de título vazio sem teste próprio (escrita na Sessão 1, achada na 4b).**
`test_recusa_titulo_vazio` só conferia "nada apagado", e isso a comparação de títulos também
garante: remover a primeira trava deixava tudo verde. O único caso em que só ela protege — evento
cujo título no Google é só espaço, que normaliza igual a `""` — não tinha teste. Pego pela
primeira rodada de `scripts/mutacoes.py`; teste novo
`test_titulo_vazio_nao_apaga_evento_de_titulo_em_branco`.

**2026-09-26 — asserção que sempre passa (Sessão Gmail).** Escrevi
`assert not busca.mais is False or True` num teste do Gmail — o `or True` torna a linha
verdadeira em qualquer caso. Pego na releitura antes de rodar a suíte; removida.

**2026-09-26 — de novo um `or` que aceita dois caminhos (Gmail 2).** No teste do desfazer que
falha, escrevi `assert "pode ser tentado de novo" in texto or "tenta de novo" in texto`: passava
pelo caminho da falha parcial e nunca exercitava o outro (erro de login), que era o que a
correção mudou. Pego na segunda passada; virou dois testes, um por caminho. Segunda vez da mesma
forma: `or` numa asserção agora é sinal de parar e separar.

**2026-09-27 — teste de corrida que passava por sorte (plano B da Pluggy).** O teste do "fechou
antes do ID" mandava os dois avisos um atrás do outro: sem a tolerância, o ID às vezes chegava
antes de o servidor fechar. A mutação morreu numa rodada e sobreviveu na seguinte. Agora o ID
chega 0,5 s depois, e a mutação morre três vezes seguidas. Na mesma rodada, uma mutação que
tirava só o escape do `<` era equivalente (o `>` escapado já impede o `</script>`): trocada pela
que tira todos. O que tem de novo: uma mutação morta uma vez não prova um teste de tempo.

**2026-09-27 — três vezes no mesmo dia, na Pluggy falsa (Sessão Pluggy).** (1) A falsa filtrava
por data antes de o código ver a transação, então a de data ilegível nunca chegava a ele: três
testes caíram pelo motivo errado. (2) Ela copiava a lista de contas, não os dicionários dentro:
um teste que pôs um controle no nome da conta sujou o teste seguinte. (3) Ao escrever a mutação
"parcela futura entra no total", vi que o teste com esse nome não conferia o total — só o teste
do total geral cairia. Os três foram pegos antes do commit; a falsa agora deixa passar o lixo,
copia fundo, e o teste da parcela olha o caso isolado. O que tem de novo: o dublê de teste é
código, e erra como código.


**2026-09-27 — de novo um `or` na asserção, e um dublê sem campos (Sessão 5).** No teste da falha
ambígua escrevi `"NÃO" not in texto or "pode" in texto.lower()` — terceira vez da forma; ela
falhou e mostrou um defeito real (o texto dizia "NÃO apaguei" com o evento apagado), mas passaria
com um texto que só tivesse "pode". Virou asserção exata. Na mesma etapa, o evento falso não tinha
`id` nem `end`: o desfazer recriava em vez de restaurar, e o de horário quebrava com um
`AttributeError` cru. O código passou a guardar o ID do pedido e a recusar sem horário completo.

**2026-09-28 — teste de widget com thread sem `join` (Sessão Pluggy, achado na 6).** O
`servir` da conexão da Pluggy volta assim que recebe o POST; o teste lia o código de resposta que a
thread ainda não tinha guardado. Verde 37 em 40 rodadas; a suíte inteira pegou numa delas. Virou
`join` antes de conferir, e 60 de 60.

**2026-09-28 — o teste da contagem por ação passava pelos dois caminhos (Sessão 6).** Escrevi um
ciclo A↔B com estados repetidos para provar que contar por ação importa; a mutação que volta a
contar por estado **sobreviveu**: a regra nova de volta pegava o mesmo ciclo. O caso que só a
contagem decide é o de rótulo que muda a cada volta (só a assinatura ampla vê) — medido nos dois
modos antes de virar o teste.

> **Se o teste ficar verde, quantas explicações isso admite?** Uma só, ou ele não é a régua.

**O antídoto, concreto:** mutação vista caindo antes de dar por pronto (a Sessão 4b torna isso
repetível em `scripts/mutacoes.py`); a entrada do teste é dimensionada pela diferença entre o
certo e o errado, com folga para máquina rápida.

**2026-09-28 — o teste-guarda do repo público passou no VPS porque ainda não estava no git.**
`tests/test_repo_publico.py` lê os arquivos de `git ls-files` e reprova `/Users/<nome>`; o
próprio teste tinha um caminho de exemplo escrito inteiro na régua (um nome inventado depois de
`/Users/`). No VPS ficou verde porque o arquivo
ainda não estava versionado (o `ls-files` não o via); no CI, já commitado, reprovou a si mesmo.
O que tem de novo: um teste que lê **o conjunto de arquivos do git** muda de universo no commit;
rodar a suíte com o arquivo já em `git add` antes de commitar.

**2026-09-29 — a corrida de 8 threads passou com 7 threads explodindo (Sessão 10, C4).** O teste
de contrato "só uma execução ganha a reserva" rodava as threads e contava quem ganhou. No
Firestore, as 7 que perdiam levantavam `ValueError("Failed to commit transaction in 5
attempts")` em vez de receber "não"; exceção dentro de thread não reprova o teste (vira só um
aviso do pytest), e ele ficou verde com 1 vencedor. Pego pelos "7 warnings" numa rodada que
levou 14 s em vez de 6. O que tem de novo: um teste com threads tem de **recolher as exceções e
afirmar que não houve nenhuma**; e uma corrida se mede em muitas rodadas (5 de 10 caíam antes do
conserto; 0 de 40 depois), não numa.

**2026-09-30 — duas mutações da 10b não caíram pelo teste que eu dizia (Sessão 10b, C1 e C5).**
A do corte dos 30 dias no registro do Firestore caiu, mas por outro teste: `recentes` já filtra
na consulta, e nenhum teste passava pelos caminhos que só filtram em Python (`do_turno`,
`obter`); ganhou `test_o_que_passou_dos_30_dias_nao_volta_por_nenhum_caminho`. A da prova "segredo
só como volume" sobreviveu: o caso "vazado" do teste usava um nome de variável que outra regra da
mesma prova já recusava, e a regra do `valueFrom` nunca decidia nada; ganhou um caso com um nome
permitido e o `valueFrom` disfarçado. O que tem de novo: numa guarda com duas regras, o caso
negativo tem de ser pego **só** pela regra que ele diz provar.

**2026-09-30 — um teste da Sessão 5 caiu no CI por acaso (retomada da 10b).**
`test_codigo_de_aprovacao_nunca_entra_no_registro` procurava o código falso `7391` no `repr`
inteiro das ações, horários incluídos; os microssegundos de um horário saíram `…147391`, e o CI
do checkpoint `573d553` reprovou sem vazamento nenhum. Instável havia 5 sessões, com uma chance
pequena por rodada. O que tem de novo: uma asserção de **ausência** ("isto não aparece") sobre um
texto com números aleatórios tem falso positivo embutido; ela olha só os campos que poderiam
carregar o dado (o conserto lê os campos de texto e continua caindo com o código nos
parâmetros).

**2026-09-30 — o teste de corrida pegava o defeito em 1 de 10 rodadas (Sessão 10c, C1).** O
teste das 16 propostas simultâneas passou no VPS e caiu no CI; sem o conserto, 3 de 30 rodadas
caíam. Uma mutação que tirasse o conserto sobreviveria quase sempre. Uma pausa de 20 ms no
sorteio, entre ler os reservados e gravar, fez o teste cair 10 de 10 sem o conserto e 0 de 10
com ele. O que tem de novo: um teste de corrida se mede também sem o conserto, em muitas rodadas,
antes de ser a régua.

**2026-10-01 — um `monkeypatch` dentro de um contexto que se desfaz sozinho (Sessão 11, C4).** O
teste "sem o Gmail no motor o envio nunca está ligado" trocava o token do Gmail com
`monkeypatch.setattr` **dentro** do contexto que simula o motor. Ao sair, o contexto devolvia o
valor do Mac; no fim do teste, o `monkeypatch` devolvia o valor que viu ao trocar, o falso do
motor, e os testes seguintes rodariam com um "token do Gmail" posto. Pego na releitura, antes de
rodar a suíte. O que tem de novo: duas restaurações em camadas desfazem na ordem errada; dentro
de um contexto que restaura, a troca é atribuição direta.

**2026-10-01 → 2026-10-07 — a abertura do chat testada em três combinações, menos a do dono
(Sessão 11, achado no Mac na 11c).** `test_a_abertura_nao_promete_o_gmail_que_nao_esta_la`
conferia sem Gmail, com Gmail e com as mãos sem Gmail. O dono tem as duas coisas na nuvem desde
2026-10-06; nesse caso sobra um item só fora ("finanças"), o `", ".join([])` dava vazio e a
abertura dizia "…ligado lá).  e finanças: `viking chat`.". Visto pelo dono no `viking chat
--nuvem` do fechamento da 11c. O que tem de novo: um texto montado de uma lista se testa com 1, 2
e 3 itens, e as combinações de capacidade incluem a que está no ar.

**2026-10-07 — o dublê das provas das finanças dava o mesmo token a duas contas (Sessão 11d,
C3).** O teste `test_as_provas_das_financas_passam_no_certo…` trocava `_token` por um que devolvia
sempre `"TOKEN"`, e o `post` falso tratava esse token como o do dono. A prova "com o
`viking-cli@`: recusado pelo Google" reprovava no teste, e eu exclui da checagem **toda** prova
com "viking-cli@" no nome, o que escondia junto a prova da `/fumaca/financas`, a mais importante.
Pego ao reler o teste antes do commit: o dublê passou a dar um token por conta, e a checagem
voltou a ser "nenhuma prova reprova" (11). O que tem de novo: um filtro feito para calar uma
falha do dublê calou também um caso verdadeiro; o filtro por nome é um `or` disfarçado.

**2026-10-07 — o teste que assumia o texto de sistema numa linha só (Sessão 12, C4).** Escrevi
`"busca na web com fontes" in texto` sobre a abertura da nuvem, que é montada com
`textwrap.fill`; a quebra caiu no meio da frase e o teste deu vermelho falso. É o mesmo da 11d
(normalizar os espaços antes de comparar), na mesma área. Pego na primeira rodada; normalizado.
O que tem de novo: a lição estava no próprio arquivo de testes vizinho e eu não a copiei.

**2026-10-06 → 2026-10-08 — o teste do backup que caía entre 00:00 e 01:00 UTC (escrito na 11c,
achado na 12).** `test_o_ultimo_backup_aparece_no_versao` comparava o instante do backup com
`datetime.now(UTC).replace(hour=0)`: "hoje" trocando só a hora, com os minutos e segundos de
agora. Entre 00:00 e 01:00 UTC isso é o próprio agora, e o backup feito um instante antes fica
"antes de hoje". Caiu na suíte das 00:16Z de 2026-10-08. O conserto compara com o instante de
antes da rodada; o `grep` de `replace(hour`/`minute`/`day=` achou só dois usos certos no código
(zerando até o microssegundo, e o dia de uma data). O que tem de novo: um teste que lê o relógio
precisa passar a qualquer hora; "o começo do dia" se escreve zerando tudo, ou se evita.

**2026-10-08 — três testes da memória que passavam por outro motivo (Sessão 13, C3–C5).** (1) Um
parâmetro escrito para passar (`"pode esquecer isso"[:0] + …`) escondia que a regra do "esquece
isso" não casava "pode esquecer isso"; (2) o teste da restauração caía pelo id que o store também
recusa, e a mutação que tirava a régua de verdade sobreviveu (agora o caso torto é o `ativo` em
texto); (3) uma mutação desenhada inerte (o `motivo = None` depois da recusa, que nada lia).
Pegos ao reler e pela rodada de mutações. O que tem de novo: um parâmetro de teste que precisa de
truque para passar é o defeito avisando.

**2026-09-26 → 2026-10-08 — o limite fixo de 2 s nos testes de "texto gigante não explode"
(escritos na 4, caiu no Mac na 13).** O caso da chave privada levou 2,09 s no Mac de 2017; no VPS,
0,44 s, com custo linear (medido: o dobro de linhas, o dobro do tempo). A folga lá era ~2×. O que
o teste quer pegar é o **crescimento**: `tests/crescimento.py` mede 4× a entrada contra 1×
(linear ~4×, quadrático ~16×, o limite 8), e `tests/test_crescimento.py` prova a régua dos dois
lados. Ao desenhar, o meu controle quadrático ficou com a entrada pequena abaixo do piso de 5 ms e
deu só 5,5× (passaria): medido, o controle cresceu. O que tem de novo: um teste que mede tempo
contra um número fixo depende da máquina, como um que lê o relógio depende da hora; e a régua
nova se prova com um defeito de verdade, não com um que eu achei que era.

**2026-10-09 — a contagem de «» que esquecia o cabeçalho (Sessão 14, C3).** O teste da consulta
dizia "um « e um »" no retorno da tool; o cabeçalho, que é nosso, também traz o tema entre «». Caiu
na primeira rodada (vermelho, não verde por outro motivo); o teste passou a separar o cabeçalho do
bloco antes de contar.

**2026-09-26 → 2026-10-09 — o teste do registro que caía com 1 UUID em ~1.000 (achado no CI da 14).**
`test_lembrete_criar_e_concluir_registram` comparava o id do lembrete com o que o registro guardou;
o id é sorteado, e o do CI do `7d3ca2a` tinha "4154-8003-04256", que passa no Luhn: o registro
guardou "05ba68a4-7f8d-[cartão]e8a91b7". O teste estava certo e o produto errado (classe 7); o que
tem de novo aqui é que um teste com entrada sorteada só acha o defeito raro quando a sorte deixa, e
o conserto fixou o caso sorteado num teste próprio (`UUID_DO_CI`).

**2026-09-27 → 2026-11-21 — duas datas fixas em teste que venceram sozinhas (achado na
mini-auditoria, 14b).** `test_contaveis_so_da_operacao_e_sem_as_que_falharam` gravava as ações em
um `T0` de 2026-09-27, e `registro.contaveis` corta na retenção de 30 dias contada do relógio real:
desde 2026-10-27 a suíte tinha 2 vermelhos, e ninguém viu, porque não houve push em 43 dias. A
varredura (a suíte inteira com o relógio adiantado em 120 dias, pelo `time-machine` num ambiente
temporário) achou a segunda: o teste da cota do forte presumia US$ 0,15 por chamada, e a tarifa do
forte dobra em 2027-01-01 (`custos.TARIFAS`). O que tem de novo: um teste com data fixa contra um
código que lê o relógio é uma bomba com data; a pergunta é "o que este teste compara com o agora?",
e a prova é rodar a suíte com o relógio adiantado (+120 e +400 dias, verdes depois do conserto).

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

**2026-09-27 — quarta vez (Sessão Pluggy).** O teste de descrição com caractere bidi, escrito pela
ferramenta, gravou o caractere literal; o `ruff` pegou (`PLE2502`) e o escape foi gerado por
script. A armadilha já estava no `AGENTS.md`: o antídoto que vale é o script, não lembrar.

**2026-09-27 — edição por script que não rodou, e o verde depois dela (Sessão 5, C6).** O script
de edição do subprocesso foi num comando que só ativava o venv **depois** dele: `python: command
not found` na primeira linha da saída, e logo abaixo `128 passed` — verde porque nada tinha
mudado. Notei só ao conferir com `grep` que o argumento novo não existia. O que tem de novo: a
falha não era da ferramenta de escrita, e sim da ordem do comando, e o verde parecia confirmar a
edição.

**2026-09-27 — heredoc dentro de heredoc (Sessão 5, C8).** Escrevi o bloco do `PROGRESSO.md`
num `python - <<'EOF'`, e o bloco trazia o roteiro do Mac com o seu próprio `<<'EOF'`. O
`EOF` de dentro fechou o de fora e o bash executou o resto do texto como comandos. Conferido com
`git status`: nada mudou (`viking` não estava no PATH daquele shell, o resto era texto que o bash
rejeitou). O roteiro do MCP virou `scripts/pedido_mcp_de_teste.py`, e o bloco foi escrito num
arquivo antes.

**2026-09-28 — hífen invisível dentro do plano (abertura da Sessão 8).** O plano listava, entre
os disfarces de domínio a testar, um host com hífen invisível (U+00AD), e eu o escrevi como o
próprio caractere, não como escape: foi parar no arquivo do plano e no `PROGRESSO.md`, invisível.
A frase ao lado dizia "gerado por script, classe 5". Pego pela varredura de caracteres de
controle logo depois de copiar o plano. O que tem de novo: o caractere não veio de um escape
convertido pela ferramenta, veio direto da minha escrita, num documento; a varredura roda também
no plano, antes de copiá-lo.

**2026-09-28 — o veredito das mutações passou por um `tail` (Sessão 8, C4).** Rodei a bateria
inteira com `python scripts/mutacoes.py 2>&1 | tail -15` em segundo plano. O resumo ("mutações: N
· mortas pelo teste esperado: N") sai no **topo** da lista, e o `tail` o jogou fora; e o "exit 0"
que a notificação mostrou era o do `tail`, não o do script (sem `pipefail`). Pego ao ir contar as
mortas. Rodei de novo com a saída inteira num arquivo. O que tem de novo: a skill manda ler a
linha literal "do topo", e fui eu que cortei o topo; resultado de portão vai inteiro para um
arquivo, e o status é o do comando, não o do pipe.

**2026-09-29 — mutações que não foram gravadas (Sessão 8b, C2).** Num comando só, `ruff format
… && ruff check … && python3 (grava as mutações)`, seguido de `ruff format` e do teste das
âncoras. O `ruff check` falhou (ISC004), a cadeia parou antes de gravar as mutações, e as linhas
seguintes rodaram: "3 passed" nas âncoras, que eram as antigas. Pego ao ler "1 file left
unchanged" onde esperava uma mudança. No mesmo dia criei um arquivo de teste com `cat >`, contra
o antídoto desta classe (sem dano: `ruff` e a varredura passaram). O que tem de novo: um verde
que vem **depois** de um passo que falhou mede o estado anterior; e o antídoto escrito não
bastou para o `cat >` — agora a varredura de invisíveis roda também nos arquivos novos.

**2026-09-30 — o título do `PROGRESSO.md` virou lixo (fechamento da Sessão 10, `736fd1a`).**
Ao marcar os checkpoints da tabela, uma substituição com `\1` na troca (sem grupo que casasse
onde eu pensava) escreveu `\1| ✅ |1| ✅ |1| ✅ |` no lugar de `# Viking — progresso em curso`.
As linhas da tabela mudaram certo, e foi para elas que as duas passadas de revisão olharam; o
título ficou errado por dois commits e um compact, até a leitura da abertura da 10b. O que tem de
novo: o defeito estava **fora** do trecho que eu pretendia mudar, onde revisão nenhuma olha; o
`git diff --stat` mostrava o número de linhas esperado mais uma. Antídoto: depois de toda troca
por expressão num documento, `head -3` do arquivo e o `git diff` inteiro dele, não só o trecho.

**2026-09-30 — três escorregões de ferramenta na mesma sessão (Sessão 10b).** (1) Ao separar o
`registro.py` em interface e stores, cortei o arquivo no primeiro "`from __future__`" do texto,
que estava **na docstring**, e não na linha do import; os testes pegaram na hora, e a emenda
passou a usar a linha inteira com as quebras em volta. (2) Rodei uma mutação em primeiro plano,
contra a regra do `AGENTS.md` (background, sem `timeout`, saída num arquivo); sem dano, porque
terminou. (3) Um valor falso com cara de chave do Google num teste (`AIza…`) foi barrado pelo
hook do gitleaks no commit; trocado por um texto sem forma de chave. O que tem de novo: a busca
por texto num código-fonte casa também o texto que **fala** do código.

**2026-09-30 — quatro escorregões de ferramenta na mesma sessão (Sessão 10c, C1 a C4).**
(1) A emenda do `confirmacao.py` cortou no primeiro `from __future__` do texto, que estava na
docstring: o **mesmo** erro da 10b, refeito na hora a partir do git; a emenda agora ancora na
linha com as quebras em volta. (2) Uma rodada de mutações (a do prazo) rodou em primeiro plano e
com `timeout`, contra a regra do `AGENTS.md`: o **mesmo** da 10b, sem dano porque terminou. (3)
Um commit (`52570bc`) saiu com a checagem `pytest … | tail -1 && git commit`: o `tail` engoliu o
código de saída, e o commit seguiu com "1 failed" na tela. A queda era do trabalho não
commitado (uma âncora de mutação deslocada pelo C2), e o HEAD limpo passou numa cópia de
trabalho separada; o CI confirmou. (4) Estendi o comentário de uma linha que é âncora de mutação;
a âncora continuou casando como pedaço da linha, e a troca virou erro de sintaxe (o runner
acusou "caiu outro"). O que tem de novo: dois dos quatro são repetições da sessão anterior. A
regra escrita não bastou; antes de emendar um arquivo ou rodar mutação, reler a entrada da
classe 5 da 10b.

**2026-10-01 — de novo uma mutação em primeiro plano (Sessão 11, C4).** Depois da rodada do C4
em background (24/24), a mutação nova do Gmail no `agendador.ligado` rodou no mesmo comando que a
conferência das âncoras, em primeiro plano. Terceira sessão seguida (10b, 10c, 11). Sem dano:
terminou (1/1). O que tem de novo: a regra estava relida no começo desta retomada; uma mutação
"só uma" pareceu exceção. Não é: toda chamada a `scripts/mutacoes.py` vai com
`run_in_background`.

> **A ferramenta interpreta o que eu escrevo antes de o arquivo receber.**

**O antídoto, concreto:** nunca escrever uma sequência de escape Unicode em parâmetro de
ferramenta, nem em prosa; gerar por script (`chr(92)`); varredura de C0/C1/bidi em todo arquivo
alterado antes do commit, sempre, inclusive em commit só de documentação; nada de `cat >` para
criar arquivo; `source .venv/bin/activate` no começo do comando, e `git diff --stat` (ou `grep`
da mudança) antes de ler o resultado dos testes. Texto que contém um heredoc nunca vai dentro de outro: escrever
num arquivo e ler dele.

**2026-10-07 — a espera do CI com o SHA digitado errado (abertura da 11d).** Para esperar o CI
do commit do lock, mandei um laço em background `until gh run list --commit 050b46e2 …`; o SHA
era `050b46e1…`. O `gh` não acha nada, e o laço nunca terminaria. Pego ao conferir o CI à mão
(`success`) e o laço foi parado. O que tem de novo: um prefixo de SHA digitado de memória; o SHA
sai do `git rev-parse`, nunca da cabeça.

**2026-11-21 — o `| tail` que escondeu a falha (14b, C4).** Rodei o `--executar alertas` em
segundo plano com `… | tail -2 | cut`, e o "exited with code 0" era o do `cut`: o `nuvem.py` tinha
saído com 1 (a API recusou a política). Só a medição seguinte, que não achou a política, mostrou.
Antídoto: um comando que escreve na nuvem roda sem pipe, com a saída num arquivo e o `$?` impresso
logo depois.

**2026-11-22 (H1) — a configuração do servidor dada ao cliente.** Para ler a flash da XIAO pelo
RFC2217, rodei o `esptool` com `ESPTOOL_CFGFILE=esptool-usbjtag.cfg`, cujo comentário diz "aplicada
localmente pelo esp_rfc2217_server". O cliente aplicou a sequência e o servidor também: duas vezes
"getting no sync reply: The serial TX path seems to be down". Sem reset (`--before no-reset`) a
sincronia funcionou, o que isolou o reset; sem o arquivo no cliente, conectou da aplicação rodando.
**Antídoto:** antes de passar uma configuração a uma ferramenta, ler de quem ela é (o comentário
dizia); e diante de uma falha nova, separar as metades (aqui: a sincronia sem reset) antes de repetir.
No mesmo dia, um teste meu da ponte deu 400 em vez de 401: o `set -- $r` do zsh não divide palavras,
e o método foi "GET /estado" inteiro. Refeito com o comando escrito por extenso: 401 em todas.

**2026-11-22 (H2, C1) — o commit antes de ler a linha da suíte.** A suíte rodou em segundo plano;
li o fim do arquivo com `tail -2`, que mostrou só `[exited with code 0]` (o `pytest` em segundo
plano sai 0 do `tail` do comando, não dele), e fiz o commit e o push do C1. A linha era `1 failed,
2904 passed`: o `test_entrada_gigante_nao_explode`, que mede crescimento de tempo e cai com o Mac
ocupado (a rodada levou 154 s contra 70 s; sozinho, 3 de 3). Não era do C1, mas eu não sabia
quando commitei. O que tem de novo: o resultado de um portão é a linha `N passed`/`failed`
**procurada** (`grep -E "passed|failed"`), nunca o fim do arquivo nem o código de saída do
invólucro.

### 6. Conserto que cobriu um ponto e não o vizinho

**2026-09-26 — `_executar` só no `.execute()` (Sessão 3b).** A falha da API também nasce ao montar
a requisição; o teste antigo de falha no `delete` pegou. `_executar` passou a receber a montagem.

**2026-09-26 — a nota do Gemini colada antes do "sair" (Gmail 2).** Pus a nota da aprovação
no começo da linha seguinte logo depois de ler a entrada, antes das checagens de `sair` e
`/custos`: no Mac, o "sair" depois de aprovar virou mensagem ao Gemini. O teste do laço tinha
"sair" no fim, mas sem aprovação logo antes. O que tem de novo: mudei a linha e não reli as
linhas **abaixo** dela que liam a mesma variável.

**2026-09-26 — `timeout` em volta do script de mutações (Gmail 2).** Depois de uma rodada travar
(teste com sorteio preso num valor, laço infinito na mutação), rodei a seguinte com `timeout 900`
— o próprio script diz "sem timeout de propósito: SIGTERM não passa pelo `finally`". Terminou
antes, sem estrago. O jeito certo, usado na rodada travada: matar só o `pytest` filho.

**2026-09-27 — de novo, pelo parâmetro da ferramenta (Sessão 5, conserto do fuso).** Rodei
`python scripts/mutacoes.py "fuso:"` em primeiro plano com o `timeout` da ferramenta de terminal
(600 s). Terminou em segundos, sem estrago; mas estourar mataria o processo como o `timeout 900`.
O que tem de novo: não era o comando `timeout`, era o limite da própria ferramenta. Rodada de
mutações vai em background, sem limite.

**2026-09-27 — teste que trava sob a mutação (Sessão 6, C3).** A mutação "a trava espera o outro
em vez de recusar" fez `test_segunda_abertura_no_mesmo_processo_tambem_ve_ocupado` (duas aberturas
aninhadas no mesmo processo) esperar por si mesmo: a rodada ficou parada 1 h. Matei só o `pytest`
filho, como manda a regra; o script restaurou o arquivo. O que tem de novo: eu tinha previsto no
plano que essa mutação esperaria o *outro processo* (15 s) e não vi o teste que esperaria por
**ele mesmo**. Agora a segunda abertura roda numa thread com prazo (5 s), e cai em vez de travar.
Antídoto: para cada mutação que muda "recusa" em "espera", perguntar *qual teste esperaria para
sempre?* antes de rodar.

**2026-09-27 — a trava nova quebrava "sempre devolve `BrowserResult`" (Sessão 6, C3; pego na
revisão, antes do commit).** `trava.ocupar` abre um arquivo; um `OSError` (pasta sem permissão,
`flock` recusado) escaparia de `run_jev` como exceção — o §10.8 da auditoria, já consertado uma vez.
Agora vira `trava_indisponivel` e não navega; o `--doctor` também.

**2026-09-20 — `fastmcp.md` fora do formato (Sessão 3).** Rodei o `ruff format` só nos `.py`; ele
também formata o Python dentro dos `.md`. Formatado na Sessão 4.


**2026-09-27 — reserva de código que desarmava a garantia vizinha (Sessão 5).** Para não travar a
limpeza com muitas propostas de outro app, deixei de reservar o número das propostas substituídas
— e com isso a proposta nova podia sortear o número da velha, e o código da primeira lista
aprovaria a segunda. O teste antigo `test_proposta_nova_invalida_o_codigo_velho` pegou. Na revisão
do mesmo commit, outro do tipo: o desfazer que falhava de modo ambíguo voltava a ser desfazível, e
um segundo `desfaz` recriaria a cópia duas vezes. O que tem de novo: uma otimização de limite
(reserva, retentativa) é exatamente onde a garantia de "uma vez só" se perde.

**2026-09-27 — nome repetido que cegava uma régua vizinha (Sessão 5, C7).** Chamei a aprovação
do clique de `liberacao.executar_aprovado`, o mesmo nome da do calendário. A régua do MCP
(`test_so_a_cli_executa_um_pedido_aprovado`) procura pelo **nome** do atributo e caiu: `agent.py`
passou a "chamar" `executar_aprovado`. O teste estava certo; ajustar o conjunto esperado teria
deixado a régua sem distinguir as duas funções. Renomeada para `clicar_aprovado`, com régua
própria.

**2026-09-27 → 2026-09-29 — o isolamento dos testes cobriu dois dos três módulos do mesmo banco
(Sessão 5, achado na abertura da 9).** Na Sessão 5 pus no `conftest` a troca do `DB_PATH` de
`confirmacao` e de `registro`, "os dois no MESMO arquivo, como em produção", e esqueci o terceiro
que abre esse arquivo: o store dos lembretes, que lia o caminho da config. O
`test_lembrete_criar_e_concluir_registram`, escrito no mesmo commit (`1b05733`), passou a gravar um
"Pagar conta" no `data/viking.db` de verdade a cada `pytest`: 132 no VPS em dois dias, e no Mac,
um por rodada, no banco do dono. Ninguém via, porque o teste conclui o lembrete e a lista só
mostra os abertos. Achado ao abrir o arquivo para medir a 9 (dados que ninguém escreveu à mão).
O que tem de novo: o vizinho não era outro ponto do mesmo código, era outro **dono do mesmo
recurso**. O conserto é de estrutura: um lugar só abre o banco (`banco.conectar`), um nome só se
troca, e um teste proíbe `sqlite3.connect` fora dele.

> **O que este conserto tornou falso, e onde mais a mesma falha nasce?** É a segunda passada de
> revisão.

**O antídoto, concreto:** na revisão, listar todos os pontos por onde a falha entra antes de
fechar; rodar os portões no repo inteiro, não só nos arquivos que eu lembro de ter tocado.

**2026-09-30 — consertei um teste instável e deixei 24 irmãos (fechamento da 10b).** De manhã, o
CI caiu porque o código falso `7391` apareceu nos microssegundos de um horário, e eu consertei
só aquele teste. O vizinho que conferi (`test_gmail_envio`) lia colunas sem horário, e parei ali.
À noite, o CI de um commit só de documentação caiu em `test_mcp_aprovacao` pelo mesmo motivo
(`…148214` contendo `4821`). A varredura depois mostrou 25 asserções do mesmo formato
(`CODIGO not in texto`) em 7 arquivos, várias sobre texto com horário, UUID ou id. Conserto de
estrutura: `tests/sentinela.aparece` procura o código como número isolado, testado dos dois lados
(`tests/test_sentinela.py`), e as 25 passaram a usá-lo; as 251 mutações seguiram mortas. O que tem
de novo: conferir **um** vizinho não é varrer; o `grep` da forma inteira da asserção era o passo.

**2026-10-01 — a espera do IAM cobria só o `viking-cli@` (Sessão 11, C5).** As provas do
deploy esperam enquanto o 403 é a página do Google (a permissão recém-dada propagando), mas só no
pedido do `cli@`, cuja permissão existia desde a Sessão 10. As provas novas do `viking-maos@`,
autorizado no mesmo deploy, caíram com 403 do Google; a resposta crua (o HTML, e o token com o
e-mail e a audience certos) mostrou a propagação, que levou mais uns minutos. A espera agora vale
para todo pedido das portas. O que tem de novo: a regra estava escrita para o primeiro deploy, e
uma conta nova num deploy seguinte é outro "primeiro".

**2026-10-07 — três âncoras de mutação quebradas pelas minhas próprias mudanças (Sessão 11d).**
Trocar `_ESCRITAS_PERMITIDAS` por `_escritas_permitidas()` na recusa da Pluggy, levar a
verificação do token do motor para `nuvem/identidade.py` e reescrever `na_nuvem.ferramentas()`
mudaram linhas que três mutações usavam de âncora (e uma delas, "as finanças entram no chat da
nuvem", perdeu o sentido: agora entram de propósito). A rodada recusou antes de rodar, e
`test_mutacoes_ancoras` caiu na suíte. Reancoradas na linha inteira, e a sem sentido foi trocada
por "uma tool do Mac some da nuvem sem decidir onde mora". O que tem de novo: um refatoramento
meu é um "conserto" para as mutações; o `grep` das âncoras nos arquivos que mudei vem antes da
rodada, não depois da recusa.

**2026-10-07 — a conta recém-criada sem esperar o IAM (Sessão 11d, ok 1).** O passo `financas`
cria a conta `viking-financas@` e logo dá a ela a leitura do segredo; o `add-iam-policy-binding`
deu 400 "Service account … does not exist". Rodado de novo, passou. Em 2026-10-01 eu tinha
posto a espera da propagação só nas **provas** do deploy (o `run.invoker` novo); o mesmo atraso
vale para o passo que cria a conta. Conserto de estrutura: `_rodar_esperando_a_conta`, em todo
`add-iam-policy-binding` de todo passo, só nesse erro. O que tem de novo: a mesma propagação, num
terceiro lugar (o deploy da 11d também esperou 15 s pelo `run.invoker` do `motor@` no serviço
de finanças, e a prova de log pegou o 502 dessa espera).

**2026-10-07 — duas âncoras de mutação quebradas pelas minhas mudanças, de novo (Sessão 12,
C3).** O `antes()` do `custos.instrumentar` virou `antes(modelo)` e a lista de tools da nuvem
ganhou o `usar_modelo_forte`: as âncoras "teto conferido depois da chamada" e "uma tool do Mac
some da nuvem" deixaram de casar. Desta vez `test_mutacoes_ancoras` pegou na suíte, antes da
rodada, e as duas foram reancoradas na linha inteira. O que tem de novo: a estrutura (o teste
das âncoras na suíte) pegou o que a disciplina da 11d dizia para fazer à mão; o `grep` das
âncoras dos arquivos mexidos continua sendo o passo antes da suíte.

**2026-10-08 — três âncoras de mutação, o `conferir` do backup e um nome que cruzou a D26
(Sessão 13).** As minhas mudanças quebraram três âncoras (a prova do chat, duas do formato do
backup; reancoradas na linha inteira, pegas pelo teste das âncoras); o `conferir` passou a contar
a memória no arquivo e não no restaurado (o teste pegou); e a função da memória chamada
`desfazer` caiu na régua de `tests/test_gmail_aprovacao.py`, que vigia esse nome (renomeada
`devolver`). O que tem de novo: um nome também é um vizinho — a régua que lê o código por nome
vale para todo módulo novo.

**2026-10-09 — três âncoras de mutação quebradas de novo, uma por fase (Sessão 14).** O `gmail/tools.py`
(no conserto da redação), o `vetores.py` (no C4) e, antes, nenhum `grep` das âncoras dos arquivos
que eu mexia: o teste das âncoras pegou as três na suíte, antes da rodada. O que tem de novo: a
mesma lição da 11d, 12 e 13 voltou três vezes numa sessão; a régua estrutural segura, e o `grep` à
mão continua não sendo feito. Passo a rodar o teste das âncoras junto do `ruff` depois de cada
emenda, não só na suíte.

**2026-10-09 — a redação de páginas aplicada a ids (o vizinho do registro, Sessão 14).** O conserto do
registro (um UUID solto fica fora da redação) cobria os ids nossos; o vizinho era a linha da busca do
Gmail, "(ID: …)", que passava inteira pela mesma redação, e um id do Gmail (16 hex) só de dígitos
tem a forma de um cartão de 16 dígitos: não dava para protegê-lo na regra geral sem abrir um buraco.
Consertado no lugar dele: o id fora da redação, o conteúdo dentro (como o `ler_email` já fazia).

**2026-11-21 (H1) — a tarifa do modelo desconhecido, que a tarifa nova desmontaria.** Ao pôr o
TTS em `custos.TARIFAS` (entrada US$ 0,50, saída US$ 6,00, o dobro em 2027), a regra "fora da
tabela cobra a mais cara" escolhia a faixa de **maior soma**: passaria a ser (1,00, 12,00), e um
modelo desconhecido com muita entrada (o `gemini-3.5-transcribe`, a US$ 2,00 de entrada) seria
contado abaixo do que custa. Peguei ao rodar o teste da tarifa, que esperava (1,50, 7,50). A regra
virou "a maior entrada e a maior saída, cada uma". **Antídoto:** ao acrescentar uma linha numa
tabela, reler toda regra que escolhe "a maior" ou "a menor" dela.

**2026-11-22 (H1) — o código fora da fala, mas a aprovação aberta sem a fala inteira.** Na voz, eu
tinha tirado o código do que é falado e posto os dois toques no lugar (a D26 pelo canal físico).
O vizinho, que a revisão do Sonnet achou: dois toques aprovavam o que o dono **não ouviu**. O
texto se cortava em 2.000 caracteres e 12 frases sem aviso; um TTS que caía no meio terminava
como fim normal (o motor fechava o streaming com `return`), e a janela abria antes da fala.
Consertado: a fala de uma aprovação vai com `inteiro` (o motor recusa com 413 o que não cabe), o
erro no meio derruba a conexão, o `aplay` que morre é erro, e a janela só abre depois do último
pedaço tocado; em qualquer falha a proposta se fecha (`tests/test_casa.py`). **Antídoto:** numa
aprovação, perguntar também *o dono viu (ou ouviu) inteiro o que está aprovando?*, além de *o
modelo alcança o código?*.

### 7. Regra de reconhecimento desenhada pelo caso típico

**2026-09-26 — `href` por substring (Sessão 4b).** A primeira versão do freio casava `sair`
dentro de qualquer caminho: o link de um artigo `/blog/como-sair-da-divida` seria recusado como
logout. Pego na releitura; virou comparação com o trecho inteiro do caminho.

**2026-09-26 — controle virando espaço (Sessão 4b).** A normalização trocava todo não-alfanumérico
por espaço, então um NUL no meio de "Sair" partia a palavra e o rótulo escapava. Pego na
releitura; controles e invisíveis passaram a ser removidos, só espaço de verdade vira espaço.

**2026-09-26 — botão genérico no contexto errado (Sessão 4b).** "Excluir" era julgado também pelo
contexto de dinheiro: excluir a tarefa "comprar pão" seria recusado. Pego pelo teste de vizinho
legítimo escrito junto; remover passou a olhar só contexto de conta.

**2026-09-26 — só o código, sem "confirma" (Gmail 2).** A interceptação da aprovação reconhecia
"confirma 8768"; no Mac, o dono digitou primeiro "confirma" e depois só "8768" — e o número foi
ao Gemini. Sem estrago (o Gemini não tem como arquivar), mas quebrava a promessa de que ele nunca
vê o código. Agora a palavra sozinha ganha a instrução ali mesmo, e o número do tamanho do código,
com proposta aberta, aprova.

**2026-09-26 — a mesma regra, de novo rígida (Gmail 2, horas depois).** O conserto acima ainda
exigia a linha inteira no formato: "desfaz 8768 do gmail" e "você arquivou - desfaz o código é
8768" foram ao Gemini, que ainda negou ter havido arquivamento. Segunda vez na mesma regra por não
ter feito a lista de vizinhos e disfarces antes: feita agora, virou a regra "número que é código
**vivo** nunca sai do Viking" e teste parametrizado dos dois lados.


**2026-09-27 — pagamento de fatura reconhecido só pela categoria (Sessão Pluggy).** Medi as
categorias e operações internas e escrevi "`Credit card payment` nas duas contas" — era verdade
no Itaú. No Nubank, os 33 pagamentos de fatura vêm como `Transfers`/`OUTROS`, e o primeiro
`--gastos` do dono no Mac contou um deles como gasto. Nenhum teste pegaria: a Pluggy falsa foi
montada com o caso típico. Agora a descrição exata também reconhece, e o disfarce ("Pagamento de
fatura VIVO", que é conta de telefone) tem teste e mutação. O que tem de novo: medir **por
conexão**, não no agregado das duas.


**2026-09-27 — prefixo de sessão com `LIKE` (Sessão 5).** O `desfaz` só alcança ações desta
sessão, pelo prefixo do turno; escrevi `turno LIKE prefixo%` tirando só o `%` do prefixo. O teste
com o disfarce mostrou: prefixo vazio vira `LIKE '%'` (qualquer sessão) e `_` também é curinga.
Virou comparação exata do começo (`substr`), e prefixo vazio não acha nada.

**2026-09-27 — prefixo `UV_` inteiro na lista do ambiente (Sessão 6).** O plano liberava todo
`UV_*` para o Jev pensando em cache e Python do `uv`. Na revisão, a pergunta "que disfarce o
prefixo deixa passar?" achou `UV_ENV_FILE`: medido, sem o `--env-file` (o `.env` do Jev não
existe) ele é lido — e poderia apontar para o `.env` do Viking, com a chave do Gemini. E
`UV_NO_ENV_FILE` desligaria o `.env` do Jev em silêncio. Viraram exceção dentro do prefixo
(`AMBIENTE_EXCETO`), com teste e mutação. O que tem de novo: numa **lista do que passa**, o
disfarce é um nome legítimo do mesmo dono (o `uv`) que muda o que a regra protege.

**2026-09-28 — o bloqueio de banco lia o host com `urlsplit` (Sessão 4; achado na revisão do
roteiro, consertado na 8).** A regra de 2026-09-26 foi desenhada por `https://banco/…` e pelos
disfarces de *domínio* (sufixo solto, `@`, sem esquema); os disfarces de *endereço* ficaram de
fora: `view-source:https://banco/` e `blob:` (o Chrome abre o de dentro), `https:banco` sem
barras, `\`, `%69tau`, letras de largura dupla, hífen invisível — 17 de 20 passavam. O vizinho
também: o endereço inicial aceitava `file:///…`, que levaria um arquivo do Mac aos modelos. O que
tem de novo: o reconhecimento era de host, e o disfarce estava uma camada acima, no **endereço**,
com uma especificação pública (WHATWG) que diz exatamente como o navegador o lê; a lista de
disfarces tem de sair da regra do leitor de verdade, não da minha imaginação.

> **Uma regra que reconhece algo é desenhada pelo exemplo que a motivou, e o exemplo não mostra
> nem o vizinho inocente nem o disfarce.**

**O antídoto, concreto:** antes de escrever a regra, uma lista escrita de vizinhos legítimos e de
disfarces, virando teste parametrizado dos dois lados (`tests/test_acoes_sensiveis.py` é o modelo).

**2026-09-30 — o "não existe" do gcloud pelo caso típico (Sessão 10, C6).** `scripts/nuvem.py`
reconhecia a ausência de um recurso por `NOT_FOUND`, "not found", "does not exist"; o `gcloud
run services describe` diz "Cannot find service [motor]", e o primeiro deploy caiu num
traceback antes de listar o que faria. O que tem de novo: cada comando do `gcloud` tem o seu
texto; a lista cresce com o texto real medido, num teste, e qualquer outro erro continua erro.

**2026-09-30 — o `scripts/nuvem.py` desenhado para a primeira execução (Sessão 10b, C5).** Na 10
tudo era criado do zero. Na segunda vida do script, com a API do Secret Manager nova e ainda
desligada, os passos que dependiam dela não eram medidos, e a lista dizia "criar" para recursos
que já existiam; e o passo dos índices, com um índice novo na lista, tentou recriar o antigo e
parou em `ALREADY_EXISTS`. Consertos: o passo não medido diz "não medido" e mostra `?→`; os
índices criam só o que falta, com teste. O que tem de novo: um script de infraestrutura tem os
dois vizinhos, "nada existe" e "quase tudo existe", e o segundo é o de todo dia depois do
primeiro.

**2026-10-08 — a régua das respostas que "confirmam registro" (Sessão 13, fechamento).** Para
medir se o modelo diz "anotado", escrevi uma regex com as palavras que eu esperava (anot…, guard…,
registr…, salv…, memoriz…). Ela não pegou "Feito! Já mudei para as terças" nem "Cadastrado!", e
contou como confirmação um "Mudou para o quinto, entendi" que só repetia o dono. Pego lendo as
respostas inteiras, as 18. O que tem de novo: uma régua de medição também é regra de
reconhecimento; o número dela só vale depois de ler os casos, e o que entrou no commit foi a
contagem lida, não a da régua.

**2026-10-08 — o desfazer desenhado para uma troca só (Sessão 13, achado na 2ª passada da 13b).**
`store.devolver` (e o `receitas.devolver`, copiado dele) reativava o fato e esquecia **o que o
substituiu**. Numa cadeia, A trocado por B e B por C, desfazer A esquecia B (já fora) e deixava A
e C ativos: dois fatos que se contradizem, ou duas receitas com o mesmo nome (o `roda` nunca
escolhe). Nenhum teste tinha mais de uma troca. Consertado (`fa53068`): nos fatos sai o ativo do
fim da cadeia, nas receitas a xará ativa; testes que caíam antes e duas mutações. O que tem de
novo: "desfazer" tem o vizinho "desfazer depois de duas mudanças", e o caso típico de um teste de
histórico é o de uma mudança só.

**2026-09-20 → 2026-10-09 — a regra do cartão lendo dígitos dentro de um id (achada no CI da 14).**
`registro.limpo` passa a redação das páginas em todo texto do registro, ids inclusive, e a regra do
cartão (13 a 19 dígitos, com espaço ou hífen, Luhn) foi desenhada para texto de página: "4154-8003-04256"
dentro de um UUID é cartão para ela (~1 em 1.000 UUIDs). O desfazer não sofria (a cópia é crua), mas
o `viking registro`, a `acoes_recentes` e o backup mostravam o id errado. Conserto (`3dc67a3`): um
UUID exato e solto fica de fora (32 hex não cabem num cartão); colado a letra, `_` ou hífen, não
(seria o meio de um token, e parti-lo o deixaria escapar: testado com um JWT). O que tem de novo: o
vizinho legítimo de uma regra de texto de página inclui o identificador que o próprio sistema gera.

**2026-11-22 (H1, E2E) — o teto de 15 s da gravação, desenhado pela frase curta.** Escolhi 15 s
pensando em "liga a luz" e "o que eu tenho amanhã". No E2E o dono ditou um e-mail e soletrou o
endereço segurando 22,5 s: a placa gravou 15 (`gravado: 14.98 s`) e cortou a soletração **sem
aviso** (o LED seguia aceso). A transcrição montou outro domínio, o dono não percebeu na leitura, e
o e-mail de teste foi a um endereço errado (irreversível). Conserto: 30 s (o WAV cabe no teto de
1 MiB da ponte e do motor) e o LED piscando nos últimos 3 s e depois do fim, até soltar. O que tem
de novo: o vizinho legítimo de um limite de duração é o ditado (endereço, número, soletração), e
um corte nunca é silencioso.

### 8. Comando que escreve com alcance maior que a mudança

**2026-09-26 — `ruff format` em `src`/`tests` inteiros (Sessão 4b).** Queria formatar os arquivos
que tinha acabado de editar; o formatador reescreveu também 5 arquivos antigos fora do padrão
(`agent.py`, `calendar/tools.py`, `custos.py` e dois testes) — em `tools.py`, duas docstrings que
o Gemini lê e que estavam fora do formato de propósito. Pego no `git status`; restaurado arquivo a
arquivo com `git show HEAD:`, repondo à mão a única linha minha em `agent.py`.


**2026-09-27 — as mesmas duas docstrings, segunda vez (Sessão 5).** Editei `calendar/tools.py` e
rodei `ruff format` nele: o arquivo era meu, mas é do baseline, e as duas docstrings da Sessão 4b
foram reformatadas de novo. Pego pelo `--check` do repo (6 em vez de 7). O antídoto antigo
("formatar só o que eu editei") não cobre arquivo do baseline: nele, olhar o `--diff` e aplicar
só os meus trechos.

> **Conferir (`--check`) é no repo inteiro; escrever é só no que eu mudei.**

**O antídoto, concreto:** `ruff format <arquivos que eu editei>`, nunca um diretório; `git status`
depois de qualquer comando que escreve.

> **Atualização (2026-09-28, Sessão 7, D45) — não é ocorrência.** O baseline acabou: os 6 `.py`
> atrasados foram formatados num commit só de formatação (`dd7d4c8`), por decisão do dono, e os
> `.md` saíram do `ruff format` (o Python deles é citação). A regra "em arquivo do baseline, só os
> meus trechos do `--diff`" deixou de existir: `ruff format --check .` tem de dar zero. O antídoto
> de cima continua: nomear os arquivos.

**2026-11-21 — `ruff check --fix --select RUF100` no repo inteiro (14b, C1).** O ruff 0.17 apontou
dois `noqa` de uma regra que não está ligada; para consertar só esses, rodei o `--fix` com
`--select RUF100`. Com a seleção reduzida a uma regra, **todo** `noqa` de outra regra pareceu
sobrando, e o ruff apagou 47 deles em 19 arquivos de `src/` e `tests/`. Olhei primeiro só o
`git diff --stat -- tests/` (12 arquivos) e restaurei `tests/`; o `ruff check` seguinte deu 49
erros em `src/`, e só então vi o resto. Restaurado tudo do commit, e as duas linhas editadas à
mão. O antídoto: `--fix` com a configuração do projeto, nunca com `--select` de uma regra só; e o
`git status` **do repo inteiro** depois, não de uma pasta.

**2026-11-22 (H1) — `ruff format src tests scripts firmware` de novo, por pressa.** Formatei as
pastas em vez dos arquivos. Desta vez só arquivos que eu tinha editado mudaram (conferido no `git
diff --stat`), mas foi sorte, não o antídoto.


**2026-11-22 (H1, C4) — o `montar_segredos.sh` guardava o antigo sempre no mesmo nome.** O script
movia um `src/segredos.h` existente para `~/viking-voz-segredos.antigo.h` com `mv` simples. O dono
o rodou duas vezes: a 2ª rodada moveu o arquivo gerado na 1ª por cima da cópia, e o `segredos.h` que
ele tinha começado à mão às 13:32 se perdeu (visto pelos horários e tamanhos no `ls -la`, sem abrir
os arquivos). Uma cópia de segurança que se sobrescreve não é cópia. Agora: um nome por rodada (a
data e a hora) e `mv -n`, e o script para se o arquivo não saiu do lugar. O antídoto: *o que
acontece na segunda rodada?* antes de entregar um script que move ou grava.
