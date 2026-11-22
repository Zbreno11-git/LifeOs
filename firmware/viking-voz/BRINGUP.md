# viking-voz — bring-up (Sessão H1 do LifeOs, D70)

Roteiro da skill `esp32-development` (`templates/hardware-bringup.md`), preenchido em 2026-11-21.
O que não foi medido está marcado como **a medir**. Escrito no VPS (`/root/esp32/projects/viking-voz`)
e trazido para este repo em 2026-11-22, para seguir no Mac: lá a placa está na USB.

## Placa

- **Placa:** Seeed XIAO ESP32S3, a comum (sem a Sense; dito pelo dono em 2026-11-21).
- **SoC:** ESP32-S3. A revisão sai no boot log (`chip … rev N`): **a medir**.
- **Memória:** 8 MB de flash e 8 MB de PSRAM (`CLAUDE.md` do workspace e wiki da Seeed). O boot
  imprime a PSRAM livre.
- **USB:** USB-Serial/JTAG nativa, plugada no Mac do dono. O `~/esp32-mac` serve a placa por
  RFC2217 em `127.0.0.1:4000` no próprio Mac (o LaunchAgent `com.esp32.serve`).
- **Firmware atual (medido em 2026-11-22):** um ESPHome mínimo (`xiao-estudio`: só `wifi`, `api`,
  `ota` e `logger`; nada de mic nem botão), gravado pelo container ESPHome do laptop de casa e
  ligado ao HA. O dono autorizou substituí-lo pelo `viking-voz` (2026-11-22): o Viking alcança o
  HA pela ponte, não pelo ESPHome. Ele volta, se um dia quiser, pelo ESPHome do laptop (USB).
  Antes dele, o `viking-hardware-teste` (o teste do mic), que fica no VPS
  (`/root/esp32/projects/viking-hardware-teste`).

## Fontes

| Artefato | Fonte | Decide |
|---|---|---|
| Pinos da placa | wiki da Seeed (`xiao_esp32s3_getting_started`), lido em 2026-11-21 | D1 = GPIO2; o 5V é o VBUS do USB; o 3V3 dá até 700 mA |
| Strapping pins | datasheet do ESP32-S3 v2.2: "GPIO0, GPIO3, GPIO45, GPIO46 : Strapping pins" | o botão no D1 (GPIO2), longe deles |
| Saída de áudio | datasheet do ESP32-S3: sem DAC, duas interfaces I2S | o som sai por I2S (MAX98357A, na H1b) |
| Microfone | o `viking-hardware-teste`, que já leu o INMP441 a 16 kHz | os pinos e a escala 24→16 bits |

## Pinos

| Função | GPIO (rótulo) | Direção | Pull | Conflitos conferidos |
|---|---|---|---|---|
| I2S BCLK (INMP441 SCK) | 7 (D8) | saída | — | o mesmo do teste |
| I2S WS (INMP441 WS) | 8 (D9) | saída | — | o mesmo do teste |
| I2S DIN (INMP441 SD) | 9 (D10) | entrada | — | o mesmo do teste |
| Botão | 2 (D1) | entrada | pull-up interno, apertado = LOW | não é strapping; não é a USB (19/20) |
| LED da placa | 21 | saída | ativo em LOW | — |
| LED externo (opcional) | 43 (D6) | saída | ativo em HIGH, com resistor | é o TX0 da UART0; a serial do console é a USB nativa |

## Alimentação

- **Agora:** pelo USB do Mac (no desenvolvimento) e por um carregador USB no estúdio. O consumo com a
  Wi-Fi ligada é **a medir**.
- **H1b:** o MAX98357A vai no 5V (o VBUS). A recomendação é uma fonte USB de 5 V e 2 A; o consumo
  real é **a medir**.

## Firmware

- **Framework:** Arduino-ESP32 3.x pelo pioarduino (`platformio.ini`, o mesmo do modelo
  `xiao_s3`).
- **Comandos:** ver "No Mac" abaixo.
- **Segredos:** `src/segredos.h`, que fica no `.gitignore`. Sem ele, o firmware roda só o
  diagnóstico: o botão, o LED e o mic, e nada vai à rede.
- **Recuperação:** se o firmware travar a USB, segure B (BOOT), aperte R (RESET), solte o B e rode
  `pio run -t upload`. Nunca apagar a flash de primeira.

## Camadas (cada uma vista no serial antes da próxima)

1. [ ] Boot: "== Viking voz (H1) ==", o chip, a PSRAM livre, "botao: D1 (GPIO2), solto".
2. [ ] Botão: segurar mostra "botao: apertou (fala)", depois "gravado: …" e "soltou"; dois toques
   mostram "botao: dois toques".
3. [ ] Mic: o "gravado" mostra o pico e o RMS da fala a ~30 cm. Calibrar o `GANHO`: a meta é o pico
   da fala normal sem saturar (`saturadas=0`).
4. [ ] Rede (com o `segredos.h`): "wifi: ok", "hora: ok" e "ponte: saude -> ok", com o certificado
   fixado. Se o `.local` não resolver, usar o IP com `--nome IP` no `viking casa --preparar`.
5. [ ] A fala inteira: "ponte /falar: HTTP 202, estado pensando", depois o estado final, e a voz
   no laptop.

## No Mac (desde 2026-11-22)

O que já existe lá: `~/esp32-mac` (a venv com o `esptool` 5.4.0 e o `pyserial`; o `serve.sh`, que
serve a placa em `127.0.0.1:4000`; o `tunnel.sh`, que a levava ao VPS), ligados como LaunchAgents
pelo `service.sh`. O que falta instalar: o PlatformIO (o `pio`), que nunca rodou no Mac.

- **Conferir a placa:** `cd ~/esp32-mac && ./service.sh status` (o `serve` servindo um
  `/dev/cu.usbmodem*`).
- **Compilar:** `cd ~/Desktop/LifeOs/firmware/viking-voz && pio run` (a 1ª vez baixa a plataforma
  pioarduino e o toolchain do macOS x86_64).
- **Gravar:** `pio run -t upload` (pelo `127.0.0.1:4000`; o reset da USB-Serial/JTAG é aplicado
  pelo servidor).
- **Ler o serial:** `~/esp32-mac/.venv/bin/python serial_log.py 15 --reset` (desde o boot) ou sem
  `--reset`; a saída também em `logs/serial.log` (fora do git).
- **Se a rede do Mac fizer inspeção TLS** (a corporativa; a de casa, em 2026-11-22, não faz) e o
  `pio` ou o `uv` recusarem certificado, use o pacote de
  certificados em que o macOS confia, que o `~/esp32-mac/setup.sh` monta (`macos-ca.pem`, por
  `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE`). Isso não contorna nada da rede; não proponha mais que isso.
- **Camadas 4 e 5 (a rede de casa):** a placa precisa estar na Wi-Fi do laptop de casa. Em
  2026-11-22 o Mac está nessa mesma Wi-Fi, então a placa fica na USB do Mac e o serial se lê daqui.
  Se o Mac estiver noutra rede, a placa vai para casa e o serial passa a ser lido no laptop, ou só
  pelo LED.
