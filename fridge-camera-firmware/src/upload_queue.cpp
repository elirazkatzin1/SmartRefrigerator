#include <Arduino.h>
#include <WiFi.h>
#include "upload_queue.h"
#include "api_client.h"

#define MAX_PENDING_ITEMS 10
// אחרי שליחה שנכשלה מחכים לפני הניסיון הבא, כדי לא לתקוע את loop בניסיונות חוזרים
#define RETRY_DELAY_MS 3000
// בלי PSRAM התמונות נשמרות בזיכרון הרגיל, וצריך להשאיר מספיק מקום ל-WiFi ול-HTTP
#define MIN_FREE_INTERNAL_HEAP 60000

enum PendingType { PENDING_DOOR_STATUS, PENDING_IMAGE };

struct PendingItem {
  PendingType type;
  String eventId;
  bool doorOpen;
  unsigned long uptimeMs;
  uint8_t *data;
  size_t len;
};

// תור מעגלי: head הוא הפריט הוותיק ביותר
static PendingItem queue[MAX_PENDING_ITEMS];
static int head = 0;
static int count = 0;
static bool waitingToRetry = false;
static unsigned long lastFailure = 0;

static const char *itemName(const PendingItem &item) {
  return item.type == PENDING_IMAGE ? "image" : "door status";
}

static void removeOldest() {
  PendingItem &item = queue[head];
  free(item.data);
  item.data = nullptr;
  item.len = 0;
  item.eventId = "";
  head = (head + 1) % MAX_PENDING_ITEMS;
  count--;
}

static void dropOldest() {
  Serial.printf("Upload queue: dropping oldest %s (event %s)\n", itemName(queue[head]), queue[head].eventId.c_str());
  removeOldest();
}

static PendingItem &pushItem() {
  if (count == MAX_PENDING_ITEMS) {
    dropOldest();
  }
  PendingItem &item = queue[(head + count) % MAX_PENDING_ITEMS];
  count++;
  return item;
}

// מקצה מקום לתמונה, עדיף ב-PSRAM. אם אין מספיק זיכרון, מוותרים על הפריטים הוותיקים
static uint8_t *allocImageBuffer(size_t len) {
  while (true) {
    uint8_t *buf = (uint8_t *)heap_caps_malloc(len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!buf) {
      buf = (uint8_t *)malloc(len);
      if (buf && heap_caps_get_free_size(MALLOC_CAP_INTERNAL) < MIN_FREE_INTERNAL_HEAP) {
        free(buf);
        buf = nullptr;
      }
    }
    if (buf || count == 0) {
      return buf;
    }
    dropOldest();
  }
}

void queueDoorStatus(bool isOpen, const String &eventId) {
  PendingItem &item = pushItem();
  item.type = PENDING_DOOR_STATUS;
  item.eventId = eventId;
  item.doorOpen = isOpen;
  item.uptimeMs = millis();
  item.data = nullptr;
  item.len = 0;
}

void queueImage(camera_fb_t *fb, const String &eventId) {
  uint8_t *copy = allocImageBuffer(fb->len);
  if (!copy) {
    Serial.println("Image not queued: out of memory");
    return;
  }
  memcpy(copy, fb->buf, fb->len);

  PendingItem &item = pushItem();
  item.type = PENDING_IMAGE;
  item.eventId = eventId;
  item.doorOpen = false;
  item.uptimeMs = millis();
  item.data = copy;
  item.len = fb->len;
}

void processUploadQueue() {
  if (count == 0 || WiFi.status() != WL_CONNECTED) {
    return;
  }
  if (waitingToRetry && millis() - lastFailure < RETRY_DELAY_MS) {
    return;
  }

  PendingItem &item = queue[head];
  bool delivered = item.type == PENDING_IMAGE
                       ? uploadImage(item.data, item.len, item.eventId)
                       : sendDoorStatus(item.doorOpen, item.eventId, item.uptimeMs);
  if (!delivered) {
    waitingToRetry = true;
    lastFailure = millis();
    Serial.printf("Upload queue: %s kept for retry (%d pending)\n", itemName(item), count);
    return;
  }

  waitingToRetry = false;
  removeOldest();
  if (count > 0) {
    Serial.printf("Upload queue: %d pending\n", count);
  }
}
