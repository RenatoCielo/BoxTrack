// El pago pendiente de una membresía; el estado real lo informa siempre el backend.
export function openPaymentFor(payments, membership) {
  if (!membership) return null;
  return (payments || []).find((payment) => payment.membership === membership.id && payment.status === 'PENDING') || null;
}

export function paymentOutcomeMessage(payment) {
  switch (payment?.status) {
    case 'APPROVED': return 'Pago aprobado. Tu membresía ya está activa.';
    case 'REJECTED': return 'El pago fue rechazado. Tu membresía no se activó; puedes intentarlo de nuevo.';
    case 'CANCELLED': return 'El pago fue cancelado. Tu membresía no se activó.';
    case 'EXPIRED': return 'El pago venció sin confirmarse. Puedes iniciar una nueva compra.';
    case 'REVIEW': return 'Recibimos tu pago y el club lo está revisando.';
    case 'REFUNDED': return 'El pago fue reembolsado.';
    default: return 'Tu pago sigue pendiente de confirmación en Mercado Pago.';
  }
}
