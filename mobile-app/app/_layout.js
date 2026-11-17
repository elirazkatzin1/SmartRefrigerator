import * as Notifications from 'expo-notifications';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { AppState } from 'react-native';

import { getInventory } from '../src/api/client';
import { ensureNotificationPermission, syncExpiryReminders } from '../src/notifications';
import { colors } from '../src/theme';

// Tapping a notification opens the screen in its data.url ("/fridge" for expiry, "/" for door/camera),
// also when the tap is what launched the app (SR-93)
function useOpenNotificationTaps() {
  const router = useRouter();
  useEffect(() => {
    const open = (response) => {
      const url = response?.notification.request.content.data?.url;
      if (typeof url === 'string') router.push(url);
    };
    const launchedBy = Notifications.getLastNotificationResponse();
    if (launchedBy) {
      open(launchedBy);
      Notifications.clearLastNotificationResponse();
    }
    const subscription = Notifications.addNotificationResponseReceivedListener(open);
    return () => subscription.remove();
  }, [router]);
}

// Ask for notification permission on the first launch, and keep the expiry reminders in step with
// the inventory: on start and whenever the app comes back to the foreground (SR-93)
function useExpiryReminders() {
  useEffect(() => {
    const sync = () =>
      getInventory()
        .then(syncExpiryReminders)
        .catch(() => {
          // Server not reachable: keep the reminders scheduled last time
        });
    ensureNotificationPermission().then(sync);
    const subscription = AppState.addEventListener('change', (state) => state === 'active' && sync());
    return () => subscription.remove();
  }, []);
}

// Root stack: the tabs, plus screens pushed above them (Profile, reached from Settings).
export default function RootLayout() {
  useOpenNotificationTaps();
  useExpiryReminders();

  return (
    <>
      <Stack screenOptions={{ contentStyle: { backgroundColor: colors.background } }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="profile" options={{ title: 'Profile' }} />
      </Stack>
      <StatusBar style="dark" />
    </>
  );
}
