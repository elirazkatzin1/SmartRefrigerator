// Notifications on the phone (SR-93).
//
// These are LOCAL notifications: the app asks the phone to show them, no server push involved.
// Server push needs a development build (it doesn't work in Expo Go) and, on iPhone, a paid Apple
// Developer account, so it is left for later. What that means:
// - Expiry reminders are scheduled ahead in the phone's system, so they fire even when the app is closed.
// - Door and camera alerts come over the WebSocket, so they only pop up while the app is running.

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { EXPIRY_ID_PREFIX, planExpiryReminders } from './notificationPlan';

const ANDROID_CHANNEL = 'fridge-alerts';

// Show notifications as a banner even while the app is open
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

let permissionPromise = null;

// Asks for permission once (the system only shows its prompt the first time). Resolves to true when
// notifications may be shown. If the user declines, everything else in the app keeps working.
export function ensureNotificationPermission() {
  permissionPromise ??= (async () => {
    try {
      // Android 13+ shows the permission prompt only once a channel exists
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL, {
          name: 'Fridge alerts',
          importance: Notifications.AndroidImportance.HIGH,
        });
      }
      const current = await Notifications.getPermissionsAsync();
      if (current.granted) return true;
      if (!current.canAskAgain) return false;
      return (await Notifications.requestPermissionsAsync()).granted;
    } catch {
      return false;
    }
  })();
  return permissionPromise;
}

// The plan scheduled last time, to skip rescheduling when nothing changed (the Fridge tab reloads every 15s)
let lastPlanKey = null;

// Replace the scheduled expiry reminders with ones for this inventory. Called whenever the app has a
// fresh inventory, so edits, new products and removed ones are reflected.
export async function syncExpiryReminders(items) {
  if (!(await ensureNotificationPermission())) return;
  const plan = planExpiryReminders(items);
  const planKey = JSON.stringify(plan.map((reminder) => [reminder.identifier, reminder.date.getTime(), reminder.body]));
  if (planKey === lastPlanKey) return;
  try {
    const scheduled = await Notifications.getAllScheduledNotificationsAsync();
    await Promise.all(
      scheduled
        .filter((request) => request.identifier.startsWith(EXPIRY_ID_PREFIX))
        .map((request) => Notifications.cancelScheduledNotificationAsync(request.identifier))
    );
    for (const reminder of plan) {
      await Notifications.scheduleNotificationAsync({
        identifier: reminder.identifier,
        content: { title: reminder.title, body: reminder.body, data: reminder.data },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.DATE,
          date: reminder.date,
          channelId: ANDROID_CHANNEL,
        },
      });
    }
    lastPlanKey = planKey;
  } catch {
    // Notifications are a convenience: never let them break the screen that called this
  }
}

// Show a door or camera alert right away
export async function notifyAlert(alert) {
  if (!(await ensureNotificationPermission())) return;
  try {
    await Notifications.scheduleNotificationAsync({
      identifier: `alert:${alert.id}`,
      content: {
        title: alert.type === 'door_open' ? 'Fridge door open' : 'Camera problem',
        body: alert.message,
        data: { url: '/' },
      },
      trigger: null,
    });
  } catch {
    // See syncExpiryReminders
  }
}
