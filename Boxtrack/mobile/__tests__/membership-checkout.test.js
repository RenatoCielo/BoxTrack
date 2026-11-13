import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
import * as WebBrowser from 'expo-web-browser';
import MembershipsScreen from '../src/screens/MembershipsScreen';
import { api } from '../src/api';
import { useResource } from '../src/hooks/useResource';
import * as ImagePicker from 'expo-image-picker';
import { useAuth } from '../src/auth/AuthContext';

jest.mock('../src/auth/AuthContext', () => ({ useAuth: jest.fn() }));
jest.mock('../src/api', () => ({ api: { post: jest.fn(), patch: jest.fn(), del: jest.fn() } }));
jest.mock('../src/hooks/useResource', () => ({ useResource: jest.fn(), useRefreshOnFocus: jest.fn() }));
jest.mock('expo-web-browser', () => ({ openBrowserAsync: jest.fn() }));
jest.mock('expo-image-picker', () => ({ requestMediaLibraryPermissionsAsync: jest.fn(), launchImageLibraryAsync: jest.fn() }));
jest.mock('@expo/vector-icons', () => ({ Ionicons: () => null }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = require('react-native');
  return { SafeAreaView: View };
});

const plan = { id: 4, name: 'Mensual', price: '30000', currency: 'CLP', duration_days: 30, is_active: true };

function setup({ settings = {}, renewal = null, memberships = [], payments = [] } = {}) {
  const refresh = jest.fn().mockResolvedValue(undefined);
  useResource.mockReturnValue({
    data: { plans: [plan], memberships, settings, payments, renewal },
    loading: false, error: '', refreshing: false, refresh,
  });
  return refresh;
}

beforeEach(() => {
  jest.clearAllMocks();
  useAuth.mockReturnValue({ user: { id: 1, role: 'ATHLETE' } });
  WebBrowser.openBrowserAsync.mockResolvedValue({ type: 'dismiss' });
});

test('explica el pago no configurado y permite solicitar el pago manual', async () => {
  setup();
  api.post.mockResolvedValue({});
  const screen = await render(<MembershipsScreen />);
  await fireEvent.press(screen.getByText('Elegir método de pago'));
  expect(screen.getByText(/pago online no está configurado/)).toBeTruthy();
  expect(screen.getByText(/Mercado Pago \(no configurado\)/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Continuar'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/', { plan: 4, payment_method: 'MANUAL' }));
  expect(WebBrowser.openBrowserAsync).not.toHaveBeenCalled();
});

test('abre el checkout del proveedor y consulta el estado sin aprobar el pago', async () => {
  const refresh = setup({ settings: { mercado_pago_available: true, transbank_available: true } });
  api.post.mockResolvedValue({ checkout_url: 'https://payment.test/checkout' });
  const screen = await render(<MembershipsScreen />);
  await fireEvent.press(screen.getByText('Elegir método de pago'));
  await fireEvent.press(screen.getByText(/Transbank Webpay Plus$/));
  await fireEvent.press(screen.getByText('Continuar'));
  await waitFor(() => expect(WebBrowser.openBrowserAsync).toHaveBeenCalledWith('https://payment.test/checkout'));
  expect(api.post).toHaveBeenCalledWith('/memberships/payments/', { plan: 4, provider: 'TRANSBANK' });
  await waitFor(() => expect(refresh).toHaveBeenCalled());
});

test('renueva con el proveedor elegido y muestra un error si no recibe enlace', async () => {
  setup({ settings: { mercado_pago_available: true }, renewal: { can_renew: true, state: 'EXPIRED', plan } });
  api.post.mockResolvedValue({ payment: {} });
  const screen = await render(<MembershipsScreen />);
  await fireEvent.press(screen.getAllByText('Elegir cómo renovar')[0]);
  await fireEvent.press(screen.getByText(/Mercado Pago$/));
  await fireEvent.press(screen.getByText('Continuar'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/renewal/', { plan: 4, method: 'ONLINE', provider: 'MERCADO_PAGO' }));
  expect(await screen.findByText(/No se recibió un enlace de pago/)).toBeTruthy();
  expect(WebBrowser.openBrowserAsync).not.toHaveBeenCalled();
});

test('una solicitud manual pendiente explica cómo cambiar de método y no crea otro pago', async () => {
  setup({
    settings: { mercado_pago_available: true },
    memberships: [{ id: 8, status: 'PENDING', plan_name: 'Mensual', price_paid: '30000', currency: 'CLP' }],
  });
  api.post.mockResolvedValue({});
  const screen = await render(<MembershipsScreen />);
  expect(screen.getByText(/Para elegir otro método, cancela esta solicitud/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Cancelar solicitud'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/8/review/', { decision: 'CANCEL' }));
  expect(WebBrowser.openBrowserAsync).not.toHaveBeenCalled();
});

test('muestra la cuenta del club y solicita transferencia sin activar la membresía', async () => {
  setup({ settings: { bank_transfer_instructions: 'Banco de prueba, cuenta 123' } });
  api.post.mockResolvedValue({});
  const screen = await render(<MembershipsScreen />);
  await fireEvent.press(screen.getByText('Elegir método de pago'));
  expect(screen.getByText('Banco de prueba, cuenta 123')).toBeTruthy();
  await fireEvent.press(screen.getByText('Continuar'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/', { plan: 4, payment_method: 'BANK_TRANSFER' }));
  expect(WebBrowser.openBrowserAsync).not.toHaveBeenCalled();
});

test('una transferencia pendiente permite enviar imagen sin aprobar la membresía', async () => {
  setup({
    settings: { bank_transfer_instructions: 'Banco de prueba' },
    memberships: [{ id: 8, status: 'PENDING', payment_method: 'BANK_TRANSFER', plan_name: 'Mensual', price_paid: '30000', currency: 'CLP' }],
  });

  ImagePicker.requestMediaLibraryPermissionsAsync.mockResolvedValue({ granted: true });
  ImagePicker.launchImageLibraryAsync.mockResolvedValue({ canceled: false, assets: [{ uri: 'file://proof.jpg', fileName: 'proof.jpg', mimeType: 'image/jpeg' }] });
  api.post.mockResolvedValue({});
  const screen = await render(<MembershipsScreen />);
  expect(screen.getByText(/Banco de prueba/)).toBeTruthy();
  await fireEvent.press(screen.getByText('Adjuntar comprobante'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/8/proof/', expect.any(FormData)));
  expect(WebBrowser.openBrowserAsync).not.toHaveBeenCalled();
});

test('el administrador revisa el comprobante y actualiza los datos comunes del club', async () => {
  const setData = jest.fn();
  setup({
    settings: { bank_transfer_instructions: 'Cuenta antigua' },
    memberships: [{ id: 8, status: 'PENDING', payment_method: 'BANK_TRANSFER', plan_name: 'Mensual', price_paid: '30000', currency: 'CLP', transfer_proof: { status: 'SUBMITTED' } }],
  });
  useResource.mockReturnValue({ ...useResource(), setData });
  useAuth.mockReturnValue({ user: { id: 2, role: 'ADMIN' } });
  api.post.mockResolvedValue({});
  api.patch.mockResolvedValue({ bank_transfer_instructions: 'Cuenta nueva' });
  const screen = await render(<MembershipsScreen />);
  await fireEvent.changeText(screen.getByLabelText('Instrucciones para transferir'), 'Cuenta nueva');
  await fireEvent.press(screen.getByText('Guardar datos de transferencia'));
  await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/store/checkout-config/', { bank_transfer_instructions: 'Cuenta nueva' }));
  expect(setData).toHaveBeenCalled();
  await fireEvent.press(screen.getByText('Aprobar comprobante'));
  await waitFor(() => expect(api.post).toHaveBeenCalledWith('/memberships/8/proof/review/', { decision: 'APPROVE', note: '' }));
});
