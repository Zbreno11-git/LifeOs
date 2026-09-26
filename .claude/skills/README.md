# Skills globais

Estas skills levam para outros projetos o modo de trabalhar que tornou a
construção do projeto de origem mais confiável ao longo de trinta sessões. Elas **não**
são uma cópia genérica do projeto de origem: nada aqui depende de imobiliária, de Supabase, de
Cloud Run ou de Stripe. O que ficou foi o princípio por trás de cada regra que
sobreviveu, junto com o erro real que a criou.

Estão em português do Brasil. Os casos citados vêm de incidentes reais, contados
sem os nomes do projeto de origem.

---

## A pergunta que gerou o conjunto

> *O que tornou o nosso modo de trabalhar mais confiável, eficiente e inteligente
> ao longo do tempo?*

A resposta, em seis ideias. Cada skill é uma delas levada à prática:

1. **A falha cara é a silenciosa.** Um sistema que quebra alto é consertado no
   mesmo dia. O caro é o que continua funcionando com menos e parece saudável.
   Diante da escolha entre fazer mais e errar mais alto, errar mais alto ganha.
2. **Documentação nossa registra uma medição passada; ela não é evidência.**
   O erro que mais se repetiu foi aceitar um texto nosso como se fosse medição.
   A pergunta que resolve é: *quem mediu isto, quando e com qual comando?*
3. **Uma verificação responde uma pergunta mais estreita do que parece.** Teste
   verde, CI verde, `/saude` 200 e "a imagem é o HEAD" viveram, cada um, ao lado
   de um defeito real. Por isso se pergunta *se isto ficar verde, quantas
   explicações diferentes esse verde admite?* E por isso se testa o teste
   (mutação).
4. **Estrutura vence disciplina.** Tudo o que dependia de alguém lembrar acabou
   divergindo: listas escritas à mão, cópias de documentação, espelhos entre
   dois idiomas. O que parou de divergir foi derivado da fonte, virou tipo ou
   ganhou teste que compara as duas pontas.
5. **O repositório não é o mundo.** Commit, push e CI verde fecham a pergunta *o
   código está certo?*. Eles não fecham *o defeito parou de acontecer?*. O
   estado do que está no ar se mede, não se deduz.
6. **Continuidade mora no disco.** Sessões curtas com fim verificável, um
   diário, um documento de progresso e um catálogo de erros usado como catálogo
   de padrões. O contexto de uma conversa acaba, e o que não foi escrito se
   perde com ele.

---

## As skills, e por que cada uma merece existir

| Skill | O que faz | Por que existe (o que ela sabe que não sai por padrão) |
|---|---|---|
| [`software-build`](software-build/SKILL.md) | Inicia, conduz e mede um projeto em sessões, ou avalia a maturidade de um projeto que já existe | Sem ela o trabalho vira uma conversa longa sem memória: dívida que se esquece, "pronto" que só está no repositório, decisão tomada por quem não devia. Ela traz a definição de pronto em degraus, as regras de quem decide o quê e a revisão em duas passadas |
| [`pre-compact`](pre-compact/SKILL.md) | Deixa o trabalho num ponto seguro antes de um `/compact` ou de uma conversa nova, e prepara a retomada | Depois do compact só sobra o que está no disco. Ela gera o bloco de retomada e o prompt pronto para a primeira mensagem, e define o que o contexto novo deve conferir antes de confiar no bloco |
| [`evidencia`](evidencia/SKILL.md) | Disciplina para afirmar um número, uma causa, um estado ou uma ausência | Cobre o erro mais repetido (documentação tomada por medição), ensina a separar hipótese de fato e a ler a saída de ferramenta sem se enganar. Serve para qualquer relatório, não só para código |
| [`falha-ruidosa`](falha-ruidosa/SKILL.md) | Confiabilidade e observabilidade: fazer o sistema errar alto | O padrão de falha mais caro que achamos foi o estado plausível e errado. Ela traz as camadas de confiança, os códigos de saída, o registro de execução, os alertas e a separação entre falha transitória e definitiva |
| [`testes-que-provam`](testes-que-provam/SKILL.md) | Testes e qualidade: testar onde a decisão acontece, e testar o teste | Suíte verde é o sinal mais enganoso que temos. Ela ensina a medir o alcance de uma verificação, a fazer teste por mutação sem mutação inerte, a usar fixture de incidente real e a testar a sequência de eventos, não só um evento |
| [`depuracao`](depuracao/SKILL.md) | A ordem de suspeita diante de um defeito, e as armadilhas das ferramentas | Já se perdeu uma hora culpando uma IA por um defeito que estava no nosso schema, e já se "consertou" código que estava certo. Ela diz por onde começar e como separar hipóteses com um controle |
| [`dados-e-banco`](dados-e-banco/SKILL.md) | Migrations, idempotência, tabelas derivadas, ciclo de vida, tipos e medição sobre dados | O dado errado se propaga em silêncio para tudo que o lê. As lições aqui (migration aplicada que não se edita, contador que não aguenta reenvio, tabela derivada sem validade) valem em qualquer banco |
| [`integracoes`](integracoes/SKILL.md) | Terceiros: APIs, webhooks, pagamentos, LLM, e-mail e dependências | O contrato de um terceiro só se prova quando a requisição sai. Aqui estão a taxonomia de falha de webhook, o modo declarado versus o deduzido e a ordem de investigação quando a saída de um LLM parece ruim |
| [`nuvem-e-deploy`](nuvem-e-deploy/SKILL.md) | Infraestrutura, deploy, CI e operação | O deploy junta metade dos erros da categoria "o repositório não é o mundo": a imagem atrasada, a variável que falta no contêiner, o output velho do Terraform, o domínio "de pé" que respondia 3 vezes em 20 |
| [`seguranca`](seguranca/SKILL.md) | Onde fica a fronteira, superfície pública declarada, segredos e privacidade | O que se aprendeu: a fronteira fica onde não dá para contorná-la, e um freio só freia se for o único caminho. Ela traz a auditoria nos dois sentidos, oráculos, SSRF e sessão emprestada |
| [`frontend-e-ux`](frontend-e-ux/SKILL.md) | Tela, texto de interface, design tokens, acessibilidade e o artefato renderizado | Nenhuma suíte vê uma tela. Ela ensina a olhar o que foi renderizado (desktop e celular, com cliques) e a tratar uma frase na tela como afirmação que precisa de prova. Traz também as armadilhas de formatação e de cor que passam em todo teste |

Onze skills. As que foram fundidas, as que não entraram e as práticas que **não**
deveriam ser generalizadas estão em [`REVISAO-CRITICA.md`](REVISAO-CRITICA.md).

---

## Quando usar cada uma

| Situação | Skill |
|---|---|
| Começar um projeto, abrir ou fechar uma sessão, planejar uma fase | `software-build` |
| "Como está este projeto?", avaliar maturidade, auditoria de processo | `software-build` (modo avaliação) |
| Vai rodar `/compact`, abrir uma conversa nova ou passar o trabalho a outro agente | `pre-compact` |
| Acabou de voltar de um compact | `pre-compact` (seção "Depois do compact") |
| Afirmar um número, uma causa, "está no ar", "não existe" ou "funciona"; escrever relatório | `evidencia` |
| Desenhar um job, pipeline, alerta, veredito ou tratamento de erro | `falha-ruidosa` |
| Escrever ou revisar teste, montar teste por mutação, decidir se um portão prova algo | `testes-que-provam` |
| Algo quebrou, está lento ou dá um número estranho | `depuracao` |
| Migration, schema, escrita concorrente, tabela derivada, consulta de medição | `dados-e-banco` |
| API de terceiro, webhook, cobrança, LLM, e-mail, dependência nova | `integracoes` |
| Build, deploy, Terraform/IaC, CI, domínio, agendador, custo de nuvem | `nuvem-e-deploy` |
| Autorização, superfície pública, segredo, dado pessoal, texto jurídico | `seguranca` |
| Tela, componente, texto de interface, cor, PDF ou imagem gerada | `frontend-e-ux` |

---

## Como combinar

As skills se chamam umas às outras. Os caminhos mais comuns:

**Projeto novo.** `software-build` (modo iniciar) cria os documentos e o
primeiro plano. `falha-ruidosa` e `seguranca` entram no desenho **antes** do
primeiro código, porque é mais barato nascer errando alto do que reformar depois.

**Uma sessão de trabalho.** `software-build` abre (leitura, estado do
repositório e do mundo) → a skill técnica da área → `testes-que-provam` antes
de dar a etapa por pronta → `software-build` fecha (revisão em duas passadas,
diário, progresso).

**Antes de escrever em produção** (migration, deploy, dado, segredo):
`nuvem-e-deploy` (ordem e conferência) + `dados-e-banco` (dry-run, réplica) +
`evidencia` (o que eu sei de fato sobre o estado atual?) + a autorização na hora,
regra de `software-build`.

**Incidente.** `depuracao` (ordem de suspeita) → `evidencia` (o que é causa
medida e o que é hipótese) → `falha-ruidosa` (por que não gritou? o conserto
tem de fazer gritar da próxima vez) → registro no catálogo de erros
(`software-build`).

**Fim do dia ou compact.** `pre-compact`.

---

## Como levar o conjunto para um projeto novo

1. **Copie as pastas** para `.claude/skills/` do repositório, se forem valer só
   nele, ou para `~/.claude/skills/`, se forem valer em todos os projetos. Cada
   skill é uma pasta com um `SKILL.md`, e algumas têm uma subpasta `modelos/` ou
   `referencia/`.
2. **Rode `software-build` no modo iniciar.** Ela cria o esqueleto de
   documentos a partir de [`software-build/modelos/`](software-build/modelos/):
   primer, roadmap, progresso, diário, catálogo de erros, decisões e barra de
   progresso. Se o projeto já existe, rode o modo avaliação primeiro. Ele diz o
   que falta sem obrigar a criar tudo.
3. **Se houver mais de um agente** (por exemplo, Codex lendo `AGENTS.md` e
   Claude lendo `CLAUDE.md`), mantenha **uma** fonte e aponte para ela das
   duas: import (`@caminho`) de um lado, ponteiro do outro. Nunca duas cópias.
4. **Ajuste os parâmetros do projeto.** Idioma, quem é o dono das decisões,
   quais portões existem, o que custa dinheiro, o que é irreversível. As skills
   falam em "o dono" e em "portões" justamente para que isso seja preenchido
   localmente.
5. **Mantenha o conjunto vivo.** Quando uma sessão ensinar algo que vale para
   outros projetos, a lição vai para a skill do assunto, com o incidente que a
   criou. Uma lição sem incidente não ensina. O corte continua sendo por tipo:
   uma restrição que ainda decide algo fica; narrativa desce para o histórico.

---

## Estrutura de cada skill

Todas seguem a mesma forma, para que se leia qualquer uma sabendo onde procurar:

```
<skill>/
├── SKILL.md          frontmatter (name, description com gatilhos) e o corpo:
│                       · Quando usar / quando não usar
│                       · O princípio
│                       · Como agir (procedimento e padrões, cada um com a
│                         pergunta que o ativa e o caso real que o criou)
│                       · Testes de falha (como perceber que você está errando)
│                       · Critério de conclusão
└── modelos/ ou referencia/   quando a skill precisa de um arquivo para copiar
                              ou de um aprofundamento que não cabe no corpo
```

A skill ensina **como agir**. Ela não substitui o `README` do projeto nem o
runbook dele: o que é específico de um projeto continua morando nele.
