/**
 * Smart Gym - Sistema de Identificação por RFID
 * CP01 - Physical Computing (IoT & IoB) - FIAP
 * 
 * Hardware: Arduino Uno / ESP32
 * Módulo: MFRC522 (protocolo SPI)
 * 
 * Conexões (Arduino Uno):
 *   MFRC522  ->  Arduino
 *   SDA      ->  D10 (SS)
 *   SCK      ->  D13
 *   MOSI     ->  D11
 *   MISO     ->  D12
 *   IRQ      ->  (não conectado)
 *   GND      ->  GND
 *   RST      ->  D9
 *   3.3V     ->  3.3V
 */

#include <SPI.h>
#include <MFRC522.h>

// Pinos do módulo RFID
#define SS_PIN  10
#define RST_PIN 9

// Pino do LED de status (built-in)
#define LED_PIN 13

MFRC522 mfrc522(SS_PIN, RST_PIN);

// Cartões/tags autorizados (cadastrados previamente)
// Formato: {byte1, byte2, byte3, byte4}
const byte CARTOES_AUTORIZADOS[][4] = {
  {0xA1, 0xB2, 0xC3, 0xD4},  // Aluno 1 - João Silva
  {0x11, 0x22, 0x33, 0x44},  // Aluno 2 - Maria Souza
  {0xDE, 0xAD, 0xBE, 0xEF},  // Aluno 3 - Carlos Lima
};

const int NUM_CARTOES = sizeof(CARTOES_AUTORIZADOS) / sizeof(CARTOES_AUTORIZADOS[0]);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  mfrc522.PCD_Init();

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.println("SMART_GYM_READY");
  Serial.println("Aproxime o cartão RFID...");
}

void loop() {
  // Aguarda novo cartão
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  // Tenta ler o cartão
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Monta string do UID
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
    if (i < mfrc522.uid.size - 1) uid += ":";
  }
  uid.toUpperCase();

  // Verifica se é autorizado
  bool autorizado = verificarCartao(mfrc522.uid.uidByte, mfrc522.uid.size);

  if (autorizado) {
    // Envia UID via serial para o Python
    Serial.print("ACESSO_LIBERADO:");
    Serial.println(uid);
    piscarLED(3, 200);  // 3 piscadas rápidas = OK
  } else {
    Serial.print("ACESSO_NEGADO:");
    Serial.println(uid);
    piscarLED(1, 1000); // 1 piscada longa = negado
  }

  // Pausa antes de ler novamente
  delay(1500);
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

bool verificarCartao(byte *uid, byte tamanho) {
  if (tamanho != 4) return false;

  for (int i = 0; i < NUM_CARTOES; i++) {
    bool match = true;
    for (int j = 0; j < 4; j++) {
      if (uid[j] != CARTOES_AUTORIZADOS[i][j]) {
        match = false;
        break;
      }
    }
    if (match) return true;
  }
  return false;
}

void piscarLED(int vezes, int intervalo) {
  for (int i = 0; i < vezes; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(intervalo / 2);
    digitalWrite(LED_PIN, LOW);
    delay(intervalo / 2);
  }
}
