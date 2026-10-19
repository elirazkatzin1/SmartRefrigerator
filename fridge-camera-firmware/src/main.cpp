#include <Arduino.h>
#include <WiFi.h>
#include "config.h"

#define FLASH_LED_PIN 4

void connectToWiFi() {
  Serial.println("=== Starting WiFi Connection ===");
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int count = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    count++;
    if (count > 20) {
      Serial.println("\nConnection timeout!");
      break;
    }
  }

  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected! IP address: ");
    Serial.println(WiFi.localIP());
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // תן למונטור להתחבר
  Serial.println("\n\n=== SETUP STARTING ===");
  pinMode(FLASH_LED_PIN, OUTPUT);

  connectToWiFi();
  Serial.println("=== SETUP DONE ===");
}

void loop() {
  digitalWrite(FLASH_LED_PIN, HIGH);
  Serial.println("LED ON");
  delay(1000);
  digitalWrite(FLASH_LED_PIN, LOW);
  Serial.println("LED OFF");
  delay(1000);
}