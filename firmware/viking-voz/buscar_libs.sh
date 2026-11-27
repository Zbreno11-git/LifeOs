#!/usr/bin/env bash
# As duas bibliotecas do teste do modelo da wake word na placa (H2m1, D73), baixadas por commit fixo
# e montadas em firmware/viking-voz/lib/ (fora do git: o `.gitignore` da raiz recusa `lib/`).
#
#   - o TFLM da Espressif, `esp-tflite-micro` v1.4.3 (Apache-2.0): só o núcleo do interpretador e os
#     kernels das 13 operações do modelo, os de **referência** (sem o ESP-NN, que troca 14 deles), e
#     sem o `signal/` (só os cabeçalhos: o `micro_mutable_op_resolver.h` os inclui) nem o
#     `debug_log.cc` (o programa de teste escreve o log pela USB);
#   - o frontend de áudio do treino, o do `pymicro-features` v2.0.2 (Apache-2.0; o kissfft dentro
#     dele é BSD), com os 16 fontes que o `setup.py` dele compila e o `-DFIXED_POINT=16` dele.
#
# Cada rodada baixa de novo, confere o commit, monta numa pasta nova e só então troca a velha; a
# impressão de cada lib (o sha256 dos caminhos e dos conteúdos) sai no fim, e duas rodadas têm de
# dar a mesma. Não grava nada fora de lib/tflm e lib/microfrontend.
#
#   bash firmware/viking-voz/buscar_libs.sh
set -euo pipefail  # roda no bash 3.2 do macOS (sem mapfile)

TFLM_URL=https://github.com/espressif/esp-tflite-micro
TFLM_COMMIT=df8722334a80ceabc609c1e72968f417cd9437f1  # a tag v1.4.3 (git ls-remote, 2026-11-27)
MF_URL=https://github.com/rhasspy/pymicro-features
MF_COMMIT=96bd69cfad79aa67697e176570d3dd87052c3def  # a tag v2.0.2 (git ls-remote, 2026-11-27)

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
FONTES_TFLM=("$M/esp/micro_time.cc")
for f in "${NUCLEO[@]}"; do FONTES_TFLM+=("$M/$f.cc"); done
for f in "${KERNELS[@]}"; do FONTES_TFLM+=("$K/$f.cc"); done
for f in common portable_tensor_utils quantization_util tensor_ctypes; do
  FONTES_TFLM+=("$K/internal/$f.cc")
done
for f in greedy_memory_planner linear_memory_planner; do FONTES_TFLM+=("$M/memory_planner/$f.cc"); done
for f in non_persistent_arena_buffer_allocator persistent_arena_buffer_allocator \
  recording_single_arena_buffer_allocator single_arena_buffer_allocator; do
  FONTES_TFLM+=("$M/arena_allocator/$f.cc")
done
CABECALHOS_TFLM=()
while IFS= read -r f; do CABECALHOS_TFLM+=("$f"); done < <(cd "$T" && find tensorflow signal -name '*.h' | LC_ALL=C sort)
NOVO_TFLM="$TMP/lib_tflm"
copiar "$T" "$NOVO_TFLM" "${FONTES_TFLM[@]}" "${CABECALHOS_TFLM[@]}" LICENSE
copiar "$T/third_party/flatbuffers/include" "$NOVO_TFLM" flatbuffers
cp "$T/third_party/flatbuffers/LICENSE" "$NOVO_TFLM/LICENSE.flatbuffers"
printf '%s\n' "$TFLM_URL @ $TFLM_COMMIT (v1.4.3)" >"$NOVO_TFLM/FONTE.txt"
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
rm -rf "$LIB/tflm" "$LIB/microfrontend"
mv "$NOVO_TFLM" "$LIB/tflm"
mv "$NOVO_MF" "$LIB/microfrontend"
echo "lib/tflm: ${#FONTES_TFLM[@]} fontes, ${#CABECALHOS_TFLM[@]} cabeçalhos; impressão $(impressao "$LIB/tflm")"
echo "lib/microfrontend: ${#FONTES_MF[@]} fontes; impressão $(impressao "$LIB/microfrontend")"
