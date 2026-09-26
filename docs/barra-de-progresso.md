# Barra de progresso — Viking

> **Para quem é:** o dono, sem precisar abrir código. Onde um termo técnico for inevitável, ele vem
> explicado na hora. Atualizada ao fechar cada sessão, com data; os números são contados na hora,
> não copiados da versão anterior.
>
> **Como contar:** uma sessão só está "fechada" quando funcionou no Mac do dono, não quando o
> código foi enviado. Se parte dela ainda não foi testada lá, ela conta como parcial.

**Última atualização: 2026-09-26 (Sessão Gmail 2, antes do teste no Mac).**

`███████████░░░░░░░░░ 5 de 12 sessões fechadas + 3 parciais (= 6,5 de 12)`

Contagem (em `sessoes.md`): fechadas 1, 2, 3, 4b e Gmail; parciais 4, 3b e Gmail 2 (feita, falta
testar no Mac); na fila Pluggy, 5, 6 e 7 (a do Pluggy entrou hoje, a seu pedido). Cada parcial
vale meio bloco na barra.

## 2026-09-26 — limpar a caixa, com você aprovando

**O que mudou:** no `viking chat` você pode dizer "arquiva tudo da loja X e do jornal Y". O Viking
mostra, direto na sua tela, quantos e-mails saem de cada um, quantos ficam e por quê (com estrela,
marcados como importantes, com anexo nunca saem), e um código de 4 números. Só quando **você**
digita `confirma` e o código é que eles saem da caixa de entrada — arquivados, não apagados: ficam
em "Todos os e-mails". O Gemini nunca vê esse código, então um e-mail malicioso pode no máximo
fazê-lo *sugerir* uma limpeza, nunca aprová-la. Errou? `desfaz` e o mesmo código, por 7 dias,
devolve exatamente aqueles e-mails. No máximo 250 por vez: o Google só deixa o Viking conferir
cerca de 300 e-mails por minuto, e com 250 a lista aparece em mais ou menos um minuto.

**Um aviso honesto:** para arquivar, o Google só oferece uma permissão que, no papel, também
deixaria enviar e-mail e mandar para a lixeira. O Viking não usa nada disso, e um teste quebra se
alguém escrever código que use. No login, a tela do Google vai descrever essa permissão maior.

**Primeiro teste no seu Mac:** não arquivou nada — o Google recusou por excesso de consultas no
minuto (o Viking relia cada e-mail duas vezes). Consertado: ele agora anda no ritmo que o Google
permite, espera quando é recusado, e confirma sem reler. Nada se perdeu naquele teste.

**Como sabemos:** 612 testes passando no VPS, inclusive um "Gemini de mentira" tentando aprovar
sozinho e um Gmail de mentira que cobra a cota como o real, e 46 proteções quebradas de propósito, todas pegas pelo teste certo. **Falta:** rodar no
seu Mac, na sua caixa de verdade.

**Finanças (Pluggy):** medi hoje — para uso pessoal é de graça (até 5 bancos). Suas credenciais
funcionam. É a próxima sessão, depois deste teste.

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

**Validado no seu Mac:** login feito; o Viking leu os não lidos de hoje, fez o raio-x da sua
caixa real (200 e-mails de 91 remetentes em 30 dias) e respondeu às perguntas no chat — cada uma
custou menos de meio centavo de dólar. A limpeza da caixa é a próxima sessão.

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
