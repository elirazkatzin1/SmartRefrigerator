import { FlatList, StyleSheet, Text, View } from 'react-native';

import { getInventory } from '../../src/api/client';
import { EmptyState, ErrorState, LoadingState } from '../../src/components/StateViews';
import { useApi } from '../../src/hooks/useApi';
import { colors, freshnessColors, getFreshness, spacing } from '../../src/theme';

// Fridge tab: a basic inventory list that proves the API client and shared states work.
// The full dashboard, filters and editing come in SR-89, SR-90 and SR-91.
export default function FridgeScreen() {
  const { data, loading, error, reload } = useApi(getInventory);

  if (loading && !data) return <LoadingState message="Loading inventory..." />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data?.length) {
    return <EmptyState icon="snow-outline" title="The fridge is empty" message="Items appear here after the cameras detect them." />;
  }

  return (
    <FlatList
      data={data}
      keyExtractor={(item) => String(item.id)}
      contentContainerStyle={styles.list}
      refreshing={loading}
      onRefresh={reload}
      renderItem={({ item }) => (
        <View style={styles.row}>
          <View style={[styles.dot, { backgroundColor: freshnessColors[getFreshness(item.expiration_date)] }]} />
          <View style={styles.info}>
            <Text style={styles.name}>{item.product_name}</Text>
            <Text style={styles.meta}>
              {item.category ?? 'No category'} · {item.expiration_date ?? 'No expiry date'}
            </Text>
          </View>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  list: { padding: spacing.md, gap: spacing.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  dot: { width: 12, height: 12, borderRadius: 6, marginRight: spacing.md },
  info: { flex: 1 },
  name: { fontSize: 16, fontWeight: '600', color: colors.text },
  meta: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
});
