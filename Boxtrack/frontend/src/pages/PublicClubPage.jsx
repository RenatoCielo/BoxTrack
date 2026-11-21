import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, ExternalLink, Mail, MapPin, Phone, Upload, X } from 'lucide-react';
import { api, getErrorMessage } from '../services/api';
import { brandColorOnLightSurface, brandSurfaceWithReadableText } from '../utils/brandColors';

const formatCLP = (amount) => new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0
}).format(Number(amount));

export function PublicClubPage() {
  const { id } = useParams();
  const [club, setClub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [signupValues, setSignupValues] = useState({
    username: '', email: '', password: '', first_name: '', last_name: '', phone: '', proof: null
  });
  const [signupError, setSignupError] = useState('');
  const [signupNotice, setSignupNotice] = useState('');
  const [signupBusy, setSignupBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api.get(`/public/clubs/${id}/`)
      .then(({ data }) => {
        if (active) setClub(data);
      })
      .catch((requestError) => {
        if (active) setError(requestError.response?.status === 404
          ? 'Este gimnasio no está disponible públicamente.'
          : getErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [id]);

  if (loading) {
    return <main className="public-site"><div className="public-state">Cargando gimnasio...</div></main>;
  }

  if (error || !club) {
    return (
      <main className="public-site public-detail-page">
        <Link className="public-back-link" to="/"><ArrowLeft size={16} /> Volver a gimnasios</Link>
        <div className="notice notice-error" role="alert">{error || 'No se encontró el gimnasio.'}</div>
      </main>
    );
  }

  const contactHref = club.phone
    ? `tel:${club.phone}`
    : club.email
      ? `mailto:${club.email}`
      : club.website || '';
  const clubBrand = {
    '--boxing-red': brandColorOnLightSurface(club.brand_primary, '#B21F32'),
    '--forest': brandColorOnLightSurface(club.brand_primary, '#B21F32'),
    '--gold': brandColorOnLightSurface(club.brand_accent, '#A67825'),
    '--forest-dark': brandSurfaceWithReadableText(club.brand_surface, '#151518'),
  };
  const submitMembershipRequest = async (event) => {
    event.preventDefault();
    setSignupBusy(true);
    setSignupError('');
    setSignupNotice('');
    const formData = new FormData();
    Object.entries(signupValues).forEach(([key, value]) => {
      if (value !== null && value !== '') formData.append(key, value);
    });
    formData.append('plan', selectedPlan.id);
    try {
      const { data } = await api.post(`/public/clubs/${id}/memberships/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSignupNotice(data.detail);
      setSelectedPlan(null);
      setSignupValues({ username: '', email: '', password: '', first_name: '', last_name: '', phone: '', proof: null });
    } catch (requestError) {
      setSignupError(getErrorMessage(requestError));
    } finally {
      setSignupBusy(false);
    }
  };

  return (
    <main className="public-site public-detail-page" style={clubBrand}>
      <header className="public-header">
        <Link className="public-brand" to="/" aria-label="BoxTrack, inicio">
          <span className="public-brand-mark">BX</span>
          <span>BOXTRACK</span>
        </Link>
        <Link className="public-login-link" to="/login">Iniciar sesión</Link>
      </header>

      <Link className="public-back-link" to="/"><ArrowLeft size={16} /> Gimnasios</Link>
      <section className="public-detail-hero">
        <div className="public-detail-logo">
          {club.logo ? <img src={club.logo} alt={`Logo de ${club.name}`} /> : <span>BX</span>}
        </div>
        <div className="public-detail-copy">
          <p className="eyebrow">GIMNASIO DE BOXEO</p>
          <h1>{club.name}</h1>
          {club.address && <p className="public-detail-address"><MapPin size={16} />{club.address}</p>}
          {club.description && <p className="public-detail-description">{club.description}</p>}
          {contactHref
            ? <a className="button primary-btn public-contact-button" href={contactHref} target={contactHref.startsWith('http') ? '_blank' : undefined} rel={contactHref.startsWith('http') ? 'noreferrer' : undefined}>Contactar al gimnasio <ArrowRight size={16} /></a>
            : <p className="public-contact-empty">Este gimnasio no tiene un contacto público disponible.</p>}
          {(club.phone || club.email || club.website) && (
            <section className="public-contact-details" style={{ width: '100%', margin: '18px 0 0' }} aria-label="Contacto del gimnasio">
              {club.phone && <a href={`tel:${club.phone}`}><Phone size={16} />{club.phone}</a>}
              {club.email && <a href={`mailto:${club.email}`}><Mail size={16} />{club.email}</a>}
              {club.website && <a href={club.website} target="_blank" rel="noreferrer"><ExternalLink size={16} />Sitio web</a>}
            </section>
          )}
        </div>
      </section>

      <section className="public-plan-section">
        <header className="public-section-heading">
          <div><p className="eyebrow">ENTRENAMIENTO</p><h2>Planes disponibles</h2></div>
          <p>Elige tu plan, envía el comprobante de transferencia y el gimnasio confirmará tu ingreso.</p>
        </header>
        {signupNotice && <div className="notice notice-success" role="status">{signupNotice}<button className="icon-button" onClick={() => setSignupNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
        {!club.plans?.length ? (
          <div className="public-state">Este gimnasio aún no tiene planes publicados.</div>
        ) : (
          <div className="public-plan-grid">
            {club.plans.map((plan) => (
              <article className="public-plan-card" key={plan.id}>
                <p className="public-plan-duration">{plan.duration}</p>
                <h3>{plan.name}</h3>
                {plan.is_premium && <span className="status-tag">PREMIUM</span>}
                {plan.description && <p className="public-plan-description">{plan.description}</p>}
                <p className="public-plan-description">{plan.classes_per_week == null ? 'Clases ilimitadas por semana · Premium' : `${plan.classes_per_week} clases por semana`}</p>
                <strong className="public-plan-price">{formatCLP(plan.price)}</strong>
                <button className="button primary-btn" disabled={!club.bank_transfer_instructions} onClick={() => { setSelectedPlan(plan); setSignupError(''); }}>
                  Solicitar ingreso <ArrowRight size={16} />
                </button>
              </article>
            ))}
          </div>
        )}
        {club.plans?.length > 0 && !club.bank_transfer_instructions && <p className="notice notice-error">Este gimnasio todavía no ha configurado sus datos de transferencia. Contacta directamente para inscribirte.</p>}
        {club.bank_transfer_instructions && <aside className="surface-panel membership-payment-details"><p className="eyebrow">PAGO POR TRANSFERENCIA</p><p>{club.bank_transfer_instructions}</p><small>La solicitud queda pendiente hasta que el administrador valide el comprobante.</small></aside>}
      </section>

      <footer className="public-footer">BOXTRACK <span>Inscripción con revisión manual del comprobante por el gimnasio.</span></footer>
      {selectedPlan && <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget && !signupBusy) setSelectedPlan(null); }}>
        <section className="form-dialog membership-dialog" role="dialog" aria-modal="true" aria-labelledby="membership-title">
          <header className="dialog-heading"><div><p className="eyebrow">SOLICITUD DE INGRESO</p><h2 id="membership-title">{selectedPlan.name}</h2><p className="page-description">{formatCLP(selectedPlan.price)} · {selectedPlan.duration} · {selectedPlan.classes_per_week == null ? 'Clases ilimitadas' : `${selectedPlan.classes_per_week} por semana`}</p></div><button className="icon-button dialog-close" onClick={() => setSelectedPlan(null)} disabled={signupBusy} aria-label="Cerrar"><X size={19} /></button></header>
          <form className="resource-form" onSubmit={submitMembershipRequest}>
            <div className="field-grid">
              <label className="field-label"><span>Nombre *</span><input className="control" required maxLength="100" autoComplete="given-name" value={signupValues.first_name} onChange={(event) => setSignupValues({ ...signupValues, first_name: event.target.value })} /></label>
              <label className="field-label"><span>Apellido *</span><input className="control" required maxLength="100" autoComplete="family-name" value={signupValues.last_name} onChange={(event) => setSignupValues({ ...signupValues, last_name: event.target.value })} /></label>
              <label className="field-label"><span>Usuario *</span><input className="control" required maxLength="150" autoComplete="username" value={signupValues.username} onChange={(event) => setSignupValues({ ...signupValues, username: event.target.value })} /></label>
              <label className="field-label"><span>Correo *</span><input className="control" type="email" required autoComplete="email" value={signupValues.email} onChange={(event) => setSignupValues({ ...signupValues, email: event.target.value })} /></label>
              <label className="field-label"><span>Contraseña *</span><input className="control" type="password" required minLength="8" autoComplete="new-password" value={signupValues.password} onChange={(event) => setSignupValues({ ...signupValues, password: event.target.value })} /></label>
              <label className="field-label"><span>Teléfono</span><input className="control" type="tel" autoComplete="tel" value={signupValues.phone} onChange={(event) => setSignupValues({ ...signupValues, phone: event.target.value })} /></label>
              <label className="field-label field-wide"><span>Comprobante de transferencia *</span><input className="control" type="file" required accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp" onChange={(event) => setSignupValues({ ...signupValues, proof: event.target.files?.[0] || null })} /><small>PDF o imagen, máximo 5 MB. Se almacenará de forma privada.</small></label>
            </div>
            {signupError && <div className="notice notice-error" role="alert">{signupError}</div>}
            <footer className="dialog-actions"><button type="button" className="button button-secondary" disabled={signupBusy} onClick={() => setSelectedPlan(null)}>Cancelar</button><button className="button primary-btn" disabled={signupBusy}>{signupBusy ? 'Enviando...' : <><Upload size={16} /> Enviar solicitud</>}</button></footer>
          </form>
        </section>
      </div>}
    </main>
  );
}
