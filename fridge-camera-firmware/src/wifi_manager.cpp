#include <Arduino.h>
#include <WiFi.h>
#include "wifi_manager.h"
#include "config.h"

#define WIFI_RETRY_INTERVAL_MS 10000

static bool wifiConnected = false;
static unsigned long lastReconnectAttempt = 0;

void connectToWiFi() {
  Serial.println("=== Starting WiFi Connection ===");
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false); // ההתחברות מחדש מנוהלת ב-checkWiFiConnection
  // ביטול חיסכון החשמל של ה-WiFi: במצב שינה הרדיו מעכב חבילות ושליחת תמונות נכשלת
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int count = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    count++;
    if (count > 20) {
      Serial.println("\nConnection timeout! Will keep retrying in loop.");
      break;
    }
  }

  Serial.println();
  wifiConnected = (WiFi.status() == WL_CONNECTED);
  if (wifiConnected) {
    Serial.print("Connected! IP address: ");
    Serial.println(WiFi.localIP());
    Serial.printf("Signal strength (RSSI): %d dBm\n", WiFi.RSSI());
  }
}

// בדיקה לא חוסמת: מזהה ניתוק ומנסה להתחבר מחדש כל WIFI_RETRY_INTERVAL_MS
void checkWiFiConnection() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiConnected) {
      wifiConnected = true;
      Serial.print("Reconnected! IP address: ");
      Serial.println(WiFi.localIP());
    }
    return;
  }

  if (wifiConnected) {
    wifiConnected = false;
    Serial.println("WiFi connection lost!");
    // לא מנסים מיד: בניתוק הראשון ספריית ה-WiFi מבצעת ניסיון אחד משלה
    lastReconnectAttempt = millis();
  }

  if (millis() - lastReconnectAttempt >= WIFI_RETRY_INTERVAL_MS) {
    lastReconnectAttempt = millis();
    Serial.println("Trying to reconnect to WiFi...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  }
}
