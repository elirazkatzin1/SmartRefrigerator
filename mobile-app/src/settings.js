// The user's settings (SR-95): their name and which notifications they want.
// Stored on this phone only (AsyncStorage), so each person's phone keeps its own choices.

import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'smartfridge.settings.v1';

export const DEFAULT_SETTINGS = {
  name: '',
  // Which phone notifications to show (SR-93)
  notify: { expiry: true, door: true, camera: true },
};

// Fill in anything missing from what was stored, e.g. a setting added in a newer version of the app
function withDefaults(stored) {
  return {
    ...DEFAULT_SETTINGS,
    ...stored,
    notify: { ...DEFAULT_SETTINGS.notify, ...(stored?.notify ?? {}) },
  };
}

const SettingsContext = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => raw && setSettings(withDefaults(JSON.parse(raw))))
      .catch(() => {
        // Unreadable storage: start from the defaults
      })
      .finally(() => setLoaded(true));
  }, []);

  // Save every change, once the stored settings were loaded (so the defaults never overwrite them)
  useEffect(() => {
    if (!loaded) return;
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(settings)).catch(() => {});
  }, [settings, loaded]);

  // updateSettings({ name }) or updateSettings({ notify: { door: false } }): merges into the settings
  const updateSettings = useCallback((patch) => {
    setSettings((current) => ({
      ...current,
      ...patch,
      notify: { ...current.notify, ...(patch.notify ?? {}) },
    }));
  }, []);

  const value = useMemo(() => ({ settings, loaded, updateSettings }), [settings, loaded, updateSettings]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

// { settings, loaded, updateSettings }
export function useSettings() {
  return useContext(SettingsContext);
}
