import { StyleSheet, Text, View } from 'react-native';

import { EmptyState } from '../../src/components/StateViews';
import { colors, spacing } from '../../src/theme';

// Home screen. Greeting and real-time alerts come in SR-92.
export default function HomeScreen() {
  const today = new Date().toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  return (
    <View style={styles.container}>
      <Text style={styles.greeting}>Hello!</Text>
      <Text style={styles.date}>{today}</Text>
      <Text style={styles.section}>Notifications</Text>
      <EmptyState icon="notifications-outline" title="No alerts right now" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.md },
  greeting: { fontSize: 26, fontWeight: '700', color: colors.text },
  date: { fontSize: 14, color: colors.textMuted, marginBottom: spacing.lg },
  section: { fontSize: 18, fontWeight: '600', color: colors.text },
});
