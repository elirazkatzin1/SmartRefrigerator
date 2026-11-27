import Ionicons from '@expo/vector-icons/Ionicons';
import { Link, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Linking, Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';

import { API_BASE_URL, getFridgeState } from '../../src/api/client';
import { useApi } from '../../src/hooks/useApi';
import { getNotificationPermissionStatus } from '../../src/notifications';
import { useSettings } from '../../src/settings';
import { colors, formatDay, parseAddedAt, spacing } from '../../src/theme';

const GREEN = '#16A34A';

const NOTIFICATIONS = [
  { key: 'expiry', title: 'Expiry reminders', hint: '9:00 the day before, even when the app is closed' },
  { key: 'door', title: 'Door left open', hint: 'While the app is running' },
  { key: 'camera', title: 'Camera problems', hint: 'While the app is running' },
];

// A UTC time from the server as "just now", "5 min ago", "today 14:05" or "12/11 14:05"
function formatWhen(utc) {
  if (!utc) return 'Never';
  const time = parseAddedAt(utc);
  const minutes = Math.round((Date.now() - time) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const clock = `${String(time.getHours()).padStart(2, '0')}:${String(time.getMinutes()).padStart(2, '0')}`;
  if (time.toDateString() === new Date().toDateString()) return `Today ${clock}`;
  return `${formatDay(time).slice(0, 5)} ${clock}`;
}

function Row({ icon, label, value, valueColor, children }) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={20} color={colors.primary} />
      <Text style={styles.rowLabel}>{label}</Text>
      {children ?? <Text style={[styles.rowValue, valueColor && { color: valueColor }]}>{value}</Text>}
    </View>
  );
}

// What the server last heard from the fridge (SR-95). The cameras send no heartbeat, so their latest
// door event and photo are what shows they work.
function FridgeStatus() {
  const { data, loading, error, reload } = useApi(getFridgeState);
  useFocusEffect(
    useCallback(() => {
      reload({ silent: true });
    }, [reload])
  );

  if (loading) {
    return (
      <View style={styles.card}>
        <ActivityIndicator color={colors.primary} style={styles.cardLoading} />
      </View>
    );
  }
  if (error && !data) {
    return (
      <View style={styles.card}>
        <Row icon="cloud-offline-outline" label="Server" value="Not reachable" valueColor={colors.danger} />
        <Pressable style={styles.retry} onPress={() => reload()}>
          <Text style={styles.link}>Try again</Text>
        </Pressable>
      </View>
    );
  }

  const offline = data.offline_cameras;
  const door = data.door_open === null ? 'No events yet' : data.door_open ? 'Open' : 'Closed';
  return (
    <View style={styles.card}>
      <Row
        icon="server-outline"
        label="Server"
        value={error ? 'Not reachable' : 'Connected'}
        valueColor={error ? colors.danger : GREEN}
      />
      <View style={styles.divider} />
      <Row icon="exit-outline" label={`Door · ${door}`} value={formatWhen(data.last_door_event_at)} />
      <View style={styles.divider} />
      <Row icon="camera-outline" label="Last photo" value={formatWhen(data.last_image_at)} />
      <View style={styles.divider} />
      <Row
        icon={offline.length ? 'videocam-off-outline' : 'videocam-outline'}
        label={`Cameras · ${data.expected_cameras}`}
        value={offline.length ? `Missing: ${offline.join(', ')}` : 'All reported'}
        valueColor={offline.length ? colors.danger : GREEN}
      />
    </View>
  );
}

// Settings tab (SR-95): profile, which notifications to show, and the fridge's status
export default function SettingsScreen() {
  const { settings, updateSettings } = useSettings();
  const [permission, setPermission] = useState('granted');

  // The user may change notification permission in the phone's settings, so check on every visit
  useFocusEffect(
    useCallback(() => {
      getNotificationPermissionStatus().then(setPermission);
    }, [])
  );

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {/* A <Link asChild> child must get one style object, not an array: expo-router throws on arrays */}
      <Link href="/profile" asChild>
        <Pressable style={styles.profileCard}>
          <Ionicons name="person-circle-outline" size={28} color={colors.primary} />
          <View style={styles.profileText}>
            <Text style={styles.profileName}>{settings.name || 'Add your name'}</Text>
            <Text style={styles.hint}>Profile</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
        </Pressable>
      </Link>

      <Text style={styles.section}>Notifications</Text>
      <View style={styles.card}>
        {permission === 'denied' && (
          <View style={styles.permission}>
            <Text style={styles.permissionText}>
              Notifications are turned off for this app in the phone's settings, so none will appear.
            </Text>
            <Pressable onPress={() => Linking.openSettings()}>
              <Text style={styles.link}>Open phone settings</Text>
            </Pressable>
          </View>
        )}
        {NOTIFICATIONS.map((option, index) => (
          <View key={option.key}>
            {index > 0 && <View style={styles.divider} />}
            <View style={styles.row}>
              <View style={styles.switchText}>
                <Text style={styles.rowLabel}>{option.title}</Text>
                <Text style={styles.hint}>{option.hint}</Text>
              </View>
              <Switch
                value={settings.notify[option.key]}
                onValueChange={(on) => updateSettings({ notify: { [option.key]: on } })}
                trackColor={{ true: colors.primary }}
              />
            </View>
          </View>
        ))}
      </View>
      <Text style={styles.footnote}>The Home screen always shows every alert; these only control the phone notifications.</Text>

      <Text style={styles.section}>Fridge</Text>
      <FridgeStatus />

      <Text style={styles.footnote}>Server: {API_BASE_URL}</Text>
    </ScrollView>
  );
}

const card = {
  borderRadius: 12,
  backgroundColor: colors.surface,
  borderWidth: 1,
  borderColor: colors.border,
  paddingHorizontal: spacing.md,
};
const row = { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.md };

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.sm },
  card,
  row,
  profileCard: { ...card, ...row },
  cardLoading: { paddingVertical: spacing.lg },
  rowLabel: { flex: 1, fontSize: 15, color: colors.text },
  rowValue: { fontSize: 14, fontWeight: '600', color: colors.textMuted },
  divider: { height: 1, backgroundColor: colors.border },
  profileText: { flex: 1 },
  profileName: { fontSize: 17, fontWeight: '600', color: colors.text },
  hint: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  switchText: { flex: 1 },
  section: { fontSize: 13, fontWeight: '700', color: colors.textMuted, marginTop: spacing.md, textTransform: 'uppercase' },
  footnote: { fontSize: 12, color: colors.textMuted },
  permission: {
    gap: spacing.xs,
    marginTop: spacing.md,
    padding: spacing.sm,
    borderRadius: 8,
    backgroundColor: '#FFFBEB',
  },
  permissionText: { fontSize: 13, color: '#92400E' },
  link: { fontSize: 14, fontWeight: '600', color: colors.primary },
  retry: { paddingBottom: spacing.md },
});
