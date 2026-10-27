#pragma once

// מגדיר את פין החיישן ואת הפסיקה. מחזיר את מצב הדלת ההתחלתי (true = פתוחה)
bool initDoorSensor();

// נקראת מ-loop. מחזירה true פעם אחת לכל שינוי יציב במצב הדלת (אחרי debounce),
// ושומרת את המצב החדש ב-isOpen
bool pollDoorChange(bool &isOpen);
