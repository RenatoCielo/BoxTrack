import { useEffect, useState } from 'react';
import { Building2, CircleCheck, Search, ShieldAlert, ShieldCheck, Users } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

const clubStatuses = {
  PENDING: 'Pendiente de documentos',
  IN_REVIEW: 'En revisión',
  NEEDS_INFO: 'Requiere información',
  APPROVED: 'Aprobado',
  REJECTED: 'Rechazado',
};
const roles = { SUPERUSER: 'Superusuario', ADMIN: 'Administrador', TRAINER: 'Entrenador', ATHLETE: 'Deportista', OTHER: 'Sin rol' };

function useGlobalList(path, revision) {
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api.get(path, { params: { page, search } })
      .then((response) => { if (active) setData(response.data); })
      .catch(() => { if (active) { setData(null); setError('No se pudo cargar la lista.'); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, page, search, revision]);

  const submit = (event) => {
    event.preventDefault();
    setPage(1);
    setSearch(input.trim());
  };
  return { input, setInput, submit, data, loading, error, page, setPage };
}

function Distribution({ title, description, rows, labels, total }) {
  return (
    <section className="surface-panel global-chart">
      <div className="section-heading"><div><p className="eyebrow">DISTRIBUCIÓN</p><h2>{title}</h2></div></div>
      <p className="global-muted">{description}</p>
      {!rows.length ? <div className="empty-state">Todavía no hay datos para mostrar.</div> : (
        <div className="global-bars">
          {rows.map(({ key, count }) => (
            <div className="global-bar-row" key={key}>
              <div><span>{labels[key] || key}</span><strong>{count}</strong></div>
              <div className="global-bar-track" aria-hidden="true"><div style={{ width: `${total ? (count / total) * 100 : 0}%` }} /></div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Directory({ title, description, list, columns, renderRow }) {
  return (
    <section className="surface-panel global-directory">
      <div className="section-heading"><div><p className="eyebrow">DIRECTORIO GLOBAL</p><h2>{title}</h2></div></div>
      <p className="global-muted">{description}</p>
      <div className="table-toolbar global-toolbar">
        <form className="search-field" onSubmit={list.submit}>
          <Search size={16} aria-hidden="true" />
          <input aria-label={`Buscar en ${title}`} placeholder="Buscar..." value={list.input} onChange={(event) => list.setInput(event.target.value)} />
          <button className="button button-secondary" type="submit">Buscar</button>
        </form>
        {list.data && !list.loading && <span className="table-count">{list.data.count} resultados</span>}
      </div>
      {list.error ? <div className="notice notice-error" role="alert">{list.error}</div> : list.loading ? (
        <div className="empty-state">Cargando {title.toLowerCase()}...</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
              <tbody>
                {list.data.results.length ? list.data.results.map(renderRow) : <tr><td className="table-empty" colSpan={columns.length}>No se encontraron resultados.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="global-pagination">
            <span>Página {list.page}</span>
            <div className="inline-actions">
              <button className="button button-secondary" onClick={() => list.setPage(list.page - 1)} disabled={!list.data.previous}>Anterior</button>
              <button className="button button-secondary" onClick={() => list.setPage(list.page + 1)} disabled={!list.data.next}>Siguiente</button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

export function GlobalAdminPage() {
  const [clubs, setClubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState('');
  const [revision, setRevision] = useState(0);
  const clubList = useGlobalList('/dashboard/global/clubs/', revision);
  const userList = useGlobalList('/dashboard/global/users/', revision);

  useEffect(() => {
    let active = true;
    readCollection('/clubs/pending/')
      .then((data) => { if (active) setClubs(data); })
      .catch(() => { if (active) setError('No se pudieron cargar los clubes pendientes.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setSummaryError('');
    api.get('/dashboard/global/')
      .then(({ data }) => { if (active) setSummary(data); })
      .catch(() => { if (active) { setSummary(null); setSummaryError('No se pudieron cargar los indicadores globales.'); } });
    return () => { active = false; };
  }, [revision]);

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
      setRevision((current) => current + 1);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-stack global-admin">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRACIÓN GLOBAL</p>
          <h1>Panel de administración</h1>
          <p className="page-description">Una vista general de los gimnasios y usuarios registrados en BoxTrack. El estado activo de un gimnasio es independiente de su verificación.</p>
        </div>
      </header>

      {summaryError ? <div className="notice notice-error" role="alert">{summaryError}</div> : !summary ? (
        <div className="empty-state">Cargando indicadores globales...</div>
      ) : (
        <>
          <div className="metric-grid">
            {[
              { label: 'Gimnasios inscritos', value: summary.clubs.total, icon: Building2, tone: 'tone-red' },
              { label: 'Gimnasios activos', value: summary.clubs.active, icon: CircleCheck, tone: 'tone-green' },
              { label: 'Usuarios registrados', value: summary.users.total, icon: Users, tone: 'tone-blue' },
              { label: 'Usuarios activos', value: summary.users.active, icon: ShieldCheck, tone: 'tone-yellow' },
            ].map(({ label, value, icon: Icon, tone }) => (
              <div className="metric-card" key={label}><div className={`metric-icon ${tone}`}><Icon size={20} /></div><div><span>{label}</span><strong>{value}</strong></div></div>
            ))}
          </div>
          <div className="global-chart-grid">
            <Distribution title="Estado de gimnasios" description="Según su verificación, incluidos los gimnasios inactivos." total={summary.clubs.total} labels={clubStatuses} rows={summary.clubs_by_status.map((item) => ({ key: item.verification_status, count: item.count }))} />
            <Distribution title="Usuarios por rol" description="Incluye cuentas activas e inactivas." total={summary.users.total} labels={roles} rows={summary.users_by_role.map((item) => ({ key: item.group, count: item.count }))} />
          </div>
        </>
      )}

      <section className="surface-panel">
        <div className="section-heading"><div><p className="eyebrow">VERIFICACIÓN GLOBAL</p><h2>Clubes pendientes</h2></div><ShieldCheck size={19} /></div>
        <p className="global-muted">Revisa los datos de cada club y aprueba o rechaza su activación.</p>
        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {loading ? <div className="empty-state">Cargando clubes pendientes...</div> : error && !clubs.length ? null : !clubs.length ? (
          <div className="empty-state">No hay clubes pendientes de revisión.</div>
        ) : (
          <div className="stacked-list">
            {clubs.map((club) => (
              <article className="agenda-row" key={club.id}>
                <div className="agenda-info">
                  <strong>{club.name}</strong>
                  <span>Verificación: {clubStatuses[club.verification_status] || club.verification_status}</span>
                  <span>RUT: {club.legal_rut || 'Sin RUT'} · Representante: {club.legal_representative_name || 'Sin datos'}</span>
                  <span>Correo: {club.email || 'Sin correo'} · Disciplinas: {(club.disciplines || []).join(', ') || 'Sin disciplinas'}</span>
                </div>
                <div className="inline-actions">
                  <button className="button button-secondary" onClick={() => updateClubStatus(club.id, 'REJECTED')} disabled={busy}><ShieldAlert size={16} /> Rechazar</button>
                  <button className="button primary-btn" onClick={() => updateClubStatus(club.id, 'APPROVED')} disabled={busy}><ShieldCheck size={16} /> Aprobar</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <Directory title="Gimnasios inscritos" description="Todos los gimnasios, independientemente de su estado de verificación." list={clubList} columns={['Gimnasio', 'Verificación', 'Estado', 'Usuarios']} renderRow={(club) => (
        <tr key={club.id}><td data-label="Gimnasio"><strong>{club.name}</strong></td><td data-label="Verificación">{clubStatuses[club.verification_status] || club.verification_status}</td><td data-label="Estado">{club.is_active ? 'Activo' : 'Inactivo'}</td><td data-label="Usuarios">{club.user_count}</td></tr>
      )} />
      <Directory title="Usuarios registrados" description="Cuentas de todos los gimnasios y cuentas sin gimnasio." list={userList} columns={['Nombre', 'Usuario', 'Rol', 'Gimnasio', 'Estado']} renderRow={(user) => (
        <tr key={user.id}><td data-label="Nombre"><strong>{user.display_name}</strong></td><td data-label="Usuario">{user.username}</td><td data-label="Rol">{roles[user.role] || user.role}</td><td data-label="Gimnasio">{user.club_name || 'Sin gimnasio'}</td><td data-label="Estado">{user.is_active ? 'Activo' : 'Inactivo'}</td></tr>
      )} />
    </section>
  );
}
