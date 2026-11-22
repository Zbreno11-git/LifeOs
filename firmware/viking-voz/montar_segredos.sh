#!/usr/bin/env bash
# Monta o src/segredos.h do viking-voz no Mac (Sessão H1, D70), sem mostrar segredo nenhum na tela.
#
# Roda o dono, no terminal do Mac, na mesma Wi-Fi do laptop de casa:
#   bash firmware/viking-voz/montar_segredos.sh
#
# - o token do aparelho e o certificado HTTPS da ponte vêm do laptop (`ssh home-server`), da pasta
#   que o `viking casa --preparar` gravou (~/.config/viking-casa/), direto para variáveis: nada é
#   impresso;
# - a Wi-Fi é perguntada aqui (a senha sem eco);
# - o arquivo sai com permissão 600, e só se o git o ignorar (o repo é público);
# - um segredos.h que já existia vai para ~/viking-voz-segredos.antigo.<data>.h (fora do repo), nunca
#   apagado.
set -euo pipefail

pasta="$(cd "$(dirname "$0")" && pwd)"
destino="$pasta/src/segredos.h"
umask 077

git -C "$pasta" check-ignore -q src/segredos.h || {
  echo "❌ o git não ignora src/segredos.h: nada foi gravado"
  exit 1
}

token="$(ssh -o BatchMode=yes home-server python3 - <<'PY'
import json, pathlib
dados = json.loads((pathlib.Path.home() / ".config/viking-casa/casa.json").read_text())
print(dados["aparelho_token"])
PY
)" || { echo "❌ não li o token no laptop (o ssh home-server responde?)"; exit 1; }
[[ "$token" =~ ^[A-Za-z0-9_-]{20,}$ ]] || { echo "❌ o token lido não tem a forma esperada"; exit 1; }

certificado="$(ssh -o BatchMode=yes home-server 'cat ~/.config/viking-casa/tls-certificado.pem')" ||
  { echo "❌ não li o certificado no laptop"; exit 1; }
[[ "$certificado" == "-----BEGIN CERTIFICATE-----"*"-----END CERTIFICATE-----" ]] ||
  { echo "❌ o certificado lido não tem BEGIN/END"; exit 1; }

# Os nomes que o certificado aceita (é público): o host do firmware tem de ser um deles.
nomes="$(printf '%s\n' "$certificado" | openssl x509 -noout -text |
  grep -A1 'Subject Alternative Name' | tail -1 | tr -d ' ')"
echo "O certificado da ponte vale para: $nomes"
padrao="$(printf '%s' "$nomes" | tr ',' '\n' | sed -n 's/^DNS://p' | head -1)"
read -r -p "PONTE_HOST [$padrao]: " host
host="${host:-$padrao}"
[[ "$host" =~ ^[A-Za-z0-9.-]+$ ]] || { echo "❌ host inválido"; exit 1; }
case ",$nomes," in
  *",DNS:$host,"* | *",IPAddress:$host,"* | *",IP:$host,"*) ;;
  *) echo "❌ $host não está no certificado (o HTTPS do aparelho recusaria)"; exit 1 ;;
esac

read -r -p "WIFI_SSID (o nome da rede de casa): " ssid
read -r -s -p "WIFI_SENHA (não aparece): " senha
echo
[[ -n "$ssid" && -n "$senha" ]] || { echo "❌ a rede e a senha não podem ser vazias"; exit 1; }

# Dentro de uma string C, \ e " precisam de escape.
c_texto() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

if [[ -e "$destino" ]]; then
  # Um nome por rodada, e o mv -n nunca sobrescreve: rodar duas vezes perdia o primeiro antigo
  # (visto em 2026-11-22).
  antigo="$HOME/viking-voz-segredos.antigo.$(date +%Y%m%d-%H%M%S).h"
  mv -n "$destino" "$antigo"
  [[ ! -e "$destino" ]] || { echo "❌ não movi o segredos.h que havia: nada foi gravado"; exit 1; }
  chmod 600 "$antigo"
  echo "↪ o segredos.h que havia foi para $antigo"
fi

{
  echo "// Gerado por montar_segredos.sh. Fora do git; nada daqui vai ao log ou ao serial."
  echo "#pragma once"
  echo
  echo "#define WIFI_SSID \"$(c_texto "$ssid")\""
  echo "#define WIFI_SENHA \"$(c_texto "$senha")\""
  echo
  echo "#define PONTE_HOST \"$host\""
  echo "#define PONTE_PORTA 8765"
  echo "#define APARELHO_TOKEN \"$token\""
  echo
  echo "static const char PONTE_CERTIFICADO[] = R\"PEM($certificado"
  echo ")PEM\";"
} >"$destino"
chmod 600 "$destino"

echo "✅ segredos.h gravado (600), $(wc -c <"$destino" | tr -d ' ') bytes; host: $host"
