import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, MapPin } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

export function PublicHomePage() {
  const [clubs, setClubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    readCollection('/public/clubs/')
      .then((data) => {
        if (active) setClubs(data);
      })
      .catch((requestError) => {
        if (active) setError(getErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, []);

  return (
    <main className="public-site">
      <header className="public-header">
        <Link className="public-brand" to="/" aria-label="BoxTrack, inicio">
          <span className="public-brand-mark">BX</span>
          <span>BOXTRACK</span>
        </Link>
        <Link className="public-login-link" to="/login">Iniciar sesión</Link>
      </header>

      <section className="public-hero">
        <div className="public-hero-copy">
          <p className="eyebrow">TU PRÓXIMO ROUND COMIENZA AQUÍ</p>
          <h1>Encuentra tu gimnasio.<br /><em>Empieza a entrenar.</em></h1>
          <p>BoxTrack conecta a quienes quieren aprender boxeo con gimnasios que comparten su información y planes. Conoce las opciones, revisa qué incluye cada plan y contacta directamente al club.</p>
          <a className="button primary-btn" href="#gimnasios">Explorar gimnasios <ArrowRight size={16} /></a>
          <Link className="button button-secondary" to="/login?registro=club">¿Tienes un gimnasio? Súmate</Link>
        </div>
        <div className="public-hero-mark" aria-hidden="true"><span>BX</span><i /><i /><i /></div>
      </section>

      <section className="public-club-section" id="gimnasios">
        <header className="public-section-heading">
          <div>
            <p className="eyebrow">GIMNASIOS</p>
            <h2>Entrena cerca de ti</h2>
          </div>
          <p>Clubes que puedes conocer y contactar directamente.</p>
        </header>

        {loading && <div className="public-state">Cargando gimnasios...</div>}
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {!loading && !error && !clubs.length && (
          <div className="public-state">Aún no hay gimnasios publicados. Vuelve pronto para descubrir opciones.</div>
        )}
        {!loading && !error && Boolean(clubs.length) && (
          <div className="public-club-grid">
            {clubs.map((club) => (
              <article className="public-club-card" key={club.id}>
                <div className="public-club-logo">
                  {club.logo
                    ? <img src={club.logo} alt={`Logo de ${club.name}`} />
                    : <span aria-hidden="true">BX</span>}
                </div>
                <div className="public-club-copy">
                  <h3>{club.name}</h3>
                  {club.address && <p><MapPin size={14} />{club.address}</p>}
                  <Link to={`/gimnasios/${club.id}`} className="public-club-link">Ver gimnasio <ArrowRight size={15} /></Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <footer className="public-footer">BOXTRACK <span>Gestión deportiva y comunidad de boxeo.</span></footer>
    </main>
  );
}
