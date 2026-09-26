---
name: seguranca
description: Segurança por construção — a fronteira de autorização onde ela não pode ser contornada (banco/servidor, nunca a tela), guarda como primeira instrução, "por onde mais se chega lá?", superfície pública declarada e auditada nos dois sentidos contra produção, funções e endpoints que nascem abertos, oráculos, tokens fora de log, redirecionamento aberto, SSRF em renderizadores, escape de dado de terceiro, segredos, sessão emprestada, e promessas de privacidade com dono no código. Use ao desenhar autorização, criar tabela, função, rota ou ação pública, lidar com segredo ou dado pessoal, escrever texto jurídico, ou revisar um achado de scanner.
---

# Segurança por construção

## Quando usar

- Antes da primeira tabela com dado de usuário.
- Ao criar função de banco, rota, Server Action ou endpoint.
- Ao abrir qualquer coisa ao público (anônimo) ou a um papel novo.
- Ao lidar com segredo, token, dado pessoal ou texto de política.
- Ao receber um achado de scanner ou de parecer automático.

## Quando não usar

- Como substituto de uma revisão de segurança dedicada antes de lidar com
  dinheiro ou dado sensível em escala. Esta skill é o piso, não o teto.

## O princípio

> **A fronteira fica onde não dá para contorná-la. A tela é a segunda parede.**
> **E um freio só freia se for o único caminho até o recurso.**

Os achados reais foram quase todos do mesmo formato: uma proteção correta num
caminho, e outro caminho até o mesmo recurso que não passava por ela.

---

## 1. Onde fica a fronteira

- **Autorização no ponto que todo caminho atravessa**: o banco (RLS, predicado
  no corpo de funções privilegiadas) ou o servidor. Uma tela que esconde um
  botão não protege nada: o POST é alcançável sem tela.
- **A guarda é a PRIMEIRA instrução** da ação. Nem um cronômetro vem antes.
  *Caso real:* um `performance.now()` inofensivo foi posto na primeira linha, e
  um teste que exigia a guarda em primeiro lugar pegou. Instrumentação é o tipo
  de código que menos faz alguém perguntar *o que eu estou empurrando para
  baixo?*.
- **Funções privilegiadas** (que rodam com os direitos do dono) **carregam o
  predicado de acesso no próprio corpo**. Sem ele, qualquer usuário autenticado
  chama a função direto pela API de dados e lê tudo.
- **Revogar é o que perdura.** "Bloquear" um usuário precisa ser lido por toda
  checagem de acesso (papel **e** status), não só pelo login.

## 2. "Por onde mais se chega lá?"

Antes de confiar num freio (captcha, limite de taxa, verificação de origem),
enumere **todos** os caminhos até o recurso.

*Caso real:* uma função devolvia uma faixa de preço (o produto vendido) e era
"protegida" por um captcha que vivia na Server Action. A chave pública, que
está no navegador por construção, chamava a função **direto** pela API de dados.
Medido como anônimo: HTTP 200, a faixa inteira, nenhum desafio. Alguns milhares
de chamadas reconstruiriam o produto. O conserto foi tirar a função do alcance
público e deixar só o servidor chamá-la, depois do captcha.

**Uma porta pública é segura pelo que ela devolve E por não poder ser chamada em
volume.**

## 3. Superfície pública declarada e auditada

- **Toda função, rota ou tabela nasce aberta** em muitas plataformas (o papel
  público herda `EXECUTE`). A regra é revogar de todos e conceder de volta, de
  forma estreita.
- **Privilégio explícito, não herdado.** Pergunte: *esta linha muda o estado,
  ou o estado já era esse?* Um `GRANT` que parece conceder, ao lado de um
  privilégio padrão que já concedia, é uma guarda que não guarda nada, e a
  mutação que o remove fica verde. Revogue de todos e conceda a um, e a guarda
  passa a ser alcançável.
- **Não esqueça o papel de máquina.** *Caso real:* um `REVOKE` que listava os
  papéis públicos esqueceu o de serviço, que tinha acesso por privilégio padrão,
  e uma chave de máquina podia apagar inventário por URL arbitrária.
- **A lista do que é público é declarada no código**, por nome, e uma auditoria
  agendada (diária) confere **contra produção, nos dois sentidos**: alcançável e
  não declarado reprova; declarado e inalcançável também. A mesma lista é
  importada pelo teste que roda contra um schema descartável.
- **Toda função tem `search_path` fixo**, e isso vira régua derivada do
  catálogo, não disciplina.
- **Duas testemunhas de que a proteção está ligada** (as suas migrations e um
  gatilho da plataforma) são ótimas enquanto concordam. Escreva que existem
  duas.

## 4. Oráculos

Uma resposta diferente para "não existe" e "existe, mas não é seu" revela quais
ids existem.

- Token errado → **zero linhas, sem erro.**
- Um log de acesso gravado **só se o objeto existe** (a FK transformaria um id
  inventado numa exceção, e a exceção é o oráculo).
- A gravação do log fica **depois** do portão, ou ele registra que alguém viu o
  que não recebeu.

## 5. Tokens, links e redirecionamentos

- **Token em link vai no fragmento (`#t=`)**: fica fora do log do servidor e do
  `Referer`. Hash no banco, `no-referrer` e `noindex` na página.
- **Link de e-mail nunca age** (varredores abrem antes do humano).
- **Redirecionamento aberto:** a origem nunca vem do `Host` da requisição.
  *Caso real:* sem a URL pública configurada, `POST /sair` com `Host` forjado
  devolveu `303` para o site de um terceiro, levando o `redirectTo` do OAuth
  junto. A URL canônica é obrigatória e declarada no deploy.
- **Chamada de agendador a rota pública:** verificada pela identidade do
  chamador, não por uma alegação que ele mesmo escreve.

## 6. Conteúdo de fora

- **Renderizador de HTML que veio de fora** (PDF, imagem) é tratado como hostil
  ao conteúdo: JavaScript desligado, **toda requisição de rede abortada** (só
  `data:` resolve, e fontes e imagens viajam dentro do HTML), processo não-root
  e sandbox do navegador **ligado**. O teste sobe um servidor de verdade e
  afirma que ele **não recebeu nada**.
- **Dado de terceiro é dado, não sintaxe.** Escape em todo canal que interpreta
  marcação: HTML, a biblioteca de terminal que lê `[tags]`, CSV, `%` em log.
  Ao escapar um campo, olhe os vizinhos na mesma linha. *Caso real:* a URL
  estava protegida e o texto gerado por IA ao lado dela não. Uma tag válida
  **some** em silêncio; uma inválida derruba o comando depois de a chamada paga
  ter sido feita.
- **Montar HTML com template string** perde o escape automático. Use o
  renderizador do framework.

## 7. Segredos

- Nunca no git, nunca no estado da IaC, nunca numa camada de imagem (a camada
  fica no registro para sempre).
- Lidos em **um módulo só**, com régua que reprova um segundo leitor.
- Cofre de segredos, com a identidade do serviço. Nenhuma chave de conta baixada.
- Variáveis `PUBLIC_*` são públicas por definição: nada pago ou privado entra
  nelas.
- Chaves restritas (por API, por origem) e com procedência conhecida. Uma chave
  criada "para um curso" sustentando o produto é falha de procedência.
- Arquivo de configuração com dado pessoal fica fora do git **e** não é impresso
  em log nem em chat.

## 8. Sessão emprestada age sobre a pessoa

Um roteiro de cliques (Playwright) numa cópia do perfil de navegador de alguém
carrega **a mesma identidade no servidor**. *Caso real:* o roteiro clicou no
primeiro `button[type=submit]` da página, que era o "Sair" da barra lateral, e o
logout global deslogou a pessoa em todos os aparelhos.

- Clique **dentro do contêiner do formulário e pelo nome acessível**, nunca pelo
  tipo.
- Antes de dirigir uma sessão real, liste os controles que **agem sobre a
  conta** (sair, excluir, cancelar assinatura, trocar senha) e exclua-os do
  alcance do roteiro por construção.

## 9. Privacidade e texto público

- **Toda promessa de retenção tem um dono no código** e um teste que amarra a
  frase ao mecanismo. *Caso real:* a política prometia apagar um registro "junto
  com o anúncio" (dependia de um `CASCADE` que uma decisão posterior tornou
  inalcançável) e apagar dados de pedido não pago (sem dono nenhum).
- **Uma decisão de infraestrutura muda fatos que o texto público afirma.** A
  política dizia "hospedado no Brasil" e o serviço rodava nos EUA. A régua lê a
  região da configuração.
- **Log mínimo:** registre `(quem, o quê, quando)` e nada além (sem IP, sem
  user-agent, sem o dado revelado) quando o propósito não exige.
- **Texto jurídico proporcional ao tamanho**, e com o aviso de que não foi
  revisado por advogado, se não foi.

## 10. Achados de scanner

- **Leia o achado contra a arquitetura real** antes de consertar. *Caso real:*
  "bucket sem policy" num produto de armazenamento que o sistema nunca usou,
  porque as fotos moram noutro provedor.
- **Exerça o caminho que o scanner aponta**, com um controle. Um achado de
  "função executável por anônimo" foi exercido: a plataforma recusou com erro de
  tipo, enquanto a mesma chave na porta declarada respondia 200. Não explorável.
- **Documente os achados esperados.** A ausência de um achado esperado pode ser
  o defeito (uma view que precisa rodar com direitos do dono sumiu do parecer =
  alguém a alterou).
- **Revogar algo por causa de um aviso não explorável é consertar o que não está
  quebrado.**

## 11. Credenciais e acesso humano

- Credencial se estabelece pela pessoa. Na falta, pare e peça.
- Na conta real de pagamento, leitura é livre e escrita é o combinado.
- MFA, chaves legadas e permissões residuais nos painéis dos fornecedores são
  ações do dono. Liste-as como *não confirmado* se você não tem como ver.

---

## Testes de falha

Há uma porta aberta se:

- uma checagem de acesso existe só no componente de tela;
- existe um freio (captcha, limite) e você não listou os outros caminhos até o
  recurso;
- uma função nova foi criada sem `REVOKE` explícito;
- a lista do que é público não existe, ou não é conferida contra produção;
- um token aparece em query string;
- a origem de um redirecionamento vem da requisição;
- um roteiro automatizado pode clicar em "Sair".

## Critério de conclusão

- [ ] Fronteira no banco/servidor, e a guarda é a primeira instrução.
- [ ] Todos os caminhos até o recurso enumerados.
- [ ] Superfície pública declarada e auditada nos dois sentidos.
- [ ] Nenhum oráculo nos caminhos anônimos.
- [ ] Segredos num leitor único, fora do git, do estado e das camadas.
- [ ] Cada promessa pública de retenção e hospedagem tem dono e teste.
