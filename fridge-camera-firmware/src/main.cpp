#include <Arduino.h>

// הגדרת הפין של הלד של הפלאש (Flash LED)
#define FLASH_LED_PIN 4

void setup() {
  // הגדרת הפין כיציאה
  pinMode(FLASH_LED_PIN, OUTPUT);
}

void loop() {
  // הדלקת הפלאש
  digitalWrite(FLASH_LED_PIN, HIGH);
  delay(1000); // מחכים שנייה
  
  // כיבוי הפלאש
  digitalWrite(FLASH_LED_PIN, LOW);
  delay(1000); // מחכים שנייה
}