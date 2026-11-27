// A escuta contínua da wake word (H2m2, D73): ver `escuta.h`.
#include "escuta.h"

#if TEM_ESCUTA
#include <Arduino.h>
#include <Preferences.h>

#include <cstdarg>
#include <cstring>
#include <new>

#include "modelo.h"
#include "tensorflow/lite/micro/micro_allocator.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_resource_variable.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend_util.h"

// O log do TFLM pela USB (a lib vem sem o `debug_log.cc`, que escreveria no stderr).
extern "C" void DebugLog(const char *format, va_list args) {
  char texto[256];
  vsnprintf(texto, sizeof(texto), format, args);
  Serial.print(texto);
}
extern "C" int DebugVsnprintf(char *buffer, size_t buf_size, const char *format, va_list vlist) {
  return vsnprintf(buffer, buf_size, format, vlist);
}

namespace {

constexpr int CANAIS = 40;
constexpr int PEDACO = 160;  // 10 ms: o passo do frontend do treino
constexpr int PASSO = 3;     // a entrada do modelo é [1, 3, 40]: uma invocação a cada 30 ms
constexpr int POR_SEGUNDO = 16000 / (PEDACO * PASSO);  // 33 invocações
constexpr int AQUECIMENTO = POR_SEGUNDO;                // 1 s sem decidir depois de cada recomeço
constexpr int ESPERA = 2 * POR_SEGUNDO;                 // 2 s sem decidir depois de acordar
constexpr size_t ARENA = 32 * 1024;                     // a H2m1 mediu 20.988 bytes
constexpr int VARIAVEIS_MAX = 20;                       // o modelo tem 6
constexpr int OPERACOES = 13;

alignas(16) uint8_t arena[ARENA];
alignas(tflite::MicroInterpreter) uint8_t lugar[sizeof(tflite::MicroInterpreter)];
tflite::MicroInterpreter *interpretador = nullptr;
tflite::MicroMutableOpResolver<OPERACOES> resolver;
FrontendState frontend;
bool montada = false;

int16_t pendente[PEDACO];
int nPendente = 0;
int8_t quadros[PASSO][CANAIS];
int nQuadros = 0;
uint8_t saidas[MODELO_JANELA];
int nSaidas = 0, proxima = 0;
int ignorar = AQUECIMENTO;

uint16_t limiar = MODELO_LIMIAR_MILESIMOS;
const char *origem = "do modelo";
char marca[9];  // o começo do sha256 do modelo: o limiar do NVS só vale para ele
EstadoDaEscuta estado;

int8_t int8DoRaw(uint16_t raw) {  // (raw*1275 - 425984) / 3328, truncado para o zero e saturado
  int32_t q = ((int32_t)raw * 1275 - 425984) / 3328;
  return (int8_t)(q > 127 ? 127 : (q < -128 ? -128 : q));
}

bool registrar() {
  TfLiteStatus s[OPERACOES] = {
      resolver.AddCallOnce(),       resolver.AddVarHandle(),      resolver.AddReshape(),
      resolver.AddReadVariable(),   resolver.AddConcatenation(),  resolver.AddStridedSlice(),
      resolver.AddAssignVariable(), resolver.AddConv2D(),         resolver.AddDepthwiseConv2D(),
      resolver.AddSplitV(),         resolver.AddFullyConnected(), resolver.AddLogistic(),
      resolver.AddQuantize()};
  for (TfLiteStatus x : s)
    if (x != kTfLiteOk) return false;
  return true;
}

void configurar(FrontendConfig &c) {  // o `init_cfg` do pymicro-features 2.0.2
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

void lerLimiarGuardado() {
  Preferences nvs;
  if (!nvs.begin("escuta", true)) return;  // nunca gravado
  if (nvs.getString("modelo", "") == marca && nvs.isKey("limiar")) {
    uint16_t guardado = nvs.getUShort("limiar", limiar);
    if (guardado >= ESCUTA_LIMIAR_MIN && guardado <= ESCUTA_LIMIAR_MAX) {
      limiar = guardado;
      origem = "do NVS";
    }
  }
  nvs.end();
}

// Uma invocação com os 3 quadros guardados; verdadeiro = acordou.
bool invocar(uint8_t &media) {
  TfLiteTensor *entrada = interpretador->input(0);
  memcpy(entrada->data.int8, quadros, sizeof(quadros));
  uint32_t t0 = micros();
  TfLiteStatus s = interpretador->Invoke();
  uint32_t dt = micros() - t0;
  estado.invocacoes++;
  estado.somaUs += dt;
  if (dt > estado.maiorUs) estado.maiorUs = dt;
  if (s != kTfLiteOk) return false;
  saidas[proxima] = interpretador->output(0)->data.uint8[0];
  proxima = (proxima + 1) % MODELO_JANELA;
  if (nSaidas < MODELO_JANELA) nSaidas++;
  if (ignorar > 0) {
    ignorar--;
    return false;
  }
  if (nSaidas < MODELO_JANELA) return false;
  uint32_t soma = 0;
  for (int i = 0; i < MODELO_JANELA; i++) soma += saidas[i];
  media = (uint8_t)(soma / MODELO_JANELA);
  if (media > estado.maiorMedia) estado.maiorMedia = media;
  // média > limiar, sem float: soma/J/255 > limiar/1000  <=>  soma*1000 > limiar*255*J
  if (soma * 1000u <= (uint32_t)limiar * 255u * MODELO_JANELA) return false;
  estado.acordou++;
  ignorar = ESPERA;
  nSaidas = 0;
  return true;
}

}  // namespace

bool escutaComecar() {
  memcpy(marca, MODELO_SHA256, 8);
  marca[8] = 0;
  const tflite::Model *modelo = tflite::GetModel(MODELO);
  if (modelo->version() != TFLITE_SCHEMA_VERSION) {
    Serial.println("escuta: FALHOU (a versão do schema do modelo)");
    return false;
  }
  if (!registrar()) {
    Serial.println("escuta: FALHOU (o resolver)");
    return false;
  }
  tflite::MicroAllocator *alocador = tflite::MicroAllocator::Create(arena, ARENA);
  tflite::MicroResourceVariables *variaveis =
      alocador ? tflite::MicroResourceVariables::Create(alocador, VARIAVEIS_MAX) : nullptr;
  if (!variaveis) {
    Serial.println("escuta: FALHOU (a arena)");
    return false;
  }
  interpretador = new (lugar) tflite::MicroInterpreter(modelo, resolver, alocador, variaveis);
  if (interpretador->AllocateTensors() != kTfLiteOk) {
    Serial.println("escuta: FALHOU (AllocateTensors)");
    return false;
  }
  TfLiteTensor *e = interpretador->input(0);
  if (e->type != kTfLiteInt8 || e->bytes != sizeof(quadros)) {
    Serial.println("escuta: FALHOU (a entrada do modelo não é int8 [1,3,40])");
    return false;
  }
  FrontendConfig cfg;
  configurar(cfg);
  if (!FrontendPopulateState(&cfg, &frontend, 16000)) {
    Serial.println("escuta: FALHOU (o frontend)");
    return false;
  }
  lerLimiarGuardado();
  estado.arena = interpretador->arena_used_bytes();
  montada = true;
  return true;
}

void escutaRecomecar() {
  if (!montada) return;
  FrontendReset(&frontend);
  interpretador->Reset();
  nPendente = nQuadros = nSaidas = proxima = 0;
  ignorar = AQUECIMENTO;
}

bool escutaOuvir(const int16_t *amostras, int n, uint8_t &media) {
  bool acordou = false;
  for (int i = 0; i < n; i++) {
    pendente[nPendente++] = amostras[i];
    if (nPendente < PEDACO) continue;
    // O mesmo laço do treino: entrega 160 e anda o que o frontend leu.
    size_t lidas = 0;
    FrontendOutput fo = FrontendProcessSamples(&frontend, pendente, PEDACO, &lidas);
    if (lidas == 0 || lidas > (size_t)PEDACO) lidas = PEDACO;  // nunca parar no mesmo lugar
    nPendente = PEDACO - (int)lidas;
    if (nPendente) memmove(pendente, pendente + lidas, nPendente * sizeof(int16_t));
    if (fo.size != CANAIS) continue;
    for (int j = 0; j < CANAIS; j++) quadros[nQuadros][j] = int8DoRaw(fo.values[j]);
    if (++nQuadros < PASSO) continue;
    nQuadros = 0;
    if (invocar(media)) acordou = true;
  }
  return acordou;
}

EstadoDaEscuta escutaEstado() {
  EstadoDaEscuta agora = estado;
  size_t arenaUsada = estado.arena;
  estado = EstadoDaEscuta();
  estado.arena = arenaUsada;
  return agora;
}

uint16_t escutaLimiar() { return limiar; }
const char *escutaOrigemDoLimiar() { return origem; }
const char *escutaMarcaDoModelo() { return marca; }

bool escutaMudarLimiar(uint16_t milesimos) {
  if (milesimos < ESCUTA_LIMIAR_MIN || milesimos > ESCUTA_LIMIAR_MAX) return false;
  Preferences nvs;
  if (!nvs.begin("escuta", false)) return false;
  bool ok = nvs.putString("modelo", marca) > 0 && nvs.putUShort("limiar", milesimos) > 0;
  nvs.end();
  if (ok) {
    limiar = milesimos;
    origem = "do NVS";
  }
  return ok;
}
#endif
