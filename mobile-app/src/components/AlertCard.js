import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, Text, View } from 'react-native';

import { colors, severityColors, spacing } from '../theme';

const ICONS = {
  door_open: 'exit-outline',
  camera_offline: 'videocam-off-outline',
  long_in_fridge: 'time-outline',
};

const SEVERITY_LABELS = { critical: 'Critical', warning: 'Warning', info: 'Info' };

// "since 14:05" for alerts raised today, otherwise "since 12/11"
function since(isoTime) {
  const time = new Date(isoTime);
  const today = new Date();
  if (time.toDateString() === today.toDateString()) {
    return `since ${String(time.getHours()).padStart(2, '0')}:${String(time.getMinutes()).padStart(2, '0')}`;
  }
  return `since ${String(time.getDate()).padStart(2, '0')}/${String(time.getMonth() + 1).padStart(2, '0')}`;
}

// One alert on the Home screen, colored by severity (SR-92)
export default function AlertCard({ alert }) {
  const color = severityColors[alert.severity] ?? severityColors.info;
  return (
    <View style={[styles.card, { backgroundColor: color.background, borderLeftColor: color.main }]}>
      <Ionicons name={ICONS[alert.type] ?? 'alert-circle-outline'} size={24} color={color.main} />
      <View style={styles.body}>
        <Text style={styles.message}>{alert.message}</Text>
        <Text style={[styles.meta, { color: color.main }]}>
          {SEVERITY_LABELS[alert.severity] ?? alert.severity}
          {/* "since" only means something for event alerts; long_in_fridge already says how long */}
          {alert.type !== 'long_in_fridge' && ` · ${since(alert.created_at)}`}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 10,
    borderLeftWidth: 5,
  },
  body: { flex: 1, gap: 2 },
  message: { fontSize: 15, color: colors.text, fontWeight: '500' },
  meta: { fontSize: 12, fontWeight: '600' },
});
