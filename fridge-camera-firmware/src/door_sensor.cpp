#include <Arduino.h>
#include "door_sensor.h"

#define DOOR_SENSOR_PIN 13 // MC-38: חוט אחד ל-GPIO13, השני ל-GND
#define DOOR_DEBOUNCE_MS 50

static bool doorOpen = false;
static volatile bool doorChanged = false;
static volatile unsigned long lastDoorInterrupt = 0;

// מגנט צמוד (דלת סגורה) = LOW, מגנט רחוק (דלת פתוחה) = HIGH
static bool readDoorSensor() {
  return digitalRead(DOOR_SENSOR_PIN) == HIGH;
}

// ISR: רצה מיד כשהמתח בפין משתנה. חייבת להיות קצרה - רק מסמנת דגל, בלי Serial
static void IRAM_ATTR onDoorChange() {
  doorChanged = true;
  lastDoorInterrupt = millis();
}

bool initDoorSensor() {
  pinMode(DOOR_SENSOR_PIN, INPUT_PULLUP);
  doorOpen = readDoorSensor();
  attachInterrupt(digitalPinToInterrupt(DOOR_SENSOR_PIN), onDoorChange, CHANGE);
  return doorOpen;
}

// מטפל בפסיקה מתוך loop: מחכה שהקפיצות יירגעו (DOOR_DEBOUNCE_MS) ובודק אם המצב באמת השתנה
bool pollDoorChange(bool &isOpen) {
  if (!doorChanged || millis() - lastDoorInterrupt < DOOR_DEBOUNCE_MS) {
    return false;
  }
  doorChanged = false;

  bool reading = readDoorSensor();
  if (reading == doorOpen) {
    return false;
  }
  doorOpen = reading;
  isOpen = doorOpen;
  return true;
}
