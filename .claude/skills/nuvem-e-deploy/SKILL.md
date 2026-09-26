---
name: nuvem-e-deploy
description: Infraestrutura, deploy, CI e operação — escolher o runtime (lote ou alguém esperando), infraestrutura como código sem segredo no estado, imagem com tag do commit, "o que está no ar?" medido por describe e "o que entrou no código desde então?", ordem de deploy entre serviços, migrations e auditorias, variáveis de ambiente declaradas onde o deploy as entrega, deploy por script que lê antes e pede ok por passo, verificação depois do deploy (versão, domínio, DNS, TLS), agendadores, CI que verifica e não publica, custo e credenciais. Use ao mexer em IaC, Dockerfile, build, deploy, CI, domínio, agendador ou credencial de nuvem, e ao fechar qualquer trabalho que muda produção.
---

# Nuvem e deploy — o repositório não é o mundo

## Quando usar

- Ao escolher onde e como algo roda.
- Ao mexer em Terraform/IaC, Dockerfile, pipeline de build, CI.
- Antes, durante e depois de qualquer deploy ou escrita em produção.
- Ao fechar uma sessão cujo trabalho muda algo agendado ou servido.

## Quando não usar

- Para decidir o que o código faz. Esta skill é sobre como ele chega ao mundo e
  como se sabe que chegou.

## O princípio

Commit, push e CI verde fecham *o código está certo?*. Nenhum dos três toca *o
defeito parou de acontecer?*. Enquanto a imagem velha roda, o defeito corrigido
continua acontecendo no horário agendado dele. E a pior forma disso é quando
**ninguém afirma nada errado**: o commit está verde, o handoff descreve o
conserto, e nada em lugar nenhum diz *"isto não está rodando"*.

---

## 1. Escolher o runtime

- **Se alguém está esperando, é serviço; se é lote, é job.** Um job não tem
  endereço HTTP; um serviço que roda lote paga por ficar ocioso ou por
  timeout.
- Compare **execução sob demanda, agendamento, custo ocioso, escala a zero,
  retries e observabilidade nativa** (a plataforma registra "execução falhou"?).
- **Custo fixo mensal versus escala a zero.** *Caso real:* um balanceador de
  carga global custava ~US$ 18/mês fixos, o único item que não escalaria a zero,
  e foi recusado até haver receita. O serviço mudou de região para usar o
  mapeamento de domínio nativo. O gatilho para voltar ficou escrito: receita.
- **Isole o que tem perfil de risco diferente.** Um renderizador de HTML externo
  com navegador headless roda num serviço separado, com a própria memória, a
  própria escala e as próprias paredes de segurança.
- **Não crie um serviço novo sem o gatilho que o justifica** (latência de
  request-response que um job não serve, GPU). Escreva esse gatilho antes.

## 2. Infraestrutura como código

- **Nenhum segredo passa pela ferramenta de IaC.** O estado é um arquivo, e o
  provider grava nele tudo o que leu. A IaC cria o cofre **vazio**; o valor entra
  por fora.
- **Estado remoto, versionado, com acesso público bloqueado.** Estado num disco
  só significa que numa máquina nova o `plan` mostra toda a infraestrutura como
  "a criar", e o comando não avisa.
- **Valores de configuração persistentes moram num arquivo de variáveis, nunca
  em `-var`.** O próximo `apply` que esquecer a flag reverte em silêncio. *Caso
  real:* uma flag de funcionalidade passada por linha de comando desligaria o
  recurso no deploy seguinte. Se o arquivo de variáveis fica fora do git (tem
  dado pessoal), guarde uma cópia num cofre e confira por hash antes de aplicar.
- **Proteja contra destruição o que derruba o produto** (domínio, banco,
  bucket). *Caso real:* sem a variável de URL pública, o `plan` propunha destruir
  o mapeamento de domínio e apagar a variável que fechava um redirecionamento
  aberto. Com `prevent_destroy`, a ferramenta recusa o plano inteiro.
- **Recurso criado à mão é adotado por `import`.** Um `plan` que diz *create*
  para ele recriaria o recurso.
- **Declare os padrões que a API devolve**, senão todo `plan` propõe removê-los:
  deriva perpétua, que aparece até num deploy sem relação.
- **Lock do provider para todas as plataformas** das máquinas que rodam a IaC.
- **Com `-target`, os outputs não se atualizam.** O valor impresso logo abaixo
  de *Apply complete!* é o do último apply completo. Quem responde é o
  `describe` do recurso.
- **Mostre o `plan` ao dono antes do `apply`**, e aplique só o plano salvo, se
  ele tocar **exatamente** os recursos esperados.

## 3. Imagens e build

- **A tag é o SHA do commit.** Saber qual código produziu qual número é a
  diferença entre investigar e adivinhar. Serviços diferentes têm tags
  **independentes** e sem padrão: a mesma tag para dois faria o deploy de um
  trocar o código do outro.
- **A imagem de job não precisa subir sozinha**, e pode ser decisão (publicar é
  ato deliberado). Mas então o fechamento precisa perguntar se ela subiu.
- **Revise o que entra no build:** o que o Dockerfile copia, linha por linha; o
  que os arquivos de ignore excluem (pode haver dois, e a ferramenta de upload
  pode não ler o do Docker); se nenhum segredo sobe; `git status` limpo e sem
  trava de processo que reescreve fontes; as variáveis que a imagem fixa. *Caso
  real:* o contexto de build subia 1 GiB por causa de um cache de build; depois
  do ajuste, 7,7 MiB.
- **Builds "standalone" podem não copiar os assets estáticos.** O contêiner
  sobe, o healthcheck passa e a página abre sem CSS. Um `RUN test -f` no
  Dockerfile para os arquivos que não podem faltar reprova o build.
- **A conta de serviço do build é estreita**, nunca a padrão com papel de editor
  no projeto.

## 4. O que está no ar

Duas perguntas diferentes. Faça as duas:

1. **A imagem no ar é qual commit?** Use `describe` do recurso, não documento,
   não memória, não output da IaC.
2. **O que entrou no código desde a imagem no ar, nos caminhos que o Dockerfile
   copia?** `git rev-list --count <tag>..HEAD -- <caminhos>`. *Caso real:* a
   primeira pergunta respondeu "sim" seis vezes seguidas enquanto um serviço
   estava **seis commits atrás**, sem a rota que o outro serviço já chamava.
   Uma imagem que não é reconstruída há dias não tem um defeito pendente: tem a
   fila inteira.

E a prova final é **exercer o código novo dentro da imagem no ar**, não inferir
da tag.

- **Saúde mede vida, não versão.** Para saber se o processo tem a rota nova,
  confira o contrato dele (`/openapi.json`, uma rota de versão).
- **Migrations:** as do disco estão aplicadas? O `--dry-run` do ledger responde.

## 5. Ordem de deploy

- **Quem fornece sobe antes de quem consome.** Um serviço que passa a chamar uma
  rota nova de outro exige que o outro suba primeiro, no mesmo movimento.
- **Migration × código:** o código que lê um objeto novo sobe depois da
  migration, ou nasce tolerante à ausência. Uma auditoria cuja régua mede o que
  a migration cria sobe **antes** da migration. As duas direções existem, e a
  frase do passo precisa dizer qual vale, porque um script não sabe distinguir.
- **Deploy que muda a régua de uma auditoria sobe duas imagens**, não uma.

## 6. O deploy como script, não como documento

Um runbook de nove passos em prosa tem um passo que ninguém executa há meses, e
ele diverge. O que funcionou:

- **Sem flag, o script só lê:** tag no ar de cada imagem, commits desde ela nos
  caminhos que o Dockerfile copia (derivados dos Dockerfiles, não de uma lista),
  migrations pendentes pelo `--dry-run`, o arquivo de variáveis contra o cofre
  por hash, e o CI do HEAD pelo SHA.
- **Com `--executar`, pede "ok" digitado antes de cada passo**, e o plano salvo
  só é aplicado se tocar exatamente os recursos das imagens trocadas.
- **As provas rodam sempre.** *Caso real:* com o plano já vazio, `--so provas`
  respondeu "nada a subir" com exit 0, sem provar nada. Um vigia que fala verde
  sem ter olhado.
- **O comando documentado é amarrado por teste** ao arquivo de build que ele
  usa. Um runbook que ensina um comando que não roda dorme até o dia em que
  alguém precisa dele.

## 7. Variáveis de ambiente e configuração

- **Toda variável lida pelo código está declarada onde o deploy a entrega:** no
  serviço (execução) ou como argumento de build (embutida no bundle). Uma régua
  derivada do código reprova a que falta. *Caso real:* uma flag vivia só no
  `.env` local; ela fecha por padrão, e o recurso rodou desligado em produção
  com o único sintoma sendo um travessão num log.
- **Página pré-renderizada congela o valor em tempo de build.** Ler em execução
  não alcança página já gerada.
- **A URL pública canônica é obrigatória.** Sem ela, a origem cai nos cabeçalhos
  da requisição, que um cliente escolhe (ver `seguranca`, redirecionamento
  aberto).

## 8. Depois do deploy: provar

- **Domínio de pé** se responde pelo aperto de mão TLS, e **sustentado** (10 de
  10). A condição "certificado provisionado" conviveu 68 minutos com o TLS
  falhando, e durante a distribuição a taxa real foi de 3 em 20.
- **DNS** se pergunta ao autoritativo.
- **Fumaça que exerce os caminhos com sessão**, não só os anônimos. Uma fumaça
  de 13/13 passou com o login quebrado.
- **Fumaça que exerce a recusa**, não só o sucesso: a ação pública recusa quem
  não passou pelo porteiro?
- **Logs da revisão nova**, filtrados pelo campo que o código escreve.

## 9. Agendadores

- **Fuso explícito** no agendador, e escrito no documento. "Segunda às 04:00"
  sem fuso é duas horas diferentes.
- **Agendador HTTP que chama rota pública:** verifique o token pela
  **identidade** (o e-mail da conta), não pela `audience`, que é alegação livre
  de quem pede o token.
- **Constantes que dependem da cadência** (um corte de defasagem que depende do
  dia do mês do agendamento) são amarradas por teste ao arquivo de agendamento.

## 10. CI: verifica, não publica

- **O CI não tem segredo de produção** e não publica. O Postgres do CI nasce e
  morre com o job.
- **Leia o `on:` de cada workflow antes de agrupar arquivos num commit.** Um
  filtro que ignora `docs/**` convive com outro que dispara em cinco arquivos de
  documentação lidos por testes. Generalizar de um workflow para "os workflows"
  cancelou a medição que fechava uma sessão.
- **Filtro de caminho olha o push inteiro; a marca de pular CI é lida no commit
  do topo, no título ou no corpo.** Um corpo que **cita** a marca para explicá-la
  pula o CI.
- **`cancel-in-progress` cancela o run anterior por desenho.** `cancelled` é
  normal.
- **A pergunta de fechamento** não é *o CI do HEAD está verde?*. É *qual foi o
  último commit que tocou cada caminho vigiado, e o run dele fechou verde?*.
  Confira pelo `headSha`: um filtro que devolve lista vazia passa por "ainda
  rodando".
- **Um filtro de caminho precisa acompanhar o que os testes leem.** Se os testes
  de A leem arquivos de B, o workflow de A dispara em B, e um teste deriva isso
  dos testes, não de uma lista escrita à mão.
- **Minutos pagos são decisão de gasto.** Agrupe commits; rode localmente os
  portões que o CI rodaria; quando o CI aponta poucas falhas, reverifique
  localmente em vez de pagar outra rodada. **Economizar é disparar menos, nunca
  pular o portão.**

## 11. Credenciais

- **Login da CLI e credencial de aplicação são duas coisas.** Uma sem a outra
  falha com cara de permissão.
- **`403` com conta ativa é IAM, não login.** Não mande refazer login por
  problema de papel.
- **`PERMISSION_DENIED` sem nomear a permissão → log de auditoria** antes de
  repetir.
- **Nenhuma chave de conta de serviço baixada.** Credencial por identidade
  anexada.
- **Credencial se estabelece pela pessoa.** Se falta, pare e peça. Procurar
  outra via que funcione é contornar o controle de acesso.
- **`printf '%s'`, nunca `echo`**, ao gravar um segredo.

## 12. Custo e operação

- **Rótulos de custo em todo recurso** e orçamento com alerta. Sem eles, *quanto
  foi a coleta e quanto foi a IA* é suposição.
- **Custo pequeno e fixo de infraestrutura é operação, não deliberação:** avise
  numa linha. **Custo que escala com uso** (chamada paga por item) precisa de
  teto no código, imposto na entrada.
- **Um runbook tem dono primário e secundário, consumidores a jusante e SLA.**
  A linha que mais importa é a dos consumidores: no dia em que o primeiro
  consumidor aparece, nada no código avisa que agora existe alguém do outro
  lado.
- **"Ainda não endurecido", com a data em que passa a doer.** Por exemplo:
  conta pessoal sem MFA aceitável até entrar dado de cliente. A condição fica
  amarrada a um marco, não a "um dia".
- **Trabalho pesado vai para a nuvem; latência se mede lá.** A rede de casa não
  mede nada sobre produção.

---

## Testes de falha

Você está afirmando um estado que não mediu se:

- disse "está no ar" sem `describe`;
- conferiu a tag e não o que entrou no código desde ela;
- o `plan` foi aplicado sem ninguém ler;
- uma variável nova no código não tem declaração no deploy;
- a fumaça passou sem exercer sessão nem recusa;
- "domínio de pé" veio de um `200` solto;
- ofereceu o deploy como passo opcional de uma dívida.

## Critério de conclusão (de um deploy)

- [ ] O plano tocou exatamente o esperado; foi lido e autorizado.
- [ ] `describe` de cada imagem = o commit pretendido; nada pendente nos
      caminhos copiados.
- [ ] Migrations do disco = ledger; auditoria com a régua certa antes da próxima
      execução.
- [ ] Provas: versão do processo, domínio 10/10, fumaça com sessão e com recusa,
      logs da revisão sem erro.
- [ ] Documento de progresso com as provas **literais** e o horário.
