import { useEffect, useState } from 'react';
import { CheckCircle2, ShieldAlert, ShieldCheck } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

export function GlobalAdminPage() {
  const [clubs, setClubs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    readCollection('/clubs/pending/')
      .then((data) => {
        if (active) setClubs(data);
      })
      .catch(() => {
        if (active) setError('No se pudieron cargar los clubes pendientes.');
      });

    return () => { active = false; };
  }, []);

  const updateClubStatus = async (clubId, status) => {
    setBusy(true);
    setError('');
    try {
      await api.patch(`/clubs/${clubId}/review/`, {
        verification_status: status,
        verification_note: status === 'APPROVED'
          ? 'Club aprobado por validación global.'
          : 'Club rechazado por validación global.'
      });
      setClubs((current) => current.filter((club) => club.id !== clubId));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRACIÓN GLOBAL</p>
          <h1>Revisión de clubes</h1>
          <p className="page-description">Revisa la documentación de cada club y aprueba o rechaza su activación.</p>
        </div>
      </header>

      {error && <div className="notice notice-error">{error}</div>}

      {!clubs.length ? (
        <div className="empty-state">No hay clubes pendientes de revisión.</div>
      ) : (
        <div className="surface-panel">
          <div className="stacked-list">
            {clubs.map((club) => (
              <article className="agenda-row" key={club.id}>
                <div className="agenda-info">
                  <strong>{club.name}</strong>
                  <span>RUT: {club.legal_rut || 'Sin RUT'} · Representante: {club.legal_representative_name || 'Sin datos'}</span>
                  <span>Correo: {club.email || 'Sin correo'} · Disciplinas: {(club.disciplines || []).join(', ') || 'Sin disciplinas'}</span>
                </div>
                <div className="inline-actions">
                  <button className="button button-secondary" onClick={() => updateClubStatus(club.id, 'REJECTED')} disabled={busy}>
                    <ShieldAlert size={16} /> Rechazar
                  </button>
                  <button className="button primary-btn" onClick={() => updateClubStatus(club.id, 'APPROVED')} disabled={busy}>
                    <ShieldCheck size={16} /> Aprobar
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
