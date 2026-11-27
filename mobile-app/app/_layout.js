import * as Notifications from 'expo-notifications';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { AppState } from 'react-native';

import { getInventory } from '../src/api/client';
import { ensureNotificationPermission, setNotificationPreferences, syncExpiryReminders } from '../src/notifications';
import { SettingsProvider, useSettings } from '../src/settings';
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
// the inventory and the user's notification settings: on start, whenever the app comes back to the
// foreground, and when a setting changes (SR-93, SR-95)
function useExpiryReminders() {
  const { settings, loaded } = useSettings();
  const { notify } = settings;

  useEffect(() => {
    // Wait for the stored settings, so reminders the user turned off are never scheduled
    if (!loaded) return undefined;
    setNotificationPreferences(notify);
    const sync = () =>
      getInventory()
        .then(syncExpiryReminders)
        .catch(() => {
          // Server not reachable: keep the reminders scheduled last time
        });
    ensureNotificationPermission().then(sync);
    const subscription = AppState.addEventListener('change', (state) => state === 'active' && sync());
    return () => subscription.remove();
  }, [loaded, notify]);
}

function AppShell() {
  useOpenNotificationTaps();
  useExpiryReminders();

  return (
    <>
      <Stack screenOptions={{ contentStyle: { backgroundColor: colors.background } }}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        {/* Without headerBackTitle the back button would show the tab group's name, "(tabs)" */}
        <Stack.Screen name="profile" options={{ title: 'Profile', headerBackTitle: 'Settings' }} />
      </Stack>
      <StatusBar style="dark" />
    </>
  );
}

// Root: the settings are available to every screen; the stack holds the tabs, plus screens pushed
// above them (Profile, reached from Settings)
export default function RootLayout() {
  return (
    <SettingsProvider>
      <AppShell />
    </SettingsProvider>
  );
}
