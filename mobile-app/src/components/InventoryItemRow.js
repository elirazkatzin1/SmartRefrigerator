import Ionicons from '@expo/vector-icons/Ionicons';
import { StyleSheet, Text, View } from 'react-native';

import {
  colors,
  describeTimeInFridge,
  formatProductName,
  fridgeTimeColors,
  getFridgeTimeStatus,
  spacing,
} from '../theme';

// One item in the Fridge list: color strip by time in the fridge, name, quantity, category
// and how long it has been in the fridge (SR-89)
export default function InventoryItemRow({ item }) {
  const color = fridgeTimeColors[getFridgeTimeStatus(item.added_at)];

  return (
    <View style={styles.row}>
      <View style={[styles.strip, { backgroundColor: color }]} />
      <View style={styles.body}>
        <View style={styles.topLine}>
          <Text style={styles.name} numberOfLines={1}>
            {formatProductName(item.product_name)}
          </Text>
          <Text style={styles.quantity}>×{item.quantity ?? 1}</Text>
        </View>
        <Text style={styles.category}>{item.category ?? 'No category'}</Text>
        <View style={styles.timeLine}>
          <Ionicons name="time-outline" size={14} color={colors.textMuted} />
          <Text style={styles.time}>{describeTimeInFridge(item.added_at)}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    borderRadius: 10,
    overflow: 'hidden',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  strip: { width: 6 },
  body: { flex: 1, padding: spacing.md, gap: 2 },
  topLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  name: { flex: 1, fontSize: 16, fontWeight: '600', color: colors.text },
  quantity: { fontSize: 14, fontWeight: '600', color: colors.textMuted },
  category: { fontSize: 13, color: colors.textMuted },
  timeLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  time: { fontSize: 13, fontWeight: '600', color: colors.text },
});
