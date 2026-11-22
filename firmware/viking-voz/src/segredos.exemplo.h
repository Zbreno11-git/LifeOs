// Modelo dos segredos do aparelho do estúdio (Sessão H1 do LifeOs, D70).
// Copie para src/segredos.h (que está no .gitignore) e preencha. O token, o host e o certificado
// saem do `viking casa --preparar` no laptop de casa; a Wi-Fi é a sua.
// Nada daqui vai para o git, para o log ou para o serial.
#pragma once

#define WIFI_SSID "nome-da-rede"
#define WIFI_SENHA "senha-da-rede"

#define PONTE_HOST "laptop.local"  // o nome do laptop na rede de casa (ou o IP, se o mDNS falhar)
#define PONTE_PORTA 8765
#define APARELHO_TOKEN "cole-aqui-o-token-do-preparar"

// O certificado HTTPS da ponte, inteiro (com as linhas BEGIN/END): o aparelho só aceita este.
static const char PONTE_CERTIFICADO[] = R"PEM(-----BEGIN CERTIFICATE-----
cole-aqui
-----END CERTIFICATE-----
)PEM";
