import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, CalendarDays, MapPin, Swords } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

export function PublicHomePage() {
  const [clubs, setClubs] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [overviewError, setOverviewError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.allSettled([
      readCollection('/public/clubs/'),
      api.get('/public/clubs/site/'),
    ]).then(([clubResult, overviewResult]) => {
      if (!active) return;
      if (clubResult.status === 'fulfilled') setClubs(clubResult.value);
      else setError(getErrorMessage(clubResult.reason));
      if (overviewResult.status === 'fulfilled') setOverview(overviewResult.value.data);
      else setOverviewError(getErrorMessage(overviewResult.reason));
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => { active = false; };
  }, []);

  const featuredFights = overview?.featured_fights || [];
  const promotionImage = overview?.promotion?.image || '/fight-night-default.svg';

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

      <section className="public-community-section">
        <header className="public-section-heading">
          <div><p className="eyebrow">BOXTRACK EN ACCIÓN</p><h2>{overview?.promotion?.headline || 'La comunidad se prepara'}</h2></div>
          <p>{overview?.promotion?.intro || 'Novedades y próximos encuentros de los gimnasios de nuestra comunidad.'}</p>
        </header>
        {overviewError && <div className="notice notice-error" role="alert">{overviewError}</div>}
        <article className="public-fight-feature">
          <div className="public-fight-feature-copy">
            <p className="eyebrow"><Swords size={14} /> PRÓXIMOS COMBATES</p>
            {featuredFights.length ? <>
              {featuredFights.slice(0, 2).map((fight) => <div className="public-fight-matchup" key={fight.id}>
                <h3>{fight.proposing_club_name}<span>VS</span>{fight.opponent_club_name}</h3>
                <p><CalendarDays size={15} />{new Date(`${fight.planned_date}T12:00:00`).toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' })} · {fight.location}</p>
                <small>{fight.confirmed_bouts.length} {fight.confirmed_bouts.length === 1 ? 'emparejamiento confirmado' : 'emparejamientos confirmados'} · {fight.confirmed_bouts.map((bout) => bout.category || 'Categoría por definir').join(' · ')}</small>
              </div>)}
            </> : <div className="public-fight-empty"><h3>El próximo encuentro puede comenzar aquí.</h3><p>Los combates aparecerán cuando ambos gimnasios acuerden el evento y sus emparejamientos.</p><Link to="/login?registro=club">Únete a la comunidad <ArrowRight size={15} /></Link></div>}
          </div>
          <img className="public-fight-feature-image" src={promotionImage} alt="Promoción del próximo encuentro BOXTRACK" />
        </article>
      </section>

      <section className="public-updates-section">
        <header className="public-section-heading"><div><p className="eyebrow">NOVEDADES DE LA COMUNIDAD</p><h2>Gimnasios que se mueven</h2></div><p>Conoce los clubes que se han sumado o actualizado su página pública recientemente.</p></header>
        {loading ? <div className="public-state">Cargando novedades...</div> : overview?.club_updates?.length ? <div className="public-updates-grid">
          {overview.club_updates.slice(0, 4).map((update) => <article className="public-update-card" key={`${update.id}-${update.update_type}`}>
            <div className="public-update-logo">{update.logo ? <img src={update.logo} alt="" /> : <span>BX</span>}</div>
            <div><span className="public-update-tag">{update.update_type === 'NEW' ? 'NUEVO EN BOXTRACK' : 'PERFIL ACTUALIZADO'}</span><h3>{update.name}</h3><p>{update.description || (update.update_type === 'NEW' ? 'Un nuevo gimnasio se suma a la comunidad.' : 'Conoce las últimas novedades de este gimnasio.')}</p><small>{new Date(update.updated_at).toLocaleDateString('es-CL', { day: 'numeric', month: 'short', year: 'numeric' })}</small></div>
            <Link to={`/gimnasios/${update.id}`} aria-label={`Conocer ${update.name}`}><ArrowRight size={17} /></Link>
          </article>)}
        </div> : <div className="public-state">Las novedades de los gimnasios publicados aparecerán aquí.</div>}
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
              <article className="public-club-card" key={club.id} style={{ '--club-primary': club.brand_primary || '#B21F32' }}>
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
