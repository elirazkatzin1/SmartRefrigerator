#include <Arduino.h>
#include "wifi_manager.h"
#include "camera.h"
#include "door_sensor.h"
#include "api_client.h"
#include "event_sync.h"
#include "config.h"

// כל מצלמה חייבת מזהה ייחודי בין 1 ל-5, מוגדר ב-config.h של אותו לוח
#ifndef CAMERA_ID
#error "CAMERA_ID is not defined - add '#define CAMERA_ID <1-5>' to include/config.h"
#endif
#if CAMERA_ID < 1 || CAMERA_ID > 5
#error "CAMERA_ID must be between 1 and 5"
#endif

// רק ללוח אחד יש חיישן דלת. הוא יוצר את event_id ומשדר אותו לשאר המצלמות
#ifndef IS_DOOR_MASTER
#error "IS_DOOR_MASTER is not defined - add '#define IS_DOOR_MASTER <1 or 0>' to include/config.h"
#endif

// מצלם ושולח לשרת עם המזהה המשותף של אירוע הסגירה
void captureAndUpload(const String &eventId) {
  camera_fb_t *fb = captureImage();
  if (fb) {
    uploadImage(fb, eventId);
    esp_camera_fb_return(fb);
  }
}

// הלוח המרכזי: מה קורה כשמצב הדלת משתנה
void handleDoorChange(bool isOpen) {
  Serial.println(isOpen ? "Door OPENED" : "Door CLOSED");
  if (isOpen) {
    sendDoorStatus(true, "");
    return;
  }

  // קודם משדרים לשאר המצלמות (כמה מילישניות), כדי שכל 5 המצלמות יצלמו כמעט באותו רגע.
  // אחר כך מצלמים, ורק בסוף פונים לשרת, שעלול להתעכב עד כמה שניות
  String eventId = generateEventId();
  Serial.printf("Door close event: %s\n", eventId.c_str());
  broadcastCaptureEvent(eventId);

  camera_fb_t *fb = captureImage();
  sendDoorStatus(false, eventId);
  if (fb) {
    uploadImage(fb, eventId);
    esp_camera_fb_return(fb);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000); // תן למונטור להתחבר
  Serial.println("\n\n=== SETUP STARTING ===");
  Serial.printf("Camera ID: %d (%s)\n", CAMERA_ID, IS_DOOR_MASTER ? "door master" : "follower");

  if (IS_DOOR_MASTER) {
    bool doorOpen = initDoorSensor();
    Serial.println(doorOpen ? "Door initial state: OPEN" : "Door initial state: CLOSED");
  }

  initCamera();
  connectToWiFi();
  initEventSync();
  Serial.println("=== SETUP DONE ===");
}

void loop() {
  checkWiFiConnection();

  if (IS_DOOR_MASTER) {
    bool doorOpen;
    if (pollDoorChange(doorOpen)) {
      handleDoorChange(doorOpen);
    }
  } else {
    String eventId;
    if (pollCaptureEvent(eventId)) {
      Serial.printf("Capture event received: %s\n", eventId.c_str());
      captureAndUpload(eventId);
    }
  }
}
