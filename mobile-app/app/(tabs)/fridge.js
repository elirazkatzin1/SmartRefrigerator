import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';

import { getInventory } from '../../src/api/client';
import EditItemModal from '../../src/components/EditItemModal';
import FilterDropdown from '../../src/components/FilterDropdown';
import InventoryItemRow from '../../src/components/InventoryItemRow';
import { EmptyState, ErrorState, LoadingState } from '../../src/components/StateViews';
import { useApi } from '../../src/hooks/useApi';
import { colors, formatProductName, getExpiryStatus, SOON_MAX_DAYS, spacing } from '../../src/theme';

// While the Fridge tab is open, reload in the background this often. The backend has no
// push channel yet, so this is how a door-close event shows up in the list. Once the
// WebSocket from SR-92 exists, reload on its door-close message instead.
const AUTO_REFRESH_MS = 15000;

const ALL = 'all';
const NO_CATEGORY = 'none';

// Values match getExpiryStatus(), so the filter follows the same rule as the colors
const EXPIRY_OPTIONS = [
  { value: ALL, label: 'All' },
  { value: 'fresh', label: 'Fresh' },
  { value: 'soon', label: `Expiring soon (0-${SOON_MAX_DAYS} days)` },
  { value: 'expired', label: 'Expired' },
  { value: 'unknown', label: 'No expiry date' },
];

// Category options from the items in the fridge, so only categories that exist are offered.
// The selected category stays in the list even if its last item was just taken out.
function categoryOptions(items, selected) {
  const names = new Set(items.map((item) => item.category ?? NO_CATEGORY));
  if (selected !== ALL) names.add(selected);
  const sorted = [...names].sort((a, b) => (a === NO_CATEGORY) - (b === NO_CATEGORY) || a.localeCompare(b));
  return [
    { value: ALL, label: 'All' },
    ...sorted.map((name) => ({ value: name, label: name === NO_CATEGORY ? 'No category' : name })),
  ];
}

function matchesFilters(item, category, expiry) {
  if (category !== ALL && (item.category ?? NO_CATEGORY) !== category) return false;
  if (expiry !== ALL && getExpiryStatus(item.expiration_date) !== expiry) return false;
  return true;
}

// Header above the list: how many different products are in the fridge, and below it the
// total units (6 tomatoes count as 1 product and 6 units)
function InventoryTotal({ items }) {
  const units = items.reduce((sum, item) => sum + (item.quantity ?? 1), 0);
  return (
    <View style={styles.total}>
      <Text style={styles.totalNumber}>{items.length}</Text>
      <View>
        <Text style={styles.totalLabel}>
          {items.length === 1 ? 'product' : 'products'} in the fridge
        </Text>
        <Text style={styles.totalSub}>
          {units} {units === 1 ? 'unit' : 'units'} in total
        </Text>
      </View>
    </View>
  );
}

// How long the "Changes saved" confirmation stays on screen
const SAVED_MESSAGE_MS = 2500;

// Fridge tab: inventory list with category and expiry filters (SR-89, SR-90, SR-123)
// and editing an item (SR-91)
export default function FridgeScreen() {
  const { data, loading, refreshing, error, reload, setData } = useApi(getInventory);
  const [category, setCategory] = useState(ALL);
  const [expiry, setExpiry] = useState(ALL);
  const [editing, setEditing] = useState(null);
  const [savedName, setSavedName] = useState(null);

  // Hide the "Changes saved" confirmation after a moment
  useEffect(() => {
    if (!savedName) return;
    const timer = setTimeout(() => setSavedName(null), SAVED_MESSAGE_MS);
    return () => clearTimeout(timer);
  }, [savedName]);

  const onSaved = (updated) => {
    setEditing(null);
    // Show the new values right away, then reload so the list matches the server
    setData((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    setSavedName(formatProductName(updated.product_name));
    reload({ silent: true });
  };

  // Reload when the tab gets focus, then poll while it stays focused
  useFocusEffect(
    useCallback(() => {
      reload({ silent: true });
      const timer = setInterval(() => reload({ silent: true }), AUTO_REFRESH_MS);
      return () => clearInterval(timer);
    }, [reload])
  );

  const items = data ?? [];
  const filtered = useMemo(() => items.filter((item) => matchesFilters(item, category, expiry)), [items, category, expiry]);
  const filtering = category !== ALL || expiry !== ALL;
  const clearFilters = () => {
    setCategory(ALL);
    setExpiry(ALL);
  };

  if (loading) return <LoadingState message="Loading inventory..." />;
  // Full-screen error only when there is nothing to show; otherwise keep the last list
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;

  return (
    <>
      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={[styles.list, !filtered.length && styles.emptyList]}
        refreshing={refreshing}
        onRefresh={reload}
        ListHeaderComponent={
          <>
            {error && <Text style={styles.staleBanner}>Couldn't refresh: {error.message}</Text>}
            {items.length > 0 && (
              <>
                <InventoryTotal items={items} />
                <View style={styles.filters}>
                  <FilterDropdown
                    title="Category"
                    options={categoryOptions(items, category)}
                    value={category}
                    onChange={setCategory}
                  />
                  <FilterDropdown title="Expiry" options={EXPIRY_OPTIONS} value={expiry} onChange={setExpiry} />
                </View>
                {filtering && (
                  <View style={styles.filterStatus}>
                    <Text style={styles.filterCount}>
                      Showing {filtered.length} of {items.length}
                    </Text>
                    <Pressable onPress={clearFilters} hitSlop={8}>
                      <Text style={styles.clear}>Clear filters</Text>
                    </Pressable>
                  </View>
                )}
              </>
            )}
          </>
        }
        ListEmptyComponent={
          items.length === 0 ? (
            <EmptyState icon="snow-outline" title="The fridge is empty" message="Items appear here after the cameras detect them." />
          ) : (
            <View style={styles.noMatch}>
              <EmptyState icon="search-outline" title="No products match these filters" />
              <Pressable style={styles.clearButton} onPress={clearFilters}>
                <Text style={styles.clearButtonText}>Clear filters</Text>
              </Pressable>
            </View>
          )
        }
        renderItem={({ item }) => <InventoryItemRow item={item} onEdit={setEditing} />}
      />
      <EditItemModal item={editing} onClose={() => setEditing(null)} onSaved={onSaved} />
      {savedName && (
        <View style={styles.saved} pointerEvents="none">
          <Text style={styles.savedText}>✓ {savedName} saved</Text>
        </View>
      )}
    </>
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md, gap: spacing.sm },
  emptyList: { flexGrow: 1 },
  staleBanner: {
    padding: spacing.sm,
    borderRadius: 8,
    backgroundColor: '#FEF2F2',
    color: colors.danger,
    fontSize: 13,
    marginBottom: spacing.sm,
  },
  total: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: 12,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  totalNumber: { fontSize: 34, fontWeight: '700', color: colors.primary },
  totalLabel: { fontSize: 16, fontWeight: '600', color: colors.text },
  totalSub: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
  filters: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  filterStatus: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  filterCount: { fontSize: 13, color: colors.textMuted },
  clear: { fontSize: 14, fontWeight: '600', color: colors.primary },
  noMatch: { flex: 1, alignItems: 'center', paddingBottom: spacing.lg },
  clearButton: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: 8,
    backgroundColor: colors.primary,
  },
  clearButtonText: { color: '#fff', fontWeight: '600' },
  saved: {
    position: 'absolute',
    bottom: spacing.lg,
    alignSelf: 'center',
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: 20,
    backgroundColor: '#16A34A',
  },
  savedText: { color: '#fff', fontWeight: '600', fontSize: 14 },
});
