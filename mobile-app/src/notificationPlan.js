// Pure logic for the expiry reminders (SR-93): which notifications to schedule for an inventory.
// Kept apart from expo-notifications so it can be tested without a phone.

import { formatProductName, parseDay } from './theme';

// Remind this many days before the expiration date, at this local hour
export const REMIND_DAYS_BEFORE = 1;
export const REMIND_HOUR = 9;

// Scheduled reminders use this identifier prefix, so they can be found and replaced
export const EXPIRY_ID_PREFIX = 'expiry-day:';

function joinNames(names) {
  if (names.length === 1) return names[0];
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

// One reminder per expiration day (not per product), so a big shop doesn't flood the phone and the
// phone's limit on scheduled notifications (64 on iOS) is far away. Reminders whose time has already
// passed are skipped: the Home screen shows those alerts anyway.
//   -> [{ identifier, date, title, body, data }]
export function planExpiryReminders(items, now = new Date()) {
  const byDay = new Map();
  for (const item of items) {
    if (!item.expiration_date) continue;
    const list = byDay.get(item.expiration_date) ?? [];
    list.push(item);
    byDay.set(item.expiration_date, list);
  }

  const plan = [];
  for (const [day, dayItems] of [...byDay.entries()].sort()) {
    const remindAt = parseDay(day);
    remindAt.setDate(remindAt.getDate() - REMIND_DAYS_BEFORE);
    remindAt.setHours(REMIND_HOUR, 0, 0, 0);
    if (remindAt <= now) continue;

    const names = dayItems.map((item) => formatProductName(item.product_name));
    // "probably" only when every date of that day is an estimate; one real date makes it certain
    const allEstimated = dayItems.every((item) => item.expiration_source === 'estimated');
    const verb = `${allEstimated ? 'probably ' : ''}expire${names.length === 1 ? 's' : ''}`;
    plan.push({
      identifier: `${EXPIRY_ID_PREFIX}${day}`,
      date: remindAt,
      title: names.length === 1 ? 'Expiring tomorrow' : `${names.length} products expiring tomorrow`,
      body: `${joinNames(names)} ${verb} tomorrow`,
      data: { url: '/fridge' },
    });
  }
  return plan;
}

// Alerts that should pop up as a notification: door and camera events that were not in the
// previous list. Expiry alerts are left out: the scheduled reminders cover them.
export const EVENT_ALERT_TYPES = new Set(['door_open', 'camera_offline']);

export function newEventAlerts(alerts, seenIds) {
  return alerts.filter((alert) => EVENT_ALERT_TYPES.has(alert.type) && !seenIds.has(alert.id));
}
