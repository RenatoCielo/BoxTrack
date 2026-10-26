import { resolveApiUrl } from '../src/config';
import { formatDate, formatMoney, isMembershipValidFor, label, todayISO, tone } from '../src/utils/format';

describe('resolveApiUrl', () => {
  test('usa la variable explícita sin barra final', () => {
    expect(resolveApiUrl({ envUrl: 'https://api.club.cl/api/' })).toBe('https://api.club.cl/api');
  });
  test('deriva la IP de la PC desde el host de Expo (dispositivo físico)', () => {
    expect(resolveApiUrl({ hostUri: '192.168.1.20:8081', platform: 'ios' })).toBe('http://192.168.1.20:8000/api');
  });
  test('emulador Android usa 10.0.2.2', () => {
    expect(resolveApiUrl({ hostUri: 'localhost:8081', platform: 'android' })).toBe('http://10.0.2.2:8000/api');
  });
  test('iOS Simulator y web usan localhost', () => {
    expect(resolveApiUrl({ platform: 'ios' })).toBe('http://localhost:8000/api');
  });
});

describe('utilidades de formato', () => {
  test('formatDate no se corre por zona horaria', () => {
    expect(formatDate('2026-10-27')).toBe('27-10-2026');
    expect(formatDate(null)).toBe('—');
  });
  test('todayISO', () => {
    expect(todayISO(new Date(2026, 9, 5))).toBe('2026-10-05');
  });
  test('formatMoney devuelve un monto legible', () => {
    expect(formatMoney('30000')).toMatch(/30/);
    expect(formatMoney('abc')).toBe('—');
  });
  test('etiquetas y tonos', () => {
    expect(label('membership', 'PENDING')).toBe('Pendiente de pago');
    expect(tone('ACTIVE')).toBe('ok');
    expect(tone('REJECTED')).toBe('bad');
  });
  test('isMembershipValidFor replica la regla del backend', () => {
    const active = { status: 'ACTIVE', start_date: '2026-10-01', end_date: '2026-10-31' };
    expect(isMembershipValidFor(active, '2026-10-27')).toBe(true);
    expect(isMembershipValidFor(active, '2026-11-01')).toBe(false);
    expect(isMembershipValidFor({ ...active, status: 'PENDING' }, '2026-10-27')).toBe(false);
    expect(isMembershipValidFor(null, '2026-10-27')).toBe(false);
  });
});
