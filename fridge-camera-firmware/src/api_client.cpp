#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "api_client.h"
#include "config.h"

#define DOOR_STATUS_ENDPOINT "/api/v1/fridge/status"
#define IMAGE_UPLOAD_ENDPOINT "/api/v1/fridge/upload-image"
#define HTTP_TIMEOUT_MS 2000
#define IMAGE_UPLOAD_TIMEOUT_MS 5000
#define UPLOAD_CHUNK_SIZE 1024
#define MULTIPART_BOUNDARY "----FridgeCamBoundary7MA4YWxk"

// מדפיס את קוד התשובה של השרת בפורמט אחיד. בשגיאה (לא 2xx) מדפיס גם את גוף התשובה
static void logHttpResponse(const char *endpoint, int code, unsigned long durationMs, const String &body) {
  bool success = code >= 200 && code < 300;
  Serial.printf("[HTTP] POST %s -> %d %s (%lu ms)\n", endpoint, code, success ? "OK" : "ERROR", durationMs);
  if (!success && body.length() > 0) {
    Serial.printf("[HTTP] Response body: %s\n", body.substring(0, 200).c_str());
  }
}

// מפרק את SERVER_URL ("http://host:port") ל-host ו-port עבור WiFiClient
static void parseServerUrl(String &host, uint16_t &port) {
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

// זמן המתנה קצר כדי לא לתקוע את loop אם השרת לא זמין
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
