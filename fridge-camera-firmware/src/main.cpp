#include <Arduino.h>
#include <WiFi.h>
#include "config.h"

#define FLASH_LED_PIN 4
#define WIFI_RETRY_INTERVAL_MS 10000
#define LED_BLINK_INTERVAL_MS 1000
#define DOOR_SENSOR_PIN 13 // MC-38: חוט אחד ל-GPIO13, השני ל-GND
#define DOOR_DEBOUNCE_MS 50

bool wifiConnected = false;
unsigned long lastReconnectAttempt = 0;
unsigned long lastLedToggle = 0;
bool ledOn = false;

bool doorOpen = false;
volatile bool doorChanged = false;
volatile unsigned long lastDoorInterrupt = 0;

void connectToWiFi() {
  Serial.println("=== Starting WiFi Connection ===");
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(false); // ההתחברות מחדש מנוהלת ב-checkWiFiConnection
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

void blinkLed() {
  if (millis() - lastLedToggle >= LED_BLINK_INTERVAL_MS) {
    lastLedToggle = millis();
    ledOn = !ledOn;
    digitalWrite(FLASH_LED_PIN, ledOn ? HIGH : LOW);
  }
}

// מגנט צמוד (דלת סגורה) = LOW, מגנט רחוק (דלת פתוחה) = HIGH
bool readDoorSensor() {
  return digitalRead(DOOR_SENSOR_PIN) == HIGH;
}

// ISR: רצה מיד כשהמתח בפין משתנה. חייבת להיות קצרה - רק מסמנת דגל, בלי Serial
void IRAM_ATTR onDoorChange() {
  doorChanged = true;
  lastDoorInterrupt = millis();
}

// מטפל בפסיקה מתוך loop: מחכה שהקפיצות יירגעו (DOOR_DEBOUNCE_MS) ומדפיס את המצב החדש
void checkDoorSensor() {
  if (!doorChanged || millis() - lastDoorInterrupt < DOOR_DEBOUNCE_MS) {
    return;
  }
  doorChanged = false;

  bool reading = readDoorSensor();
  if (reading != doorOpen) {
    doorOpen = reading;
    Serial.println(doorOpen ? "Door OPENED" : "Door CLOSED");
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // תן למונטור להתחבר
  Serial.println("\n\n=== SETUP STARTING ===");
  pinMode(FLASH_LED_PIN, OUTPUT);
  pinMode(DOOR_SENSOR_PIN, INPUT_PULLUP);

  doorOpen = readDoorSensor();
  Serial.println(doorOpen ? "Door initial state: OPEN" : "Door initial state: CLOSED");
  attachInterrupt(digitalPinToInterrupt(DOOR_SENSOR_PIN), onDoorChange, CHANGE);

  connectToWiFi();
  Serial.println("=== SETUP DONE ===");
}

void loop() {
  checkWiFiConnection();
  checkDoorSensor();
  blinkLed();
}
