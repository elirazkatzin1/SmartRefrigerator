#include <Arduino.h>
#include "wifi_manager.h"
#include "camera.h"
#include "door_sensor.h"
#include "api_client.h"
#include "config.h"

// כל מצלמה חייבת מזהה ייחודי בין 1 ל-5, מוגדר ב-config.h של אותו לוח
#ifndef CAMERA_ID
#error "CAMERA_ID is not defined - add '#define CAMERA_ID <1-5>' to include/config.h"
#endif
#if CAMERA_ID < 1 || CAMERA_ID > 5
#error "CAMERA_ID must be between 1 and 5"
#endif

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
  Serial.printf("Camera ID: %d\n", CAMERA_ID);

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
