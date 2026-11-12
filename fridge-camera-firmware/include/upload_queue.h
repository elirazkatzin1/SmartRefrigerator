#pragma once

#include <Arduino.h>
#include "esp_camera.h"

// תור של הודעות ותמונות שמחכות לשליחה לשרת.
// כשדלת המקרר סגורה ה-WiFi לא יוצא מהמקרר, ולכן לא שולחים מיד: מכניסים לתור,
// ו-processUploadQueue שולחת כשיש חיבור (בדרך כלל בפתיחה הבאה של הדלת), לפי סדר ההכנסה

// מכניס לתור הודעת מצב דלת. זמן ה-uptime נשמר עכשיו, ולא ברגע השליחה
void queueDoorStatus(bool isOpen, const String &eventId);

// מעתיק את התמונה לתור. הקורא עדיין אחראי להחזיר את fb עם esp_camera_fb_return
void queueImage(camera_fb_t *fb, const String &eventId);

// נקראת מ-loop: כשיש WiFi שולחת פריט אחד מהתור. פריט שנכשל נשאר בתור ונשלח שוב אחר כך
void processUploadQueue();
