# Avaliar a maturidade de um projeto existente

Use quando alguém perguntar *"como está este projeto?"*, *"está robusto?"* ou
*"dá para confiar?"*, ou quando você assumir um repositório que não conhece.

O objetivo não é dar uma nota. É dizer **o que falta, em que ordem, e o que cada
falta custa**. Toda resposta sai de um comando ou de um arquivo lido; nada sai
do README do próprio projeto sem conferir (ver `evidencia`).

## Como conduzir

1. **Leia antes de julgar.** Primer, roadmap, progresso, `git log --oneline -30`,
   os workflows de CI e a estrutura de diretórios.
2. **Para cada dimensão abaixo, rode a sonda** e classifique em 0–3 pelo
   critério **observável**, não pela intenção declarada.
3. **Relate as três faltas mais caras primeiro.** Custo = o que acontece no dia
   em que a falta morder × a chance de morder. Uma lista de vinte itens
   equivalentes não ajuda ninguém a decidir.
4. **Separe fato medido, inferência e o que não deu para verificar** (fora do
   seu alcance: painéis de fornecedor, produção sem credencial). Marque o último
   como `Não confirmado / requer verificação externa`.

## As dimensões

| Dimensão | Sonda (o comando ou arquivo) | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| **Continuidade** | Primer, progresso, diário, roadmap existem? O "retomar aqui" bate com o `git log`? | nada escrito | README só | documentos existem mas divergem do código | documentos com data, conferidos, com teto |
| **Evidência** | Os números nos docs têm comando e data? Hipótese está marcada como hipótese? | números soltos | alguns com fonte | a maioria com fonte | medição e hipótese separadas por vocabulário |
| **Testes** | Rodar a suíte; ler 3 testes da área mais crítica; há teste por mutação? | sem suíte | suíte verde que testa o caminho feliz | testa falha e borda | a suíte é testada (mutação) e cobre a decisão, não o símbolo |
| **Falha ruidosa** | Um job que termina parcial sai ≠ 0? Existe alerta? Ausência de execução aparece? | falha engolida | log sem alerta | alerta de erro | parcial e ausência também alertam, com a causa na mensagem |
| **Estado do mundo** | O que está no ar = qual commit? Há como saber em 1 comando? Migrations do disco = aplicadas? | ninguém sabe | alguém sabe de memória | há comando | o fechamento de sessão confere por comando |
| **Deploy** | Como se publica? Tag de imagem é o SHA? Há ordem entre serviços? | à mão, sem registro | script sem conferência | script que confere | script que lê o estado, pede ok por passo e prova depois |
| **Segurança** | Onde está a fronteira de autorização? Superfície pública listada? Segredos fora do git e do estado de IaC? | na tela | no servidor, sem lista | lista declarada | lista auditada nos dois sentidos, contra produção |
| **Dados** | Migrations numeradas e imutáveis? Escritas aguentam reenvio? | schema à mão | migrations sem ledger | ledger | ledger + checksum conferido + réplica antes de mudar regra |
| **Decisões** | Existe registro com o porquê e o gatilho de reabertura? | na cabeça de alguém | no chat | registradas | registradas com gatilho, e o primer carrega as vigentes |
| **Dívida** | Há lista de dívida? Tem dono e data? | desconhecida | existe em comentários | listada | listada com dono, e fecha na sessão ou tem adiamento autorizado |

## Sinais que valem mais que a nota

- **Um documento que diz o contrário do código.** É a assinatura de um processo
  que parou de conferir. Ache um e procure outros.
- **CI verde há meses sem nenhum teste novo** na área que mais mudou.
- **"Funciona na minha máquina"** para algo que só roda agendado.
- **Nenhum alerta disparou nunca.** Pode ser saúde, ou pode ser alerta que não
  alcança nada. Pergunte qual evento dispararia cada um e se esse evento ainda é
  emitido pelo código.
- **Um número que ninguém sabe de onde vem** e que aparece para o cliente.

## Formato do relatório

```
## Maturidade de <projeto> — <data>

**Em uma frase:** <o estado, sem adjetivo>

### As três faltas mais caras
1. <falta> — custa <o que acontece> quando <gatilho>. Prova: <comando/arquivo>.
   Conserto proposto: <o menor que fecha a classe>.
2. …
3. …

### Por dimensão
| Dimensão | Nível | Prova |
|---|---|---|

### Não confirmado / requer verificação externa
- <item> — por que não deu para medir daqui.

### O que está bom e não deve ser mexido
- <item> — por que é bom (para ninguém "melhorar" o que funciona).
```

A última seção não é cortesia. Um relatório de maturidade que só lista faltas
convida a refazer o que está certo.
