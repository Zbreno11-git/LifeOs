#!/usr/bin/env bash
# Liga o scanner de segredos no commit desta cópia do repo (Sessão 10, D58): o hook `pre-commit`
# roda o gitleaks no que está no stage e recusa o commit se achar segredo. O CI roda o mesmo
# scanner no histórico inteiro; o hook pega antes de o segredo virar commit (e push).
#
#     bash scripts/instalar_hooks.sh
#
# Idempotente. Recusa sobrescrever um `pre-commit` que não seja o nosso.
set -euo pipefail

RAIZ="$(git rev-parse --show-toplevel)"
HOOK="$(git rev-parse --git-path hooks)/pre-commit"
MARCA="# viking: scanner de segredos (scripts/instalar_hooks.sh)"

if [[ -e "$HOOK" ]] && ! grep -qF "$MARCA" "$HOOK"; then
  echo "instalar_hooks.sh: já existe um pre-commit que não é o nosso: $HOOK" >&2
  exit 1
fi

cat > "$HOOK" <<HOOK
#!/usr/bin/env bash
$MARCA
exec bash "$RAIZ/scripts/gitleaks.sh" git --pre-commit --staged --redact --no-banner "$RAIZ"
HOOK
chmod 755 "$HOOK"
echo "hook instalado: $HOOK"
