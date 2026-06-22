/*
 *  Robô PIE V - Ponte Bluetooth -> Serial
 *
 *  O QUE FAZ:
 *    - O ESP32 vira um "servidor" Bluetooth Classic (SPP) que o celular pareia.
 *    - As mensagens recebidas devem ser strings terminadas em '\n'.
 *    - Valida se cada mensagem é um JSON bem-formado.
 *    - Se for válido, repassa via Serial.
 *    - Se for inválido, descarta e responde com erro via Bluetooth.
 */

#include "BluetoothSerial.h"
#include <ArduinoJson.h>

// Garante que o core do ESP32 foi compilado com Bluetooth Classic habilitado.
#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error "Bluetooth Classic nao esta habilitado. Selecione um core/placa ESP32 com Bluedroid."
#endif

#if !defined(CONFIG_BT_SPP_ENABLED)
#error "SPP (Serial Port Profile) nao esta habilitado neste core."
#endif

// ----------------------------------------------------------------------------
// Configuração
// ----------------------------------------------------------------------------
const char*  BT_DEVICE_NAME  = "piev";       // nome que aparece no pareamento
const size_t MAX_LINE        = 512;          // tamanho máx de uma mensagem
const char   LINE_DELIMITER  = '\n';         // fronteira de mensagem

// Para qual porta os dados validados vão (o link com o Raspberry Pi).
//   Serial  -> via cabo USB (padrão, mais simples).
//   Serial2 -> via pinos UART (GPIO17 TX), libera o USB para debug.
#define PI_SERIAL Serial
const uint32_t PI_BAUD = 115200;             // precisa bater com o lado Pi

BluetoothSerial SerialBT;

// Buffer de acumulação de uma mensagem até chegar o '\n'.
char   lineBuf[MAX_LINE];
size_t lineLen = 0;

// ----------------------------------------------------------------------------
// Valida e, se válido, repassa o JSON ao Pi.
// ----------------------------------------------------------------------------
void processLine(const char* line, size_t len) {
  if (len == 0) {
    return;  // linha vazia, ignora
  }

  // documento dinâmico, sem precisar dimensionar manualmente.
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, line, len);

  if (err) {
    // Não é JSON válido -> NÃO manda nada pro Serial; só avisa o celular.
    SerialBT.print("{\"ack\":\"erro\",\"motivo\":\"json_invalido\"}\n");
    return;
  }

  // JSON válido -> repassa via Serial como UMA linha compacta (NDJSON).
  serializeJson(doc, PI_SERIAL);
  PI_SERIAL.print('\n');

  // Confirma ao celular que foi aceito.
  SerialBT.print("{\"ack\":\"ok\"}\n");
}

// ----------------------------------------------------------------------------
void setup() {
  PI_SERIAL.begin(PI_BAUD);

  if (!SerialBT.begin(BT_DEVICE_NAME)) {
    // Se o BT não iniciar, trava aqui piscando seria ideal; sem dados ao Pi.
    while (true) {
      delay(1000);
    }
  }

  // (Opcional) PIN de pareamento legado. A assinatura varia entre versões
  // do core; deixe comentado a menos que precise e teste na sua versão.
  // SerialBT.setPin("1234", 4);
}

// ----------------------------------------------------------------------------
void loop() {
  while (SerialBT.available()) {
    char c = (char)SerialBT.read();

    if (c == LINE_DELIMITER || c == '\r') {
      // Fim de mensagem: fecha a string e processa.
      lineBuf[lineLen] = '\0';
      processLine(lineBuf, lineLen);
      lineLen = 0;
    } else {
      if (lineLen < MAX_LINE - 1) {
        lineBuf[lineLen++] = c;
      } else {
        // Estouro de buffer: descarta a linha inteira e avisa o celular.
        lineLen = 0;
        SerialBT.print("{\"ack\":\"erro\",\"motivo\":\"linha_muito_longa\"}\n");
      }
    }
  }
}
