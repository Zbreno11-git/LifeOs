---
name: frontend-e-ux
description: Frontend e UX — olhar o artefato renderizado (desktop e celular, com cliques e latência, julgando como designer sênior), abrir o mockup antes da primeira linha, tratar texto de tela como afirmação que precisa de prova, avisos que dizem a consequência, o que mede não é o que se mostra, um fato num lugar só, cercas de erro por seção, armadilhas de formatação (espaço não separável, fuso de data), tokens de cor que existem e contraste medido sobre a cor composta, lógica pura fora do componente para ser testável, e servidor de desenvolvimento preso num estado velho. Use antes de construir ou revisar tela, componente, página pública, texto de interface, PDF ou imagem gerada.
---

# Frontend e UX — nenhuma suíte vê a tela

## Quando usar

- Antes de construir uma tela ou um componente.
- Ao escrever qualquer texto que o usuário lê: rótulo, aviso, erro, vazio.
- Ao gerar um artefato visual (PDF, imagem, e-mail).
- Ao declarar uma tela pronta para a conferência de alguém.

## Quando não usar

- Para decidir a marca (cor, tipografia, voz). Isso é do guia de marca do
  projeto, que ganha de qualquer referência externa.

## O princípio

Testes leem o disco; a pessoa lê a tela. Os defeitos mais visíveis desta casa
passaram por typecheck, lint e centenas de testes: o nome em 1,74:1 sobre foto
clara, o número da página que sumiu do rodapé, "R$ 4,2 mi / R$ 6 mi" contra um
comentário que dizia o contrário, uma data que caía no domingo, um aviso
correto que ninguém entendia. **A tela é conferida olhando.**

---

## 1. Olhar o artefato

Três coisas diferentes, e costuma-se fazer só a primeira:

| O pedido | O que exige |
|---|---|
| **Olhar** | captura em **desktop e celular**. Uma página pública é lida de pé, no telefone |
| **Clicar** | dirigir o navegador pelo fluxo inteiro, medindo o tempo, não só carregar a primeira tela |
| **Analisar como designer sênior** | hierarquia, carga cognitiva, espaçamento, contraste. Não é só confirmar que "o campo está lá" |

- **O pior caso se constrói:** título no teto de caracteres, foto clara, logo
  presente, lista vazia, lista enorme, 390 px de largura sem rolagem lateral.
- **Olhar acha o sintoma; a causa ainda se mede.** Um padrão que parecia defeito
  do véu era artefato da imagem inspecionada (variação de 1 em 255).
- **Fixture binária se decodifica antes de usar** (um "PNG branco" era amarelo
  meio transparente).
- **Telas atrás de login** precisam da sessão de alguém ou de uma rota liberada
  com autorização. Não libere rota de QA por conta própria. E cuidado com a
  sessão emprestada (ver `seguranca`).

## 2. Abrir a referência antes da primeira linha

Se existe mockup, abra-o **e renderize-o** antes de escrever código, e escreva
no código o nome do arquivo quando divergir, com o motivo. *Caso real:* uma tela
foi construída do zero em coluna única enquanto o mockup, que estava listado no
próprio plano, trazia duas colunas e o padrão "escolheu, vira uma linha com
TROCAR", que resolvia de graça a rolagem infinita produzida. **Antes de
desenhar, olhar.**

Os artefatos do mockup (achatamento de camadas, valores de exemplo) não se
portam sem medir.

## 3. Texto de tela é uma afirmação sobre o sistema

É a única afirmação que o usuário pode conferir, e ele vai repeti-la a um
cliente.

- **Pergunte: que comando eu rodaria para provar esta frase?** *Caso real:*
  "Ordenado entre os até 200 mais parecidos" ficou na tela enquanto o código
  ordenava só 21. Um rótulo errado dá resultado plausível com explicação falsa,
  e a explicação desarma a desconfiança.
- **Mecanismo e texto no mesmo commit, ou nenhum.**
- **O aviso diz a consequência, não o mecanismo.** "Sem restringir a faixa de
  área" é mecanismo. "Os imóveis comparados são muito maiores que o seu, então
  este valor é pouco confiável" é consequência. **Se o dono não entendeu, o
  usuário não vai entender.** Um aviso que não comunica cria a aparência de
  transparência.
- **O que mede não é o que se mostra.** `k/N`, pontos percentuais, `n` servem
  para calibrar. Na tela entra o argumento e, no máximo, uma direção legível sem
  treino. E **um sinal nunca vai sozinho:** uma seta vermelha ao lado de um ponto
  de venda, sem uma palavra, se lê como defeito.
- **"Tente novamente" só quando tentar de novo resolve.**
- **Página pública:** nada de escassez inventada (contador de vagas, prazo
  falso). Mostre o total cobrado, não só a parcela. O desconto anunciado é
  arredondado para baixo.
- **Um selo de "em breve"** é comparado com a página de destino **nos dois
  sentidos**: não pode negar o que abriu nem prometer o que não abriu.

## 4. Um fato, um lugar

Um dado aparece em um componente só. Nunca dois trilhos para a mesma faixa, nem
cartões repetindo os números que o trilho já mostra. Quando a mesma informação
aparece duas vezes, uma delas fica velha.

## 5. Falha com fronteira

- **Uma cerca de erro por seção**, com a API do framework, que deixa passar
  redirecionamento e "não encontrado" (uma cerca feita à mão os captura e
  transforma "sessão expirada" em "algo deu errado").
- **Uma leitura que falha não pode levar outras seções junto.**
- **Lance erros de verdade** (`new Error(msg, { cause })`), não o objeto cru do
  cliente: sem mensagem nem pilha, o erro chega exatamente quando essas duas
  seriam necessárias.
- **Ausência não é zero.** "Sem dados", "zero" e "não sei" têm aparências
  diferentes.

## 6. Formatação: o que o formatador decide por você

- **`Intl` emite caracteres que você não escolheu:** U+00A0 antes de unidade, às
  vezes U+202F, e um hífen que não é o seu. `replace("R$ ", "")` com espaço
  comum nunca casa. Case por classe (`/\s/`) e escreva o esperado do teste por
  código de ponto (`"\u00a0"`), nunca colando o caractere. Varra os arquivos
  novos por U+00A0, U+202F, U+FEFF e U+200B antes de fechar.
- **`date` não tem fuso.** Passar uma data pura pelo formatador com fuso mostra
  o dia anterior. O tipo do banco decide o leitor: `timestamptz` passa pelo
  `Intl` com fuso, `date` se lê pelo texto.
- **Função de formatação que mora dentro de um componente não tem teste.** Tire
  para uma biblioteca pura.

## 7. Cor, token e contraste

- **Toda classe utilitária de cor aponta para um token que existe.** Uma classe
  para um token inexistente não gera regra, o elemento herda `currentColor`, e
  nada acusa. Um teste sobre o CSS **compilado** pega isso.
- **Contraste se mede sobre a cor composta**, em cada fundo onde o elemento
  aparece. Uma opacidade de 55% sobre papel dá 3,6:1, abaixo do piso de 4,5.
  Meça o valor **entregue** (o hexadecimal arredondado), não o float
  intermediário.
- **Cor do usuário (marca do cliente) em vários fundos:** pode não existir cor
  que passe em fundos opostos. A derivação é por superfície, com piso de 3:1
  onde a cor não carrega palavra e 4,5:1 para texto, e **só se toca a cor que
  sumiria**, senão o cliente não reconhece a marca dele.
- **Superfície escura dentro de invólucro claro:** componentes que herdam
  `currentColor` pegam a cor do tema errado. Quem põe algo sobre fundo escuro
  declara a superfície.
- **Cor nunca é o único canal de significado.**
- **Documento para imprimir** tem papel branco (fundo tingido é tinta de
  verdade).

## 8. Testável por construção

- **A decisão sai do componente** para uma função pura, testada com fixture. O
  componente só a chama e é testado pelo HTML renderizado.
- **Se não dá para importar** (o módulo puxa cabeçalhos do servidor, sessão ou
  cliente de banco), o sintoma é esse, e varrer o texto do arquivo não resolve.
- **Uma régua por unidade de tela**, com a lista de unidades derivada do
  arquivo (ver `testes-que-provam`).
- **Âncoras de menu apontam para ids que a página declara**, com teste derivado
  das duas pontas.
- **Limites do framework se leem do pacote instalado**, não da memória nem de
  artigos (por exemplo, o tamanho máximo de corpo de uma Server Action, com o
  `413` lançado antes de a ação rodar). A documentação da **versão instalada**
  vence o que você lembra. E quando a prosa da doc contradiz os tipos, os tipos
  vencem.

## 9. O servidor de desenvolvimento mente

- Editar em dois passos um arquivo que o servidor está servindo pode deixá-lo
  preso no estado do meio (erro de símbolo inexistente, com a linha do erro
  diferente da do disco). Leia o log do servidor depois de cada mudança; se o
  erro cita uma linha que no disco é outra, reinicie o servidor (pelo PID da
  porta).
- **Typecheck com o servidor de dev no ar** pode ler tipos gerados por ele.

## 10. Ordem de construção

- **A tela que consome vem antes da métrica especulativa.** Construa a tela com
  o que já está medido e deixe que ela mostre qual métrica faz falta.
- **Valor que a tela sempre mostra é pré-calculado** pelo pipeline (ver
  `dados-e-banco`).
- **Dado antes de acabamento:** polimento de uma tela que já funciona perde para
  trabalho de dado.
- **Tela separa por superfície**, não por fio: cartões com hierarquia antes de
  uma lista corrida de itens iguais.

## 11. Acessibilidade, o mínimo

- Contraste de texto ≥ 4,5:1 em cada fundo; ≥ 3:1 para elementos não textuais.
- Significado por texto, não só por cor ou ícone.
- `aria-label` e `title` no idioma do usuário.
- Celular sem rolagem lateral; alvos de toque que caibam um dedo.
- A tela impressa (quando o usuário imprime para o cliente dele) continua legível.

---

## Testes de falha

A tela não foi conferida se:

- você não a viu em 390 px;
- não clicou até o fim do fluxo;
- existe uma frase na tela que você não saberia provar com um comando;
- o aviso descreve o que o sistema fez em vez do que isso significa para quem
  lê;
- uma classe de cor nova não foi conferida no CSS compilado;
- a lógica que decide o que aparece vive dentro do componente.

## Critério de conclusão

- [ ] Vista em desktop e celular, com o pior caso construído.
- [ ] Fluxo clicado até o fim, com o tempo medido.
- [ ] Cada frase da tela provável por um comando; avisos dizem a consequência.
- [ ] Contraste medido sobre a cor composta, em todos os fundos.
- [ ] Decisões fora do componente, testadas; componente testado pelo HTML.
- [ ] Divergências do mockup escritas no código, com o nome do arquivo.
