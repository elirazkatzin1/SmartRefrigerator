import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';

// One line of the shopping list (SR-94): a check circle, the name, an "Auto-added" badge for
// products added because they ran out, and a delete button
export default function ShoppingItemRow({ item, onToggle, onDelete }) {
  return (
    <View style={styles.row}>
      <Pressable
        style={styles.check}
        onPress={() => onToggle(item)}
        hitSlop={8}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: item.checked }}
        accessibilityLabel={item.name}
      >
        <Ionicons
          name={item.checked ? 'checkmark-circle' : 'ellipse-outline'}
          size={26}
          color={item.checked ? '#16A34A' : colors.textMuted}
        />
      </Pressable>
      <View style={styles.body}>
        <Text style={[styles.name, item.checked && styles.nameChecked]} numberOfLines={2}>
          {item.name}
        </Text>
        {item.source === 'auto' && !item.checked && (
          <View style={styles.badge}>
            <Ionicons name="sparkles-outline" size={12} color={colors.primary} />
            <Text style={styles.badgeText}>Auto-added: ran out</Text>
          </View>
        )}
      </View>
      <Pressable style={styles.delete} onPress={() => onDelete(item)} hitSlop={8} accessibilityLabel={`Delete ${item.name}`}>
        <Ionicons name="trash-outline" size={20} color={colors.textMuted} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  check: { alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1, gap: 4 },
  name: { fontSize: 16, color: colors.text },
  nameChecked: { color: colors.textMuted, textDecorationLine: 'line-through' },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    borderRadius: 10,
    backgroundColor: '#EAF2FD',
  },
  badgeText: { fontSize: 12, fontWeight: '600', color: colors.primary },
  delete: { padding: spacing.xs },
});
