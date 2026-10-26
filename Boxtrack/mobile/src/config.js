import { Platform } from 'react-native';
import Constants from 'expo-constants';

const API_PORT = 8000;

// Orden: variable explícita -> host del servidor de desarrollo de Expo (IP de la PC en la red local)
// -> alias del emulador Android -> localhost (iOS Simulator / web).
export function resolveApiUrl({ envUrl, hostUri, platform } = {}) {
  const explicit = (envUrl || '').trim();
  if (explicit) return explicit.replace(/\/+$/, '');

  const host = (hostUri || '').split(':')[0];
  if (host && host !== 'localhost' && host !== '127.0.0.1') return `http://${host}:${API_PORT}/api`;

  if (platform === 'android') return `http://10.0.2.2:${API_PORT}/api`;
  return `http://localhost:${API_PORT}/api`;
}

export const API_URL = resolveApiUrl({
  envUrl: process.env.EXPO_PUBLIC_API_URL,
  hostUri: Constants.expoConfig?.hostUri,
  platform: Platform.OS
});

// Origen del backend (sin /api) para resolver archivos servidos por Django.
export const API_ORIGIN = API_URL.replace(/\/api$/, '');
