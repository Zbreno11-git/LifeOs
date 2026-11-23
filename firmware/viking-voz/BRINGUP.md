# viking-voz — bring-up (Sessão H1 do LifeOs, D70)

Roteiro da skill `esp32-development` (`templates/hardware-bringup.md`), preenchido em 2026-11-21.
O que não foi medido está marcado como **a medir**. Escrito no VPS (`/root/esp32/projects/viking-voz`)
e trazido para este repo em 2026-11-22, para seguir no Mac: lá a placa está na USB.

## Placa

- **Placa:** Seeed XIAO ESP32S3, a comum (sem a Sense; dito pelo dono em 2026-11-21).
- **SoC:** ESP32-S3 (QFN56) **rev 0.2** (`esptool flash-id` e o boot log, 2026-11-22).
- **Flash medida:** GigaDevice (`c8`/`4017`), **8 MB** detectados, quad, 3,3 V por eFuse
  (`esptool flash-id`, 2026-11-22). O bootloader do ESPHome dizia "4 MB": era o cabeçalho da
  imagem dele, não o chip.
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

A fonte única da pinagem, com o desenho e as regras para soldar, é o `ESQUEMA.md` (desde
2026-11-22). A tabela abaixo é o resumo; mudou um pino, muda lá primeiro.

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
  Monta-se no Mac com `bash firmware/viking-voz/montar_segredos.sh` (o token e o certificado vêm
  do laptop por `ssh home-server`, a Wi-Fi é perguntada; nada se imprime; o arquivo sai 600).
- **Recuperação:** se o firmware travar a USB, segure B (BOOT), aperte R (RESET), solte o B e rode
  `pio run -t upload`. Nunca apagar a flash de primeira.

## Camadas (cada uma vista no serial antes da próxima)

1. [x] Boot: "== Viking voz (H1) ==", o chip, a PSRAM livre, "botao: D1 (GPIO2), solto".
   **Visto em 2026-11-22 13:44Z** (gravado do Mac, sem o `segredos.h`): `chip ESP32-S3 rev 2;
   psram livre: 8386096 bytes`, `botao: D1 (GPIO2), solto` (ainda sem botão ligado: o pull-up).
2. [x] Botão (2026-11-22 14:13Z, no protoboard): `botao: fala`, `soltou (7164 ms)`, `dois toques`.
   Antes, o botão de 4 pernas num mesmo par dava `APERTADO no boot?` (ver `ESQUEMA.md`).
   O roteiro: segurar mostra "botao: apertou (fala)", depois "gravado: …" e "soltou"; dois toques
   mostram "botao: dois toques".
3. [x] Mic (2026-11-22 14:37–14:51Z, três rodadas de 5 gravações, no protoboard): o `GANHO` é
   **4** (com 8 a fala de perto saturava); o silêncio parado nunca teve trecho de 100 ms acima de
   4× o fundo da gravação, e a fala mais fraca ("liga a luz", baixo, de longe) teve 4. As
   distâncias são **aproximadas** (o dono não mediu; com o botão na mão, "longe" é o braço
   esticado). Daí o filtro de silêncio do motor (`voz.tem_fala`, com as sequências medidas nos
   testes). O roteiro: o "gravado" mostra o pico e o RMS da fala a ~30 cm. Calibrar o `GANHO`: a meta é o pico
   da fala normal sem saturar (`saturadas=0`).
4. [x] Rede (2026-11-22 16:49Z, com a antena U.FL e o `segredos.h` montado por
   `montar_segredos.sh`): `wifi: ok, sinal -35 dBm`, `hora: ok`, `ponte /saude: HTTP 200, estado
   ok`, com o certificado fixado. O roteiro: "wifi: ok", "hora: ok" e "ponte: saude -> ok". Se o
   nome não resolver, rodar o script de novo com o IP do laptop (está no certificado).
5. [x] A fala inteira (o E2E da H1, 2026-11-22): `ponte /falar: HTTP 202, estado pensando`, o
   estado final e a voz nas caixas (pela Scarlett do laptop; ver `CLAUDE.md`).
6. [x] A coleta da wake word (H2, D71), com o **firmware único** (2026-11-23 ~17:45Z): a placa liga
   no uso; `coleta.py` pede a coleta ao abrir a porta e o uso ao fechar. Visto:
   - `~/esp32-mac/.venv/bin/python coleta.py medir --minutos 1`: 1874 quadros, 0 lacunas, 0
     checksums errados, 16000,0 Hz, `maior_volta_us=661`, `ganho=2`; depois `coleta: volta ao uso
     (pedido do Mac)` e o PRONTO;
   - sem o sinal do Mac, `coleta: volta ao uso (sem sinal do Mac)` depois de 30 s, e o PRONTO.

   `coleta.py takes …`, `sala …` e `pacote …` gravam em `~/viking-wakeword/` (fora do repo), numa
   pasta por sessão (`AAAA-MM-DD_descricao`). O ganho é 2, congelado (o comentário do `GANHO`).

## No Mac (desde 2026-11-22)

O que já existe lá: `~/esp32-mac` (a venv com o `esptool` 5.4.0 e o `pyserial`; o `serve.sh`, que
serve a placa em `127.0.0.1:4000`; o `tunnel.sh`, que a levava ao VPS), ligados como LaunchAgents
pelo `service.sh`. O que falta instalar: o PlatformIO (o `pio`), que nunca rodou no Mac.

- **Conferir a placa:** `cd ~/esp32-mac && ./service.sh status` (o `serve` servindo um
  `/dev/cu.usbmodem*`).
- **Compilar:** `cd ~/Desktop/LifeOs/firmware/viking-voz && pio run` (a 1ª vez baixa a plataforma
  pioarduino e o toolchain do macOS x86_64).
- **Gravar:** `pio run -t upload` (pelo `127.0.0.1:4000`; o reset da USB-Serial/JTAG é aplicado
  pelo servidor). O `pio` está em `~/.platformio/penv/bin/pio` (Core 6.2.0, fora do PATH).
  **O cliente nunca leva o `ESPTOOL_CFGFILE`** (o `esptool-usbjtag.cfg` é do servidor): com ele
  dos dois lados, o reset dobra e o `esptool` falha com "getting no sync reply: The serial TX path
  seems to be down" (medido em 2026-11-22; sem ele, conecta da aplicação rodando).
- **O servidor preso numa porta velha:** se a placa sair e voltar com o mesmo nome, o
  `rfc2217_local.py` pode seguir com o descritor velho (`[Errno 6] Device not configured` a cada
  cliente; visto em 2026-11-22, de pé desde 20/11). Conserto: `launchctl kickstart -k
  gui/$UID/com.esp32.serve` (com o ok do dono).
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
