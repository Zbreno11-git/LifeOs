# viking-voz — o esquema elétrico (protótipo e produto)

A fonte única da pinagem do aparelho do estúdio (Sessão H1, D70). O firmware (`src/main.cpp`) e o
`BRINGUP.md` apontam para cá. **Toda mudança de pino entra aqui primeiro**, com a fonte, e só depois
no código.

## Estado

- **2026-11-22: protótipo em protoboard, nada soldado.** Montado pelo dono e conferido no serial
  (camadas 1 e 2 do `BRINGUP.md`; o mic dá leitura de fala e de silêncio na camada 3).
- O produto soldado ainda não existe: as regras de montagem abaixo valem para ele.

## As peças

| Peça | Modelo | Fonte |
|---|---|---|
| Placa | Seeed XIAO ESP32S3 (a comum, sem Sense); S3 rev 0.2; flash 8 MB (GigaDevice), PSRAM 8 MB | `esptool flash-id` e o boot log, 2026-11-22 |
| Microfone | INMP441 (I2S, digital), plaquinha de 6 pinos: SD, VDD, GND, L/R, WS, SCK | o dono, 2026-11-22 |
| Botão | push-button de 4 pernas (tátil), normalmente aberto | o dono, 2026-11-22 |
| Som (H1b) | MAX98357A, **a comprar**; os pinos dele **a decidir** com o datasheet | D70 |

## As ligações (medidas no protótipo de 2026-11-22)

```
            XIAO ESP32S3                     INMP441
         ┌───────────────┐              ┌────────────┐
         │ 3V3 ──────────┼──────────────┤ VDD        │   nunca no 5V
         │ GND ──┬───────┼──────────────┤ GND        │
         │       ├───────┼──────────────┤ L/R        │   L/R no GND = canal esquerdo
         │ D8  (GPIO7) ──┼──────────────┤ SCK        │   I2S BCLK
         │ D9  (GPIO8) ──┼──────────────┤ WS         │   I2S LRCLK
         │ D10 (GPIO9) ──┼──────────────┤ SD         │   I2S dados (entrada no ESP32)
         │       │       │              └────────────┘
         │ D1  (GPIO2) ──┼───[ botão ]───┐
         │       └───────┼───────────────┘   o outro lado do botão no GND
         │ USB-C ────────┼── o Mac (desenvolvimento) ou um carregador USB (estúdio)
         └───────────────┘
```

| Função | Pino da XIAO | GPIO | Liga em | No firmware |
|---|---|---|---|---|
| Alimentação do mic | 3V3 | — | INMP441 VDD | — |
| Terra comum | GND | — | INMP441 GND, INMP441 L/R e um lado do botão | — |
| I2S BCLK | D8 | 7 | INMP441 SCK | `i2s.setPins` |
| I2S WS | D9 | 8 | INMP441 WS | `i2s.setPins` |
| I2S dados | D10 | 9 | INMP441 SD | `i2s.setPins`; lido no `I2S_STD_SLOT_LEFT` |
| Botão | D1 | 2 | o outro lado do botão | `INPUT_PULLUP`: solto = HIGH, apertado = LOW |
| LED da placa | — | 21 | (na placa) | ativo em LOW |
| LED externo (opcional) | D6 | 43 | LED + **resistor em série** (220 Ω–1 kΩ) ao GND | ativo em HIGH |

**Nenhum resistor externo é preciso** no mic nem no botão: o botão usa o pull-up interno, e o INMP441
é digital. O datasheet do INMP441 fala num pull-down de 100 kΩ no SD para quando vários mics dividem
o barramento (lembrado, **não reconferido** em 2026-11-22); com um mic só, não se pôs. Se a camada 3
mostrar ruído estranho, reabrir o datasheet antes.

## O que o protótipo ensinou (vale para soldar)

- **O botão de 4 pernas, sempre na diagonal.** As pernas vêm em pares ligados por dentro; os dois
  fios num mesmo par deixam o D1 no GND o tempo todo. Visto em 2026-11-22: o boot dizia `botao: D1
  (GPIO2), APERTADO no boot?` e nenhum evento saía; na diagonal, `solto` e os eventos certos.
- **Três fios no GND** (o do mic, o L/R e o botão): a XIAO tem os pinos de terra contados; unir antes
  do pino.
- **O mic no 3V3**, nunca no 5V (o 5V da XIAO é o VBUS do USB).
- **O clique do botão entra na gravação** (ela nasce no aperto e morre no soltar): no produto, o mic
  longe do botão e sem os dois na mesma peça rígida, se der; o firmware mede o pico sem as pontas de
  150 ms por isso.

## O produto (a decidir)

- A distância de fala: **de 50 cm a 1,5 m**, com o aparelho na mesa (o dono, 2026-11-22). O ganho e
  o filtro de silêncio se medem nessas duas distâncias.
- O MAX98357A (H1b): os pinos saem do datasheet dele e da tabela de pinos livres da XIAO (fora dos
  strapping GPIO0/3/45/46 e da USB 19/20), e entram aqui antes do código.
- A caixa, o furo do mic e a fonte de 5 V: a medir quando o som do aparelho existir.
