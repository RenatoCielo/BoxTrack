import { openPaymentFor, paymentOutcomeMessage } from '../src/utils/payment';
import { label, tone } from '../src/utils/format';

describe('pagos de membresía', () => {
  const membership = { id: 7 };

  test('encuentra solo el pago pendiente de la membresía indicada', () => {
    const payments = [
      { id: 1, membership: 6, status: 'PENDING' },
      { id: 2, membership: 7, status: 'REJECTED' },
      { id: 3, membership: 7, status: 'PENDING' }
    ];
    expect(openPaymentFor(payments, membership).id).toBe(3);
    expect(openPaymentFor(payments, { id: 99 })).toBeNull();
    expect(openPaymentFor(undefined, membership)).toBeNull();
    expect(openPaymentFor(payments, null)).toBeNull();
  });

  test('los mensajes no afirman aprobación salvo estado APPROVED del backend', () => {
    expect(paymentOutcomeMessage({ status: 'APPROVED' })).toMatch(/aprobado/i);
    for (const status of ['PENDING', 'REJECTED', 'CANCELLED', 'EXPIRED']) {
      expect(paymentOutcomeMessage({ status })).not.toMatch(/ya está activa/i);
    }
    expect(paymentOutcomeMessage(undefined)).toMatch(/pendiente/i);
  });

  test('etiquetas y tonos de estado', () => {
    expect(label('paymentStatus', 'REFUNDED')).toBe('Reembolsado');
    expect(tone('APPROVED')).toBe('ok');
    expect(tone('REJECTED')).toBe('bad');
    expect(tone('PENDING')).toBe('warn');
  });
});
