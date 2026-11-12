import Ionicons from '@expo/vector-icons/Ionicons';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { API_BASE_URL } from '../../src/api/client';
import { colors, spacing } from '../../src/theme';

// Settings tab. Alert toggles and fridge status come in SR-95.
export default function SettingsScreen() {
  return (
    <View style={styles.container}>
      <Link href="/profile" asChild>
        <Pressable style={styles.row}>
          <Ionicons name="person-circle-outline" size={24} color={colors.primary} />
          <Text style={styles.label}>Profile</Text>
          <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
        </Pressable>
      </Link>
      <Text style={styles.caption}>Server: {API_BASE_URL}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: spacing.md, gap: spacing.md },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  label: { flex: 1, fontSize: 16, color: colors.text },
  caption: { fontSize: 12, color: colors.textMuted },
});
