// O teste do modelo da wake word na placa (Sessão H2m1 do LifeOs, D73): um firmware à parte, que
// não ouve o microfone nem vai à rede. Ele responde ao agente do Colab, medido na XIAO ESP32-S3:
//   (a) o TFLM carrega o modelo e o invoca? (as 13 operações, as 6 variáveis, os 2 subgrafos)
//   (b) quanta arena ele usa, e a menor com que ainda aloca e invoca;
//   (c) o frontend do treino (pymicro-features 2.0.2) dá, sobre o WAV de referência, os mesmos
//       197 x 40 quadros do Python (README_paridade.md: igualdade exata, porque é aritmética
//       inteira);
//   (d) a entrada int8 pela fórmula inteira do firmware, com saturação;
//   (e) o modelo sobre os 197 quadros de referência, de 3 em 3, três vezes: A num interpretador
//       novo, B depois do Reset() (o estado zerado) e C noutro interpretador novo; A = B prova que o
//       estado zera, e A = C, que o resultado não depende de nada guardado;
//   (f) os tempos do frontend por quadro e do Invoke.
//
// O resultado sai uma vez, depois do boot; `VKC1 RELATORIO` pela USB o repete. As linhas `FE,k,...`
// e `SAIDAS,R,...` são lidas por `gerar_modelo.py conferir`. O modelo e o vetor entram por
// cabeçalhos gerados por `gerar_modelo.py gerar` (fora do git: o modelo é da voz do dono).
// Compila só no env `xiao_s3_modelo`; o firmware de uso (src/main.cpp) é outro.

#include <Arduino.h>

#include <cstdarg>
#include <cstring>
#include <new>

#include "modelo.h"
#include "paridade.h"
#include "tensorflow/lite/micro/flatbuffer_utils.h"
#include "tensorflow/lite/micro/micro_allocator.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend_util.h"

// --- o log do TFLM pela USB ---------------------------------------------------------------------
// O `debug_log.cc` do TFLM escreve no stderr, que no Arduino não é a USB: o erro literal se
// perderia. Por isso a lib vem sem ele (buscar_libs.sh) e o log sai aqui.
static bool calado = false;  // a busca da menor arena erra de propósito
extern "C" void DebugLog(const char *format, va_list args) {
  if (calado) return;
  char texto[256];
  vsnprintf(texto, sizeof(texto), format, args);
  Serial.print(texto);
}
extern "C" int DebugVsnprintf(char *buffer, size_t buf_size, const char *format, va_list vlist) {
  return vsnprintf(buffer, buf_size, format, vlist);
}

// --- o modelo ------------------------------------------------------------------------------------
constexpr int OPERACOES = 13;
constexpr int VARIAVEIS_MAX = 20;  // o modelo tem 6 (lidas do .tflite em 2026-11-23)
constexpr size_t ARENA = 64 * 1024;  // o hey_viking.json estima 11.161
constexpr int PASSO = 3;             // a entrada do modelo é [1, 3, 40]
constexpr int INVOCACOES = PARIDADE_QUADROS / PASSO;
constexpr float ESCALA_ENTRADA = 26.0f / 255.0f;  // o README_paridade.md, medido no .tflite
constexpr int ZERO_ENTRADA = -128;

alignas(16) static uint8_t arena[ARENA];
alignas(tflite::MicroInterpreter) static uint8_t lugar[sizeof(tflite::MicroInterpreter)];
static tflite::MicroInterpreter *interpretador = nullptr;
static tflite::MicroMutableOpResolver<OPERACOES> resolver;
static const tflite::Model *modelo = nullptr;

void desmontar() {
  if (interpretador) interpretador->~MicroInterpreter();
  interpretador = nullptr;
}

// Um interpretador novo, com a arena (os primeiros `tamanho` bytes dela) do zero: o alocador e as
// variáveis moram dentro da arena, então nada sobra do anterior.
bool montar(size_t tamanho) {
  desmontar();
  tflite::MicroAllocator *alocador = tflite::MicroAllocator::Create(arena, tamanho);
  if (!alocador) return false;
  tflite::MicroResourceVariables *variaveis =
      tflite::MicroResourceVariables::Create(alocador, VARIAVEIS_MAX);
  if (!variaveis) return false;
  interpretador = new (lugar) tflite::MicroInterpreter(modelo, resolver, alocador, variaveis);
  return interpretador->initialization_status() == kTfLiteOk &&
         interpretador->AllocateTensors() == kTfLiteOk;
}

bool registrar() {
  TfLiteStatus s[OPERACOES] = {
      resolver.AddCallOnce(),        resolver.AddVarHandle(),     resolver.AddReshape(),
      resolver.AddReadVariable(),    resolver.AddConcatenation(), resolver.AddStridedSlice(),
      resolver.AddAssignVariable(),  resolver.AddConv2D(),        resolver.AddDepthwiseConv2D(),
      resolver.AddSplitV(),          resolver.AddFullyConnected(), resolver.AddLogistic(),
      resolver.AddQuantize()};
  bool ok = true;
  for (TfLiteStatus x : s) ok = ok && x == kTfLiteOk;
  return ok;
}

// As operações que o próprio modelo pede, cada uma conferida no resolver (a lista que conta é a do
// arquivo, não a de cima).
int operacoesFaltando() {
  auto *codigos = modelo->operator_codes();
  int faltam = 0;
  Serial.printf("ops do modelo: %u;", codigos ? (unsigned)codigos->size() : 0u);
  for (unsigned i = 0; codigos && i < codigos->size(); i++) {
    tflite::BuiltinOperator op = tflite::micro::GetBuiltinCode(codigos->Get(i));
    bool tem = resolver.FindOp(op) != nullptr;
    Serial.printf(" %s%s", tflite::EnumNameBuiltinOperator(op), tem ? "" : "(FALTA)");
    if (!tem) faltam++;
  }
  Serial.println();
  return faltam;
}

bool invocarComReferencia(uint8_t *saidas, uint32_t &somaUs, uint32_t &maiorUs) {
  TfLiteTensor *entrada = interpretador->input(0);
  TfLiteTensor *saida = interpretador->output(0);
  for (int i = 0; i < INVOCACOES; i++) {
    memcpy(entrada->data.int8, PARIDADE_INT8[i * PASSO], PASSO * PARIDADE_CANAIS);
    uint32_t t0 = micros();
    if (interpretador->Invoke() != kTfLiteOk) return false;
    uint32_t dt = micros() - t0;
    somaUs += dt;
    if (dt > maiorUs) maiorUs = dt;
    saidas[i] = saida->data.uint8[0];
  }
  return true;
}

void imprimirSaidas(const char *rodada, const uint8_t *q) {
  Serial.printf("SAIDAS,%s,", rodada);
  for (int i = 0; i < INVOCACOES; i++) Serial.printf(i ? " %u" : "%u", q[i]);
  Serial.println();
}

// --- o frontend ----------------------------------------------------------------------------------
static uint16_t placa[PARIDADE_QUADROS][PARIDADE_CANAIS];

// O mesmo `init_cfg` do pymicro-features 2.0.2 (src/micro_features.cpp).
void configurar(FrontendConfig &c) {
  c.window.size_ms = 30;
  c.window.step_size_ms = 10;
  c.filterbank.num_channels = 40;
  c.filterbank.lower_band_limit = 125.0f;
  c.filterbank.upper_band_limit = 7500.0f;
  c.noise_reduction.smoothing_bits = 10;
  c.noise_reduction.even_smoothing = 0.025f;
  c.noise_reduction.odd_smoothing = 0.06f;
  c.noise_reduction.min_signal_remaining = 0.05f;
  c.pcan_gain_control.enable_pcan = 1;
  c.pcan_gain_control.strength = 0.95f;
  c.pcan_gain_control.offset = 80.0f;
  c.pcan_gain_control.gain_bits = 21;
  c.log_scale.enable_log = 1;
  c.log_scale.scale_shift = 6;
}

int8_t int8DoRaw(uint16_t raw) {  // (raw*1275 - 425984) / 3328, truncado para o zero e saturado
  int32_t q = ((int32_t)raw * 1275 - 425984) / 3328;
  return (int8_t)(q > 127 ? 127 : (q < -128 ? -128 : q));
}

// --- o relatório ---------------------------------------------------------------------------------
struct Resultado {
  bool versao = false, registrou = false, alocou = false, invocou = false;
  int faltam = -1;
  size_t usada = 0, menor = 0;
  int quadros = 0, sobra = 0, diferentes = 0, maiorDiferenca = 0;
  int int8Placa = 0, int8Ref = 0;
  bool frontendOk = false;
  uint32_t feSomaUs = 0, feMaiorUs = 0, invSomaUs = 0, invMaiorUs = 0, invocacoes = 0;
  uint8_t a[INVOCACOES], b[INVOCACOES], c[INVOCACOES];
  bool bOk = false, cOk = false;
  char entrada[96] = "", saida[96] = "";
};
static Resultado r;

void testarFrontend() {
  FrontendConfig cfg;
  FrontendState st;
  configurar(cfg);
  r.frontendOk = FrontendPopulateState(&cfg, &st, 16000) != 0;
  if (!r.frontendOk) return;
  const size_t total = PARIDADE_AMOSTRAS * 2;
  size_t idx = 0;  // em bytes, como o laço do treino
  while (idx + 320 < total) {
    size_t lidas = 0;
    uint32_t t0 = micros();
    FrontendOutput fo = FrontendProcessSamples(&st, PARIDADE_WAV + idx / 2, 160, &lidas);
    uint32_t dt = micros() - t0;
    idx += lidas * 2;
    if (lidas == 0) break;  // não avançaria nunca
    if (!fo.size) continue;
    r.feSomaUs += dt;
    if (dt > r.feMaiorUs) r.feMaiorUs = dt;
    if (r.quadros < PARIDADE_QUADROS && fo.size == PARIDADE_CANAIS) {
      memcpy(placa[r.quadros], fo.values, sizeof(placa[0]));
      r.quadros++;
    } else {
      r.sobra++;
    }
  }
  FrontendFreeStateContents(&st);
  for (int k = 0; k < r.quadros; k++) {
    for (int j = 0; j < PARIDADE_CANAIS; j++) {
      int d = (int)placa[k][j] - (int)PARIDADE_RAW[k][j];
      if (d) {
        r.diferentes++;
        if (abs(d) > r.maiorDiferenca) r.maiorDiferenca = abs(d);
      }
      if (int8DoRaw(placa[k][j]) != PARIDADE_INT8[k][j]) r.int8Placa++;
      if (int8DoRaw(PARIDADE_RAW[k][j]) != PARIDADE_INT8[k][j]) r.int8Ref++;
    }
  }
}

void descreverTensores() {
  TfLiteTensor *e = interpretador->input(0), *s = interpretador->output(0);
  auto forma = [](TfLiteTensor *t, char *buf, size_t n) {
    int p = snprintf(buf, n, "%s [", TfLiteTypeGetName(t->type));
    for (int i = 0; t->dims && i < t->dims->size; i++)
      p += snprintf(buf + p, n - p, i ? ",%d" : "%d", t->dims->data[i]);
    snprintf(buf + p, n - p, "] escala=%.9f zero=%d", t->params.scale, (int)t->params.zero_point);
  };
  forma(e, r.entrada, sizeof(r.entrada));
  forma(s, r.saida, sizeof(r.saida));
}

void testarModelo() {
  modelo = tflite::GetModel(MODELO);
  r.versao = modelo->version() == TFLITE_SCHEMA_VERSION;
  if (!r.versao) return;
  r.registrou = registrar();
  r.faltam = operacoesFaltando();
  r.alocou = montar(ARENA);
  if (!r.alocou) return;
  r.usada = interpretador->arena_used_bytes();
  descreverTensores();
  r.invocou = invocarComReferencia(r.a, r.invSomaUs, r.invMaiorUs);
  if (!r.invocou) return;
  r.invocacoes = INVOCACOES;
  r.bOk = interpretador->Reset() == kTfLiteOk &&
          invocarComReferencia(r.b, r.invSomaUs, r.invMaiorUs);
  if (r.bOk) r.invocacoes += INVOCACOES;
  r.cOk = montar(ARENA) && invocarComReferencia(r.c, r.invSomaUs, r.invMaiorUs);
  if (r.cOk) r.invocacoes += INVOCACOES;
  // A menor arena que aloca e invoca, de 16 em 16 bytes (a arena dá o alinhamento de 16).
  calado = true;
  size_t baixo = 0, alto = ARENA;  // `alto` sempre funciona; `baixo` nunca
  while (alto - baixo > 16) {
    size_t meio = ((baixo + alto) / 2) & ~(size_t)15;
    if (meio <= baixo) meio = baixo + 16;
    bool ok = montar(meio) && interpretador->Invoke() == kTfLiteOk;
    (ok ? alto : baixo) = meio;
  }
  calado = false;
  r.menor = alto;
  desmontar();
}

bool iguais(const uint8_t *x, const uint8_t *y) { return memcmp(x, y, INVOCACOES) == 0; }

void relatorio() {
  Serial.println("\n== Viking voz: teste do modelo (H2m1) ==");
  Serial.printf("chip %s rev %d a %lu MHz; heap livre %u bytes\n", ESP.getChipModel(),
                ESP.getChipRevision(), (unsigned long)getCpuFrequencyMhz(),
                (unsigned)ESP.getFreeHeap());
  Serial.printf("modelo: %u bytes, sha256 %s, subgrafos %u\n", (unsigned)MODELO_TAMANHO,
                MODELO_SHA256, modelo && modelo->subgraphs() ? modelo->subgraphs()->size() : 0u);
  Serial.printf("versao do schema: %s; resolver: %s; ops faltando: %d\n", r.versao ? "ok" : "ERRADA",
                r.registrou ? "ok" : "FALHOU", r.faltam);
  Serial.printf("carregou=%s invoke=%s\n", r.alocou ? "sim" : "nao", r.invocou ? "ok" : "falhou");
  if (r.alocou) {
    Serial.printf("entrada: %s\nsaida: %s\n", r.entrada, r.saida);
    Serial.printf("arena: usada=%u de %u; a menor que aloca e invoca: %u\n", (unsigned)r.usada,
                  (unsigned)ARENA, (unsigned)r.menor);
  }
  Serial.printf("wav: %u amostras, sha256 %s\n", (unsigned)PARIDADE_AMOSTRAS, PARIDADE_WAV_SHA256);
  for (int k = 0; k < r.quadros; k++) {
    Serial.printf("FE,%d", k);
    for (int j = 0; j < PARIDADE_CANAIS; j++) Serial.printf(",%u", placa[k][j]);
    Serial.println();
  }
  if (!r.frontendOk) Serial.println("frontend: FrontendPopulateState FALHOU");
  Serial.printf("frontend: %dx%d, %d diferentes (maior diferenca %d); quadros a mais: %d\n",
                r.quadros, PARIDADE_CANAIS, r.diferentes, r.maiorDiferenca, r.sobra);
  Serial.printf("int8: %d de %d (do frontend da placa); a formula sobre o cru da referencia: %d\n",
                r.int8Placa, PARIDADE_QUADROS * PARIDADE_CANAIS, r.int8Ref);
  if (r.invocou) imprimirSaidas("A", r.a);
  if (r.bOk) imprimirSaidas("B", r.b);
  if (r.cOk) imprimirSaidas("C", r.c);
  if (r.invocou) {
    Serial.printf("estado zerado (A=B): %s; interpretador novo (A=C): %s\n",
                  !r.bOk ? "FALHOU" : (iguais(r.a, r.b) ? "iguais" : "DIFERENTES"),
                  !r.cOk ? "FALHOU" : (iguais(r.a, r.c) ? "iguais" : "DIFERENTES"));
  }
  Serial.printf("tempos: frontend media=%lu us maior=%lu us por quadro; invoke media=%lu us "
                "maior=%lu us (%lu invocacoes)\n",
                (unsigned long)(r.quadros ? r.feSomaUs / r.quadros : 0),
                (unsigned long)r.feMaiorUs,
                (unsigned long)(r.invocacoes ? r.invSomaUs / r.invocacoes : 0),
                (unsigned long)r.invMaiorUs, (unsigned long)r.invocacoes);
  Serial.println("== FIM do teste do modelo ==");
}

void setup() {
  Serial.setTxBufferSize(16384);
  Serial.begin(115200);
  for (uint32_t t = millis(); !Serial && millis() - t < 5000;) delay(10);  // o Mac abrir a porta
  delay(1500);
  Serial.println("\nteste do modelo: comecando (o microfone e a rede ficam desligados)");
  testarModelo();
  testarFrontend();
  relatorio();
}

void loop() {
  static char linha[24];
  static size_t n = 0;
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n') {
      linha[n < sizeof(linha) ? n : sizeof(linha) - 1] = 0;
      if (n < sizeof(linha) && strcmp(linha, "VKC1 RELATORIO") == 0) relatorio();
      n = 0;
    } else if (ch != '\r') {
      if (n < sizeof(linha) - 1) linha[n] = ch;
      if (n < sizeof(linha)) n++;
    }
  }
  delay(20);
}
