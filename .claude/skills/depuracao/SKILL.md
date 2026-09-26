---
name: depuracao
description: A ordem de investigação diante de um defeito, um número estranho ou algo lento — consultar o catálogo de erros por classe, reproduzir com a ferramenta que É a configuração, suspeitar primeiro do nosso lado (nossa régua, nosso schema, nosso cache, nosso processo velho), instrumentar a resposta crua, separar hipóteses com um controle, ler a fonte autoritativa, e medir o raio de uma falha externa em vez de consertá-la. Inclui as armadilhas de shell e de ferramenta que já produziram resultado falso. Use quando algo quebrar, der número implausível, ficar lento, ou quando uma ferramenta nova acusar algo.
---

# Depuração — por onde começar

## Quando usar

- Algo quebrou, está lento, ou devolveu um número que não bate.
- Uma régua, um teste ou um alerta novo acusou algo na primeira execução.
- A saída de uma IA parece ruim.
- Um erro cita algo que não está no disco (linha errada, identificador de
  execução antiga).

## Quando não usar

- Para um erro transitório **isolado** de terceiro que já cicatrizou. Meça,
  registre e vigie a recorrência (passo 6). Não abra uma investigação.

## O princípio

As investigações caras desta casa seguiram o mesmo roteiro: a primeira
hipótese era a mais cara e a menos provável. Foi uma hora comparando modelos de
IA quando o defeito estava no schema que nós enviávamos. Foi um "conserto" de
uma ferramenta de coleta que estava certa, porque a sondagem manual estava
errada. A ordem abaixo põe primeiro o que é barato de conferir e costuma ser
culpado.

---

## A ordem

### 0. Abra o catálogo de erros antes de atacar

A pergunta é *de que classe isto é uma instância?* Se for de alguma, o antídoto
já está escrito e não precisa ser redescoberto. *Caso real:* um conserto deixou
a suíte verde e o problema continuou, porque o mesmo endereço também chegava por
outro caminho. A classe ("confiei no meu atalho em vez da config declarada")
estava no catálogo, lida naquela manhã.

Procure também no roadmap, no diário e **no docstring do arquivo que você vai
mexer**. Várias "descobertas" já estavam escritas no próprio módulo.

### 1. Reproduza com a ferramenta que É a configuração

Quando a pergunta é *"a config deste componente funciona?"*, a ferramenta tem de
**ser** a config. Reimplementá-la à mão (um `curl` com o caminho que você supõe,
um `grep` com o padrão que você imagina) testa a sua suposição, não o sistema.
*Caso real:* três fontes apontadas como quebradas por um `curl` manual estavam
todas de pé. Elas declaravam caminhos diferentes do que foi chumbado.

**A sondagem manual também mente.** Um servidor pode responder 403 para uma
requisição pobre e 200 para a completa, e um `href` sem barra inicial escapa do
seu regex. Antes de "consertar" o sistema com base numa sondagem, confira a
sondagem.

### 2. Suspeite primeiro do seu lado

Nesta ordem:

1. **A régua.** Se uma verificação nova acusa algo na primeira execução, a
   primeira suspeita é ela. Ela está comparando a coluna que o produto usa? Ela
   sabe ler a outra grafia da mesma guarda?
2. **O seu dado de teste**, se o sintoma apareceu com uma fixture (ver
   `testes-que-provam`).
3. **O que você enviou ao terceiro**: schema, prompt, parâmetros, e a
   normalização que roda na resposta. **Com IA, a ordem é: schema → prompt
   exato → normalização → e só então o modelo.** O sintoma *"o modelo se
   absteve"* é indistinguível de *"o modelo respondeu e nós jogamos fora"*.
4. **Um processo ou cache velho.** Se o `git diff` está limpo e o erro não bate
   com o disco (linha diferente, símbolo que existe), o suspeito é um servidor
   de desenvolvimento preso numa edição intermediária, um cache incremental
   (typecheck, build) ou um processo iniciado antes da mudança. A saúde mede
   vida, não versão: confira o contrato do processo em execução.
5. **O estado fora do arquivo**: banco de teste com objeto de uma rodada
   anterior, lockfile regravado, variável de ambiente de outro ambiente.

### 3. Instrumente a resposta crua

Antes da normalização, antes do parse, antes do `?.`. Isso custa minutos.
Comparar alternativas (modelos, bibliotecas, versões) custa horas e dinheiro, e
produz medições rigorosas **da coisa errada**, que são as conclusões erradas
mais convincentes.

### 4. Separe as hipóteses com um controle

Um controle é uma medição que dá resultados diferentes conforme a hipótese.

| Sintoma | Controle que separa |
|---|---|
| TLS falha no domínio novo | a porta 80 do mesmo frontend responde com o redirect certo → a borda conhece o domínio; só falta o certificado |
| A chave foi recusada ao chamar a função | a mesma chave, noutro endpoint que deveria aceitar → responde 200 → a recusa é do endpoint, não da chave |
| Um pedido deu 504 | os pedidos irmãos do mesmo instante voltaram 200 em < 2 s → soluço, não sobrecarga |
| O login não fecha | o caminho com **mais** saltos respondeu **mais rápido** → o cliente falha localmente e nem chega à rede |

Sem controle, `000` em 443 é indistinguível de "domínio apontado errado".

### 5. Leia a fonte autoritativa, não a mensagem

- **`PERMISSION_DENIED` pode nomear o lugar errado.** Vá ao log de auditoria
  antes de repetir o comando.
- **DNS:** pergunte ao servidor autoritativo (`dig +norecurse @<ns>`), nunca ao
  resolvedor, que devolve o cache dentro do TTL. E a consequência vale para o
  usuário também: o navegador dele guarda o registro velho.
- **Estado de recurso:** `describe` do recurso, não o output da ferramenta de
  IaC (com `-target`, ele imprime o valor do último apply completo).
- **"Não consegui estabelecer a causa"** depois de olhar uma fonte é ausência de
  procura. Pergunte *que outra tabela ou log sabe quando isto mudou?*

### 6. Falha externa: meça o raio, não a causa

Um transitório de terceiro (token recusado por dois minutos, 504 isolado):

1. meça o suficiente para dizer de quem é (os pedidos irmãos, os logs do
   fornecedor, o relógio de cada lado);
2. **não afirme a causa** se não mediu: "externo, transitório, cicatrizou";
3. conserte o que é seu, que é o **raio** (a página inteira caiu junto?);
4. registre e **vigie a recorrência**. É a recorrência que muda o veredito.

### 7. Explique antes de consertar

Escreva: *o que era, por que passou pelos portões, o que agora impede que
volte*. Se você não consegue escrever a segunda parte, o conserto não fecha a
classe, só a instância.

Depois do conserto, faça a segunda passada (ver `software-build`): **o que este
conserto tornou falso?**

---

## Armadilhas de shell e de ferramenta que já produziram resultado falso

| Armadilha | O que aconteceu | Antídoto |
|---|---|---|
| `pkill -f <padrão>` / `pgrep -f` | o padrão casou com o próprio shell que o executava; ele matou a si mesmo, ou achou os próprios laços | matar pelo PID lido da **porta** (`ss -ltnp`) ou do `ps` filtrado com `awk` |
| comandos em linhas separadas, sem `&&` | o primeiro falhou e o segundo rodou sobre o arquivo antigo: "19 passed" | `&&` entre passos dependentes; `set -e` |
| caminho relativo depois de um `cd` | o `cat >>` foi para lugar nenhum | caminho absoluto sempre |
| flag inventada num `&&` | a corrente parou e um commit foi pulado em silêncio | conferir cada elo; ler a saída |
| `cmd $ARGS` em zsh | sem divisão de palavras, 28 flags chegaram como um argumento | array, ou uma linha literal |
| `cut -d'\|'` sobre trechos com várias linhas | as mutações quebraram no meio e duas não aplicaram | `assert velho in s` dentro do script |
| `s[:i] + novo` depois de um `Read` paginado | 1.641 linhas apagadas; a suíte ficou verde e **menor** | `wc -l` antes; substituição por âncora com `count == 1` |
| `rindex("]")` para achar o fim de uma lista | inseriu dentro de uma fatia de string; `ast.parse` passou | afirmar sobre a **estrutura** depois (contar os elementos) |
| `cat > arquivo_novo` | o nome estava ocupado, e seis testes foram apagados | `git status --short` antes de criar (esperar `??`) |
| `echo "$SEGREDO" \| …` | o `\n` virou parte do segredo; a falha parecia senha errada | `printf '%s'` |

## Como recuperar sem destruir

- **Nunca** use um comando que descarta mudanças não commitadas para "desfazer".
  Ele já destruiu trabalho.
- Faça backup por cópia antes de mexer.
- Para recuperar um arquivo: `git show HEAD:<arquivo> > <arquivo>`. Para
  recuperar só a cauda perdida, **acrescente** o trecho sem tocar no trabalho
  novo.

## Testes de falha

Você está depurando errado se:

- trocou de modelo, biblioteca ou versão antes de imprimir o que enviou e o que
  recebeu;
- repetiu o mesmo comando esperando outro resultado sem nenhuma hipótese nova;
- escreveu a causa antes de ter um controle que a separe das alternativas;
- está prestes a "consertar" algo que uma régua recém-escrita acusou, sem ter
  aberto o objeto acusado.

## Critério de conclusão

- [ ] A causa foi **medida**, com um controle, ou está escrita como hipótese.
- [ ] O conserto veio com teste que cai sem ele.
- [ ] A explicação diz por que passou e o que impede que volte.
- [ ] Se era uma classe conhecida, a ocorrência nova entrou no catálogo com o
      que ela tem de diferente.
