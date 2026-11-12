#pragma once

#include <Arduino.h>

// שתי הפונקציות מחזירות true אם השרת ענה (גם בתשובת שגיאה - אין טעם לשלוח שוב),
// ו-false אם לא הייתה תקשורת עם השרת, ואז כדאי לנסות שוב מאוחר יותר

// שולח את מצב הדלת לשרת כ-JSON (POST /api/v1/fridge/status).
// eventId: המזהה המשותף של אירוע הסגירה, או מחרוזת ריקה בפתיחה.
// uptimeMs: הזמן שבו הדלת זזה בפועל (ההודעה יכולה להישלח מאוחר יותר)
bool sendDoorStatus(bool isOpen, const String &eventId, unsigned long uptimeMs);

// שולח תמונת JPEG לשרת כ-multipart/form-data (POST /api/v1/fridge/upload-image),
// יחד עם camera_id ו-event_id
bool uploadImage(const uint8_t *data, size_t len, const String &eventId);
