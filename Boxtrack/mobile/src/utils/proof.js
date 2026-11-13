import { Platform } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';

export async function buildProofForm(asset) {
  const form = new FormData();
  const name = asset.fileName || `comprobante-${Date.now()}.jpg`;
  const type = asset.mimeType || 'image/jpeg';
  if (Platform.OS === 'web') {
    const blob = await (await fetch(asset.uri)).blob();
    form.append('proof', blob, name);
  } else {
    form.append('proof', { uri: asset.uri, name, type });
  }
  return form;
}

export async function openPrivateProof(blob) {
  if (Platform.OS === 'web') {
    const url = URL.createObjectURL(blob);
    try { window.open(url, '_blank', 'noopener,noreferrer'); }
    finally { setTimeout(() => URL.revokeObjectURL(url), 60000); }
    return;
  }
  if (!await Sharing.isAvailableAsync()) throw new Error('No hay una aplicación disponible para abrir el comprobante.');
  const extensions = { 'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };
  const extension = extensions[blob.type];
  if (!extension) throw new Error('No se puede abrir este tipo de comprobante.');
  const base64 = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('No se pudo leer el comprobante.'));
    reader.readAsDataURL(blob);
  });
  const path = `${FileSystem.cacheDirectory}comprobante-${Date.now()}.${extension}`;
  await FileSystem.writeAsStringAsync(path, base64, { encoding: FileSystem.EncodingType.Base64 });
  try { await Sharing.shareAsync(path, { mimeType: blob.type, dialogTitle: 'Abrir comprobante' }); }
  finally { await FileSystem.deleteAsync(path, { idempotent: true }); }
}
