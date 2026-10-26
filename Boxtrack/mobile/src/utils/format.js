const MONEY_FORMATTERS = {};

export function formatMoney(value, currency = 'CLP') {
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  if (!MONEY_FORMATTERS[currency]) {
    try {
      MONEY_FORMATTERS[currency] = new Intl.NumberFormat('es-CL', { style: 'currency', currency, maximumFractionDigits: 0 });
    } catch {
      MONEY_FORMATTERS[currency] = { format: (n) => `$${Math.round(n)}` };
    }
  }
  return MONEY_FORMATTERS[currency].format(amount);
}

// Las fechas del backend son 'YYYY-MM-DD'; se formatean sin pasar por Date para evitar corrimientos de zona horaria.
export function formatDate(value) {
  if (!value) return '—';
  const [year, month, day] = String(value).slice(0, 10).split('-');
  return year && month && day ? `${day}-${month}-${year}` : String(value);
}

export function formatTime(value) {
  return value ? String(value).slice(0, 5) : '';
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function todayISO(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const LABELS = {
  role: { ADMIN: 'Administrador', TRAINER: 'Entrenador', ATHLETE: 'Deportista' },
  training: { SCHEDULED: 'Programada', CANCELLED: 'Cancelada', COMPLETED: 'Completada' },
  reservation: { RESERVED: 'Reservado', CANCELLED: 'Cancelado' },
  membership: {
    PENDING: 'Pendiente de pago', ACTIVE: 'Activa', EXPIRED: 'Vencida', REJECTED: 'Rechazada', CANCELLED: 'Cancelada'
  },
  order: { PENDING: 'Pendiente', PAID: 'Pagada', READY: 'Lista para retirar', COMPLETED: 'Retirada', CANCELLED: 'Cancelada' },
  paymentStatus: {
    PENDING: 'Pendiente', APPROVED: 'Aprobado', REJECTED: 'Rechazado', CANCELLED: 'Cancelado',
    EXPIRED: 'Vencido', REFUNDED: 'Reembolsado', REVIEW: 'En revisión'
  },
  payment: { MERCADO_PAGO: 'Mercado Pago', BANK_TRANSFER: 'Transferencia', RESERVE: 'Reserva para retiro' },
  proof: { NOT_SUBMITTED: 'Sin comprobante', SUBMITTED: 'En revisión', APPROVED: 'Aprobado', REJECTED: 'Rechazado' },
  match: {
    PROPOSED: 'Propuesto', ACCEPTED: 'Confirmado', DECLINED: 'Rechazado', CANCELLED: 'Cancelado', COMPLETED: 'Realizado'
  },
  request: { PENDING: 'Pendiente', APPROVED: 'Aprobada', REJECTED: 'Rechazada' },
  result: { WIN: 'Victoria', LOSS: 'Derrota', DRAW: 'Empate' },
  activity: {
    TECHNICAL: 'Técnica', TACTICAL: 'Táctica', PHYSICAL: 'Acondicionamiento físico', SPARRING: 'Sparring',
    COMPETITION: 'Preparación competitiva'
  },
  fightType: { AMATEUR: 'Amateur', PRO: 'Profesional', SPARRING: 'Sparring' },
  category: {
    GLOVES: 'Guantes', WRAPS: 'Vendas', HEADGEAR: 'Cabezal', MOUTHGUARD: 'Bucal', BOOTS: 'Botas',
    CLOTHING: 'Vestimenta', PROTECTIVE: 'Protección', SUPPLEMENTS: 'Complementos', OTHER: 'Otros'
  }
};

export function label(group, value) {
  return LABELS[group]?.[value] || value || '—';
}

// Tono visual de un estado: ok | warn | bad | info | neutral
const TONES = {
  ACTIVE: 'ok', APPROVED: 'ok', PAID: 'ok', READY: 'ok', COMPLETED: 'ok', ACCEPTED: 'ok', RESERVED: 'ok', SCHEDULED: 'info',
  PENDING: 'warn', SUBMITTED: 'warn', PROPOSED: 'warn', REVIEW: 'warn',
  REJECTED: 'bad', CANCELLED: 'bad', DECLINED: 'bad', EXPIRED: 'bad'
};

export function tone(value) {
  return TONES[value] || 'neutral';
}

// Misma regla que el backend: ACTIVE y la fecha de la clase dentro de [start_date, end_date].
export function isMembershipValidFor(membership, dateISO) {
  if (!membership || membership.status !== 'ACTIVE') return false;
  if (!membership.start_date || !membership.end_date) return false;
  return membership.start_date <= dateISO && dateISO <= membership.end_date;
}

export function isNotificationUnread(item) {
  return item && item.is_read === false;
}
