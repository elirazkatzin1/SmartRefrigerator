#include <WiFi.h>
#include <esp_now.h>
#include "event_sync.h"
#include "config.h"

#define EVENT_ID_LENGTH 16
// מזהה את ההודעות שלנו, כדי להתעלם מהודעות ESP-NOW של מכשירים אחרים
#define CAPTURE_MESSAGE_MAGIC 0x46524447 // "FRDG"
// לשידור (broadcast) אין אישור קבלה, אז שולחים כמה פעמים. המקבלים מסננים כפילויות לפי event_id
#define BROADCAST_REPEATS 3
#define BROADCAST_REPEAT_DELAY_MS 5

typedef struct {
  uint32_t magic;
  uint8_t senderCameraId;
  char eventId[EVENT_ID_LENGTH + 1];
} CaptureMessage;

static const uint8_t BROADCAST_ADDRESS[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static bool eventSyncReady = false;
// ה-callback רץ ב-task של ה-WiFi, ולכן הגישה למשתנים המשותפים מוגנת ב-mutex
static portMUX_TYPE pendingMux = portMUX_INITIALIZER_UNLOCKED;
static char pendingEventId[EVENT_ID_LENGTH + 1] = "";
static bool hasPendingEvent = false;
static String lastHandledEventId;

static void onMessageReceived(const uint8_t *mac, const uint8_t *data, int len) {
  if (len != sizeof(CaptureMessage)) {
    return;
  }
  CaptureMessage message;
  memcpy(&message, data, sizeof(message));
  if (message.magic != CAPTURE_MESSAGE_MAGIC) {
    return;
  }
  message.eventId[EVENT_ID_LENGTH] = '\0';

  portENTER_CRITICAL(&pendingMux);
  strncpy(pendingEventId, message.eventId, sizeof(pendingEventId));
  hasPendingEvent = true;
  portEXIT_CRITICAL(&pendingMux);
}

void initEventSync() {
  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed - cameras will not be synchronized");
    return;
  }
  esp_now_register_recv_cb(onMessageReceived);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST_ADDRESS, sizeof(BROADCAST_ADDRESS));
  peer.channel = 0; // 0 = הערוץ הנוכחי של רשת ה-WiFi
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("ESP-NOW add broadcast peer failed");
    return;
  }

  eventSyncReady = true;
  Serial.printf("ESP-NOW ready on WiFi channel %d\n", WiFi.channel());
}

String generateEventId() {
  char id[EVENT_ID_LENGTH + 1];
  snprintf(id, sizeof(id), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  return String(id);
}

void broadcastCaptureEvent(const String &eventId) {
  if (!eventSyncReady) {
    Serial.println("Capture event not broadcast: ESP-NOW not ready");
    return;
  }

  CaptureMessage message = {};
  message.magic = CAPTURE_MESSAGE_MAGIC;
  message.senderCameraId = CAMERA_ID;
  strncpy(message.eventId, eventId.c_str(), EVENT_ID_LENGTH);

  for (int i = 0; i < BROADCAST_REPEATS; i++) {
    esp_now_send(BROADCAST_ADDRESS, (const uint8_t *)&message, sizeof(message));
    delay(BROADCAST_REPEAT_DELAY_MS);
  }
  Serial.printf("Capture event broadcast: %s\n", eventId.c_str());
}

bool pollCaptureEvent(String &eventId) {
  if (!hasPendingEvent) {
    return false;
  }

  portENTER_CRITICAL(&pendingMux);
  String received(pendingEventId);
  hasPendingEvent = false;
  portEXIT_CRITICAL(&pendingMux);

  // אותו אירוע מגיע כמה פעמים (BROADCAST_REPEATS) - מטפלים בו רק פעם אחת
  if (received == lastHandledEventId) {
    return false;
  }
  lastHandledEventId = received;
  eventId = received;
  return true;
}
