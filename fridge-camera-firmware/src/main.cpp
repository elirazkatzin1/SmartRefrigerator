#include <Arduino.h>
#include "wifi_manager.h"
#include "camera.h"
#include "door_sensor.h"
#include "api_client.h"
#include "event_sync.h"
#include "upload_queue.h"
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

// מצלם ומכניס לתור השליחה עם המזהה המשותף של אירוע הסגירה.
// התמונה לא נשלחת מיד: כשהדלת סגורה אין WiFi, והיא תישלח כשהחיבור יחזור
void captureAndQueue(const String &eventId) {
  camera_fb_t *fb = captureImage();
  if (fb) {
    queueImage(fb, eventId);
    esp_camera_fb_return(fb);
  }
}

// חיישן הדלת מדווח "סגור" כשהמגנט מתקרב, עוד לפני שהדלת נסגרה עד הסוף. מחכים שהדלת והמוצרים
// שבה יפסיקו לזוז, אחרת התמונות מטושטשות
#define CAPTURE_DELAY_MS 700

static bool capturePending = false;
static unsigned long captureAt = 0;
static String pendingEventId;

// הלוח המרכזי: מה קורה כשמצב הדלת משתנה
void handleDoorChange(bool isOpen) {
  Serial.println(isOpen ? "Door OPENED" : "Door CLOSED");
  if (isOpen) {
    queueDoorStatus(true, "");
    return;
  }

  String eventId = generateEventId();
  Serial.printf("Door close event: %s (capture in %d ms)\n", eventId.c_str(), CAPTURE_DELAY_MS);
  queueDoorStatus(false, eventId);

  // הצילום עצמו קורה ב-loop אחרי ההמתנה, בלי לעצור את הלוח (ה-WiFi ותור השליחה ממשיכים לעבוד)
  pendingEventId = eventId;
  captureAt = millis() + CAPTURE_DELAY_MS;
  capturePending = true;
}

// אחרי ההמתנה: קודם משדרים לשאר המצלמות (כמה מילישניות), כדי שכולן יצלמו כמעט באותו רגע,
// ואז מצלמים. השידור עובד גם כשהדלת סגורה, כי כל הלוחות נמצאים יחד בתוך המקרר
void runPendingCapture() {
  if (!capturePending || (long)(millis() - captureAt) < 0) {
    return;
  }
  capturePending = false;
  broadcastCaptureEvent(pendingEventId);
  captureAndQueue(pendingEventId);
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
    runPendingCapture();
  } else {
    String eventId;
    if (pollCaptureEvent(eventId)) {
      Serial.printf("Capture event received: %s\n", eventId.c_str());
      captureAndQueue(eventId);
    }
  }

  processUploadQueue();
}
