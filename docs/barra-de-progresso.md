# Barra de progresso — Viking

> **Para quem é:** o dono, sem precisar abrir código. Onde um termo técnico for inevitável, ele vem
> explicado na hora. Atualizada ao fechar cada sessão, com data; os números são contados na hora,
> não copiados da versão anterior.
>
> **Como contar:** uma sessão só está "fechada" quando funcionou no Mac do dono, não quando o
> código foi enviado. Se parte dela ainda não foi testada lá, ela conta como parcial.

**Última atualização: 2026-09-26 (Sessão Gmail).**

`██████████░░░░░░░░░░ 4 de 11 sessões fechadas + 3 parciais (= 5,5 de 11)`

Contagem (em `sessoes.md`): fechadas 1, 2, 3 e 4b; parciais 4, 3b e Gmail; na fila Gmail 2, 5, 6
e 7 (a Gmail 2, limpar a caixa, entrou hoje a seu pedido). Cada
parcial vale meio bloco na barra.

## 2026-09-26 — o Viking lê o seu Gmail (e só lê)

**O que mudou:** no `viking chat` você pode perguntar "o que chegou hoje?", "tem e-mail do
fulano?", "lê esse pra mim" e "quem me manda coisa que eu nunca abro?". O Viking lê pela porta
oficial do Google, com permissão só de leitura: ele não consegue apagar, arquivar nem enviar
nada. CPF, cartão, chaves e links de redefinir senha são apagados antes de o Gemini ler; o Gemini
também é avisado de que o texto do e-mail é de terceiros e não manda em nada. Outras ferramentas
ligadas ao Viking (o servidor MCP) não enxergam seus e-mails.

**Como sabemos:** 528 testes passando no VPS, incluindo e-mails "maliciosos" montados de
propósito, e 27 proteções quebradas de propósito — todas pegas pelo teste certo. De brinde: se o
Google um dia cancelar o seu login, o Viking pede login de novo em vez de travar.

**Falta:** você fazer o login do Gmail no Mac (o Google vai mostrar "app não verificado" — é
esperado) e rodar o roteiro. A limpeza da caixa é a próxima sessão.

## 2026-09-26 — o navegador não sai, não mexe na sua conta e não gasta dinheiro sozinho

**O que mudou:** quando o Viking usa a sua Chrome logada, ele agora para **antes** de clicar em
"Sair", em excluir ou cancelar algo da conta, em trocar senha, ou em comprar, pagar e transferir.
A aba fica aberta e a mensagem diz qual botão foi recusado; se era isso mesmo, você clica. Isso
vale também para o botão final de um aviso ("Tem certeza que deseja excluir sua conta?
[Excluir]"), para o link de sair que só tem um ícone e para menus que agem ao escolher a
opção.

**Como sabemos:** 444 testes passando no VPS nesta data, e um teste novo que "quebra de
propósito" cada proteção importante (16 no total) e confere que o teste certo reclama — os 16
reclamaram. Um deles achou um buraco antigo no teste de apagar evento, já coberto.

**Falta:** nada para esta sessão — você rodou no Mac e o freio recusou o "Sair" e o "Excluir" do
aviso, sem clicar, e deixou o "Buscar" passar.

## 2026-09-26 — o jeito de trabalhar ganhou regras escritas

**O que mudou:** nada no que o Viking faz. Mudou como o trabalho é conduzido. As skills que você
trouxe estão instaladas no projeto, e agora existem quatro documentos novos: as decisões que você
já tomou (e o que faria cada uma ser revista), os erros que eu já cometi aqui (para não repetir),
o ponto exato onde retomar depois de um `/compact`, e esta barra.

**Como sabemos:** 324 testes passando no VPS nesta data, os mesmos 324 que passaram no seu Mac na
validação das Sessões 4 e 3b.

**Falta, para as duas parciais virarem fechadas:**
- Sessão 4: ver a redação funcionando numa página real que mostre CPF, cartão ou chave.
- Sessão 3b: usar as ferramentas de calendário pelo servidor MCP contra a sua agenda de verdade.
  Isso depende de você rodar no Mac.

**Próximo:** a Sessão 4b impede que o navegador clique em "Sair", "Excluir conta" ou "Comprar" na
sua Chrome logada. Antes de começar, preciso que você escolha a lista exata do que ele recusa.
