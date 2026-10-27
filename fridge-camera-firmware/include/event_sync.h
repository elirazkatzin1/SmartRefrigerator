#pragma once

#include <Arduino.h>

// תיאום בין 5 המצלמות דרך ESP-NOW (תקשורת ישירה בין לוחות ESP32, בלי ראוטר).
// הלוח המרכזי (עם חיישן הדלת) משדר event_id בכל סגירת דלת, ושאר הלוחות מצלמים עם אותו מזהה.
// כל הלוחות חייבים להיות מחוברים לאותה רשת WiFi, כדי שישדרו על אותו ערוץ

// נקראת אחרי connectToWiFi - ESP-NOW עובד על הערוץ של רשת ה-WiFi
void initEventSync();

// מזהה אקראי ייחודי לאירוע סגירה, 16 תווים הקסדצימליים
String generateEventId();

// הלוח המרכזי: משדר לכל המצלמות לצלם עם eventId
void broadcastCaptureEvent(const String &eventId);

// שאר הלוחות: מחזירה true פעם אחת לכל אירוע חדש שהתקבל, ושומרת את המזהה ב-eventId
bool pollCaptureEvent(String &eventId);
