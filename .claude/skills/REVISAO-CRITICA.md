# Revisão crítica do conjunto

Este arquivo registra o que foi fundido, o que ficou de fora de propósito, as
práticas do projeto de origem que **não** deveriam ser levadas a outro projeto e os
aprendizados que mais valem. Ele existe para que ninguém "complete" o conjunto
com o que já foi pesado e recusado.

---

## 1. O que foi fundido, e por quê

| Proposta inicial | Destino | Motivo |
|---|---|---|
| `observabilidade` + `confiabilidade` | **`falha-ruidosa`** | As duas respondiam a mesma pergunta: *se isto estivesse errado, o que apareceria?* Alerta, código de saída, veredito e registro de execução são quatro formas dessa pergunta, e separá-las obrigaria a ler duas skills para desenhar um job |
| `cloud` + `deploy` + `ci` + `operacao` | **`nuvem-e-deploy`** | O tema das quatro era um só: o repositório não é o mundo. A ordem de deploy depende da IaC, o CI decide o que o deploy pode confiar, e a operação é a prova depois do deploy |
| `revisao` | **`software-build`** (seção 6 + [`referencia/revisao.md`](software-build/referencia/revisao.md)) | A revisão é um momento da sessão (fim de fase, depois do conserto, antes de produção), não uma área técnica. Como skill própria, ela competiria com o fechamento da sessão |
| `colaboracao-com-o-dono` | **`software-build`** (seção 4) | "Quem decide o quê" só faz sentido dentro do ciclo de planejar, executar e fechar |
| `arquitetura` | **`software-build`** (seção 4, "Decisões de arquitetura") + `nuvem-e-deploy` §1 | O que o projeto de origem ensinou de arquitetura que generaliza é pouco e é de **processo**: gatilho escrito antes de criar peça nova, decisão com gatilho de reabertura, estrutura vence disciplina, "se alguém espera é serviço; se é lote é job". O vocabulário de desenho de módulos já existe em skills públicas (por exemplo, `codebase-design`), e repeti-lo seria volume sem conhecimento novo |
| `llm` / `ia` | **`integracoes`** §4 | As lições de LLM (schema → prompt → normalização → modelo; a ausência no contexto preenchida pela pergunta; teto de saída que inclui o raciocínio) são lições de **integração com um terceiro que devolve texto**. Se um projeto viver de IA, esta é a primeira seção a virar skill própria |
| `ui` + `ux` + `design` | **`frontend-e-ux`** | Na prática, as falhas de UX desta casa foram de **texto** (aviso que descreve o mecanismo) e de **conferência** (ninguém olhou no celular). Isso é um modo de trabalhar, não uma teoria de design separada |
| `evidencia` + `depuracao` | **mantidas separadas** | Foi a fusão mais tentadora e foi recusada. `evidencia` vale para qualquer frase escrita (relatório, plano, commit), mesmo sem defeito à vista; `depuracao` é uma **ordem de investigação**. Juntas, a primeira ficaria escondida dentro de um contexto de incidente, e ela é mais usada fora dele |

## 2. O que ficou de fora de propósito

- **Uma skill de coleta web (scraping).** No projeto de origem era o coração do produto, e
  há conhecimento profundo: famílias de CMS, veredito por alvo, curva de
  saturação. Mas é conhecimento de **domínio**. O que generaliza (postura
  identificável, falha nunca como vazio, teto silencioso é interrupção,
  veredito em camadas) já está em `falha-ruidosa` e `integracoes` §7.
- **Uma skill de pagamentos.** A seção de pagamentos de `integracoes` cobre os
  princípios. Um fornecedor específico de pagamentos tem armadilhas que mudam a
  cada versão de API, e isso é runbook de projeto.
- **Uma skill de "multi-agente".** O protocolo implementador → revisor →
  validador é útil só quando há dois agentes. Ficou em uma seção de
  `referencia/revisao.md` e no passo 3 do README.
- **Skills de marca, de ofício de corretagem e de negócio SaaS.** São do
  produto, não do modo de trabalhar.

## 3. Práticas do projeto de origem que NÃO deveriam ser generalizadas

Algumas práticas funcionaram, ou foram necessárias, por causa de um contexto
que outro projeto provavelmente não terá. Outras tiveram custo alto demais.

| Prática | Por que não levar | O que levar no lugar |
|---|---|---|
| **Carregar o catálogo de erros inteiro em toda sessão.** Medido em 26/09/2026: o primer mais o catálogo importado somam ~317 KB (`wc -c`), com 3.858 linhas só no catálogo | O catálogo é o material mais valioso da casa, e mesmo assim cada ocorrência virou narrativa longa, e tudo é pago em contexto em toda sessão. O teto de tamanho do primer só veio depois de ele chegar a 45 mil tokens | Um **índice por classe** (nome, número de ocorrências, antídoto em uma linha) carregado sempre; as narrativas num arquivo que se abre **ao achar um defeito**. O modelo em `software-build/modelos/ERROS.md` já tem o índice |
| **Mais de mil mutações rodando no CI a cada push** (~1h30 por execução, com minutos de CI pagos) | O custo levou a uma coreografia de marcas de "pular CI" que, por sua vez, gerou dois erros novos (marca no commit do meio, marca citada no corpo) | Mutações **curadas para as regras que decidem dinheiro, acesso e apagamento**; rodada completa quando a mudança toca o que elas miram; reverificação isolada do resto |
| **A coreografia de `[skip ci]` em todo commit intermediário** | É remédio para um CI caro, não uma prática | Um CI rápido o bastante para rodar sempre; o caro vai para agendamento ou para gatilho manual |
| **Testes que leem o código-fonte como texto** (regex sobre o arquivo), usados em larga escala | Funcionaram para invariantes estruturais (a guarda é a primeira instrução; nenhuma variável sem declaração de deploy), mas foram a origem de vários verdes falsos: menção não é ramo, prefixo não é nome, um regex não sabe o que é string | **Comportamento primeiro.** Varredura de fonte só para invariantes que não têm como ser exercidas, e sempre por tokenizador ou AST, com piso derivado |
| **"Pelo menos 10 perguntas antes do plano"** | O número era a forma de um dono específico dizer "não comece antes de entender" | Perguntar em rodadas até ter **confiança de implementação**, e somar as respostas |
| **Tudo em português, inclusive nomes de função, com uma exceção de fronteira no frontend** | Decisão de idioma é do projeto e da equipe | Decidir o idioma no primer, com a fronteira escrita |
| **O painel externo de progresso como obrigação** | Dependia de uma ferramenta que nem sempre estava no ar | Um `.md` com barra auditável, atualizado por etapa |
| **Os limiares e preferências do dono** (11 s de latência "está bom", US$ 2/mês "é investimento") | São decisões **dele**, sobre **aquele** produto | Generalizou-se o princípio: o limiar de "bom" é do dono; custo pequeno fixo se avisa, e custo que escala ganha teto |
| **Arquivos "intocáveis" por nome** (um módulo de deduplicação que só muda com autorização) | O nome é do projeto | O princípio: **o código que define a identidade de uma entidade** (o que é "o mesmo" registro) é zona protegida; muda com autorização do dono, réplica, controle e diff antes |
| **Documentos com muitos alertas (⚠️) e parágrafos longos** | A ênfase inflacionou; quando tudo é aviso, nada é | Um aviso por seção, no máximo; o resto vira tabela ou lista |

## 4. Redundâncias que ficaram, de propósito

Alguns princípios aparecem em mais de uma skill, **sempre com a mesma frase e
com um ponteiro para a skill dona**:

- *Transitória × definitiva* é dona em `falha-ruidosa`; `integracoes` a aplica
  a webhooks.
- *Presença e validade* é dona em `falha-ruidosa`; `dados-e-banco` traz a
  armadilha do conserto.
- *O estado espelhado de um terceiro tem a transição do terceiro* é dona em
  `dados-e-banco`; `integracoes` a aplica a assinaturas.
- *O que está no ar* é dona em `nuvem-e-deploy`; `software-build` usa como
  degrau 5 da escada de pronto.

A repetição é o custo de cada skill poder ser lida sozinha. O que **não** se
repete é o desenvolvimento: cada princípio é desenvolvido em um lugar só.

## 5. Os aprendizados mais valiosos

Se só couberem sete frases num projeto novo, são estas:

1. **"Se isto estivesse errado, o que apareceria?"** Quando a resposta honesta
   é "nada", é ali que está o trabalho. Foi a pergunta que mais evitou dano.
2. **"Quem mediu isto, quando, com qual comando?"** Um documento nosso
   concordar com a nossa conclusão abre a questão, não fecha. Foi o erro mais
   repetido (mais de nove ocorrências registradas).
3. **"Se esta verificação ficar verde, quantas explicações isso admite?"** E o
   seu corolário prático: teste o teste, revertendo o conserto e vendo cair.
4. **Estrutura vence disciplina.** Tudo que dependia de alguém lembrar divergiu.
   O que foi derivado, tipado ou amarrado por teste parou de divergir.
5. **Pronto é quando o defeito parou de acontecer**, não quando o commit passou.
   E a pergunta de deploy tem duas metades: *qual commit está no ar?* e *o que
   entrou no código desde ele?*
6. **A segunda passada de revisão muda a pergunta.** O conserto é onde nasce o
   próximo defeito: *o que este conserto tornou falso?*
7. **Decisões têm dono.** A técnica chega como recomendação; a de domínio,
   dinheiro, limiar e adiamento é do dono, perguntada na hora. E o que só foi
   dito no chat vai para o disco antes de o contexto acabar.

## 6. Como saber se o conjunto está envelhecendo

- Uma skill que ninguém abriu em várias sessões: ou o gatilho da `description`
  está errado, ou ela não é necessária.
- Um erro novo que não cabe em classe nenhuma: é candidato a uma seção nova, não
  a uma skill nova. Uma skill nova só nasce quando um **modo de trabalhar**
  aparece em mais de um projeto.
- Uma regra aqui que um projeto precisou desobedecer para funcionar: escreva a
  exceção e o motivo na skill, com o caso.
