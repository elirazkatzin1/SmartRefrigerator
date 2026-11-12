import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { colors } from '../src/theme';

// Root stack: the tabs, plus screens pushed above them (Profile, reached from Settings).
export default function RootLayout() {
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
