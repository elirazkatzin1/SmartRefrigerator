import Ionicons from '@expo/vector-icons/Ionicons';
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { updateInventoryItem } from '../api/client';
import { CATEGORIES } from '../categories';
import {
  colors,
  describeExpiry,
  describeTimeInFridge,
  formatDay,
  formatProductName,
  parseAddedAt,
  parseDay,
  spacing,
  toIsoDay,
} from '../theme';

// "Edit Item" bottom sheet: fix the expiration date (SR-123), date added, category and quantity of
// one item (SR-91). Stays open with an error message if saving fails; calls onSaved(updatedItem) on success.
export default function EditItemModal({ item, onClose, onSaved }) {
  const insets = useSafeAreaInsets();
  const [expiresOn, setExpiresOn] = useState(null);
  const [addedOn, setAddedOn] = useState(null);
  const [category, setCategory] = useState(null);
  const [quantity, setQuantity] = useState(1);
  // Which inline date picker is open on iOS: 'expiry' | 'added' | null
  const [iosPicker, setIosPicker] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // Start from the item's current values every time the sheet opens for an item
  useEffect(() => {
    if (!item) return;
    setExpiresOn(item.expiration_date ? parseDay(item.expiration_date) : null);
    setAddedOn(parseAddedAt(item.added_at));
    setCategory(item.category);
    setQuantity(item.quantity ?? 1);
    setIosPicker(null);
    setSaving(false);
    setError(null);
  }, [item]);

  if (!item || !addedOn) return null;

  const changes = {};
  if (expiresOn && toIsoDay(expiresOn) !== item.expiration_date) changes.expiration_date = toIsoDay(expiresOn);
  if (toIsoDay(addedOn) !== toIsoDay(parseAddedAt(item.added_at))) changes.added_on = toIsoDay(addedOn);
  if (category !== item.category) changes.category = category;
  if (quantity !== (item.quantity ?? 1)) changes.quantity = quantity;
  const hasChanges = Object.keys(changes).length > 0;

  // How the expiry field reads right now: the item's own text until the user picks another date
  const expiryPreview = changes.expiration_date
    ? describeExpiry({ expiration_date: changes.expiration_date, expiration_source: 'manual' })
    : describeExpiry(item);

  // Android opens a dialog; iOS shows an inline calendar under the field
  const pickDate = (which, value, onPick, maximumDate) => {
    if (Platform.OS === 'android') {
      DateTimePickerAndroid.open({
        value,
        mode: 'date',
        maximumDate,
        onChange: (event, day) => event.type === 'set' && day && onPick(day),
      });
    } else {
      setIosPicker((open) => (open === which ? null : which));
    }
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateInventoryItem(item.id, changes);
      onSaved(updated);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} onPress={saving ? undefined : onClose} />
        <View style={[styles.sheet, { paddingBottom: insets.bottom + spacing.md }]}>
          <ScrollView contentContainerStyle={styles.content}>
            <Text style={styles.title}>Edit Item</Text>
            <Text style={styles.subtitle}>{formatProductName(item.product_name)}</Text>

            <Text style={styles.label}>Expiry date</Text>
            <Pressable style={styles.field} onPress={() => pickDate('expiry', expiresOn ?? new Date(), setExpiresOn)}>
              <Ionicons name="hourglass-outline" size={20} color={colors.primary} />
              <Text style={styles.fieldText}>{expiresOn ? formatDay(expiresOn) : 'Not set'}</Text>
              <Text style={styles.fieldHint}>{expiryPreview}</Text>
            </Pressable>
            <Text style={styles.help}>
              {item.expiration_source === 'estimated' && !changes.expiration_date
                ? 'Estimated from the product type. Copy the date from the package to make it exact.'
                : 'The date printed on the package.'}
            </Text>
            {iosPicker === 'expiry' && (
              <DateTimePicker
                value={expiresOn ?? new Date()}
                mode="date"
                display="inline"
                onChange={(event, day) => day && setExpiresOn(day)}
              />
            )}

            <Text style={styles.label}>Date added</Text>
            <Pressable style={styles.field} onPress={() => pickDate('added', addedOn, setAddedOn, new Date())}>
              <Ionicons name="calendar-outline" size={20} color={colors.primary} />
              <Text style={styles.fieldText}>{formatDay(addedOn)}</Text>
              <Text style={styles.fieldHint}>{describeTimeInFridge(addedOn.toISOString())}</Text>
            </Pressable>
            {iosPicker === 'added' && (
              <DateTimePicker
                value={addedOn}
                mode="date"
                display="inline"
                maximumDate={new Date()}
                onChange={(event, day) => day && setAddedOn(day)}
              />
            )}

            <Text style={styles.label}>Category</Text>
            <View style={styles.chips}>
              {CATEGORIES.map((name) => (
                <Pressable
                  key={name}
                  style={[styles.chip, category === name && styles.chipSelected]}
                  onPress={() => setCategory(name)}
                >
                  <Text style={[styles.chipText, category === name && styles.chipTextSelected]}>{name}</Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.label}>Quantity</Text>
            <View style={styles.stepper}>
              <Pressable
                style={[styles.stepButton, quantity <= 1 && styles.stepDisabled]}
                onPress={() => setQuantity((q) => Math.max(1, q - 1))}
                disabled={quantity <= 1}
              >
                <Ionicons name="remove" size={22} color={colors.primary} />
              </Pressable>
              <Text style={styles.quantity}>{quantity}</Text>
              <Pressable style={styles.stepButton} onPress={() => setQuantity((q) => q + 1)}>
                <Ionicons name="add" size={22} color={colors.primary} />
              </Pressable>
            </View>

            {error && <Text style={styles.error}>Couldn't save: {error}</Text>}
          </ScrollView>

          <View style={styles.actions}>
            <Pressable style={[styles.button, styles.cancel]} onPress={onClose} disabled={saving}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable
              style={[styles.button, styles.save, (!hasChanges || saving) && styles.saveDisabled]}
              onPress={save}
              disabled={!hasChanges || saving}
            >
              {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveText}>Save Changes</Text>}
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,0.35)' },
  sheet: {
    maxHeight: '90%',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    backgroundColor: colors.surface,
  },
  content: { padding: spacing.lg, paddingBottom: spacing.sm },
  title: { fontSize: 20, fontWeight: '700', color: colors.text },
  subtitle: { fontSize: 15, color: colors.textMuted, marginTop: 2 },
  label: { fontSize: 13, fontWeight: '600', color: colors.textMuted, marginTop: spacing.lg, marginBottom: spacing.sm },
  field: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  fieldText: { fontSize: 16, color: colors.text, fontWeight: '600' },
  fieldHint: { flex: 1, textAlign: 'right', fontSize: 13, color: colors.textMuted },
  help: { fontSize: 12, color: colors.textMuted, marginTop: spacing.xs },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  chip: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { fontSize: 14, color: colors.text },
  chipTextSelected: { color: '#fff', fontWeight: '600' },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
  stepButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.primary,
  },
  stepDisabled: { opacity: 0.35 },
  quantity: { fontSize: 22, fontWeight: '700', color: colors.text, minWidth: 32, textAlign: 'center' },
  error: {
    marginTop: spacing.lg,
    padding: spacing.sm,
    borderRadius: 8,
    backgroundColor: '#FEF2F2',
    color: colors.danger,
    fontSize: 13,
  },
  actions: { flexDirection: 'row', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
  button: { flex: 1, height: 48, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  cancel: { borderWidth: 1, borderColor: colors.border },
  cancelText: { fontSize: 16, fontWeight: '600', color: colors.text },
  save: { backgroundColor: colors.primary },
  saveDisabled: { opacity: 0.45 },
  saveText: { fontSize: 16, fontWeight: '600', color: '#fff' },
});
