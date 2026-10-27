#pragma once

#include "esp_camera.h"

// מאתחל את המצלמה ואת הפלאש. אם האתחול נכשל, captureImage תחזיר nullptr
void initCamera();

// מצלם עם פלאש. מחזיר nullptr אם הצילום נכשל.
// מי שקורא לפונקציה אחראי להחזיר את הבאפר עם esp_camera_fb_return
camera_fb_t *captureImage();
