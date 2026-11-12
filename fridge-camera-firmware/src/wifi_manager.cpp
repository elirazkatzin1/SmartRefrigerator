#include <Arduino.h>
#include <WiFi.h>
#include "wifi_manager.h"
#include "config.h"

// כשהדלת סגורה אין WiFi. ניסיון קצר כל כמה שניות, כדי להתחבר מהר ברגע שהדלת נפתחת
// ולשלוח את מה שמחכה בתור עוד לפני שהיא נסגרת שוב
#define WIFI_RETRY_INTERVAL_MS 5000
// ניסיון רגיל פונה ישירות לערוץ ולנתב שהיינו מחוברים אליהם, בלי לסרוק את כל הערוצים.
// זה מהיר יותר, וגם משאיר את הרדיו על הערוץ של ESP-NOW כדי לא לפספס שידור צילום.
// סריקה מלאה רק מדי פעם, למקרה שהנתב החליף ערוץ
#define WIFI_FULL_SCAN_INTERVAL_MS 300000

static bool wifiConnected = false;
static unsigned long lastReconnectAttempt = 0;
static int32_t savedChannel = 0; // 0 = עוד לא התחברנו, אין ערוץ שמור
static uint8_t savedBssid[6];
static unsigned long lastFullScan = 0;

static void rememberAccessPoint() {
  savedChannel = WiFi.channel();
  memcpy(savedBssid, WiFi.BSSID(), sizeof(savedBssid));
  lastFullScan = millis();
}

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
    rememberAccessPoint();
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
      rememberAccessPoint();
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
    WiFi.disconnect();
    if (savedChannel == 0 || millis() - lastFullScan >= WIFI_FULL_SCAN_INTERVAL_MS) {
      lastFullScan = millis();
      Serial.println("Trying to reconnect to WiFi (full scan)...");
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    } else {
      Serial.printf("Trying to reconnect to WiFi (channel %d)...\n", savedChannel);
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD, savedChannel, savedBssid);
    }
  }
}
