import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const KEYS = { access: 'boxtrack.access', refresh: 'boxtrack.refresh' };

// En web (solo usado para pruebas de desarrollo) SecureStore no existe.
const webStore = {
  get: async (key) => globalThis.localStorage?.getItem(key) ?? null,
  set: async (key, value) => globalThis.localStorage?.setItem(key, value),
  remove: async (key) => globalThis.localStorage?.removeItem(key)
};

const nativeStore = {
  get: (key) => SecureStore.getItemAsync(key),
  set: (key, value) => SecureStore.setItemAsync(key, value),
  remove: (key) => SecureStore.deleteItemAsync(key)
};

const store = Platform.OS === 'web' ? webStore : nativeStore;

export const tokenStorage = {
  getAccess: () => store.get(KEYS.access),
  getRefresh: () => store.get(KEYS.refresh),
  async save({ access, refresh }) {
    if (access) await store.set(KEYS.access, access);
    if (refresh) await store.set(KEYS.refresh, refresh);
  },
  async clear() {
    await store.remove(KEYS.access);
    await store.remove(KEYS.refresh);
  }
};
