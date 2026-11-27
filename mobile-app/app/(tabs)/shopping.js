import Ionicons from '@expo/vector-icons/Ionicons';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, SectionList, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  addShoppingItem,
  clearBoughtItems,
  deleteShoppingItem,
  getShoppingList,
  setShoppingItemChecked,
} from '../../src/api/client';
import ShoppingItemRow from '../../src/components/ShoppingItemRow';
import { EmptyState, ErrorState, LoadingState } from '../../src/components/StateViews';
import { useApi } from '../../src/hooks/useApi';
import { colors, spacing } from '../../src/theme';

// How long an error from a background action (check, delete, clear) stays on screen
const ACTION_ERROR_MS = 4000;

// Same order as the server: to buy first (in the order added), then bought
function sortItems(items) {
  return [...items].sort(
    (a, b) => a.checked - b.checked || a.created_at.localeCompare(b.created_at) || a.id - b.id
  );
}

// Shopping tab (SR-94): the list on the backend, with items the user adds and products added
// automatically when they run out. Check, delete and clear show right away and are sent in the
// background; if the server refuses, the list is reloaded from it and an error is shown.
export default function ShoppingScreen() {
  const { data, loading, refreshing, error, reload, setData } = useApi(getShoppingList);
  const [text, setText] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Auto-added items appear after door events, so reload whenever the tab is opened
  useFocusEffect(
    useCallback(() => {
      reload({ silent: true });
    }, [reload])
  );

  useEffect(() => {
    if (!actionError) return;
    const timer = setTimeout(() => setActionError(null), ACTION_ERROR_MS);
    return () => clearTimeout(timer);
  }, [actionError]);

  // Show a change right away, send it, and fall back to the server's list if it fails
  const change = async (update, send) => {
    setData((current) => sortItems(update(current ?? [])));
    try {
      await send();
    } catch (err) {
      setActionError(err.message);
      reload({ silent: true });
    }
  };

  const add = async () => {
    const name = text.trim();
    if (!name || adding) return;
    setAdding(true);
    setAddError(null);
    try {
      const item = await addShoppingItem(name);
      setData((current) => sortItems([...(current ?? []), item]));
      setText('');
    } catch (err) {
      setAddError(err.status === 409 ? `${name} is already on the list` : err.message);
    } finally {
      setAdding(false);
    }
  };

  const toggle = (item) =>
    change(
      (items) => items.map((i) => (i.id === item.id ? { ...i, checked: !i.checked } : i)),
      () => setShoppingItemChecked(item.id, !item.checked)
    );
  const remove = (item) =>
    change((items) => items.filter((i) => i.id !== item.id), () => deleteShoppingItem(item.id));
  const clearBought = () => change((items) => items.filter((i) => !i.checked), clearBoughtItems);

  if (loading) return <LoadingState message="Loading shopping list..." />;
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;

  const toBuy = data.filter((item) => !item.checked);
  const bought = data.filter((item) => item.checked);
  const sections = [
    toBuy.length > 0 && { key: 'toBuy', title: `To buy · ${toBuy.length}`, data: toBuy },
    bought.length > 0 && { key: 'bought', title: `Bought · ${bought.length}`, data: bought },
  ].filter(Boolean);

  return (
    <SectionList
      sections={sections}
      keyExtractor={(item) => String(item.id)}
      contentContainerStyle={[styles.list, !sections.length && styles.emptyList]}
      keyboardShouldPersistTaps="handled"
      stickySectionHeadersEnabled={false}
      refreshing={refreshing}
      onRefresh={reload}
      ListHeaderComponent={
        <View style={styles.header}>
          {error && <Text style={styles.banner}>Couldn't refresh: {error.message}</Text>}
          {actionError && <Text style={styles.banner}>Couldn't save: {actionError}</Text>}
          <View style={styles.addRow}>
            <TextInput
              style={styles.input}
              value={text}
              onChangeText={(value) => {
                setText(value);
                setAddError(null);
              }}
              placeholder="Add an item, e.g. Bread"
              placeholderTextColor={colors.textMuted}
              returnKeyType="done"
              onSubmitEditing={add}
              maxLength={60}
              editable={!adding}
            />
            <Pressable
              style={[styles.addButton, (!text.trim() || adding) && styles.addDisabled]}
              onPress={add}
              disabled={!text.trim() || adding}
              accessibilityLabel="Add item"
            >
              {adding ? <ActivityIndicator color="#fff" /> : <Ionicons name="add" size={26} color="#fff" />}
            </Pressable>
          </View>
          {addError && <Text style={styles.addError}>{addError}</Text>}
        </View>
      }
      renderSectionHeader={({ section }) => (
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{section.title}</Text>
          {section.key === 'bought' && (
            <Pressable onPress={clearBought} hitSlop={8}>
              <Text style={styles.clear}>Clear</Text>
            </Pressable>
          )}
        </View>
      )}
      renderItem={({ item }) => <ShoppingItemRow item={item} onToggle={toggle} onDelete={remove} />}
      ListEmptyComponent={
        <EmptyState
          icon="cart-outline"
          title="Your shopping list is empty"
          message="Add items above. Products you buy regularly are added here when they run out."
        />
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md, gap: spacing.sm },
  emptyList: { flexGrow: 1 },
  header: { gap: spacing.sm },
  banner: {
    padding: spacing.sm,
    borderRadius: 8,
    backgroundColor: '#FEF2F2',
    color: colors.danger,
    fontSize: 13,
  },
  addRow: { flexDirection: 'row', gap: spacing.sm },
  input: {
    flex: 1,
    height: 48,
    paddingHorizontal: spacing.md,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    fontSize: 16,
    color: colors.text,
  },
  addButton: {
    width: 48,
    height: 48,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  addDisabled: { opacity: 0.45 },
  addError: { fontSize: 13, color: colors.danger },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
  },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: colors.textMuted },
  clear: { fontSize: 14, fontWeight: '600', color: colors.primary },
});
