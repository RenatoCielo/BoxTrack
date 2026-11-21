import { useEffect, useState } from 'react';
import { Check, Download, X } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

const formatDate = (value) => value
  ? new Date(`${value}T12:00:00`).toLocaleDateString('es-CL')
  : 'Por definir';

const today = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
};

const statusLabels = {
  PENDING: 'Pendiente',
  ACTIVE: 'Activo',
  REJECTED: 'Rechazado',
  EXPIRED: 'Vencido'
};

export function MembershipsPage() {
  const [memberships, setMemberships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reviewTarget, setReviewTarget] = useState(null);
  const [decision, setDecision] = useState('APPROVE');
  const [values, setValues] = useState({ starts_on: today(), expires_on: '', note: '' });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setMemberships(await readCollection('/clubs/memberships/'));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openReview = (membership, nextDecision) => {
    setReviewTarget(membership);
    setDecision(nextDecision);
    setValues({ starts_on: today(), expires_on: '', note: '' });
    setError('');
  };

  const submitReview = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.post(`/clubs/memberships/${reviewTarget.id}/review/`, {
        decision,
        starts_on: values.starts_on,
        expires_on: values.expires_on,
        note: values.note
      });
      setReviewTarget(null);
      setNotice(decision === 'APPROVE' ? 'Membresía aprobada y cuenta activada.' : 'Solicitud rechazada.');
      await load();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const downloadProof = async (membership) => {
    setError('');
    try {
      const { data } = await api.get(`/clubs/memberships/${membership.id}/proof/`, { responseType: 'blob' });
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `comprobante-membresia-${membership.id}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    }
  };

  const pending = memberships.filter((item) => item.status === 'PENDING');
  const reviewed = memberships.filter((item) => item.status !== 'PENDING');

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">INGRESOS Y CONTRATOS</p><h1>Solicitudes de planes</h1><p className="page-description">Revisa comprobantes, aprueba el ingreso y define la vigencia del plan contratado.</p></div></header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {loading ? <div className="empty-state">Cargando solicitudes...</div> : <>
      <section className="surface-panel membership-review-panel">
        <div className="section-heading"><div><p className="eyebrow">POR REVISAR</p><h2>{pending.length} solicitudes pendientes</h2></div></div>
        {pending.length ? <div className="membership-list">{pending.map((membership) => <article className="membership-row" key={membership.id}>
          <div className="membership-person"><span className="roster-avatar">{membership.athlete_name?.slice(0, 1) || 'D'}</span><div><strong>{membership.athlete_name}</strong><small>{membership.user_email} · Solicitud {formatDate(membership.created_at?.slice(0, 10))}</small></div></div>
          <div className="membership-plan"><strong>{membership.plan_name}</strong><span>{membership.plan_duration} · {membership.classes_per_week == null ? 'Ilimitadas' : `${membership.classes_per_week} clases/semana`}</span><small>${Number(membership.price_at_signup).toLocaleString('es-CL')} CLP</small></div>
          <div className="membership-actions"><button className="button button-secondary" disabled={!membership.has_payment_proof} onClick={() => downloadProof(membership)}><Download size={15} /> Comprobante</button><button className="button primary-btn" onClick={() => openReview(membership, 'APPROVE')}><Check size={15} /> Aprobar</button><button className="button button-danger" onClick={() => openReview(membership, 'REJECT')}><X size={15} /> Rechazar</button></div>
        </article>)}</div> : <div className="empty-state">No hay solicitudes pendientes.</div>}
      </section>
      {reviewed.length > 0 && <section className="surface-panel">
        <div className="section-heading"><div><p className="eyebrow">HISTORIAL</p><h2>Solicitudes revisadas</h2></div></div>
        <div className="closed-training-list membership-history">{reviewed.map((membership) => <div key={membership.id}><span>{membership.athlete_name} · {membership.plan_name}</span><span>{formatDate(membership.starts_on)} – {formatDate(membership.expires_on)}</span><span className={`status-pill status-${membership.status.toLowerCase()}`}>{statusLabels[membership.status]}</span></div>)}</div>
      </section>}
    </>}
    {reviewTarget && <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setReviewTarget(null); }}>
      <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="membership-review-title">
        <header className="dialog-heading"><div><p className="eyebrow">{decision === 'APPROVE' ? 'ACTIVAR MEMBRESÍA' : 'REVISAR SOLICITUD'}</p><h2 id="membership-review-title">{decision === 'APPROVE' ? 'Confirmar ingreso' : 'Rechazar solicitud'}</h2><p className="page-description">{reviewTarget.athlete_name} · {reviewTarget.plan_name}</p></div><button className="icon-button dialog-close" onClick={() => setReviewTarget(null)} disabled={busy} aria-label="Cerrar"><X size={19} /></button></header>
        <form className="resource-form" onSubmit={submitReview}>
          {decision === 'APPROVE' ? <div className="field-grid">
            <label className="field-label"><span>Inicio del contrato *</span><input className="control" type="date" required value={values.starts_on} onChange={(event) => setValues({ ...values, starts_on: event.target.value })} /></label>
            <label className="field-label"><span>Vencimiento *</span><input className="control" type="date" required min={values.starts_on} value={values.expires_on} onChange={(event) => setValues({ ...values, expires_on: event.target.value })} /></label>
            <label className="field-label field-wide"><span>Nota (opcional)</span><textarea className="control" rows="2" maxLength="500" value={values.note} onChange={(event) => setValues({ ...values, note: event.target.value })} /></label>
          </div> : <label className="field-label"><span>Motivo del rechazo *</span><textarea className="control" required rows="3" maxLength="500" value={values.note} onChange={(event) => setValues({ ...values, note: event.target.value })} /></label>}
          {error && <div className="notice notice-error" role="alert">{error}</div>}
          <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={() => setReviewTarget(null)} disabled={busy}>Cancelar</button><button className={`button ${decision === 'APPROVE' ? 'primary-btn' : 'button-danger'}`} disabled={busy}>{busy ? 'Guardando...' : decision === 'APPROVE' ? 'Aprobar e ingresar' : 'Confirmar rechazo'}</button></footer>
        </form>
      </section>
    </div>}
  </section>;
}
