// A escuta contínua da palavra de ativação "Hey Viking" (Sessão H2m2 do LifeOs, D73).
//
// Com o `modelo.h` (gerado por `gerar_modelo.py gerar --so-modelo`, fora do git: o modelo foi
// treinado com a voz do dono), a placa ouve o tempo todo quando está parada: cada bloco do I2S passa
// pelo mesmo `converter()` do uso e da coleta, pelo frontend do treino (pedaços de 160 amostras) e
// pelo modelo (a cada 3 quadros, 30 ms). Acorda quando a média das últimas `MODELO_JANELA` saídas passa
// do limiar. Sem o `modelo.h`, nada disto existe e o firmware é o de antes (TEM_ESCUTA = 0).
//
// O mesmo caminho foi provado igual ao do treino na H2m1 (2026-11-27): o frontend em 7.880 de 7.880
// valores e o modelo nas 65 saídas (`src/teste_modelo/main.cpp`).
#pragma once

#include <stddef.h>
#include <stdint.h>

#if __has_include("modelo.h")
#define TEM_ESCUTA 1
#else
#define TEM_ESCUTA 0
#endif

#if TEM_ESCUTA
// O que a escuta conta desde a última linha de status.
struct EstadoDaEscuta {
  uint32_t invocacoes = 0, somaUs = 0, maiorUs = 0, acordou = 0;
  uint8_t maiorMedia = 0;  // a maior média vista (q/255): o quanto chegou perto
  size_t arena = 0;
};

// Monta o modelo e o frontend, e lê o limiar. Falso = a escuta fica desligada (o botão segue igual);
// o motivo sai no serial.
bool escutaComecar();
// Depois de cada aperto ou turno: o frontend e o modelo do zero, e 1 s de aquecimento sem decidir.
void escutaRecomecar();
// Um bloco já convertido. Verdadeiro = acordou; `media` é a média das saídas que decidiu (q/255).
bool escutaOuvir(const int16_t *amostras, int n, uint8_t &media);
// O estado desde a última chamada (e zera a contagem da janela).
EstadoDaEscuta escutaEstado();
uint16_t escutaLimiar();  // em milésimos da probabilidade (q/255)
const char *escutaOrigemDoLimiar();
// O começo do sha256 do modelo (o `modelo.h` só entra na escuta: 62 KB, uma cópia).
const char *escutaMarcaDoModelo();
// Grava no NVS, ligado a este modelo (um modelo novo volta ao limiar do json dele). Falso fora de
// [ESCUTA_LIMIAR_MIN, ESCUTA_LIMIAR_MAX].
bool escutaMudarLimiar(uint16_t milesimos);
constexpr uint16_t ESCUTA_LIMIAR_MIN = 500;
constexpr uint16_t ESCUTA_LIMIAR_MAX = 999;
#endif
