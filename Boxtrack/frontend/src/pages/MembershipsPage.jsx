import { useEffect, useState } from 'react';
import { Check, CreditCard, Pencil, Plus, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const statusLabels = { PENDING: 'Pendiente de pago', ACTIVE: 'Activa', SCHEDULED: 'Renovación programada', EXPIRED: 'Vencida', REJECTED: 'Rechazada', CANCELLED: 'Cancelada' };
const paymentLabels = { PENDING: 'Pendiente', APPROVED: 'Aprobado', REJECTED: 'Rechazado', CANCELLED: 'Cancelado', EXPIRED: 'Vencido', REFUNDED: 'Reembolsado', REVIEW: 'En revisión' };
const returnNotices = {
  success: 'Volviste de Mercado Pago. Tu membresía se activará cuando el pago sea confirmado; puede tardar unos segundos.',
  pending: 'Tu pago está pendiente en Mercado Pago. La membresía se activará cuando se confirme.',
  failure: 'El pago no se completó. Tu membresía no fue activada; puedes intentarlo nuevamente.'
};
const money = (value, currency = 'CLP') => new Intl.NumberFormat('es-CL', { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(value));
const dateLabel = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('es-CL') : '—');

function PlanDialog({ plan, onClose, onSave, busy, error }) {
  const [values, setValues] = useState({ name: '', description: '', price: '', currency: 'CLP', duration_days: 30, benefits: '', weekly_class_limit: '', is_active: true, ...plan });
  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  return <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="plan-dialog-title">
      <header className="dialog-heading"><div><p className="eyebrow">PLANES DEL CLUB</p><h2 id="plan-dialog-title">{plan?.id ? 'Editar plan' : 'Crear plan'}</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
      <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSave({ ...values, price: values.price, duration_days: Number(values.duration_days), weekly_class_limit: values.weekly_class_limit === '' || values.weekly_class_limit === null ? null : Number(values.weekly_class_limit) }); }}>
        <div className="field-grid">
          <label className="field-label"><span>Nombre *</span><input className="control" name="name" required value={values.name} onChange={update} /></label>
          <label className="field-label"><span>Precio (CLP) *</span><input className="control" type="number" min="1" step="1" name="price" required value={values.price} onChange={update} /></label>
          <label className="field-label"><span>Duración (días) *</span><input className="control" type="number" min="1" name="duration_days" required value={values.duration_days} onChange={update} /></label>
          <label className="field-label"><span>Clases por semana</span><input className="control" type="number" min="1" name="weekly_class_limit" placeholder="Sin límite" value={values.weekly_class_limit ?? ''} onChange={update} /></label>
          <label className="field-label field-wide"><span>Descripción</span><textarea className="control" name="description" rows="2" value={values.description} onChange={update} /></label>
          <label className="field-label field-wide"><span>Beneficios incluidos</span><textarea className="control" name="benefits" rows="3" value={values.benefits} onChange={update} /></label>
          <label className="checkbox-control"><input type="checkbox" checked={Boolean(values.is_active)} onChange={(event) => setValues({ ...values, is_active: event.target.checked })} /><span>Disponible para nuevos deportistas</span></label>
        </div>
        {error && <div className="notice notice-error">{error}</div>}
        <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy}>{busy ? 'Guardando...' : 'Guardar plan'}</button></footer>
      </form>
    </section>
  </div>;
}

export function MembershipsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const [plans, setPlans] = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [editor, setEditor] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  const [requireMembership, setRequireMembership] = useState(false);
  const [payments, setPayments] = useState([]);
  const [onlineAvailable, setOnlineAvailable] = useState(false);
  const [renewal, setRenewal] = useState(null);
  const returnedFrom = new URLSearchParams(window.location.search).get('payment');

  const load = async () => {
    setError('');
    try {
      const [planRows, membershipRows, settingsRow, paymentRows, renewalRow] = await Promise.all([
        readCollection('/memberships/plans/'),
        api.get('/memberships/').then((response) => response.data),
        api.get('/memberships/settings/').then((response) => response.data),
        api.get('/memberships/payments/').then((response) => response.data).catch(() => []),
        isAdmin ? Promise.resolve(null) : api.get('/memberships/renewal/').then((response) => response.data).catch(() => null)
      ]);
      setPlans(planRows);
      setMemberships(membershipRows);
      setPayments(paymentRows);
      setRenewal(renewalRow);
      setOnlineAvailable(Boolean(settingsRow.mercado_pago_available));
      setRequireMembership(Boolean(settingsRow.require_active_membership));
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (returnedFrom && returnNotices[returnedFrom]) setNotice(returnNotices[returnedFrom]); }, [returnedFrom]);

  // El estado solo cambia cuando el backend recibe la confirmación verificada de Mercado Pago.
  const hasOpenOnlinePayment = payments.some((item) => item.status === 'PENDING');
  useEffect(() => {
    if (!returnedFrom || !hasOpenOnlinePayment) return undefined;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [returnedFrom, hasOpenOnlinePayment]);

  const saveRequirement = async (value) => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.patch('/memberships/settings/', { require_active_membership: value });
      setRequireMembership(data.require_active_membership);
      setNotice(data.require_active_membership ? 'Ahora se exige membresía activa para reservar clases.' : 'Ya no se exige membresía para reservar clases.');
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const activeMembership = memberships.find((item) => item.status === 'ACTIVE');
  const pendingMembership = memberships.find((item) => item.status === 'PENDING');
  const scheduledMembership = memberships.find((item) => item.status === 'SCHEDULED');
  const openMembership = activeMembership || pendingMembership;
  const openPayment = payments.find((item) => item.status === 'PENDING' && item.membership === pendingMembership?.id);
  const canRenew = Boolean(renewal?.can_renew);
  const hasCurrentPlan = Boolean(openMembership || scheduledMembership);

  const savePlan = async (values) => {
    setBusy(true);
    setFormError('');
    try {
      if (editor?.id) await api.patch(`/memberships/plans/${editor.id}/`, values);
      else await api.post('/memberships/plans/', values);
      setEditor(null);
      setNotice('Plan guardado.');
      await load();
    } catch (requestError) { setFormError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const requestPlan = async (plan) => {
    setBusy(true);
    setError('');
    try {
      await api.post('/memberships/', { plan: plan.id });
      setNotice('Solicitud enviada. Tu membresía se activará cuando el club confirme tu pago.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const payOnline = async (plan) => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/memberships/payments/', { plan: plan.id });
      if (data.checkout_url) window.location.assign(data.checkout_url);
      else await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); await load(); }
    finally { setBusy(false); }
  };

  const renew = async (method, plan) => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/memberships/renewal/', { method, ...(plan ? { plan: plan.id } : {}) });
      if (method === 'ONLINE' && data.payment?.checkout_url) { window.location.assign(data.payment.checkout_url); return; }
      setNotice(method === 'ONLINE' ? 'Renovación iniciada. Se confirmará cuando Mercado Pago apruebe el pago.' : 'Renovación solicitada. Se aplicará cuando el club confirme tu pago.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); await load(); }
    finally { setBusy(false); }
  };

  const cancelPayment = async (payment) => {
    if (!window.confirm('¿Cancelar este pago pendiente?')) return;
    setBusy(true);
    setError('');
    try {
      await api.delete(`/memberships/payments/${payment.id}/`);
      setNotice('Pago cancelado.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const review = async (membership, decision) => {
    let note = '';
    if (decision === 'REJECT') {
      note = window.prompt('Indica el motivo del rechazo:') || '';
      if (!note.trim()) return;
    }
    if (decision === 'CANCEL' && !window.confirm('¿Cancelar esta membresía?')) return;
    setBusy(true);
    setError('');
    try {
      await api.post(`/memberships/${membership.id}/review/`, { decision, note });
      setNotice(decision === 'CONFIRM' ? 'Pago confirmado y membresía activada.' : decision === 'REJECT' ? 'Solicitud rechazada.' : 'Membresía cancelada.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const pending = memberships.filter((item) => item.status === 'PENDING');

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">PLANES Y PAGOS</p><h1>Membresías</h1><p className="page-description">{isAdmin ? 'Crea los planes de tu club y confirma los pagos de los deportistas.' : 'Revisa los planes de tu club y el estado de tu membresía.'}</p></div>{isAdmin && <button className="button primary-btn" onClick={() => { setEditor({}); setFormError(''); }}><Plus size={16} /> Crear plan</button>}</header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}
    {loading ? <div className="empty-state">Cargando membresías...</div> : <>
      {isAdmin && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">REGLAS DE RESERVA</p><h2>Exigir membresía activa para reservar clases</h2></div></div>
        <label className="field-label"><span>Estado de la regla</span><select className="control" value={requireMembership ? 'on' : 'off'} disabled={busy} onChange={(event) => saveRequirement(event.target.value === 'on')}><option value="off">Desactivado</option><option value="on">Activado</option></select></label>
        <p className="page-description">{requireMembership ? 'Solo los deportistas con una membresía activa y vigente en la fecha de la clase pueden reservar.' : 'Cualquier deportista activo puede reservar, tenga o no membresía.'}</p>
      </section>}      {!isAdmin && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">MI MEMBRESÍA</p><h2>{openMembership ? openMembership.plan_name : 'Sin membresía activa'}</h2></div>{openMembership && <span className="status-pill">{statusLabels[openMembership.status]}</span>}</div>
        {openMembership ? <p className="page-description">{openMembership.status === 'PENDING' ? (openPayment ? 'Esperando la confirmación del pago de Mercado Pago.' : 'Esperando que el club confirme tu pago.') : `Vigente del ${dateLabel(openMembership.start_date)} al ${dateLabel(openMembership.end_date)}.`}</p> : <p className="page-description">{memberships[0] ? `Tu última membresía quedó ${statusLabels[memberships[0].status].toLowerCase()}${memberships[0].review_note ? `: ${memberships[0].review_note}` : '.'}` : 'Elige un plan para comenzar.'}</p>}
        {openPayment?.checkout_url && <a className="button primary-btn" href={openPayment.checkout_url}><CreditCard size={15} /> Continuar pago</a>}
        {openPayment && <button className="button button-secondary" disabled={busy} onClick={load}>Actualizar estado</button>}
        {openPayment && <button className="button button-secondary" disabled={busy} onClick={() => cancelPayment(openPayment)}>Cancelar pago</button>}
        {pendingMembership && !openPayment && <button className="button button-secondary" disabled={busy} onClick={() => review(pendingMembership, 'CANCEL')}>Cancelar solicitud</button>}
        {activeMembership && pendingMembership && <p className="page-description">{pendingMembership.is_renewal ? 'Renovación' : 'Compra'} pendiente de pago: {pendingMembership.plan_name}. Tu membresía actual sigue vigente hasta el {dateLabel(activeMembership.end_date)}.</p>}
        {scheduledMembership && <p className="page-description">Renovación programada: {scheduledMembership.plan_name}, del {dateLabel(scheduledMembership.start_date)} al {dateLabel(scheduledMembership.end_date)}.</p>}
        {canRenew && !pendingMembership && <div className="renewal-box">
          <p className="page-description">{renewal.state === 'EXPIRED' ? `Tu membresía venció el ${dateLabel(renewal.end_date)}. Si renuevas, comenzará el día en que se confirme el pago.` : `Tu membresía vence el ${dateLabel(renewal.end_date)} (${renewal.days_left === 0 ? 'hoy' : `en ${renewal.days_left} día${renewal.days_left === 1 ? '' : 's'}`}). Si renuevas ahora, la nueva comienza el ${dateLabel(renewal.next_start_date)} y no pierdes días.`}</p>
          {renewal.plan ? <div className="training-actions">
            {onlineAvailable && <button className="button primary-btn" disabled={busy} onClick={() => renew('ONLINE')}><CreditCard size={15} /> Renovar {renewal.plan.name} con Mercado Pago</button>}
            <button className={onlineAvailable ? 'button button-secondary' : 'button primary-btn'} disabled={busy} onClick={() => renew('MANUAL')}>{onlineAvailable ? 'Renovar y pagar al club' : `Renovar ${renewal.plan.name}`}</button>
          </div> : <p className="page-description">Tu plan anterior ya no está disponible. Elige otro plan abajo para renovar.</p>}
        </div>}
        {!canRenew && renewal?.reason && !pendingMembership && !scheduledMembership && renewal.state === 'ACTIVE' && <p className="page-description">{renewal.reason}</p>}
      </section>}
      <div className="training-grid">{plans.map((plan) => <article className="training-card" key={plan.id}>
        <div className="training-card-top"><span className="activity-tag">{plan.duration_days} días</span>{isAdmin && <button className="icon-button table-action" title="Editar plan" aria-label="Editar plan" onClick={() => { setEditor(plan); setFormError(''); }}><Pencil size={15} /></button>}</div>
        <h2>{plan.name}</h2>
        <p className="training-description">{plan.description || plan.benefits || 'Plan del club.'}</p>
        <div className="training-meta"><span><CreditCard size={15} />{money(plan.price, plan.currency)}</span><span>{plan.weekly_class_limit ? `${plan.weekly_class_limit} clases/semana` : 'Clases sin límite'}</span>{isAdmin && <span>{plan.active_members} activos{plan.is_active ? '' : ' · Inactivo'}</span>}</div>
        {plan.benefits && plan.description && <p className="training-description">{plan.benefits}</p>}
        {!isAdmin && <div className="training-actions">
          {canRenew && !pendingMembership ? <>
            {onlineAvailable && <button className="button primary-btn" disabled={busy} onClick={() => renew('ONLINE', plan)}><CreditCard size={15} /> Renovar con este plan (Mercado Pago)</button>}
            <button className={onlineAvailable ? 'button button-secondary' : 'button primary-btn'} disabled={busy} onClick={() => renew('MANUAL', plan)}>{onlineAvailable ? 'Renovar y pagar al club' : 'Renovar con este plan'}</button>
          </> : <>
            {onlineAvailable && <button className="button primary-btn" disabled={busy || hasCurrentPlan} onClick={() => payOnline(plan)}><CreditCard size={15} /> Pagar con Mercado Pago</button>}
            <button className={onlineAvailable ? 'button button-secondary' : 'button primary-btn'} disabled={busy || hasCurrentPlan} onClick={() => requestPlan(plan)}>{hasCurrentPlan ? 'Ya tienes un plan' : onlineAvailable ? 'Solicitar y pagar al club' : 'Solicitar plan'}</button>
          </>}
        </div>}
      </article>)}{!plans.length && <div className="surface-panel empty-state">{isAdmin ? 'Aún no creas planes. Crea el primero para que tus deportistas puedan contratarlo.' : 'Tu club todavía no publica planes.'}</div>}</div>
      <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">{isAdmin ? 'PAGOS Y VENCIMIENTOS' : 'HISTORIAL'}</p><h2>{isAdmin ? `Membresías (${pending.length} por confirmar)` : 'Mis membresías'}</h2></div></div>
        <div className="closed-training-list">{memberships.map((item) => <div key={item.id}>
          <span>{isAdmin ? `${item.athlete_name} · ` : ''}{item.plan_name}{item.is_renewal ? ' (renovación)' : ''} · {money(item.price_paid, item.currency)}</span>
          <span>{item.end_date ? `${item.status === 'SCHEDULED' ? `Desde ${dateLabel(item.start_date)} hasta` : 'Hasta'} ${dateLabel(item.end_date)}` : dateLabel(item.created_at?.slice(0, 10))}</span>
          <span className="status-pill">{statusLabels[item.status]}</span>
          {isAdmin && item.status === 'PENDING' && <><button className="button primary-btn" disabled={busy} onClick={() => review(item, 'CONFIRM')}><Check size={15} /> Confirmar pago</button><button className="button button-secondary" disabled={busy} onClick={() => review(item, 'REJECT')}>Rechazar</button></>}
          {isAdmin && ['ACTIVE', 'SCHEDULED'].includes(item.status) && <button className="button button-secondary" disabled={busy} onClick={() => review(item, 'CANCEL')}>Cancelar</button>}
        </div>)}{!memberships.length && <div className="empty-state">Todavía no hay membresías.</div>}</div>
      </section>
      {payments.length > 0 && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">MERCADO PAGO</p><h2>Pagos online</h2></div></div>
        <div className="closed-training-list">{payments.map((item) => <div key={item.id}>
          <span>{isAdmin ? `${item.athlete_name} · ` : ''}{item.plan_name}{item.is_renewal ? ' (renovación)' : ''} · {money(item.amount, item.currency)}</span>
          <span>{dateLabel(item.created_at?.slice(0, 10))}</span>
          <span className="status-pill">{paymentLabels[item.status] || item.status}</span>
        </div>)}</div>
      </section>}
    </>}
    {editor && <PlanDialog plan={editor.id ? editor : undefined} onClose={() => setEditor(null)} onSave={savePlan} busy={busy} error={formError} />}
  </section>;
}
