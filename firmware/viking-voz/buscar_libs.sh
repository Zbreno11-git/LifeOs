#!/usr/bin/env bash
# As duas bibliotecas do teste do modelo da wake word na placa (H2m1, D73), baixadas por commit fixo
# e montadas em firmware/viking-voz/lib/ (fora do git: o `.gitignore` da raiz recusa `lib/`).
#
#   - o TFLM da Espressif, `esp-tflite-micro` v1.4.3 (Apache-2.0): só o núcleo do interpretador e os
#     kernels das 13 operações do modelo, os de **referência** (sem o ESP-NN, que troca 14 deles), e
#     sem o `signal/` (só os cabeçalhos: o `micro_mutable_op_resolver.h` os inclui) nem o
#     `debug_log.cc` (o programa de teste escreve o log pela USB);
#   - (H2m2) a mesma base com os kernels do ESP-NN (`lib/tflm_nn`) e o `esp-nn` v1.5.0 da Espressif
#     (Apache-2.0), com o assembly do S3 (`lib/esp-nn`);
#   - o frontend de áudio do treino, o do `pymicro-features` v2.0.2 (Apache-2.0; o kissfft dentro
#     dele é BSD), com os 16 fontes que o `setup.py` dele compila e o `-DFIXED_POINT=16` dele.
#
# Cada rodada baixa de novo, confere o commit, monta numa pasta nova e só então troca a velha; a
# impressão de cada lib (o sha256 dos caminhos e dos conteúdos) sai no fim, e duas rodadas têm de
# dar a mesma. Não grava nada fora de lib/tflm, lib/tflm_nn, lib/esp-nn e lib/microfrontend.
#
#   bash firmware/viking-voz/buscar_libs.sh
set -euo pipefail  # roda no bash 3.2 do macOS (sem mapfile)

TFLM_URL=https://github.com/espressif/esp-tflite-micro
TFLM_COMMIT=df8722334a80ceabc609c1e72968f417cd9437f1  # a tag v1.4.3 (git ls-remote, 2026-11-27)
MF_URL=https://github.com/rhasspy/pymicro-features
MF_COMMIT=96bd69cfad79aa67697e176570d3dd87052c3def  # a tag v2.0.2 (git ls-remote, 2026-11-27)
NN_URL=https://github.com/espressif/esp-nn
NN_COMMIT=ace42ac7721119cd543fc40ffe719e601fa8f20f  # a tag v1.5.0 (git ls-remote, 2026-11-27)

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$AQUI/lib"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

baixar() {  # pasta url commit
  git init -q "$TMP/$1"
  git -C "$TMP/$1" fetch -q --depth 1 "$2" "$3"
  git -C "$TMP/$1" checkout -q FETCH_HEAD
  local visto
  visto="$(git -C "$TMP/$1" rev-parse HEAD)"
  if [[ "$visto" != "$3" ]]; then
    echo "ERRO: $2 veio no commit $visto, e o fixado é $3" >&2
    exit 1
  fi
  echo "$1: $2 @ $visto"
}

copiar() {  # origem destino arquivo...  (os caminhos relativos se mantêm)
  local de="$1" para="$2"
  shift 2
  mkdir -p "$para"
  (cd "$de" && tar cf - "$@") | (cd "$para" && tar xf -)
}

impressao() {  # o sha256 dos caminhos e dos conteúdos, sem a hora dos arquivos
  (cd "$1" && find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 |
    cut -c1-64)
}

baixar tflm "$TFLM_URL" "$TFLM_COMMIT"
baixar mf "$MF_URL" "$MF_COMMIT"
baixar nn "$NN_URL" "$NN_COMMIT"

# --- o TFLM ------------------------------------------------------------------------------------
T="$TMP/tflm"
M=tensorflow/lite/micro
K=$M/kernels
for op in var_handle read_variable assign_variable call_once; do
  [[ -f "$T/$K/$op.cc" ]] || { echo "ERRO: falta o kernel $op no $TFLM_COMMIT" >&2; exit 1; }
done
NUCLEO=(flatbuffer_conversions flatbuffer_utils memory_helpers micro_allocation_info micro_allocator
  micro_common micro_context micro_interpreter_context micro_interpreter_graph micro_interpreter
  micro_log micro_op_resolver micro_profiler micro_resource_variable micro_utils
  recording_micro_allocator system_setup)
# As 13 operações do modelo (lidas do .tflite em 2026-11-27) e os `_common` de que elas dependem.
KERNELS=(call_once var_handle read_variable assign_variable reshape reshape_common concatenation
  strided_slice strided_slice_common conv conv_common depthwise_conv depthwise_conv_common split_v
  fully_connected fully_connected_common logistic logistic_common quantize quantize_common
  kernel_util)
# O ESP-NN troca estes 5 dos nossos kernels pelos de `kernels/esp_nn/` (os `_common` ficam).
TROCADOS_PELO_NN=(conv depthwise_conv fully_connected logistic quantize)
CABECALHOS_TFLM=()
while IFS= read -r f; do CABECALHOS_TFLM+=("$f"); done < <(cd "$T" && find tensorflow signal -name '*.h' | LC_ALL=C sort)

montar_tflm() {  # destino [nn]: sem o 2º argumento, os kernels de referência
  local destino="$1" variante="${2:-}" f
  local fontes=("$M/esp/micro_time.cc")
  for f in "${NUCLEO[@]}"; do fontes+=("$M/$f.cc"); done
  for f in "${KERNELS[@]}"; do
    if [[ "$variante" == nn && " ${TROCADOS_PELO_NN[*]} " == *" $f "* ]]; then
      fontes+=("$K/esp_nn/$f.cc")
    else
      fontes+=("$K/$f.cc")
    fi
  done
  for f in common portable_tensor_utils quantization_util tensor_ctypes; do
    fontes+=("$K/internal/$f.cc")
  done
  for f in greedy_memory_planner linear_memory_planner; do fontes+=("$M/memory_planner/$f.cc"); done
  for f in non_persistent_arena_buffer_allocator persistent_arena_buffer_allocator \
    recording_single_arena_buffer_allocator single_arena_buffer_allocator; do
    fontes+=("$M/arena_allocator/$f.cc")
  done
  copiar "$T" "$destino" "${fontes[@]}" "${CABECALHOS_TFLM[@]}" LICENSE
  copiar "$T/third_party/flatbuffers/include" "$destino" flatbuffers
  cp "$T/third_party/flatbuffers/LICENSE" "$destino/LICENSE.flatbuffers"
  printf '%s\n' "$TFLM_URL @ $TFLM_COMMIT (v1.4.3)" >"$destino/FONTE.txt"
  N_FONTES_TFLM=${#fontes[@]}
}

NOVO_TFLM="$TMP/lib_tflm"
montar_tflm "$NOVO_TFLM"
FONTES_TFLM=$N_FONTES_TFLM
cat >"$NOVO_TFLM/library.json" <<'JSON'
{
  "name": "tflm",
  "version": "1.4.3",
  "description": "esp-tflite-micro v1.4.3, kernels de referência, só o que o modelo da wake word usa (buscar_libs.sh)",
  "build": {
    "srcDir": ".",
    "includeDir": ".",
    "srcFilter": ["+<tensorflow/>"],
    "flags": ["-O3", "-Wno-unused-parameter", "-Wno-missing-field-initializers"]
  }
}
JSON

# A variante com o ESP-NN (H2m2): os mesmos fontes, com os 5 kernels de `esp_nn/`. O `ESP_NN` e as
# definições do S3 vêm do env (`platformio.ini`), para o `esp_nn.h` escolher a mesma versão aqui e na
# lib `esp-nn`.
NOVO_TFLM_NN="$TMP/lib_tflm_nn"
montar_tflm "$NOVO_TFLM_NN" nn
FONTES_TFLM_NN=$N_FONTES_TFLM
cat >"$NOVO_TFLM_NN/library.json" <<'JSON'
{
  "name": "tflm_nn",
  "version": "1.4.3",
  "description": "esp-tflite-micro v1.4.3 com os kernels do ESP-NN para conv, depthwise_conv, fully_connected, logistic e quantize (buscar_libs.sh)",
  "build": {
    "srcDir": ".",
    "includeDir": ".",
    "srcFilter": ["+<tensorflow/>"],
    "flags": ["-O3", "-Wno-unused-parameter", "-Wno-missing-field-initializers"]
  }
}
JSON

# --- o esp-nn -------------------------------------------------------------------------------------
# Os fontes saem do próprio CMakeLists.txt dele (as listas `c_srcs` e `s3_srcs`), não de uma lista
# escrita aqui: uma versão nova que acrescente um arquivo o traz junto.
fontes_do_cmake() {  # o nome da lista
  awk -v nome="$1" '
    $0 ~ ("set\\(" nome "[ \t]*$") { f = 1; next }
    f { linha = $0
        while (match(linha, /"[^"]+"/)) {
          print substr(linha, RSTART + 1, RLENGTH - 2); linha = substr(linha, RSTART + RLENGTH)
        }
        if (linha ~ /\)/) exit }' "$TMP/nn/CMakeLists.txt"
}
FONTES_NN=()
while IFS= read -r f; do FONTES_NN+=("$f"); done < <(fontes_do_cmake c_srcs; fontes_do_cmake s3_srcs)
[[ ${#FONTES_NN[@]} -ge 40 ]] || { echo "ERRO: só ${#FONTES_NN[@]} fontes lidos do CMakeLists do esp-nn" >&2; exit 1; }
for f in "${FONTES_NN[@]}"; do
  [[ -f "$TMP/nn/$f" ]] || { echo "ERRO: o CMakeLists do esp-nn cita $f, que não existe" >&2; exit 1; }
done
NOVO_NN="$TMP/lib_nn"
copiar "$TMP/nn" "$NOVO_NN" include src LICENSE
printf '%s\n' "$NN_URL @ $NN_COMMIT (v1.5.0)" >"$NOVO_NN/FONTE.txt"
{
  printf '{\n  "name": "esp-nn",\n  "version": "1.5.0",\n'
  printf '  "description": "o esp-nn v1.5.0 da Espressif, o ANSI-C e o assembly do S3 do CMakeLists dele (buscar_libs.sh)",\n'
  printf '  "build": {\n    "srcDir": ".",\n    "includeDir": "include",\n    "srcFilter": ["-<*>"'
  for f in "${FONTES_NN[@]}"; do printf ', "+<%s>"' "$f"; done
  printf '],\n    "flags": ["-Isrc/common", "-mlongcalls", "-fno-unroll-loops", "-O2", "-Wno-unused-function", "-Werror=vla"]\n  }\n}\n'
} >"$NOVO_NN/library.json"

# --- o frontend ----------------------------------------------------------------------------------
F=tensorflow/lite/experimental/microfrontend/lib
FONTES_MF=()
for f in kiss_fft_int16 fft fft_util filterbank filterbank_util frontend frontend_util log_lut \
  log_scale log_scale_util noise_reduction noise_reduction_util pcan_gain_control \
  pcan_gain_control_util window window_util; do
  FONTES_MF+=("$F/$f.cc")
done
CABECALHOS_MF=()
while IFS= read -r f; do CABECALHOS_MF+=("$f"); done < <(cd "$TMP/mf" && find "$F" -name '*.h' | LC_ALL=C sort)
NOVO_MF="$TMP/lib_mf"
copiar "$TMP/mf" "$NOVO_MF" "${FONTES_MF[@]}" "${CABECALHOS_MF[@]}" LICENSE
# O kissfft vai na raiz da lib: o `kiss_fft_int16.cc` o inclui (`#include "kiss_fft.cc"`) dentro do
# namespace dele, e por isso o kissfft não se compila sozinho (o `srcFilter` só pega `tensorflow/`).
copiar "$TMP/mf/kissfft" "$NOVO_MF" kiss_fft.cc kiss_fft.h _kiss_fft_guts.h tools/kiss_fftr.cc \
  tools/kiss_fftr.h
printf '%s\n' "$MF_URL @ $MF_COMMIT (v2.0.2)" >"$NOVO_MF/FONTE.txt"
cat >"$NOVO_MF/library.json" <<'JSON'
{
  "name": "microfrontend",
  "version": "2.0.2",
  "description": "o micro_frontend do pymicro-features v2.0.2, o mesmo do treino (buscar_libs.sh)",
  "build": {
    "srcDir": ".",
    "includeDir": ".",
    "srcFilter": ["+<tensorflow/>"],
    "flags": ["-DFIXED_POINT=16"]
  }
}
JSON

# --- a troca: a pasta nova só entra inteira ----------------------------------------------------
mkdir -p "$LIB"
rm -rf "$LIB/tflm" "$LIB/tflm_nn" "$LIB/esp-nn" "$LIB/microfrontend"
mv "$NOVO_TFLM" "$LIB/tflm"
mv "$NOVO_TFLM_NN" "$LIB/tflm_nn"
mv "$NOVO_NN" "$LIB/esp-nn"
mv "$NOVO_MF" "$LIB/microfrontend"
echo "lib/tflm: $FONTES_TFLM fontes, ${#CABECALHOS_TFLM[@]} cabeçalhos; impressão $(impressao "$LIB/tflm")"
echo "lib/tflm_nn: $FONTES_TFLM_NN fontes; impressão $(impressao "$LIB/tflm_nn")"
echo "lib/esp-nn: ${#FONTES_NN[@]} fontes; impressão $(impressao "$LIB/esp-nn")"
echo "lib/microfrontend: ${#FONTES_MF[@]} fontes; impressão $(impressao "$LIB/microfrontend")"
