#!/usr/bin/env bash
# O scanner de segredos do Viking (Sessão 10, D58): o gitleaks, numa versão fixa e com o sha256
# conferido antes de rodar. Entra antes de o repo virar privado, porque o secret scanning do GitHub
# some em repo privado de conta pessoal (D50). Roda no CI (histórico inteiro), no hook `pre-commit`
# do VPS (`scripts/instalar_hooks.sh`) e à mão:
#
#     bash scripts/gitleaks.sh git .                 (o histórico inteiro)
#     bash scripts/gitleaks.sh git --staged .        (o que vai entrar no próximo commit)
#
# O binário fica em ~/.cache/viking/, fora do repo e fora do `uv.lock`. Os hashes abaixo foram
# copiados do `checksums.txt` do release em 2026-09-29; trocar de versão = trocar os três valores
# juntos, conferindo o novo `checksums.txt`.
set -euo pipefail

VERSAO="8.30.1"
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)
    ALVO="linux_x64"
    SHA256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
    ;;
  Darwin-x86_64)
    ALVO="darwin_x64"
    SHA256="dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709"
    ;;
  *)
    echo "gitleaks.sh: plataforma sem hash fixado: $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac

PASTA="${XDG_CACHE_HOME:-$HOME/.cache}/viking/gitleaks-$VERSAO"
BINARIO="$PASTA/gitleaks"

if [[ ! -x "$BINARIO" ]]; then
  mkdir -p "$PASTA"
  TEMP="$(mktemp -d)"
  trap 'rm -rf "$TEMP"' EXIT
  ARQUIVO="gitleaks_${VERSAO}_${ALVO}.tar.gz"
  curl -fsSL --retry 3 -o "$TEMP/$ARQUIVO" \
    "https://github.com/gitleaks/gitleaks/releases/download/v$VERSAO/$ARQUIVO"
  if command -v sha256sum >/dev/null; then
    CALCULADO="$(sha256sum "$TEMP/$ARQUIVO" | cut -d' ' -f1)"
  else
    CALCULADO="$(shasum -a 256 "$TEMP/$ARQUIVO" | cut -d' ' -f1)"
  fi
  if [[ "$CALCULADO" != "$SHA256" ]]; then
    echo "gitleaks.sh: sha256 não bate ($CALCULADO); nada foi instalado" >&2
    exit 1
  fi
  tar -xzf "$TEMP/$ARQUIVO" -C "$TEMP" gitleaks
  install -m 755 "$TEMP/gitleaks" "$BINARIO"
fi

exec "$BINARIO" "$@"
