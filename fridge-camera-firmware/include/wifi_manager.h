#pragma once

// מתחבר ל-WiFi בזמן setup (מחכה עד כ-10 שניות). אם נכשל, checkWiFiConnection ממשיכה לנסות
void connectToWiFi();

// בדיקה לא חוסמת שנקראת מ-loop: מזהה ניתוק ומתחברת מחדש
void checkWiFiConnection();
