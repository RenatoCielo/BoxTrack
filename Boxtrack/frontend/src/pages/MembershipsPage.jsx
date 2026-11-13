import { useEffect, useRef, useState } from 'react';
import { Check, CreditCard, Download, Pencil, Plus, RefreshCw, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';
import { fetchMembershipSections } from '../services/membershipData';

const statusLabels = { PENDING: 'Pendiente de pago', ACTIVE: 'Activa', SCHEDULED: 'Renovación programada', EXPIRED: 'Vencida', REJECTED: 'Rechazada', CANCELLED: 'Cancelada' };
const paymentLabels = { PENDING: 'Pendiente', APPROVED: 'Aprobado', REJECTED: 'Rechazado', CANCELLED: 'Cancelado', EXPIRED: 'Vencido', REFUNDED: 'Reembolsado', REVIEW: 'En revisión' };
const returnNotices = {
  success: 'Volviste del proveedor de pago. Tu membresía se activa cuando el backend confirma la transacción.',
  pending: 'El proveedor aún no confirmó el pago. La membresía se activará cuando llegue la confirmación.',
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

function AssignMembershipDialog({ athletes, plans, onClose, onSave, busy, error }) {
  const [athlete, setAthlete] = useState('');
  const [plan, setPlan] = useState('');
  return <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="membership-dialog-title">
      <header className="dialog-heading"><div><p className="eyebrow">MEMBRESÍAS DEL CLUB</p><h2 id="membership-dialog-title">Asignar membresía</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
      <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSave({ athlete: Number(athlete), plan: Number(plan) }); }}>
        <div className="field-grid">
          <label className="field-label field-wide"><span>Deportista con cuenta vinculada *</span><select className="control" required value={athlete} onChange={(event) => setAthlete(event.target.value)}><option value="">Selecciona...</option>{athletes.filter((row) => row.status === 'ACTIVE' && row.user).map((row) => <option key={row.id} value={row.id}>{row.display_name || `${row.first_name} ${row.last_name}`}</option>)}</select></label>
          <label className="field-label field-wide"><span>Plan *</span><select className="control" required value={plan} onChange={(event) => setPlan(event.target.value)}><option value="">Selecciona...</option>{plans.filter((row) => row.is_active).map((row) => <option key={row.id} value={row.id}>{row.name} · {money(row.price, row.currency)}</option>)}</select></label>
        </div>
        {!athletes.some((row) => row.status === 'ACTIVE' && row.user) && <p className="page-description">No hay deportistas activos con cuenta vinculada. Vincula una cuenta en la ficha del deportista antes de asignar una membresía.</p>}
        {error && <div className="notice notice-error">{error}</div>}
        <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy || !athlete || !plan}>{busy ? 'Guardando...' : 'Asignar membresía'}</button></footer>
      </form>
    </section>
  </div>;
}

export function PaymentDialog({ plan, renewal, onlineAvailable, transbankAvailable, bankInstructions = '', onClose, onChoose }) {
  const [method, setMethod] = useState(bankInstructions.trim() ? 'BANK_TRANSFER' : 'MANUAL');
  return <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="payment-dialog-title">
      <header className="dialog-heading"><div><p className="eyebrow">MEMBRESÍAS</p><h2 id="payment-dialog-title">Elige cómo pagar</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
      <p className="page-description">{renewal ? 'Renovación' : 'Plan'}: {plan.name} · {money(plan.price, plan.currency)} · {plan.duration_days} días</p>
      <p className="page-description">El pago online se completa en el proveedor. La membresía se activa solo cuando el pago se confirma.</p>
      <div className="resource-form">
        <label className="checkbox-control"><input type="radio" name="membership-payment" value="BANK_TRANSFER" checked={method === 'BANK_TRANSFER'} disabled={!bankInstructions.trim()} onChange={(event) => setMethod(event.target.value)} /><span>Transferencia bancaria{bankInstructions.trim() ? '' : ' (datos no configurados)'}</span></label>
        <label className="checkbox-control"><input type="radio" name="membership-payment" value="MANUAL" checked={method === 'MANUAL'} onChange={(event) => setMethod(event.target.value)} /><span>Pagar directamente al club</span></label>
        <label className="checkbox-control"><input type="radio" name="membership-payment" value="MERCADO_PAGO" checked={method === 'MERCADO_PAGO'} disabled={!onlineAvailable} onChange={(event) => setMethod(event.target.value)} /><span>Mercado Pago{onlineAvailable ? '' : ' (no configurado)'}</span></label>
        <label className="checkbox-control"><input type="radio" name="membership-payment" value="TRANSBANK" checked={method === 'TRANSBANK'} disabled={!transbankAvailable} onChange={(event) => setMethod(event.target.value)} /><span>Transbank Webpay Plus{transbankAvailable ? '' : ' (no configurado para pruebas)'}</span></label>
      </div>
      {method === 'BANK_TRANSFER' && <div className="bank-transfer-details"><strong>Datos para transferir</strong><p>{bankInstructions}</p><small>Después de solicitar el plan, envía el comprobante para que el club lo revise.</small></div>}
      {!onlineAvailable && !transbankAvailable && <p className="page-description">El pago online no está configurado en el servidor.</p>}
      <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Volver</button><button type="button" className="button primary-btn" onClick={() => onChoose(method)}>Continuar</button></footer>
    </section>
  </div>;
}

export function MembershipsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const isTrainer = user?.role === 'TRAINER';
  const [plans, setPlans] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [editor, setEditor] = useState(null);
  const [membershipEditor, setMembershipEditor] = useState(false);
  const [paymentChoice, setPaymentChoice] = useState(null);
  const [assignmentError, setAssignmentError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [plansError, setPlansError] = useState('');
  const [detailsError, setDetailsError] = useState('');
  const [detailsReady, setDetailsReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const loadSequence = useRef(0);
  const loadInFlight = useRef(false);
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  const [requireMembership, setRequireMembership] = useState(false);
  const [payments, setPayments] = useState([]);
  const [onlineAvailable, setOnlineAvailable] = useState(false);
  const [transbankAvailable, setTransbankAvailable] = useState(false);
  const [bankInstructions, setBankInstructions] = useState('');
  const [proofFiles, setProofFiles] = useState({});
  const [renewal, setRenewal] = useState(null);
  const returnedFrom = new URLSearchParams(window.location.search).get('payment');

  const load = async () => {
    const sequence = ++loadSequence.current;
    loadInFlight.current = true;
    setRefreshing(true);
    const [planResult, detailsResult] = await fetchMembershipSections({
      role: user?.role,
      get: (path) => api.get(path).then((response) => response.data),
      readCollection,
    });
    if (sequence !== loadSequence.current) return;
    loadInFlight.current = false;
    if (planResult.status === 'fulfilled') {
      setPlans(planResult.value);
      setPlansError('');
    } else {
      setPlansError(`No se pudieron cargar los planes: ${getErrorMessage(planResult.reason)}`);
    }
    if (detailsResult.status === 'fulfilled') {
      const [membershipRows, settingsRow, paymentRows, renewalRow, athleteRows] = detailsResult.value;
      setAthletes(athleteRows);
      setMemberships(membershipRows);
      setPayments(paymentRows);
      setRenewal(renewalRow);
      setOnlineAvailable(Boolean(settingsRow.mercado_pago_available));
      setTransbankAvailable(Boolean(settingsRow.transbank_available));
      setBankInstructions(settingsRow.bank_transfer_instructions || '');
      setRequireMembership(Boolean(settingsRow.require_active_membership));
      setDetailsError('');
      setDetailsReady(true);
    } else {
      setDetailsReady(false);
      setDetailsError(`No se pudo cargar el estado de membresías y pagos: ${getErrorMessage(detailsResult.reason)}`);
    }
    setLoading(false);
    setRefreshing(false);
  };
  useEffect(() => {
    setLoading(true);
    setPlans([]);
    setDetailsReady(false);
    load();
    const refresh = () => { if (document.visibilityState === 'visible' && !loadInFlight.current) load(); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      loadSequence.current += 1;
      loadInFlight.current = false;
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [user?.id, user?.role]);
  useEffect(() => { if (returnedFrom && returnNotices[returnedFrom]) setNotice(returnNotices[returnedFrom]); }, [returnedFrom]);

  const hasOpenOnlinePayment = payments.some((item) => item.status === 'PENDING');
  useEffect(() => {
    const interval = returnedFrom && hasOpenOnlinePayment ? 5000 : 15000;
    const timer = setInterval(() => { if (document.visibilityState === 'visible' && !loadInFlight.current) load(); }, interval);
    return () => clearInterval(timer);
  }, [returnedFrom, hasOpenOnlinePayment, user?.id, user?.role]);

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

  const assignMembership = async (values) => {
    setBusy(true);
    setAssignmentError('');
    try {
      await api.post('/memberships/', values);
      setMembershipEditor(false);
      setNotice('Membresía asignada. El deportista ya puede verla en su cuenta.');
      await load();
    } catch (requestError) { setAssignmentError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const requestPlan = async (plan, paymentMethod = 'MANUAL') => {
    setBusy(true);
    setError('');
    try {
      await api.post('/memberships/', { plan: plan.id, payment_method: paymentMethod });
      setNotice(paymentMethod === 'BANK_TRANSFER' ? 'Solicitud enviada. Adjunta tu comprobante de transferencia.' : 'Solicitud enviada. Tu membresía se activará cuando el club confirme tu pago.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const payOnline = async (plan, provider = 'MERCADO_PAGO') => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/memberships/payments/', { plan: plan.id, provider });
      if (data.checkout_url) window.location.assign(data.checkout_url);
      else { setError('No se recibió un enlace de pago. Actualiza el estado antes de volver a intentarlo.'); await load(); }
    } catch (requestError) { setError(getErrorMessage(requestError)); await load(); }
    finally { setBusy(false); }
  };

  const renew = async (method, plan, provider = 'MERCADO_PAGO', paymentMethod = 'MANUAL') => {
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/memberships/renewal/', { method, ...(plan ? { plan: plan.id } : {}), ...(method === 'ONLINE' ? { provider } : { payment_method: paymentMethod }) });
      if (method === 'ONLINE' && data.payment?.checkout_url) { window.location.assign(data.payment.checkout_url); return; }
      if (method === 'ONLINE') setError('No se recibió un enlace de pago. Actualiza el estado antes de volver a intentarlo.');
      else setNotice(paymentMethod === 'BANK_TRANSFER' ? 'Renovación solicitada. Adjunta tu comprobante de transferencia.' : 'Renovación solicitada. Se aplicará cuando el club confirme tu pago.');
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

  const uploadProof = async (membership) => {
    const proof = proofFiles[membership.id];
    if (!proof) { setError('Selecciona el comprobante de transferencia.'); return; }
    setBusy(true); setError('');
    const form = new FormData();
    form.append('proof', proof);
    try {
      await api.post(`/memberships/${membership.id}/proof/`, form, { headers: { 'Content-Type': 'multipart/form-data' } });
      setProofFiles((current) => ({ ...current, [membership.id]: null }));
      setNotice('Comprobante enviado. El club lo revisará.');
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const downloadProof = async (membership) => {
    try {
      const { data } = await api.get(`/memberships/${membership.id}/proof/file/`, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      const extension = { 'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' }[data.type] || 'bin';
      link.href = url; link.download = `comprobante-membresia-${membership.id}.${extension}`; link.click();
      URL.revokeObjectURL(url);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const reviewProof = async (membership, decision) => {
    const note = decision === 'REJECT' ? window.prompt('Indica el motivo del rechazo:') : '';
    if (decision === 'REJECT' && !note?.trim()) return;
    setBusy(true); setError('');
    try {
      await api.post(`/memberships/${membership.id}/proof/review/`, { decision, note });
      setNotice(decision === 'APPROVE' ? 'Comprobante aprobado y membresía confirmada.' : 'Comprobante rechazado; se notificó al deportista.');
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
    <header className="page-heading"><div><p className="eyebrow">PLANES Y PAGOS</p><h1>Membresías</h1><p className="page-description">{isAdmin ? 'Crea planes y asigna membresías a deportistas de tu club.' : isTrainer ? 'Consulta las membresías de tus deportistas asignados.' : 'Revisa los planes de tu club y el estado de tu membresía.'} {user?.club?.name ? `Club: ${user.club.name}.` : ''}</p></div><div className="heading-actions"><button className="button button-secondary" disabled={refreshing} onClick={load}><RefreshCw size={16} /> {refreshing ? 'Actualizando...' : 'Actualizar'}</button>{isAdmin && <><button className="button button-secondary" disabled={!detailsReady || Boolean(plansError)} onClick={() => { setMembershipEditor(true); setAssignmentError(''); }}><Plus size={16} /> Asignar membresía</button><button className="button primary-btn" onClick={() => { setEditor({}); setFormError(''); }}><Plus size={16} /> Crear plan</button></>}</div></header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}
    {plansError && <div className="notice notice-error" role="alert">{plansError}</div>}
    {detailsError && <div className="notice notice-error" role="alert">{detailsError} {!plansError && 'Los planes pueden consultarse, pero las acciones requieren cargar el estado actualizado.'}</div>}
    {loading ? <div className="empty-state">Cargando membresías...</div> : <>
      {isAdmin && detailsReady && <div className="notice notice-success">Transferencia bancaria: {bankInstructions.trim() ? 'configurada' : 'sin configurar'}. <a href="/store">Configurar datos en Tienda</a>; se usarán también para las membresías.</div>}
      {isAdmin && detailsReady && !onlineAvailable && !transbankAvailable && <div className="notice notice-error">El pago online no está configurado en el servidor. Los deportistas pueden solicitar planes y pagar directamente al club.</div>}
      {isAdmin && detailsReady && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">REGLAS DE RESERVA</p><h2>Exigir membresía activa para reservar clases</h2></div></div>
        <label className="field-label"><span>Estado de la regla</span><select className="control" value={requireMembership ? 'on' : 'off'} disabled={busy} onChange={(event) => saveRequirement(event.target.value === 'on')}><option value="off">Desactivado</option><option value="on">Activado</option></select></label>
        <p className="page-description">{requireMembership ? 'Solo los deportistas con una membresía activa y vigente en la fecha de la clase pueden reservar.' : 'Cualquier deportista activo puede reservar, tenga o no membresía.'}</p>
    </section>}      {user?.role === 'ATHLETE' && detailsReady && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">MI MEMBRESÍA</p><h2>{openMembership ? openMembership.plan_name : 'Sin membresía activa'}</h2></div>{openMembership && <span className="status-pill">{statusLabels[openMembership.status]}</span>}</div>
        {openMembership ? <div className="membership-summary-details">
          <p className="page-description">{openMembership.status === 'PENDING' ? (openPayment ? `Esperando la confirmación de ${openPayment.payment_provider === 'TRANSBANK' ? 'Transbank' : 'Mercado Pago'}.` : 'Esperando que el club confirme tu pago.') : `Vigente del ${dateLabel(openMembership.start_date)} al ${dateLabel(openMembership.end_date)}.`}</p>
          <p className="page-description">{openMembership.club_name || user?.club?.name} · {money(openMembership.price_paid, openMembership.currency)}{openMembership.days_remaining !== null && openMembership.days_remaining !== undefined ? ` · ${openMembership.days_remaining} días restantes` : ''}</p>
          {openMembership.payment_status && <p className="page-description">Último pago: {paymentLabels[openMembership.payment_status] || openMembership.payment_status} ({openMembership.payment_provider === 'TRANSBANK' ? 'Transbank' : 'Mercado Pago'}).</p>}
        </div> : <p className="page-description">{memberships[0] ? `Tu última membresía quedó ${statusLabels[memberships[0].status].toLowerCase()}${memberships[0].review_note ? `: ${memberships[0].review_note}` : '.'}` : 'Elige un plan para comenzar.'}</p>}
        {openPayment?.checkout_url && <a className="button primary-btn" href={openPayment.checkout_url}><CreditCard size={15} /> Continuar pago</a>}
        {openPayment && <button className="button button-secondary" disabled={busy} onClick={load}>Actualizar estado</button>}
        {openPayment && <button className="button button-secondary" disabled={busy} onClick={() => cancelPayment(openPayment)}>Cancelar pago</button>}
        {pendingMembership && !openPayment && <>
          {pendingMembership.payment_method === 'BANK_TRANSFER' ? <div>
            <div className="bank-transfer-details"><strong>Datos para transferir</strong><p>{bankInstructions || 'Consulta los datos de transferencia con tu club.'}</p></div>
            {pendingMembership.transfer_proof?.status === 'SUBMITTED' ? <p className="page-description">Comprobante en revisión por el club.</p> : <div className="proof-upload-row">
              {pendingMembership.transfer_proof?.status === 'REJECTED' && <p className="notice notice-error">Comprobante rechazado: {pendingMembership.transfer_proof.review_note}. Envía otro comprobante.</p>}
              <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" aria-label="Seleccionar comprobante de transferencia" onChange={(event) => setProofFiles((current) => ({ ...current, [pendingMembership.id]: event.target.files?.[0] || null }))} />
              <button className="button primary-btn" disabled={busy || !proofFiles[pendingMembership.id]} onClick={() => uploadProof(pendingMembership)}>Enviar comprobante</button>
            </div>}
          </div> : <p className="page-description">Esta solicitud es para pago al club. Para elegir otro método, cancélala y vuelve a elegir el plan.</p>}
          <button className="button button-secondary" disabled={busy} onClick={() => review(pendingMembership, 'CANCEL')}>Cancelar solicitud</button>
        </>}
        {activeMembership && pendingMembership && <p className="page-description">{pendingMembership.is_renewal ? 'Renovación' : 'Compra'} pendiente de pago: {pendingMembership.plan_name}. Tu membresía actual sigue vigente hasta el {dateLabel(activeMembership.end_date)}.</p>}
        {scheduledMembership && <p className="page-description">Renovación programada: {scheduledMembership.plan_name}, del {dateLabel(scheduledMembership.start_date)} al {dateLabel(scheduledMembership.end_date)}.</p>}
        {canRenew && !pendingMembership && <div className="renewal-box">
          <p className="page-description">{renewal.state === 'EXPIRED' ? `Tu membresía venció el ${dateLabel(renewal.end_date)}. Si renuevas, comenzará el día en que se confirme el pago.` : `Tu membresía vence el ${dateLabel(renewal.end_date)} (${renewal.days_left === 0 ? 'hoy' : `en ${renewal.days_left} día${renewal.days_left === 1 ? '' : 's'}`}). Si el pago se confirma hasta el día del vencimiento, la nueva comienza el ${dateLabel(renewal.next_start_date)} sin perder días; si se confirma después, comienza el día de la confirmación.`}</p>
          {renewal.plan ? <div className="training-actions">
            <button className="button primary-btn" disabled={busy || Boolean(plansError)} onClick={() => setPaymentChoice({ plan: renewal.plan, renewal: true })}><CreditCard size={15} /> Elegir cómo renovar {renewal.plan.name}</button>
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
        {user?.role === 'ATHLETE' && <div className="training-actions">
          <button className="button primary-btn" disabled={busy || (!canRenew && hasCurrentPlan) || !detailsReady || Boolean(plansError)} onClick={() => setPaymentChoice({ plan, renewal: canRenew })}><CreditCard size={15} /> {canRenew ? 'Elegir cómo renovar' : hasCurrentPlan ? 'Ya tienes un plan' : 'Elegir método de pago'}</button>
        </div>}
      </article>)}{!plans.length && !plansError && <div className="surface-panel empty-state">{isAdmin ? 'Aún no creas planes. Crea el primero para que tus deportistas puedan contratarlo.' : 'Tu club todavía no publica planes.'}</div>}</div>
      {detailsReady && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">{isAdmin ? 'PAGOS Y VENCIMIENTOS' : 'HISTORIAL'}</p><h2>{isAdmin ? `Membresías (${pending.length} por confirmar)` : isTrainer ? 'Membresías de mis deportistas' : 'Mis membresías'}</h2></div></div>
        <div className="closed-training-list">{memberships.map((item) => <div key={item.id}>
          <span>{isAdmin || isTrainer ? `${item.athlete_name} · ` : ''}{item.plan_name}{item.is_renewal ? ' (renovación)' : ''} · {money(item.price_paid, item.currency)}</span>
          <span>{item.end_date ? `${item.status === 'SCHEDULED' ? `Desde ${dateLabel(item.start_date)} hasta` : 'Hasta'} ${dateLabel(item.end_date)}` : dateLabel(item.created_at?.slice(0, 10))}</span>
          <span className="status-pill">{statusLabels[item.status]}</span>
          {isAdmin && item.payment_method === 'BANK_TRANSFER' && <span>Transferencia · {item.transfer_proof ? ({ SUBMITTED: 'Comprobante en revisión', APPROVED: 'Comprobante aprobado', REJECTED: 'Comprobante rechazado' }[item.transfer_proof.status]) : 'Sin comprobante'}</span>}
          {isAdmin && item.status === 'PENDING' && item.payment_method === 'BANK_TRANSFER' && item.transfer_proof?.status === 'SUBMITTED' && <><button className="button button-secondary" disabled={busy} onClick={() => downloadProof(item)}><Download size={15} /> Ver comprobante</button><button className="button primary-btn" disabled={busy} onClick={() => reviewProof(item, 'APPROVE')}><Check size={15} /> Aprobar comprobante</button><button className="button button-secondary" disabled={busy} onClick={() => reviewProof(item, 'REJECT')}>Rechazar comprobante</button></>}
          {isAdmin && item.status === 'PENDING' && !item.payment_status && item.payment_method !== 'BANK_TRANSFER' && <><button className="button primary-btn" disabled={busy} onClick={() => review(item, 'CONFIRM')}><Check size={15} /> Confirmar pago</button><button className="button button-secondary" disabled={busy} onClick={() => review(item, 'REJECT')}>Rechazar</button></>}
          {isAdmin && ['ACTIVE', 'SCHEDULED'].includes(item.status) && <button className="button button-secondary" disabled={busy} onClick={() => review(item, 'CANCEL')}>Cancelar</button>}
        </div>)}{!memberships.length && <div className="empty-state">Todavía no hay membresías.</div>}</div>
      </section>}
      {detailsReady && payments.length > 0 && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">HISTORIAL DE PAGOS</p><h2>Pagos online</h2></div></div>
        <div className="closed-training-list">{payments.map((item) => <div key={item.id}>
          <span>{isAdmin || isTrainer ? `${item.athlete_name} · ` : ''}{item.plan_name}{item.is_renewal ? ' (renovación)' : ''} · {money(item.amount, item.currency)}</span>
          <span>{item.payment_provider === 'TRANSBANK' ? 'Transbank Webpay Plus' : 'Mercado Pago'}</span>
          <span>{dateLabel(item.created_at?.slice(0, 10))}</span>
          <span className="status-pill">{paymentLabels[item.status] || item.status}</span>
        </div>)}</div>
      </section>}
    </>}
    {editor && <PlanDialog plan={editor.id ? editor : undefined} onClose={() => setEditor(null)} onSave={savePlan} busy={busy} error={formError} />}
    {membershipEditor && <AssignMembershipDialog athletes={athletes} plans={plans} onClose={() => setMembershipEditor(false)} onSave={assignMembership} busy={busy} error={assignmentError} />}
    {paymentChoice && detailsReady && !plansError && <PaymentDialog {...paymentChoice} onlineAvailable={onlineAvailable} transbankAvailable={transbankAvailable} bankInstructions={bankInstructions} onClose={() => setPaymentChoice(null)} onChoose={(method) => {
      const { plan, renewal: isRenewal } = paymentChoice;
      setPaymentChoice(null);
      const online = ['MERCADO_PAGO', 'TRANSBANK'].includes(method);
      if (isRenewal) renew(online ? 'ONLINE' : 'MANUAL', plan, online ? method : undefined, method);
      else if (online) payOnline(plan, method);
      else requestPlan(plan, method);
    }} />}
  </section>;
}
