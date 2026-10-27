#include <Arduino.h>
#include "wifi_manager.h"
#include "camera.h"
#include "door_sensor.h"
#include "api_client.h"

// מה קורה כשמצב הדלת משתנה
void handleDoorChange(bool isOpen) {
  Serial.println(isOpen ? "Door OPENED" : "Door CLOSED");
  if (isOpen) {
    sendDoorStatus(true);
    return;
  }

  // כשהדלת נסגרת מצלמים מיד, עוד לפני שליחת הסטטוס לשרת,
  // כדי שהמתנה לשרת איטי או לא זמין (עד כמה שניות) לא תעכב את הצילום
  camera_fb_t *fb = captureImage();
  sendDoorStatus(false);
  if (fb) {
    uploadImage(fb);
    esp_camera_fb_return(fb);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // תן למונטור להתחבר
  Serial.println("\n\n=== SETUP STARTING ===");

  bool doorOpen = initDoorSensor();
  Serial.println(doorOpen ? "Door initial state: OPEN" : "Door initial state: CLOSED");

  initCamera();
  connectToWiFi();
  Serial.println("=== SETUP DONE ===");
}

void loop() {
  checkWiFiConnection();

  bool doorOpen;
  if (pollDoorChange(doorOpen)) {
    handleDoorChange(doorOpen);
  }
}
