import Ionicons from '@expo/vector-icons/Ionicons';
import { useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, spacing } from '../theme';

// A chip like "Category: Dairy ▾" that opens a bottom sheet with the options (SR-90).
// options: [{ value, label }]; the first one is the "no filter" option (e.g. All).
export default function FilterDropdown({ title, options, value, onChange }) {
  const [open, setOpen] = useState(false);
  const insets = useSafeAreaInsets();
  const selected = options.find((option) => option.value === value) ?? options[0];
  const active = selected !== options[0];

  const choose = (optionValue) => {
    setOpen(false);
    onChange(optionValue);
  };

  return (
    <>
      <Pressable style={[styles.chip, active && styles.chipActive]} onPress={() => setOpen(true)}>
        <Text style={[styles.chipText, active && styles.chipTextActive]} numberOfLines={1}>
          {title}: {selected.label}
        </Text>
        <Ionicons name="chevron-down" size={16} color={active ? '#fff' : colors.text} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          {/* Inner Pressable keeps taps on the sheet from closing it */}
          <Pressable style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md }]}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <FlatList
              data={options}
              keyExtractor={(option) => option.value}
              renderItem={({ item: option }) => (
                <Pressable style={styles.option} onPress={() => choose(option.value)}>
                  <Text style={[styles.optionText, option.value === selected.value && styles.optionSelected]}>
                    {option.label}
                  </Text>
                  {option.value === selected.value && <Ionicons name="checkmark" size={20} color={colors.primary} />}
                </Pressable>
              )}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    flexShrink: 1,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 14, color: colors.text, flexShrink: 1 },
  chipTextActive: { color: '#fff', fontWeight: '600' },
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.35)' },
  sheet: {
    maxHeight: '70%',
    paddingTop: spacing.md,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    backgroundColor: colors.surface,
  },
  sheetTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.text,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  optionText: { fontSize: 16, color: colors.text },
  optionSelected: { color: colors.primary, fontWeight: '600' },
});
