import { ScrollView, StyleSheet, Text, View } from 'react-native';

import AlertCard from '../../src/components/AlertCard';
import { EmptyState } from '../../src/components/StateViews';
import { useAlertNotifications } from '../../src/hooks/useAlertNotifications';
import { useAlerts } from '../../src/hooks/useAlerts';
import { colors, spacing } from '../../src/theme';

// Greeting by the time of day. The user's name comes with the Profile screen (SR-95)
function greeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 17) return 'Good afternoon';
  if (hour >= 17 && hour < 22) return 'Good evening';
  return 'Good night';
}

const CONNECTION = {
  connected: { color: '#16A34A', label: 'Live' },
  connecting: { color: colors.textMuted, label: 'Connecting...' },
  disconnected: { color: colors.danger, label: 'Offline, retrying' },
};

// Home screen: greeting, today's date and the live fridge alerts (SR-92)
export default function HomeScreen() {
  const { alerts, status, loaded } = useAlerts();
  useAlertNotifications(alerts, loaded);
  const connection = CONNECTION[status];
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.greeting}>{greeting()}!</Text>
      <Text style={styles.date}>{today}</Text>

      <View style={styles.sectionHeader}>
        <Text style={styles.section}>Notifications</Text>
        <View style={styles.connection}>
          <View style={[styles.dot, { backgroundColor: connection.color }]} />
          <Text style={[styles.connectionText, { color: connection.color }]}>{connection.label}</Text>
        </View>
      </View>

      {alerts.length > 0 ? (
        <View style={styles.list}>
          {alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </View>
      ) : status === 'connected' ? (
        <EmptyState icon="notifications-outline" title="No alerts right now" message="The fridge looks fine." />
      ) : status === 'connecting' ? (
        <EmptyState icon="notifications-outline" title="Loading alerts..." />
      ) : (
        <EmptyState
          icon="cloud-offline-outline"
          title="Can't reach the server"
          message="Alerts will appear once the connection is back."
        />
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: spacing.md },
  greeting: { fontSize: 26, fontWeight: '700', color: colors.text },
  date: { fontSize: 14, color: colors.textMuted, marginBottom: spacing.lg },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  section: { fontSize: 18, fontWeight: '600', color: colors.text },
  connection: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  dot: { width: 8, height: 8, borderRadius: 4 },
  connectionText: { fontSize: 12, fontWeight: '600' },
  list: { gap: spacing.sm },
});
