import { reservationState } from '../src/utils/reservation';

const training = { id: 1, scheduled_date: '2026-10-27', capacity: 2, reserved_count: 0 };
const active = { status: 'ACTIVE', start_date: '2026-10-01', end_date: '2026-10-31' };

const base = { training, reservations: [], settings: { require_active_membership: false }, memberships: [], isAthlete: true };

describe('reservationState', () => {
  test('con la opción desactivada el deportista sin membresía puede reservar', () => {
    const state = reservationState(base);
    expect(state.needsMembership).toBe(false);
    expect(state.blockedMessage).toBe('');
  });

  test('con la opción activada y sin membresía bloquea y explica', () => {
    const state = reservationState({ ...base, settings: { require_active_membership: true } });
    expect(state.needsMembership).toBe(true);
    expect(state.blockedMessage).toMatch(/exige una membresía activa/);
  });

  test('membresía pendiente muestra el aviso de pago', () => {
    const state = reservationState({ ...base, settings: { require_active_membership: true }, memberships: [{ status: 'PENDING' }] });
    expect(state.blockedMessage).toMatch(/pendiente de pago/);
  });

  test('membresía activa y vigente para la fecha permite reservar', () => {
    const state = reservationState({ ...base, settings: { require_active_membership: true }, memberships: [active] });
    expect(state.needsMembership).toBe(false);
  });

  test('membresía vencida para la fecha de la clase bloquea', () => {
    const late = { ...training, scheduled_date: '2026-11-05' };
    const state = reservationState({ ...base, training: late, settings: { require_active_membership: true }, memberships: [active] });
    expect(state.needsMembership).toBe(true);
  });

  test('clase llena y reserva propia', () => {
    expect(reservationState({ ...base, training: { ...training, reserved_count: 2 } }).full).toBe(true);
    const own = reservationState({ ...base, reservations: [{ id: 9, status: 'RESERVED' }] });
    expect(own.own.id).toBe(9);
  });

  test('el staff nunca queda bloqueado por membresía propia', () => {
    const state = reservationState({ ...base, isAthlete: false, settings: { require_active_membership: true } });
    expect(state.needsMembership).toBe(false);
  });
});
