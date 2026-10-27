#pragma once

#include "esp_camera.h"

// שולח את מצב הדלת לשרת כ-JSON (POST /api/v1/fridge/status)
void sendDoorStatus(bool isOpen);

// שולח תמונה לשרת כ-multipart/form-data (POST /api/v1/fridge/upload-image).
// לא משחרר את הבאפר - זה באחריות הקורא
void uploadImage(camera_fb_t *fb);
