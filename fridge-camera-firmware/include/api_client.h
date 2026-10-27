#pragma once

#include <Arduino.h>
#include "esp_camera.h"

// שולח את מצב הדלת לשרת כ-JSON (POST /api/v1/fridge/status).
// eventId: המזהה המשותף של אירוע הסגירה, או מחרוזת ריקה בפתיחה
void sendDoorStatus(bool isOpen, const String &eventId);

// שולח תמונה לשרת כ-multipart/form-data (POST /api/v1/fridge/upload-image),
// יחד עם camera_id ו-event_id. לא משחרר את הבאפר - זה באחריות הקורא
void uploadImage(camera_fb_t *fb, const String &eventId);
