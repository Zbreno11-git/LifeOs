#!/usr/bin/env bash
# O emulador do Firestore para o contrato dos lembretes (Sessão 10, D58): o mesmo jar que o
# firebase-tools baixa, numa versão fixa e com o sha256 conferido antes de rodar. Só para testes:
# nenhum dado real passa por ele. Precisa de Java 21 (`VIKING_JAVA` aponta outro binário).
#
#     bash scripts/emulador_firestore.sh 127.0.0.1 8765     (fica rodando até ser morto)
#
# O `tests/conftest.py` o sobe sozinho quando o jar está no cache (ou com
# `VIKING_EXIGIR_EMULADOR=1`, que o CI liga). Versão, tamanho e hash copiados de
# `src/emulator/downloadableEmulatorInfo.json` do firebase-tools v15.32.0 em 2026-09-29; trocar de
# versão = trocar os três juntos, conferindo o arquivo novo.
set -euo pipefail

VERSAO="1.22.0"
SHA256="9b6498b7f62714d67f48f59b3818883cd682dbcd46b9f59511de81c97bb5166c"
HOST="${1:-127.0.0.1}"
PORTA="${2:-8765}"

PASTA="${XDG_CACHE_HOME:-$HOME/.cache}/viking"
JAR="$PASTA/cloud-firestore-emulator-v$VERSAO.jar"

if [[ ! -f "$JAR" ]]; then
  mkdir -p "$PASTA"
  PARCIAL="$JAR.parcial"
  curl -fsSL --retry 3 -o "$PARCIAL" \
    "https://storage.googleapis.com/firebase-preview-drop/emulator/cloud-firestore-emulator-v$VERSAO.jar"
  if command -v sha256sum >/dev/null; then
    CALCULADO="$(sha256sum "$PARCIAL" | cut -d' ' -f1)"
  else
    CALCULADO="$(shasum -a 256 "$PARCIAL" | cut -d' ' -f1)"
  fi
  if [[ "$CALCULADO" != "$SHA256" ]]; then
    rm -f "$PARCIAL"
    echo "emulador_firestore.sh: sha256 não bate ($CALCULADO); nada foi instalado" >&2
    exit 1
  fi
  mv "$PARCIAL" "$JAR"
fi

if [[ "${VIKING_EMULADOR_SO_BAIXAR:-}" == "1" ]]; then
  exit 0
fi
exec "${VIKING_JAVA:-java}" -jar "$JAR" --host "$HOST" --port "$PORTA"
