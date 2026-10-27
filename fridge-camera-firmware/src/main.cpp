#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "config.h"

#define FLASH_LED_PIN 4
// עוצמת הפלאש: 0 (כבוי) עד 255 (מלא). עוצמה נמוכה צורכת פחות זרם ומונעת נפילת מתח שמנתקת את ה-WiFi
#define FLASH_BRIGHTNESS 80
// ערוץ 2 (טיימר 1) - ערוץ 0 וטיימר 0 תפוסים על ידי שעון המצלמה
#define FLASH_PWM_CHANNEL 2
#define FLASH_PWM_FREQ 5000
#define FLASH_PWM_RESOLUTION 8
#define WIFI_RETRY_INTERVAL_MS 10000
#define DOOR_SENSOR_PIN 13 // MC-38: חוט אחד ל-GPIO13, השני ל-GND
#define DOOR_DEBOUNCE_MS 50
#define DOOR_STATUS_ENDPOINT "/api/v1/fridge/status"
#define IMAGE_UPLOAD_ENDPOINT "/api/v1/fridge/upload-image"
#define HTTP_TIMEOUT_MS 2000
#define IMAGE_UPLOAD_TIMEOUT_MS 5000
#define UPLOAD_CHUNK_SIZE 1024
#define MULTIPART_BOUNDARY "----FridgeCamBoundary7MA4YWxk"

// פיני המצלמה של לוח AI-Thinker ESP32-CAM
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

bool wifiConnected = false;
unsigned long lastReconnectAttempt = 0;
bool cameraReady = false;

bool doorOpen = false;
volatile bool doorChanged = false;
volatile unsigned long lastDoorInterrupt = 0;

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

void initCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  // באפר אחד + GRAB_WHEN_EMPTY: המצלמה מצלמת רק כשמבקשים ממנה ונחה בין צילומים.
  // צילום רציף ברקע (GRAB_LATEST) מעמיס על הזיכרון ומאט מאוד את ה-WiFi
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_count = 1;

  // עם PSRAM אפשר רזולוציה גבוהה יותר
  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA; // 800x600
    config.jpeg_quality = 12;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size = FRAMESIZE_VGA; // 640x480
    config.jpeg_quality = 15;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  cameraReady = (err == ESP_OK);
  if (cameraReady) {
    Serial.println("Camera initialized");
  } else {
    Serial.printf("Camera init failed: 0x%x\n", err);
  }
}

// מדפיס את קוד התשובה של השרת בפורמט אחיד. בשגיאה (לא 2xx) מדפיס גם את גוף התשובה
void logHttpResponse(const char *endpoint, int code, unsigned long durationMs, const String &body) {
  bool success = code >= 200 && code < 300;
  Serial.printf("[HTTP] POST %s -> %d %s (%lu ms)\n", endpoint, code, success ? "OK" : "ERROR", durationMs);
  if (!success && body.length() > 0) {
    Serial.printf("[HTTP] Response body: %s\n", body.substring(0, 200).c_str());
  }
}

// מפרק את SERVER_URL ("http://host:port") ל-host ו-port עבור WiFiClient
void parseServerUrl(String &host, uint16_t &port) {
  String url = SERVER_URL;
  url.replace("http://", "");
  int slash = url.indexOf('/');
  if (slash >= 0) {
    url = url.substring(0, slash);
  }
  int colon = url.indexOf(':');
  host = colon >= 0 ? url.substring(0, colon) : url;
  port = colon >= 0 ? url.substring(colon + 1).toInt() : 80;
}

// שולח את ה-frame buffer כ-multipart/form-data (שדה "file").
// הגוף נכתב לסוקט בחתיכות ישירות מה-frame buffer, בלי להעתיק את התמונה לזיכרון נוסף
void uploadImage(camera_fb_t *fb) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Image not sent: WiFi not connected");
    return;
  }

  String host;
  uint16_t port;
  parseServerUrl(host, port);

  WiFiClient client;
  if (!client.connect(host.c_str(), port, HTTP_TIMEOUT_MS)) {
    Serial.println("Image upload failed: connection refused");
    return;
  }

  String head = String("--") + MULTIPART_BOUNDARY + "\r\n" +
                "Content-Disposition: form-data; name=\"file\"; filename=\"fridge.jpg\"\r\n" +
                "Content-Type: image/jpeg\r\n\r\n";
  String tail = String("\r\n--") + MULTIPART_BOUNDARY + "--\r\n";
  size_t contentLength = head.length() + fb->len + tail.length();

  unsigned long start = millis();
  client.printf("POST %s HTTP/1.1\r\n", IMAGE_UPLOAD_ENDPOINT);
  client.printf("Host: %s:%u\r\n", host.c_str(), port);
  client.printf("Content-Type: multipart/form-data; boundary=%s\r\n", MULTIPART_BOUNDARY);
  client.printf("Content-Length: %u\r\n", contentLength);
  client.print("Connection: close\r\n\r\n");
  client.print(head);

  for (size_t sent = 0; sent < fb->len; sent += UPLOAD_CHUNK_SIZE) {
    size_t chunk = min((size_t)UPLOAD_CHUNK_SIZE, fb->len - sent);
    if (client.write(fb->buf + sent, chunk) != chunk) {
      Serial.println("Image upload failed: write error");
      client.stop();
      return;
    }
  }
  client.print(tail);

  // שורת הסטטוס של התשובה, למשל "HTTP/1.1 200 OK"
  unsigned long waitStart = millis();
  while (!client.available() && client.connected() && millis() - waitStart < IMAGE_UPLOAD_TIMEOUT_MS) {
    delay(10);
  }
  String statusLine = client.readStringUntil('\n');
  int code = statusLine.length() > 12 ? statusLine.substring(9, 12).toInt() : 0;
  unsigned long duration = millis() - start;

  // גוף התשובה מגיע אחרי שורה ריקה שמסיימת את הכותרות
  String body;
  if (code > 0 && client.find("\r\n\r\n")) {
    body = client.readString();
  }
  client.stop();

  if (code > 0) {
    Serial.printf("Image uploaded: %u bytes\n", fb->len);
    logHttpResponse(IMAGE_UPLOAD_ENDPOINT, code, duration, body);
  } else {
    Serial.println("Image upload failed: no response from server");
  }
}

// מצלם עם פלאש (בתוך מקרר סגור חשוך). מחזיר nullptr אם הצילום נכשל.
// מי שקורא לפונקציה אחראי להחזיר את הבאפר עם esp_camera_fb_return
camera_fb_t *captureImage() {
  if (!cameraReady) {
    Serial.println("Image not captured: camera not ready");
    return nullptr;
  }

  ledcWrite(FLASH_PWM_CHANNEL, FLASH_BRIGHTNESS);
  // הפריים שבבאפר צולם מיד אחרי הצילום הקודם (ישן ובלי פלאש) - זורקים אותו
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) {
    esp_camera_fb_return(fb);
  }
  fb = esp_camera_fb_get();
  ledcWrite(FLASH_PWM_CHANNEL, 0);

  if (!fb) {
    Serial.println("Image capture failed");
    return nullptr;
  }

  Serial.printf("Image captured: %u bytes\n", fb->len);
  return fb;
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

// שולח את מצב הדלת לשרת. זמן המתנה קצר כדי לא לתקוע את loop אם השרת לא זמין
void sendDoorStatus(bool isOpen) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Door status not sent: WiFi not connected");
    return;
  }

  HTTPClient http;
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(String(SERVER_URL) + DOOR_STATUS_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  String body = String("{\"event\":\"door\",\"door_open\":") + (isOpen ? "true" : "false") +
                ",\"uptime_ms\":" + millis() + "}";
  unsigned long start = millis();
  int code = http.POST(body);

  if (code > 0) {
    logHttpResponse(DOOR_STATUS_ENDPOINT, code, millis() - start, http.getString());
  } else {
    Serial.printf("Door status send failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
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
    if (doorOpen) {
      sendDoorStatus(true);
    } else {
      // כשהדלת נסגרת מצלמים מיד, עוד לפני שליחת הסטטוס לשרת,
      // כדי שהמתנה לשרת איטי או לא זמין (עד כמה שניות) לא תעכב את הצילום
      camera_fb_t *fb = captureImage();
      sendDoorStatus(false);
      if (fb) {
        uploadImage(fb);
        esp_camera_fb_return(fb);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // תן למונטור להתחבר
  Serial.println("\n\n=== SETUP STARTING ===");
  ledcSetup(FLASH_PWM_CHANNEL, FLASH_PWM_FREQ, FLASH_PWM_RESOLUTION);
  ledcAttachPin(FLASH_LED_PIN, FLASH_PWM_CHANNEL);
  ledcWrite(FLASH_PWM_CHANNEL, 0);
  pinMode(DOOR_SENSOR_PIN, INPUT_PULLUP);

  doorOpen = readDoorSensor();
  Serial.println(doorOpen ? "Door initial state: OPEN" : "Door initial state: CLOSED");
  attachInterrupt(digitalPinToInterrupt(DOOR_SENSOR_PIN), onDoorChange, CHANGE);

  initCamera();
  connectToWiFi();
  Serial.println("=== SETUP DONE ===");
}

void loop() {
  checkWiFiConnection();
  checkDoorSensor();
}
