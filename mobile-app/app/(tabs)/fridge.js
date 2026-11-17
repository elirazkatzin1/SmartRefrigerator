import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';

import { getInventory } from '../../src/api/client';
import InventoryItemRow from '../../src/components/InventoryItemRow';
import { EmptyState, ErrorState, LoadingState } from '../../src/components/StateViews';
import { useApi } from '../../src/hooks/useApi';
import { colors, spacing } from '../../src/theme';

// While the Fridge tab is open, reload in the background this often. The backend has no
// push channel yet, so this is how a door-close event shows up in the list. Once the
// WebSocket from SR-92 exists, reload on its door-close message instead.
const AUTO_REFRESH_MS = 15000;

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

// Fridge tab: inventory list, each item colored by how long it has been in the fridge (SR-89)
export default function FridgeScreen() {
  const { data, loading, refreshing, error, reload } = useApi(getInventory);

  // Reload when the tab gets focus, then poll while it stays focused
  useFocusEffect(
    useCallback(() => {
      reload({ silent: true });
      const timer = setInterval(() => reload({ silent: true }), AUTO_REFRESH_MS);
      return () => clearInterval(timer);
    }, [reload])
  );

  if (loading) return <LoadingState message="Loading inventory..." />;
  // Full-screen error only when there is nothing to show; otherwise keep the last list
  if (error && !data) return <ErrorState error={error} onRetry={reload} />;

  return (
    <FlatList
      data={data}
      keyExtractor={(item) => String(item.id)}
      contentContainerStyle={[styles.list, !data.length && styles.emptyList]}
      refreshing={refreshing}
      onRefresh={reload}
      ListHeaderComponent={
        <>
          {error && <Text style={styles.staleBanner}>Couldn't refresh: {error.message}</Text>}
          {data.length > 0 && <InventoryTotal items={data} />}
        </>
      }
      ListEmptyComponent={
        <EmptyState icon="snow-outline" title="The fridge is empty" message="Items appear here after the cameras detect them." />
      }
      renderItem={({ item }) => <InventoryItemRow item={item} />}
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md, gap: spacing.sm },
  emptyList: { flexGrow: 1 },
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
  staleBanner: {
    padding: spacing.sm,
    borderRadius: 8,
    backgroundColor: '#FEF2F2',
    color: colors.danger,
    fontSize: 13,
  },
});
