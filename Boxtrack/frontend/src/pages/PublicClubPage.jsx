import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, ExternalLink, Mail, MapPin, Phone } from 'lucide-react';
import { api, getErrorMessage } from '../services/api';

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

  return (
    <main className="public-site public-detail-page">
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
          <p>Consulta el plan que se ajusta a tus objetivos y coordina directamente con el gimnasio.</p>
        </header>
        {!club.plans?.length ? (
          <div className="public-state">Este gimnasio aún no tiene planes publicados.</div>
        ) : (
          <div className="public-plan-grid">
            {club.plans.map((plan) => (
              <article className="public-plan-card" key={plan.id}>
                <p className="public-plan-duration">{plan.duration}</p>
                <h3>{plan.name}</h3>
                {plan.description && <p className="public-plan-description">{plan.description}</p>}
                <strong className="public-plan-price">{formatCLP(plan.price)}</strong>
              </article>
            ))}
          </div>
        )}
      </section>

      <footer className="public-footer">BOXTRACK <span>Contacta directamente; no se realizan pagos en línea.</span></footer>
    </main>
  );
}
