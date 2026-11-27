import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput } from 'react-native';

import { useSettings } from '../src/settings';
import { colors, spacing } from '../src/theme';

// Profile screen, reached from Settings (SR-95): the user's name, used in the Home greeting.
// Saved on this phone only.
export default function ProfileScreen() {
  const router = useRouter();
  const { settings, updateSettings } = useSettings();
  const [name, setName] = useState(settings.name);
  const trimmed = name.trim();
  const changed = trimmed !== settings.name;

  const save = () => {
    updateSettings({ name: trimmed });
    router.back();
  };

  // contentInsetAdjustmentBehavior="automatic" starts the content below the header: on recent iOS the
  // header of a pushed screen is see-through and the screen's content would otherwise sit under it
  return (
    <ScrollView
      contentContainerStyle={styles.container}
      contentInsetAdjustmentBehavior="automatic"
      keyboardShouldPersistTaps="handled"
    >
      <Text style={styles.label}>Your name</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Hadar"
        placeholderTextColor={colors.textMuted}
        maxLength={30}
        autoFocus
        returnKeyType="done"
        onSubmitEditing={() => changed && save()}
      />
      <Text style={styles.help}>Shown in the greeting on the Home screen. Saved on this phone only.</Text>
      <Pressable style={[styles.button, !changed && styles.buttonDisabled]} onPress={save} disabled={!changed}>
        <Text style={styles.buttonText}>Save</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md, gap: spacing.sm },
  label: { fontSize: 13, fontWeight: '600', color: colors.textMuted },
  input: {
    height: 48,
    paddingHorizontal: spacing.md,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    fontSize: 16,
    color: colors.text,
  },
  help: { fontSize: 12, color: colors.textMuted },
  button: {
    marginTop: spacing.md,
    height: 48,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  buttonDisabled: { opacity: 0.45 },
  buttonText: { fontSize: 16, fontWeight: '600', color: '#fff' },
});
