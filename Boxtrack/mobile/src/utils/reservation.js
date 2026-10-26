import { isMembershipValidFor } from './format';

// Mismos criterios que el backend; la decisión final siempre la toma la API.
export function reservationState({ training, reservations, settings, memberships, isAthlete }) {
  const own = isAthlete ? reservations.find((r) => r.status === 'RESERVED') : null;
  const full = training.reserved_count >= training.capacity;
  const needsMembership = Boolean(
    isAthlete && settings.require_active_membership && !memberships.some((m) => isMembershipValidFor(m, training.scheduled_date))
  );
  const pending = memberships.some((m) => m.status === 'PENDING');
  let blockedMessage = '';
  if (own) blockedMessage = '';
  else if (needsMembership) {
    blockedMessage = pending
      ? 'Tu membresía está pendiente de pago. Podrás reservar cuando el club la confirme.'
      : 'Tu club exige una membresía activa para reservar clases.';
  } else if (full) blockedMessage = 'Clase llena: no quedan cupos.';
  return { own, full, needsMembership, blockedMessage };
}
