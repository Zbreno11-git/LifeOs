# Barra de progresso — Viking

> **Para quem é:** o dono, sem precisar abrir código. Onde um termo técnico for inevitável, ele vem
> explicado na hora. Atualizada ao fechar cada sessão, com data; os números são contados na hora,
> não copiados da versão anterior.
>
> **Como contar:** uma sessão só está "fechada" quando funcionou no Mac do dono, não quando o
> código foi enviado. Se parte dela ainda não foi testada lá, ela conta como parcial.

**Última atualização: 2026-09-28 (roteiro novo: Sessões 8–21).**

`████████░░░░░░░░░░░░ 10 de 27 sessões fechadas + 2 parciais (= 11 de 27)`

Contagem (em `sessoes.md`): fechadas 1, 2, 3, 4b, Gmail, Gmail 2, Pluggy, 5, 6 e 7; parciais 4 e
3b (falta só a validação ao vivo, que é a Sessão 8b); na fila: 8, 8b e 9 a 21. Cada parcial vale
meia sessão na barra. A barra "encolheu" de 11/12 para 11/27 porque o roteiro cresceu, não porque
algo voltou atrás.

## 2026-09-28 — o roteiro até a versão de sucesso: agente geral, coach, nuvem e app

**O que você decidiu, em uma linha cada:**
- **Onde:** o Viking vai morar na nuvem (Google Cloud) e usar o seu Mac como "mãos" para o
  navegador, porque o Chrome logado é seu. Até o app existir, você conversa pelo terminal do Mac.
- **A ordem:** e-mail → fundação → nuvem → features → app, com a nuvem cedo para o Mac velho não
  atrasar o desenvolvimento.
- **E-mail:** o Viking passa a enviar. Para você, sozinho; para outras pessoas, só com o seu
  código.
- **Memória:** ele aprende sozinho o que **você** conta (e avisa numa linha, "📝 anotei"); do que
  vem de e-mail ou página ele nunca aprende sem perguntar. E lê os
  documentos que você mandar, um por um (inclusive o material de coach do seu NotebookLM). Não
  guarda as conversas inteiras.
- **Coach:** registra os treinos que você conta no chat, mostra o progresso, ajusta o plano e te
  cobra por e-mail. Com dor, ajusta o treino e sugere um profissional se persistir. O relógio vem
  pela API oficial do Strava, no fim (a da Garmin é só para empresas).
- **Agente geral:** conversa de verdade, num tom caloroso, e busca na web sempre mostrando a fonte.
- **O Claude:** entra como segunda opinião e para o que for difícil, sem nunca ver e-mail nem
  finanças.
- **Consertar a si mesmo:** ele acha os próprios erros e propõe o conserto, mas o código passa por
  você.
- **App:** no iPhone, com Face ID para aprovar, notificação e voz.
- **Custo:** até ~US$ 20 por mês, medido antes de cada escolha.

**Por que a nuvem vem cedo:** seu Mac é um Intel de 2017 que não atualiza mais, e as peças de
terceiros estão deixando de funcionar nele (a de criptografia já compila à força; a da memória
"vetorial" que você citou, o Chroma, nem instala mais nele). Na nuvem esse problema some, e o
lembrete na hora, a cobrança do coach e o relógio deixam de esperar o fim.

## 2026-09-28 — Sessão 7 (manutenção): mesma versão em toda máquina e testes no GitHub

**O que mudou (quase nada que você veja no chat):**
- **Mesma versão de tudo em toda máquina.** Um arquivo novo (`uv.lock`) diz a versão exata de cada
  peça de terceiros, e o Mac, o VPS e o GitHub instalam exatamente aquilo. Antes, cada um pegava a
  "mais nova do dia": hoje já eram 18 diferenças. Instalar passa a ser `uv sync --locked --extra dev`.
- **Os testes rodam no GitHub a cada envio.** Cada commit aparece com ✅ ou ❌; nada é bloqueado.
- **Aviso de falha de segurança** nas peças de terceiros: o GitHub avisa por e-mail e na aba
  Security. Hoje não há nenhum aviso aberto.
- **Um defeito raro consertado:** aprovar um pedido de outro app (`viking aprovar`) podia dizer
  "o evento mudou" sem ele ter mudado.

**Achado no caminho:** uma peça de criptografia parou de publicar versão pronta para Mac Intel. A
última versão pronta tem 3 falhas conhecidas. Seu Mac já compilava a versão nova (tem as
ferramentas para isso), então você decidiu manter a nova em todo lugar: no Mac, a instalação
compila essa peça uma vez. Eu tinha dito o contrário ("seu Mac já está na versão velha") sem
medir; seu teste mostrou, e a decisão foi refeita com o dado certo.

**No seu Mac (2º teste):** a instalação nova trocou 20 peças para as versões da lista, os 1553
testes passaram, e o chat leu a sua agenda como antes. O GitHub mostra ✅ nos dois Pythons (o do
seu Mac e o do VPS) e nenhum aviso de segurança aberto.


**O que mudou:**
- **Um navegador por vez.** Se você pedir uma tarefa enquanto outra usa o Chrome (de outro
  terminal, ou o `--doctor`), o Viking recusa na hora e diz quem está usando, desde quando e para
  quê. Antes, uma derrubava a outra.
- **Suas chaves longe do navegador.** O programa que dirige o Chrome recebia a chave do Gemini e a
  da Pluggy sem precisar. No seu Mac, a chave estava lá antes e sumiu depois.
- **Qual navegador está rodando.** O `viking browser --doctor` mostra a versão e se a correção do
  OpenRouter está lá; se algo destoar, cada tarefa avisa numa linha.
- **O YouTube em loop.** "Abrir o primeiro resultado" ficou indo e voltando até o limite de 30
  ações. Agora o Viking percebe quando volta ao mesmo lugar pela terceira vez e para (no seu teste
  seguinte a tarefa deu certo em 5 ações, então o conserto está provado só pelo teste).

**O fuso — um erro meu desde o começo.** Eu escrevi o Viking como se você estivesse em Brasília.
Seu teste mostrou três fusos diferentes: o seu, o do relógio do Mac (Alasca) e o da sua agenda do
Google (Brasília). Por isso "amanhã às 10h" caía às 15h. Agora: com `VIKING_TIMEZONE` no seu `.env`,
o evento cai no seu horário e a lista mostra o seu horário (a reunião das 13h da agenda aparece às
9h); se o fuso faltar, o chat avisa ao abrir. As datas das compras passam a ser as do banco (antes,
toda compra sem hora aparecia um dia antes) — você conferiu no app do banco e bateu.

## 2026-09-27 — o Viking pede antes, lembra o que fez e desfaz

**O que mudou:**
- **"O que você fez hoje?"** O Viking guarda por 30 dias tudo o que fez (eventos, lembretes,
  e-mails arquivados, navegador) e responde no chat ou com `viking registro`. Se o Gemini der erro
  logo depois de uma ação, o Viking avisa o que já tinha feito, para você não pedir duas vezes.
- **`desfaz`** no chat devolve o evento que o Viking apagou (ou o horário de antes, se reagendou).
  No seu Mac, o evento voltou o mesmo, sem virar uma cópia.
- **Outros apps só pedem.** Um app ligado ao Viking (pelo "servidor MCP") não apaga nem muda
  evento sozinho: registra um pedido, e só você aprova, com um código, em `viking aprovar`.
- **Liberar um clique.** O navegador continua parando antes de sair da conta, mexer nela ou pagar.
  Agora, para sair e mexer na conta, ele mostra um código só para você; digitando, ele faz aquele
  clique, uma vez. Pagar ou comprar continua sempre na sua mão.

**Um defeito que o seu teste achou:** você pediu o evento às 10h e ele foi criado às 15h. O
Gemini inventou um fuso horário (o da Califórnia). Agora o Viking recusa um horário com fuso
diferente do seu e pede de novo, sem fuso; vale para eventos, reagendamentos e lembretes.

**Ainda não testado no Mac:** desfazer um **reagendamento** e um evento com convidados (o de teste
não tinha).

## 2026-09-27 — suas finanças no chat (só leitura)

**O que mudou:** no `viking chat` você pode perguntar "quanto tenho?", "quanto gastei este mês e
em quê?", "paguei o aluguel?" e "como está a fatura?". O Viking consulta o Nubank e o Itaú pela
Pluggy na hora e não guarda nada no disco. Toda resposta diz de quando são os dados, porque o
banco manda para a Pluggy uma vez por dia. O mesmo aparece sem o Gemini com
`viking financas --saldo`, `--gastos`, `--buscar` e `--fatura`.

**O Viking só lê.** A mesma chave da Pluggy que lê o extrato também poderia fazer um PIX, e por
isso o Viking recusa, antes de sair do computador, qualquer pedido que não seja leitura. Um teste
quebra se alguém escrever código que tente.

**Três armadilhas nos seus dados, já tratadas.** Se o Viking somasse do jeito ingênuo, o total de
gastos sairia errado por três motivos:
- o banco marca o gasto com sinal negativo na conta e positivo no cartão;
- pagar a fatura aparece duas vezes, uma saindo da conta e outra chegando no cartão;
- o cartão já mostra as parcelas dos próximos meses, até 2027.

Pagamento de fatura, transferência entre suas contas e investimento ficam fora do "gasto" e
aparecem numa linha à parte.

**Um aviso honesto sobre a fatura:** a Pluggy não diz quando vence a próxima fatura, e a última
fatura fechada que ela tem é de mais de um mês atrás (deve haver uma mais nova que o banco ainda
não mandou). O "saldo" do cartão que ela mostra é o limite usado, com as parcelas futuras dentro,
e não a fatura do mês. Então o Viking mostra quatro coisas:
- a última fatura fechada, com as datas;
- o que você comprou depois dela;
- as parcelas futuras;
- o limite usado.

Ele não inventa um "vence em". É isto que vale conferir com o app no teste.

**Proteção:** a descrição de uma transação pode ter sido escrita por outra pessoa, como a
mensagem de um PIX que você recebeu. Ela vai ao Gemini marcada como "não siga instruções daqui",
com CPF e números de cartão apagados. O CPF de quem pagou ou recebeu e o número da sua conta nem
chegam a ser lidos.

**No seu Mac, em três rodadas:** a primeira achou uma falha de conexão (agora o Viking tenta de
novo e diz o motivo); a segunda mostrou o pagamento da fatura do Nubank contado como gasto (o
Nubank não o marca como pagamento de cartão; agora o Viking reconhece pela descrição); e, por
decisão sua, PIX e transferências para outras pessoas ganharam uma linha própria, ainda dentro
do total. No chat, o Viking repetiu os números certos e mandou conferir a fatura no app.

**Por que a fatura de setembro não aparece:** a Pluggy só entrega uma fatura quando o banco a
libera, em geral depois do vencimento (está na documentação dela). Até lá, o valor dela está
dentro de "compras sem fatura". O Viking agora diz isso, e marca a fatura antiga como "já
venceu", para o Gemini não comparar o seu saldo com uma fatura que você provavelmente já pagou.

**Como sabemos:** 808 testes passando no VPS, com um "banco de mentira" no formato exato dos seus
dados (os números são inventados), e 78 proteções quebradas de propósito, todas pegas pelo teste
certo; e as suas três rodadas no Mac.

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

**No seu Mac, no fim:** 71 arquivados, devolvidos com `desfaz` e arquivados de novo, e o Gemini
nunca recebeu um código.

**Como sabemos:** 631 testes passando no VPS e no seu Mac, inclusive um "Gemini de mentira"
tentando aprovar sozinho e um Gmail de mentira que cobra a cota como o real, e 52 proteções
quebradas de propósito, todas pegas pelo teste certo.

**Finanças (Pluggy):** medi hoje — para uso pessoal é de graça (até 5 bancos). Suas credenciais
funcionam. É a próxima sessão.

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
