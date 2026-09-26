---
name: testes-que-provam
description: Testes e qualidade — testar onde a decisão acontece e testar o próprio teste. Medir o alcance de uma verificação ("se ficar verde, quantas explicações isso admite?"), denominadores derivados em vez de listas à mão, teste por mutação sem mutação inerte, fixtures do incidente e do contrato reais, testes de sequência (a segunda entrega), banco que nunca começa vazio em produção, paridade por saída e não por constante, e o que nenhuma suíte alcança. Use ao escrever ou revisar teste, ao montar ou ler uma rodada de mutação, ao decidir se um portão prova algo, e antes de dizer que algo "está testado".
---

# Testes que provam

## Quando usar

- Ao escrever um teste para um conserto ou uma regra nova.
- Ao revisar uma suíte que "está verde".
- Ao montar, rodar ou ler teste por mutação.
- Ao escolher quais portões rodar, e quanto verificação repetir.

## Quando não usar

- Para decidir **o que** o sistema deve fazer. Um teste prende uma decisão;
  ele não a toma.

## O princípio

> **Um teste prova só o que ele exercita.** Suíte verde é o sinal mais
> enganoso que existe, porque ela responde exatamente o que foi perguntado, e
> a pergunta costuma ser mais estreita do que parece.

A régua e a pergunta coincidem no caso comum e divergem justamente no caso que
importa. Por isso não há sintoma: no dia a dia as duas respostas batem.

---

## 1. Meça o alcance da régua

Antes de aceitar um teste, pergunte: **se ele ficar verde, quantas explicações
diferentes isso admite?** Se admitir mais de uma, ele não é a régua.

| A régua | Responde | A pergunta era |
|---|---|---|
| `"<nome>.error"` aparece no arquivo | o símbolo existe | a **guarda** existe? (a menção dentro do `console.error` mantém a string viva) |
| regex `/<Componente/` | o prefixo existe | o componente? (`<ComponenteRemovido` também casa) |
| a frase aparece no HTML inteiro | ela existe em algum lugar | ela está **nesta** unidade? |
| `set(dict_por_chave)` | quais chaves vieram | **quantas linhas** vieram? (agrupar descarta cardinalidade) |
| os bytes dos dois arquivos diferem | os arquivos diferem | o fundo foi **pintado**? |
| o conjunto de **nomes** bate | o nome existe | o **par** (cidade, bairro) foi decidido? |
| a saída da função = a saída de quem a usa | as duas compartilham a função | o **efeito** é o certo? (mude a função, e as duas mudam juntas) |

Os consertos:

- **Recorte a unidade e afirme dentro dela.** A lista de unidades sai do próprio
  arquivo (por exemplo, todas as funções que casam `^function Cartao\w+`), com
  um **piso derivado**. Uma varredura que encolhe tem de reprovar, não
  emudecer.
- **Conte antes de agrupar.** `assert len(linhas) == 2` vem antes do dicionário.
- **Compartilhamento e efeito são dois testes:** um derivado, para o
  compartilhamento, e um **literal**, com o valor escrito à mão, para o efeito.
- **Afirme sobre a saída, não sobre a fonte.** Renderize e leia o HTML; abra o
  PDF e leia os operadores; construa o schema e inspecione o objeto.

## 2. Denominadores derivados, nunca escritos à mão

Uma lista escrita num teste ("as tabelas do usuário", "as ações do servidor")
não cresce quando nasce o próximo item, e o item novo estreia fora do portão.
**Derive do catálogo, do disco ou do código**: toda tabela com FK para usuários
e RLS ligada, toda função exportada de um módulo de ações, todo
`process.env.X` lido em `src/`.

*Caso real:* a regra "acesso, não identidade" valia para as tabelas de uma
tupla escrita à mão. A tabela nova, que guardava nome, registro profissional e
telefone, nasceu fora da tupla com a porta aberta.

## 3. Teste por mutação: o teste dos testes

Reverter o conserto, ver o teste ficar vermelho, restaurar. Se não cai, o teste
não protege. As regras que custaram caro estão em
[`referencia/mutacao.md`](referencia/mutacao.md). As principais:

- **A mutação precisa afirmar que casou exatamente uma vez** antes de rodar.
  Uma mutação que não aplicou não é um teste que passou; é um teste que não
  rodou.
- **Ela tem de mudar o código, não o comentário.** Compare o arquivo **sem
  comentários** antes e depois, com um tokenizador que conheça strings (um
  regex não sabe que `"/**"` é string).
- **Em arquivo de dados** (YAML, JSON, TOML, `.env`), compare o **valor
  carregado**. Uma chave duplicada tem vencedora, e a mutação na perdedora é
  inerte.
- **Preserve a aridade.** Uma mutação que quebra o SQL prova que o teste toca o
  código, não que a regra está testada. A mutação boa muda só a semântica, e
  derruba **o** teste do achado.
- **Restaure byte a byte, e isso inclui os arquivos que o comando reescreve**
  (lockfiles, tipos gerados, snapshots) e o estado fora do arquivo (funções no
  banco, cache do typecheck).
- **Uma rodada interrompida deixa código mutado e trava no disco.** Nunca rode
  mutação com `timeout`. Depois de matar uma rodada, rode `git status` e confira
  a trava.

**Uma mutação verde admite três leituras:**

1. o teste é fraco → escreva o caso;
2. o código é **inalcançável** → escrever teste para ele consolida uma ilusão
   de proteção; a pergunta é *este trecho é alcançável?*;
3. o código é redundante em execução e **necessário para o compilador** (ele
   estreita um tipo) → rode o typecheck antes de apagar.

E uma quarta situação: **defesa em profundidade.** Duas guardas redundantes uma
a uma e necessárias em par. A mutação, que muda uma coisa por vez, não alcança
isso. O comentário certo diz: *"esta linha não é alcançável hoje, e estas são as
que a tornam inalcançável"*.

**Verificação proporcional:** quando uma rodada completa já provou tudo e só uma
mutação mudou, prove essa isoladamente. Rodar tudo de novo é tempo parado. A
rodada completa volta a valer quando a mudança é ampla ou não dá para isolar o
efeito.

## 4. Fixtures que carregam o mundo real

- **A fixture devolve o que você escreveu, não o que a API aceita.** O contrato
  real só aparece quando a requisição sai. *Casos reais:* uma API com máximo de
  20 pontos por pedido (a fixture aceitava 24), um objeto da API que recusa dois
  parâmetros juntos, um evento cuja referência tinha mudado de lugar na versão
  nova. Capture o payload **real** e use-o.
- **Quando o teste cita um incidente, a fixture carrega os valores do
  incidente:** o status HTTP (405, não 500), o tamanho, a contagem. Pergunte:
  *se eu trocar este valor pelo que de fato aconteceu, o teste continua
  passando pelo mesmo motivo?*
- **Pergunte de quantas formas o campo grava ausência** (`NULL` e `0`, `""` e
  espaço, U+0020 e U+00A0). *Caso real:* 55 áreas iguais a zero lideravam a
  ordenação por área.
- **Fixture binária colada se decodifica e se afirma antes de usar.** Um "PNG
  branco" era amarelo meio transparente e produziu um achado visual falso, com
  conserto plausível.
- **O calendário também é fixture:** 31 dias não é um mês.
- **Meça com a fixture larga.** Varrer a roda de cores inteira achou um
  arredondamento que nenhuma das cores escolhidas à mão pegaria.

## 5. Teste a sequência, não só o evento

As réguas costumam exercitar o caminho **uma vez**. As perguntas que faltam:

- *O que a segunda execução encontra?* (retentativa depois de falha parcial)
- *O que acontece se o evento chegar duas vezes?* (reentrega, retry do cliente)
- *O que acontece com o evento B depois do A?* (recusado → aprovado com outro
  cartão)

O duplo de teste precisa de **estado**. Um falso que esquece o que foi apagado
não acha o defeito de um passo que consome a própria entrada.

## 6. O banco de teste sempre começa vazio; o de produção nunca

Toda fixture cria o banco do zero, e isso esconde qualquer defeito que só
aparece em base que já tem coisa dentro: migração incremental, `ALTER` que
assume coluna, backfill. *Caso real:* 506 testes verdes, e o programa não abria
o banco real.

- Rode o comando de verdade contra uma base populada.
- Quando o defeito for dessa classe, o teste de regressão **cria o banco no
  formato antigo de propósito**.

## 7. Espelhos se comparam pela saída

Duas implementações do mesmo contrato (dois bancos, duas linguagens, schema e
tipo) divergem na **semântica**, não nas constantes. Um teste de paridade que
compara o nome do modelo e o teto de tokens fica verde com os corpos
divergindo. Monte a entrada, chame os dois lados e compare as saídas, ou os
**conjuntos**.

## 8. Código que o teste não alcança é sintoma

Se você está varrendo o texto de um arquivo porque não consegue importá-lo
(depende do framework, do servidor, de `headers()`), a pergunta é **por que este
código não é importável?** Tire a peça pura para onde o teste a alcança, e o
arquivo original só a chama. Rotas HTTP e componentes de servidor são os
lugares onde regra de dinheiro e de acesso mais se esconde de teste.

## 9. Os outros portões e os outros sinais

- **Typecheck é outro portão.** A mutação roda a suíte e não vê o que só o
  compilador pega.
- **`skipped > 0` numa suíte que não pula nada é vermelho.** `pass + fail +
  skip` tem de bater com o total.
- **Um teste que pendura não diz o que faltou.** Se o defeito estiver lá, o
  teste **reprova** ou só não termina? Declare timeout próprio e faça o falso
  recusar na hora.
- **Regras de documentação também podem ser testes:** fonte única (uma âncora
  não pode aparecer em dois arquivos), teto de tamanho, links que apontam para
  âncoras que existem.

## 10. O que nenhuma suíte alcança

Uma divergência entre o **disco** e o **mundo** não aparece em teste. Os casos
reais: migration no disco e não aplicada, variável de ambiente só no `.env`
local, checksum de migration editada, imagem atrasada. Cada par precisa de um
instrumento próprio: `--dry-run` do ledger, `describe` da imagem, uma régua que
lê o código e a declaração de deploy. Ver `nuvem-e-deploy`.

---

## Ordem dos portões

1. conserto do defeito, com teste e **mutação verificada** (vermelho → verde);
2. suíte inteira verde, lint e formatação limpos, typecheck;
3. **explicar o defeito**: o que era, por que passou, o que agora o impede;
4. só então build, aplicação e execução.

## Testes de falha

Sua suíte está mentindo se:

- um teste afirma sobre uma lista que você escreveu à mão;
- a mutação que desliga a regra deixa tudo verde e você leu isso como "o código
  não precisa";
- a fixture foi inventada para um caminho que fala com um terceiro;
- nenhum teste entrega o mesmo evento duas vezes;
- o único teste de uma função de formatação vive dentro de um componente.

## Critério de conclusão

- [ ] Existe um teste que **cai** com o defeito, e a queda foi vista.
- [ ] O verde admite uma explicação só.
- [ ] Denominadores derivados; piso derivado onde há varredura.
- [ ] Contratos de terceiros testados com payload real.
- [ ] A contagem `pass/fail/skip` bate com o esperado.
