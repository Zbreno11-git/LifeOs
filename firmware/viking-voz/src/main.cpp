// A voz do estúdio (Sessão H1 do LifeOs, D70): segure o botão, fale, solte.
//
// XIAO ESP32-S3 (a comum, sem a Sense) + o microfone INMP441 (I2S), como o viking-hardware-teste:
//   INMP441: VDD->3V3, GND->GND, L/R->GND, SCK->D8 (GPIO7), WS->D9 (GPIO8), SD->D10 (GPIO9)
//   Botão:   um push-button entre D1 (GPIO2) e GND (pull-up interno; apertado = LOW).
//            O D1 não é strapping pin (no S3 eles são GPIO0, 3, 45 e 46: datasheet e wiki da XIAO).
//   LED:     o da placa (GPIO21, ativo em LOW) e, se ligado, o externo do teste em D6 (GPIO43).
//
// O aparelho não guarda chave de nada: fala só com a ponte de casa (`viking casa`, no laptop), por
// HTTPS com o certificado dela fixado (não aceita outro) e o token do aparelho. Os segredos ficam em
// src/segredos.h (fora do git); sem ele, o firmware roda só o diagnóstico (botão, LED, microfone).
//
// O botão:
//   segurar (>= 400 ms) = gravar enquanto estiver apertado (até 30 s) e mandar a fala à ponte;
//   dois toques curtos  = aprovar o que o Viking pediu (um envio de e-mail, uma limpeza).
// O LED: aceso = gravando; piscando bem rápido com o botão apertado = a gravação está acabando (ou
// acabou: o resto não entra); piscando rápido = esperando a resposta; piscando devagar = esperando
// os dois toques; 1 piscada = ok; 2 longas = a voz está desligada no HA; 3 rápidas = erro.

#include <Arduino.h>
#include <ESP_I2S.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <WiFi.h>
#include <esp_task_wdt.h>
#include <time.h>

#include "escuta.h"

#if __has_include("segredos.h")
#include "segredos.h"
#define TEM_SEGREDOS 1
#endif
#ifndef TEM_SEGREDOS
#define TEM_SEGREDOS 0
#endif

constexpr int PIN_BCLK = 7;      // D8
constexpr int PIN_WS = 8;        // D9
constexpr int PIN_DIN = 9;       // D10
constexpr int PIN_BOTAO = 2;     // D1
constexpr int PIN_LED_EXT = 43;  // D6
constexpr uint32_t TAXA = 16000;
constexpr int BLOCO = 512;  // amostras por leitura (~32 ms)
// O teto de uma fala. Era 15 s: no E2E de 2026-11-22 o dono ditou um endereço de e-mail segurando
// 22,5 s, a placa gravou 15 e cortou a soletração sem aviso (o e-mail foi a outro endereço). 30 s
// dão um WAV de 960.044 bytes, abaixo do teto de 1 MiB da ponte e do motor (`MAX_WAV`).
constexpr uint32_t MAX_GRAVACAO_S = 30;
constexpr uint32_t AVISO_S = 3;  // o LED avisa quando faltam estes segundos
constexpr uint32_t MAX_AMOSTRAS = TAXA * MAX_GRAVACAO_S;
constexpr uint32_t SEGURAR_MS = 400;       // menos que isto é um toque
constexpr uint32_t ENTRE_TOQUES_MS = 600;  // o segundo toque tem de vir antes disto
constexpr uint32_t DEBOUNCE_MS = 30;
// O ganho de 24 bits -> 16 bits, **congelado em 2 pelo dono em 2026-11-22** (a abertura da H2).
// A conta é `(int)(y/256) * GANHO`: trunca antes de multiplicar, então o ganho só desloca o volume
// (a mesma informação, o passo de quantização = GANHO). Com 8 a fala a ~50 cm saturava (921
// amostras); com 4, uma fala alta de perto ainda saturou 189 no E2E; com 2 há 6 dB a mais de folga.
// **Não mudar sem avisar o agente que treina a wake word** (o domínio do treino é este áudio: mudar
// o ganho depois da coleta é retreino). O filtro de silêncio do motor é relativo e não depende dele.
constexpr int GANHO = 2;
// O `HTTPClient::setTimeout` é `uint16_t` em ms (330000 virava 2320: o aviso -Woverflow da
// compilação de 2026-11-21). Por isso a ponte aceita na hora (202, "pensando") e o aparelho
// pergunta `GET /estado` a cada segundo até o resultado, com um teto total.
constexpr uint16_t PRAZO_HTTP_MS = 15000;
constexpr uint32_t ESPERA_TOTAL_MS = 330000;  // o turno do motor (até 220 s) e a fala inteira
constexpr uint32_t PERGUNTAR_A_CADA_MS = 1000;
constexpr uint32_t WDT_S = 360;

I2SClass i2s;
int32_t bloco[BLOCO];
int16_t *gravacao = nullptr;  // na PSRAM

#if TEM_ESCUTA
// Acordou: o LED aceso 1 s quando a escuta ouve a palavra (H2m2; o dono escolheu em 2026-11-27).
enum class Led : uint8_t { Ocioso, Gravando, Esperando, Aguardando, Ok, Desligado, Erro, Acordou };
#else
enum class Led : uint8_t { Ocioso, Gravando, Esperando, Aguardando, Ok, Desligado, Erro };
#endif
volatile Led led = Led::Ocioso;
volatile uint32_t aguardandoAte = 0;
volatile uint32_t gravandoDesde = 0;  // o aperto em curso (0 = nenhum): o LED acende passado o toque
volatile bool avisoDeLimite = false;  // a gravação está no fim (ou passou dele) e o botão segue apertado

void ledFisico(bool aceso) {
  digitalWrite(LED_BUILTIN, aceso ? LOW : HIGH);
  digitalWrite(PIN_LED_EXT, aceso ? HIGH : LOW);
}

// Depois de uma animação, o LED volta ao ocioso só se o laço não pôs outro estado no meio dela (um
// "esperando" novo não é apagado por um "ok" velho). A troca é atômica: as duas tarefas a disputam.
void voltarAoOcioso(Led animado) {
  static portMUX_TYPE trava = portMUX_INITIALIZER_UNLOCKED;
  portENTER_CRITICAL(&trava);
  if (led == animado) led = Led::Ocioso;
  portEXIT_CRITICAL(&trava);
}

// O LED numa tarefa própria: o laço principal fica bloqueado no HTTPS por até minutos.
void tarefaDoLed(void *) {
  for (;;) {
    switch (led) {
      case Led::Ocioso:
        if (avisoDeLimite) {  // está acabando (ou acabou): pisca bem rápido até soltar
          ledFisico(true);
          delay(60);
          ledFisico(false);
          delay(60);
          break;
        }
        // Um aperto em curso que passou do toque já é fala: o LED acende enquanto grava.
        ledFisico(gravandoDesde && millis() - gravandoDesde >= SEGURAR_MS);
        delay(20);
        break;
      case Led::Gravando:
        ledFisico(true);
        delay(50);
        break;
      case Led::Esperando:
        ledFisico(true);
        delay(120);
        ledFisico(false);
        delay(120);
        break;
      case Led::Aguardando:
        if (millis() > aguardandoAte) {
          led = Led::Ocioso;
          break;
        }
        ledFisico(true);
        delay(500);
        ledFisico(false);
        delay(500);
        break;
      case Led::Ok:
        ledFisico(true);
        delay(150);
        ledFisico(false);
        voltarAoOcioso(Led::Ok);
        break;
      case Led::Desligado:
        for (int i = 0; i < 2; i++) {
          ledFisico(true);
          delay(600);
          ledFisico(false);
          delay(300);
        }
        voltarAoOcioso(Led::Desligado);
        break;
      case Led::Erro:
        for (int i = 0; i < 3; i++) {
          ledFisico(true);
          delay(100);
          ledFisico(false);
          delay(100);
        }
        voltarAoOcioso(Led::Erro);
        break;
#if TEM_ESCUTA
      case Led::Acordou:
        ledFisico(true);
        delay(1000);
        ledFisico(false);
        voltarAoOcioso(Led::Acordou);
        break;
#endif
    }
  }
}

bool apertado() { return digitalRead(PIN_BOTAO) == LOW; }

// Espera o botão ficar em `alvo` por DEBOUNCE_MS seguidos; false se passar `prazoMs`.
bool esperarBotao(bool alvo, uint32_t prazoMs) {
  uint32_t inicio = millis(), estavelDesde = 0;
  while (millis() - inicio < prazoMs) {
    if (apertado() == alvo) {
      if (!estavelDesde) estavelDesde = millis();
      if (millis() - estavelDesde >= DEBOUNCE_MS) return true;
    } else {
      estavelDesde = 0;
    }
    delay(2);
  }
  return false;
}

// --- o microfone -------------------------------------------------------------------------------

// Grava desde o aperto enquanto o botão estiver apertado (ou até MAX_GRAVACAO_S). O começo da fala
// não se perde: a gravação nasce no aperto, e só depois se decide se foi fala ou toque (a revisão
// da H1 mediu que esperar os 400 ms antes cortava "Qual" de "Qual é a minha agenda"). Soltar
// precisa de 2 blocos seguidos (~64 ms) para valer (o debounce). Devolve o número de amostras; 0
// se o I2S parar de entregar.
// A medição para o filtro de silêncio (C4, camada 3, 2026-11-22): o RMS de cada quadro de 100 ms e
// o pico sem as pontas, onde caem os cliques do botão (a gravação nasce no aperto e morre no
// soltar). Só imprime; não muda o que vai à ponte.
constexpr uint32_t QUADRO = TAXA / 10;      // 100 ms
constexpr uint32_t PONTA = TAXA * 15 / 100;  // 150 ms de cada lado
void medir(uint32_t n) {
  int32_t picoMeio = 0;
  for (uint32_t i = PONTA; n > 2 * PONTA && i < n - PONTA; i++) {
    int32_t a = gravacao[i] < 0 ? -gravacao[i] : gravacao[i];
    if (a > picoMeio) picoMeio = a;
  }
  Serial.printf("medida: pico sem as pontas=%ld; rms por 100 ms:", (long)picoMeio);
  for (uint32_t q = 0; q + QUADRO <= n; q += QUADRO) {
    double s2 = 0;
    for (uint32_t i = q; i < q + QUADRO; i++) s2 += (double)gravacao[i] * gravacao[i];
    Serial.printf(" %.0f", sqrt(s2 / QUADRO));
  }
  Serial.println();
}

// O caminho do áudio, um só para o uso e para a coleta (o que o modelo da wake word aprende é
// exatamente isto): o I2S entrega frames de 32 bits com os 24 de dado alinhados à esquerda; `>>8`,
// o passa-alta de 1ª ordem (tira o DC; o estado é contínuo entre chamadas), e o 24 -> 16 bits
// truncado em direção ao zero **antes** do ganho, cortado no int16. Devolve as saturadas somadas.
float prevX = 0, prevY = 0;
void converter(const int32_t *entrada, int n, int16_t *saida, uint32_t &saturadas) {
  for (int i = 0; i < n; i++) {
    float x = entrada[i] >> 8;
    float y = x - prevX + 0.995f * prevY;
    prevX = x;
    prevY = y;
    int32_t s = (int32_t)(y / 256.0f) * GANHO;
    if (s > 32767) {
      s = 32767;
      saturadas++;
    }
    if (s < -32768) {
      s = -32768;
      saturadas++;
    }
    saida[i] = (int16_t)s;
  }
}

constexpr int BLOCOS_PARA_SOLTAR = 2;
constexpr int LEITURAS_CURTAS_MAX = 50;  // ~50 leituras sem um bloco inteiro: o I2S parou
uint32_t gravar() {
  uint32_t n = 0;
  int32_t pico = 0;
  double soma2 = 0;
  uint32_t saturadas = 0;
  int soltos = 0, curtas = 0;
  while (n + BLOCO <= MAX_AMOSTRAS) {
    size_t lidos = i2s.readBytes((char *)bloco, sizeof(bloco));
    if (lidos < sizeof(bloco)) {
      esp_task_wdt_reset();
      if (++curtas > LEITURAS_CURTAS_MAX) {
        Serial.println("ERRO: o I2S parou de entregar áudio");
        return 0;
      }
      if (!apertado() && ++soltos >= BLOCOS_PARA_SOLTAR) break;
      continue;
    }
    curtas = 0;
    converter(bloco, BLOCO, gravacao + n, saturadas);
    for (int i = 0; i < BLOCO; i++) {
      int32_t s = gravacao[n + i];
      int32_t a = s < 0 ? -s : s;
      if (a > pico) pico = a;
      soma2 += (double)s * s;
    }
    n += BLOCO;
    esp_task_wdt_reset();
    soltos = apertado() ? 0 : soltos + 1;
    if (soltos >= BLOCOS_PARA_SOLTAR) break;
    if (!avisoDeLimite && n >= MAX_AMOSTRAS - AVISO_S * TAXA) {
      avisoDeLimite = true;
      Serial.printf("gravacao: faltam %lu s\n", (unsigned long)AVISO_S);
    }
  }
  if (n + BLOCO > MAX_AMOSTRAS && apertado()) {
    Serial.printf("gravacao: chegou ao limite de %lu s; o que vier depois nao entra\n",
                  (unsigned long)MAX_GRAVACAO_S);
  }
  Serial.printf("gravado: %.2f s, pico=%ld, rms=%.0f, saturadas=%lu (ganho %d)\n", n / (float)TAXA,
                (long)pico, n ? sqrt(soma2 / n) : 0.0, (unsigned long)saturadas, GANHO);
  medir(n);
  return n;
}

// A gravação de um aperto: 0 se foi um toque (soltou antes de SEGURAR_MS; o áudio se descarta),
// senão as amostras da fala.
uint32_t gravarDecidindo(uint32_t apertouEm) {
  gravandoDesde = apertouEm;
  uint32_t amostras = gravar();
  gravandoDesde = 0;
  if (millis() - apertouEm < SEGURAR_MS) return 0;  // um toque
  Serial.println("botao: fala");
  return amostras;
}

// O WAV (PCM 16 kHz, mono, 16 bits): o cabeçalho e as amostras, num buffer novo da PSRAM.
uint8_t *montarWav(uint32_t amostras, size_t &tamanho) {
  uint32_t dados = amostras * 2;
  tamanho = 44 + dados;
  uint8_t *wav = (uint8_t *)ps_malloc(tamanho);
  if (!wav) return nullptr;
  auto u32 = [&](int off, uint32_t v) { memcpy(wav + off, &v, 4); };
  auto u16 = [&](int off, uint16_t v) { memcpy(wav + off, &v, 2); };
  memcpy(wav, "RIFF", 4);
  u32(4, 36 + dados);
  memcpy(wav + 8, "WAVEfmt ", 8);
  u32(16, 16);
  u16(20, 1);
  u16(22, 1);
  u32(24, TAXA);
  u32(28, TAXA * 2);
  u16(32, 2);
  u16(34, 16);
  memcpy(wav + 36, "data", 4);
  u32(40, dados);
  memcpy(wav + 44, gravacao, dados);
  return wav;
}

// --- a rede e a ponte ----------------------------------------------------------------------------

#if TEM_SEGREDOS
NetworkClientSecure cliente;

bool garantirWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.println("wifi: conectando...");
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  for (int i = 0; i < 60 && WiFi.status() != WL_CONNECTED; i++) {
    delay(250);
    esp_task_wdt_reset();
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.printf("wifi: falhou (status %d)\n", WiFi.status());
    return false;
  }
  Serial.printf("wifi: ok, sinal %d dBm\n", WiFi.RSSI());  // nem o nome da rede nem o IP no log
  return true;
}

// O estado que a ponte devolveu ("ok", "aguardando", "desligado", "vazio", "nada", "ocupado",
// "erro"), ou "sem-rede"/"http-N" quando nem chegou lá. A resposta é pequena: sem biblioteca JSON.
String pedirPonte(const char *rota, const uint8_t *corpo, size_t tamanho) {
  if (!garantirWifi()) return "sem-rede";
  HTTPClient http;
  http.setTimeout(PRAZO_HTTP_MS);
  http.setConnectTimeout(10000);
  if (!http.begin(cliente, PONTE_HOST, PONTE_PORTA, rota, true)) return "sem-rede";
  http.addHeader("Authorization", String("Bearer ") + APARELHO_TOKEN);
  int codigo;
  if (corpo) {
    http.addHeader("Content-Type", "audio/wav");
    codigo = http.POST((uint8_t *)corpo, tamanho);
  } else if (strcmp(rota, "/saude") == 0 || strcmp(rota, "/estado") == 0) {
    codigo = http.GET();
  } else {
    codigo = http.POST(String());
  }
  String texto = codigo > 0 ? http.getString() : "";
  http.end();
  if (codigo <= 0) {
    Serial.printf("ponte %s: falhou (%s)\n", rota, HTTPClient::errorToString(codigo).c_str());
    return "sem-rede";
  }
  int i = texto.indexOf("\"estado\":\"");
  String estado = i >= 0 ? texto.substring(i + 10, texto.indexOf('"', i + 10)) : "";
  if (texto.indexOf("\"ok\":true") >= 0) estado = "ok";  // o /saude
  if (estado.isEmpty()) estado = String("http-") + codigo;
  if (strcmp(rota, "/estado") != 0 || estado != "pensando") {  // sem uma linha por segundo
    Serial.printf("ponte %s: HTTP %d, estado %s\n", rota, codigo, estado.c_str());
  }
  return estado;
}

// Depois do 202: pergunta até sair do "pensando" (o LED pisca rápido enquanto isso).
String esperarResultado(String estado) {
  uint32_t inicio = millis();
  while (estado == "pensando") {
    if (millis() - inicio > ESPERA_TOTAL_MS) return "erro";
    delay(PERGUNTAR_A_CADA_MS);
    esp_task_wdt_reset();
    estado = pedirPonte("/estado", nullptr, 0);
    if (estado == "sem-rede") estado = "pensando";  // um soluço da Wi-Fi não perde a resposta
  }
  return estado;
}

void mostrar(const String &estado) {
  if (estado == "ok") {
    led = Led::Ok;
  } else if (estado == "aguardando") {
    aguardandoAte = millis() + 60000;
    led = Led::Aguardando;
  } else if (estado == "desligado") {
    led = Led::Desligado;
  } else if (estado == "vazio" || estado == "nada") {
    led = Led::Ocioso;
  } else {
    led = Led::Erro;
  }
}
#endif

// --- a coleta da wake word (H2) ----------------------------------------------------------------------

// Um firmware só (D71): a placa liga sempre no uso. Com o laço parado, a linha PEDIDO_COLETA vinda
// pela USB (o `coleta.py` do Mac) põe a placa na coleta: o áudio vai sem parar pela USB, pelo mesmo
// `converter` do uso, e nada vai à ponte. Na coleta, a mesma linha repetida é o sinal de que o Mac
// segue lá; PEDIDO_USO, ou SINAL_MS sem sinal (o Mac travou ou dormiu), reinicia a placa, e ela volta
// no uso: a voz do estúdio nunca fica desligada à espera de alguém. Só quem tem o cabo USB pede.
constexpr char PEDIDO_COLETA[] = "VKC1 COLETA";
constexpr char PEDIDO_USO[] = "VKC1 USO";
constexpr uint32_t SINAL_MS = 30000;
constexpr int BLOCOS_VELHOS = 16;  // o áudio velho que o DMA guardou com o laço parado (~0,5 s)
bool emColeta = false;
uint32_t ultimoSinal = 0;

#if TEM_ESCUTA
// O limiar da escuta pela USB: `VKC1 LIMIAR 0.95` (gravado no NVS, ligado a este modelo). Não é um
// Pedido: o laço o trata depois (`limiarPendente`), e a coleta o ignora.
constexpr char PEDIDO_LIMIAR[] = "VKC1 LIMIAR ";
float limiarPedido = -1;  // < 0: o número não se leu
bool limiarPendente = false;
#endif
enum class Pedido : uint8_t { Nenhum, Coleta, Uso };
Pedido lerPedido() {
  static char linha[24];
  static size_t n = 0;
  Pedido visto = Pedido::Nenhum;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n') {
      linha[n < sizeof(linha) ? n : sizeof(linha) - 1] = 0;
      bool coube = n < sizeof(linha);  // uma linha comprida demais nunca é pedido
      n = 0;
      if (coube && strcmp(linha, PEDIDO_USO) == 0) return Pedido::Uso;
      if (coube && strcmp(linha, PEDIDO_COLETA) == 0) visto = Pedido::Coleta;
#if TEM_ESCUTA
      if (coube && strncmp(linha, PEDIDO_LIMIAR, sizeof(PEDIDO_LIMIAR) - 1) == 0) {
        const char *numero = linha + sizeof(PEDIDO_LIMIAR) - 1;
        char *fim = nullptr;
        float v = strtof(numero, &fim);
        limiarPedido = (fim != numero && *fim == 0) ? v : -1;
        limiarPendente = true;
      }
#endif
    } else if (c != '\r') {
      if (n < sizeof(linha) - 1) linha[n] = c;
      if (n < sizeof(linha)) n++;
    }
  }
  return visto;
}

// Um quadro por bloco do I2S (32 ms), little-endian: "VKC1" | seq u32 | t_us u32 (micros() logo
// depois da leitura) | n u16 | flags u16 (bit 0 = botão apertado) | n × int16 | FNV-1a 32 de tudo
// entre o mágico e ele. O `coleta.py` do Mac confere o seq (buraco = quadro perdido), o checksum e o
// tempo (um transbordo do DMA do I2S não pula o seq, mas aparece no t_us).
constexpr char MAGICO[4] = {'V', 'K', 'C', '1'};
constexpr int QUADRO_BYTES = 4 + 4 + 4 + 2 + 2 + BLOCO * 2 + 4;
constexpr uint32_t STATUS_A_CADA_MS = 10000;
uint8_t quadro[QUADRO_BYTES];
int16_t blocoColetado[BLOCO];

uint32_t fnv1a(const uint8_t *dados, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; i++) {
    h ^= dados[i];
    h *= 16777619u;
  }
  return h;
}

void coletar() {
  static uint32_t seq = 0, descartados = 0, curtas = 0, saturadas = 0, maiorVoltaUs = 0;
  static uint32_t ultimoStatus = 0;
  size_t lidos = i2s.readBytes((char *)bloco, sizeof(bloco));
  esp_task_wdt_reset();
  if (lidos < sizeof(bloco)) {
    curtas++;  // o bloco incompleto se perde: o Mac vê pelo t_us
    return;
  }
  uint32_t t = micros();
  converter(bloco, BLOCO, blocoColetado, saturadas);
  uint16_t n = BLOCO, flags = apertado() ? 1 : 0;
  memcpy(quadro, MAGICO, 4);
  memcpy(quadro + 4, &seq, 4);
  memcpy(quadro + 8, &t, 4);
  memcpy(quadro + 12, &n, 2);
  memcpy(quadro + 14, &flags, 2);
  memcpy(quadro + 16, blocoColetado, BLOCO * 2);
  uint32_t soma = fnv1a(quadro + 4, QUADRO_BYTES - 8);
  memcpy(quadro + QUADRO_BYTES - 4, &soma, 4);
  // O quadro vai inteiro ou não vai: meio quadro viraria lixo no Mac, e esperar a USB atrasaria o
  // I2S. Sem espaço, descarta, e o seq pula (o Mac conta a lacuna).
  if (Serial.availableForWrite() >= QUADRO_BYTES) {
    Serial.write(quadro, QUADRO_BYTES);
  } else {
    descartados++;
  }
  seq++;
  uint32_t volta = micros() - t;
  if (volta > maiorVoltaUs) maiorVoltaUs = volta;
  if (millis() - ultimoStatus >= STATUS_A_CADA_MS) {
    ultimoStatus = millis();
    Serial.printf("\ncoleta: status ganho=%d seq=%lu descartados=%lu curtas=%lu saturadas=%lu "
                  "maior_volta_us=%lu\n",
                  GANHO, (unsigned long)seq, (unsigned long)descartados, (unsigned long)curtas,
                  (unsigned long)saturadas, (unsigned long)maiorVoltaUs);
    maiorVoltaUs = 0;
  }
}

void entrarNaColeta() {
  emColeta = true;
  ultimoSinal = millis();
  led = Led::Ocioso;
  Serial.printf("\ncoleta: ganho=%d taxa=%lu bloco=%d quadro=%d\n", GANHO, (unsigned long)TAXA, BLOCO,
                QUADRO_BYTES);
  for (int i = 0; i < BLOCOS_VELHOS; i++) {
    i2s.readBytes((char *)bloco, sizeof(bloco));
    esp_task_wdt_reset();
  }
}

void voltarAoUso(const char *motivo) {
  Serial.printf("\ncoleta: volta ao uso (%s)\n", motivo);
  Serial.flush();
  delay(200);
  ESP.restart();  // pelo boot: o uso começa do mesmo estado de sempre
}

void lacoDaColeta() {
  Pedido pedido = lerPedido();
  if (pedido == Pedido::Uso) voltarAoUso("pedido do Mac");
  if (pedido == Pedido::Coleta) ultimoSinal = millis();
  if (millis() - ultimoSinal > SINAL_MS) voltarAoUso("sem sinal do Mac");
  coletar();
}

#if TEM_ESCUTA
// --- a escuta contínua (H2m2) ----------------------------------------------------------------------

// Com a placa parada, um bloco do I2S por volta do laço, pelo mesmo `converter()`. O I2S guarda 6 x
// 240 amostras (90 ms; o padrão do ESP_I2S): uma volta do laço mais longa que isso perde áudio, e a
// linha de status diz a maior.
constexpr uint32_t DMA_US = 6 * 240 * 1000000ull / TAXA;
constexpr uint32_t STATUS_ESCUTA_MS = 60000;
bool escutaLigada = false;
bool escutaRecomeca = false;  // depois de um aperto ou de um turno: o áudio velho não conta
int16_t blocoEscuta[BLOCO];

void ouvirUmBloco() {
  static uint32_t fimDaLeitura = 0, maiorVolta = 0, voltasLongas = 0, curtas = 0, saturadas = 0;
  static uint32_t ultimoStatus = millis();
  if (escutaRecomeca) {
    escutaRecomeca = false;
    escutaRecomecar();
    for (int i = 0; i < BLOCOS_VELHOS; i++) {
      i2s.readBytes((char *)bloco, sizeof(bloco));
      esp_task_wdt_reset();
    }
    fimDaLeitura = 0;
  }
  uint32_t comeco = micros();
  if (fimDaLeitura) {
    uint32_t volta = comeco - fimDaLeitura;  // o tempo em que ninguém leu o I2S
    if (volta > maiorVolta) maiorVolta = volta;
    if (volta > DMA_US - 32000) voltasLongas++;  // perto de transbordar
  }
  size_t lidos = i2s.readBytes((char *)bloco, sizeof(bloco));
  fimDaLeitura = micros();
  if (lidos < sizeof(bloco)) {
    curtas++;
    return;
  }
  converter(bloco, BLOCO, blocoEscuta, saturadas);
  uint8_t media = 0;
  if (escutaOuvir(blocoEscuta, BLOCO, media)) {
    led = Led::Acordou;
    Serial.printf("escuta: acordou (media %u/255 = %.3f; limiar %.3f %s)\n", media, media / 255.0f,
                  escutaLimiar() / 1000.0f, escutaOrigemDoLimiar());
  }
  if (millis() - ultimoStatus >= STATUS_ESCUTA_MS) {
    ultimoStatus = millis();
    EstadoDaEscuta e = escutaEstado();
    Serial.printf("escuta: status invocacoes=%lu media_us=%lu maior_us=%lu maior_volta_us=%lu "
                  "voltas_longas=%lu curtas=%lu acordou=%lu maior_media=%u heap=%u\n",
                  (unsigned long)e.invocacoes,
                  (unsigned long)(e.invocacoes ? e.somaUs / e.invocacoes : 0),
                  (unsigned long)e.maiorUs, (unsigned long)maiorVolta, (unsigned long)voltasLongas,
                  (unsigned long)curtas, (unsigned long)e.acordou, e.maiorMedia,
                  (unsigned)ESP.getFreeHeap());
    maiorVolta = voltasLongas = curtas = 0;
  }
}

void tratarLimiar() {
  float v = limiarPedido;
  uint16_t m = v > 0 ? (uint16_t)(v * 1000.0f + 0.5f) : 0;
  if (v > 0 && escutaMudarLimiar(m)) {
    Serial.printf("escuta: limiar %.3f (gravado)\n", m / 1000.0f);
  } else {
    Serial.printf("escuta: limiar recusado (entre %.3f e %.3f; segue %.3f)\n",
                  ESCUTA_LIMIAR_MIN / 1000.0f, ESCUTA_LIMIAR_MAX / 1000.0f,
                  escutaLimiar() / 1000.0f);
  }
}
#endif

// --- o laço ----------------------------------------------------------------------------------------

void setup() {
  Serial.setTxBufferSize(16384);  // a coleta: ~15 quadros de folga para a USB
  Serial.setTxTimeoutMs(5);
  Serial.begin(115200);
  delay(500);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PIN_LED_EXT, OUTPUT);
  pinMode(PIN_BOTAO, INPUT_PULLUP);
  ledFisico(false);
  Serial.println("\n== Viking voz (H1) ==");
  Serial.printf("chip %s rev %d; psram livre: %u bytes\n", ESP.getChipModel(),
                ESP.getChipRevision(), (unsigned)ESP.getFreePsram());

  esp_task_wdt_config_t wdt = {
      .timeout_ms = WDT_S * 1000, .idle_core_mask = 0, .trigger_panic = true};
  esp_task_wdt_reconfigure(&wdt);
  esp_task_wdt_add(NULL);

  gravacao = (int16_t *)ps_malloc(MAX_AMOSTRAS * sizeof(int16_t));
  if (!gravacao) {
    Serial.println("ERRO: sem PSRAM para a gravação");
    while (true) {
      ledFisico(true);
      delay(100);
      ledFisico(false);
      delay(100);
      esp_task_wdt_reset();
    }
  }
  i2s.setPins(PIN_BCLK, PIN_WS, -1, PIN_DIN);
  if (!i2s.begin(I2S_MODE_STD, TAXA, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO,
                 I2S_STD_SLOT_LEFT)) {
    Serial.println("ERRO: i2s.begin falhou");
    while (true) {
      delay(1000);
      esp_task_wdt_reset();
    }
  }
  xTaskCreatePinnedToCore(tarefaDoLed, "led", 2048, nullptr, 1, nullptr, 0);
  Serial.printf("botao: D1 (GPIO%d), %s\n", PIN_BOTAO, apertado() ? "APERTADO no boot?" : "solto");

#if TEM_SEGREDOS
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  cliente.setCACert(PONTE_CERTIFICADO);
  if (garantirWifi()) {
    configTime(0, 0, "pool.ntp.org", "time.google.com");  // a validade do certificado
    struct tm agora;
    Serial.println(getLocalTime(&agora, 10000) ? "hora: ok" : "hora: sem NTP (segue)");
    Serial.printf("ponte: saude -> %s\n", pedirPonte("/saude", nullptr, 0).c_str());
  }
#else
  Serial.println("sem src/segredos.h: só o diagnóstico (botão, LED e microfone), nada vai à rede");
#endif
#if TEM_ESCUTA
  escutaLigada = escutaComecar();
  if (escutaLigada) {
    EstadoDaEscuta e = escutaEstado();
    Serial.printf("escuta: ligada, limiar %.3f (%s), arena %u bytes, modelo %s\n",
                  escutaLimiar() / 1000.0f, escutaOrigemDoLimiar(), (unsigned)e.arena,
                  escutaMarcaDoModelo());
  }
  escutaRecomeca = true;
#endif
  Serial.println(">>> PRONTO: segure o botão para falar; dois toques para aprovar <<<");
}

void loop() {
  if (emColeta) {
    lacoDaColeta();
    return;
  }
  if (lerPedido() == Pedido::Coleta) {
    entrarNaColeta();
    return;
  }
  esp_task_wdt_reset();
#if TEM_ESCUTA
  if (limiarPendente) {
    limiarPendente = false;
    tratarLimiar();
  }
  if (escutaLigada && !apertado()) {
    ouvirUmBloco();
    return;
  }
  if (!esperarBotao(true, escutaLigada ? 100 : 1000)) return;  // nada apertado (ou um soluço)
  escutaRecomeca = true;  // o aperto e o turno: a escuta recomeça do zero depois
#else
  if (!esperarBotao(true, 1000)) return;  // nada apertado
#endif
  uint32_t apertouEm = millis();
  // Grava já; depois decide: segurou (>= SEGURAR_MS) é fala, soltou antes é toque (talvez o
  // primeiro de dois). O LED só acende de "gravando" se passou do toque.
  uint32_t amostras = gravarDecidindo(apertouEm);
  if (amostras) {
    // Passou do teto (MAX_GRAVACAO_S) ainda apertado: espera soltar, para não começar outra.
    while (apertado()) {
      delay(10);
      esp_task_wdt_reset();
    }
    avisoDeLimite = false;
    Serial.printf("botao: soltou (%lu ms)\n", (unsigned long)(millis() - apertouEm));
    led = Led::Ocioso;
#if TEM_SEGREDOS
    size_t tamanho = 0;
    uint8_t *wav = montarWav(amostras, tamanho);
    if (!wav) {
      Serial.println("ERRO: sem PSRAM para o WAV");
      led = Led::Erro;
      return;
    }
    led = Led::Esperando;
    String estado = pedirPonte("/falar", wav, tamanho);
    free(wav);
    mostrar(esperarResultado(estado));
#else
    (void)amostras;
    led = Led::Ok;
#endif
    return;
  }
  // Um toque curto: o segundo tem de vir logo.
  if (esperarBotao(true, ENTRE_TOQUES_MS) && esperarBotao(false, SEGURAR_MS)) {
    Serial.println("botao: dois toques");
#if TEM_SEGREDOS
    led = Led::Esperando;
    mostrar(esperarResultado(pedirPonte("/toque", nullptr, 0)));
#else
    led = Led::Ok;
#endif
  } else {
    Serial.println("botao: um toque (nada)");
    esperarBotao(false, 2000);
  }
}
