#include <Arduino.h>
#include "camera.h"
#include "camera_pins.h"

#define FLASH_LED_PIN 4
// עוצמת הפלאש: 0 (כבוי) עד 255 (מלא). עוצמה נמוכה צורכת פחות זרם ומונעת נפילת מתח שמנתקת את ה-WiFi
#define FLASH_BRIGHTNESS 80
// ערוץ 2 (טיימר 1) - ערוץ 0 וטיימר 0 תפוסים על ידי שעון המצלמה
#define FLASH_PWM_CHANNEL 2
#define FLASH_PWM_FREQ 5000
#define FLASH_PWM_RESOLUTION 8

static bool cameraReady = false;

static void initFlash() {
  ledcSetup(FLASH_PWM_CHANNEL, FLASH_PWM_FREQ, FLASH_PWM_RESOLUTION);
  ledcAttachPin(FLASH_LED_PIN, FLASH_PWM_CHANNEL);
  ledcWrite(FLASH_PWM_CHANNEL, 0);
}

void initCamera() {
  initFlash();

  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  // 10MHz ולא 20MHz: שעון של 20MHz יוצר הפרעות לרדיו של ה-WiFi
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  // באפר אחד + GRAB_WHEN_EMPTY: המצלמה מצלמת רק כשמבקשים ממנה ונחה בין צילומים.
  // צילום רציף ברקע (GRAB_LATEST) מעמיס על הזיכרון ומאט מאוד את ה-WiFi
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_count = 1;

  // עם PSRAM אפשר רזולוציה גבוהה יותר
  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA; // 800x600
    config.jpeg_quality = 12;
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size = FRAMESIZE_VGA; // 640x480
    config.jpeg_quality = 15;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  cameraReady = (err == ESP_OK);
  if (cameraReady) {
    Serial.println("Camera initialized");
  } else {
    Serial.printf("Camera init failed: 0x%x\n", err);
  }
}

camera_fb_t *captureImage() {
  if (!cameraReady) {
    Serial.println("Image not captured: camera not ready");
    return nullptr;
  }

  ledcWrite(FLASH_PWM_CHANNEL, FLASH_BRIGHTNESS);
  // הפריים שבבאפר צולם מיד אחרי הצילום הקודם (ישן ובלי פלאש) - זורקים אותו
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) {
    esp_camera_fb_return(fb);
  }
  fb = esp_camera_fb_get();
  ledcWrite(FLASH_PWM_CHANNEL, 0);

  if (!fb) {
    Serial.println("Image capture failed");
    return nullptr;
  }

  Serial.printf("Image captured: %u bytes\n", fb->len);
  return fb;
}
