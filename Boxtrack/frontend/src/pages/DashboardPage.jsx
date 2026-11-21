import { useEffect, useState } from 'react';
import { CalendarDays, ChartNoAxesColumn, ClipboardCheck, ClipboardList, Search, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getErrorMessage, readCollection } from '../services/api';
import { useAuth } from '../auth/AuthContext';

const numberFormat = new Intl.NumberFormat('es-CL');
const today = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
};
const attendanceLabels = {
  PRESENT: 'Presentes',
  ABSENT: 'Ausentes',
  LATE: 'Atrasos',
  JUSTIFIED: 'Justificados',
};

export function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [period, setPeriod] = useState(30);

  useEffect(() => {
    let active = true;
    const requests = [
      readCollection('/athletes/'),
      readCollection('/trainings/'),
      readCollection('/attendance/'),
      user?.role === 'ADMIN' ? readCollection('/clubs/memberships/') : Promise.resolve([]),
    ];
    Promise.all(requests).then(([athletes, trainings, attendance, memberships]) => {
      if (active) setSummary({ athletes, trainings, attendance, memberships });
    }).catch((requestError) => {
      if (active) setError(getErrorMessage(requestError));
    });
    return () => { active = false; };
  }, [user?.role]);

  const activeAthletes = summary?.athletes.filter((athlete) => athlete.status === 'ACTIVE') || [];
  const weekLimit = new Date(`${today()}T12:00:00`);
  weekLimit.setDate(weekLimit.getDate() + 7);
  const upcomingAll = (summary?.trainings || [])
    .filter((training) => training.status === 'SCHEDULED' && training.scheduled_date >= today() && training.scheduled_date < weekLimit.toISOString().slice(0, 10))
    .sort((first, second) => `${first.scheduled_date} ${first.start_time}`.localeCompare(`${second.scheduled_date} ${second.start_time}`))
  const upcoming = upcomingAll.slice(0, 8);
  const searchedClasses = upcoming.filter((training) => `${training.title} ${training.description || ''}`.toLowerCase().includes(query.toLowerCase()));
  const searchedAthletes = query.trim()
    ? activeAthletes.filter((athlete) => `${athlete.display_name || ''} ${athlete.first_name} ${athlete.last_name}`.toLowerCase().includes(query.toLowerCase())).slice(0, 5)
    : [];
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - Number(period));
  const attendanceInPeriod = (summary?.attendance || []).filter((record) => (
    record.registered_at && new Date(record.registered_at) >= cutoff
  ));
  const attendanceCounts = Object.keys(attendanceLabels).map((key) => ({
    key,
    label: attendanceLabels[key],
    value: attendanceInPeriod.filter((record) => record.status === key).length,
  }));
  const attendanceMax = Math.max(1, ...attendanceCounts.map(({ value }) => value));
  const attendanceTotal = attendanceInPeriod.length;
  const attendanceRate = attendanceTotal
    ? Math.round((attendanceCounts.find(({ key }) => key === 'PRESENT').value / attendanceTotal) * 100)
    : 0;
  const pendingMemberships = (summary?.memberships || []).filter((membership) => membership.status === 'PENDING').length;
  return <section className="page-stack">
    <header className="page-heading">
      <div><p className="eyebrow">PANEL DEL CLUB</p><h1>Resumen</h1><p className="page-description">La actividad y los pendientes importantes de tu gimnasio.</p></div>
    </header>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    <div className="dashboard-toolbar">
      <label className="search-field"><Search size={16} /><input aria-label="Buscar clases o deportistas" placeholder="Buscar clases o deportistas..." value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <label className="field-label"><span>Periodo de asistencia</span><select className="control" value={period} onChange={(event) => setPeriod(Number(event.target.value))}><option value={7}>Últimos 7 días</option><option value={30}>Últimos 30 días</option><option value={90}>Últimos 90 días</option></select></label>
    </div>
    <div className="dashboard-metrics">
      <article className="metric-card"><div className="metric-icon tone-red"><Users size={19} /></div><div><span>Deportistas activos</span><strong>{summary ? numberFormat.format(activeAthletes.length) : '—'}</strong></div><Link to="/athletes">Mis deportistas</Link></article>
      <article className="metric-card"><div className="metric-icon tone-green"><CalendarDays size={19} /></div><div><span>Clases esta semana</span><strong>{summary ? numberFormat.format(upcomingAll.length) : '—'}</strong></div><Link to="/trainings">Abrir agenda</Link></article>
      <article className="metric-card"><div className="metric-icon tone-blue"><ClipboardCheck size={19} /></div><div><span>Asistencia positiva</span><strong>{summary ? `${attendanceRate}%` : '—'}</strong></div><span className="metric-caption">Últimos {period} días</span></article>
      {user?.role === 'ADMIN' && <article className="metric-card"><div className="metric-icon tone-gold"><ClipboardList size={19} /></div><div><span>Solicitudes de ingreso</span><strong>{summary ? numberFormat.format(pendingMemberships) : '—'}</strong></div><Link to="/memberships">Revisar solicitudes</Link></article>}
    </div>
    {query.trim() && <section className="surface-panel dashboard-search-results">
      <div className="section-heading"><div><p className="eyebrow">BÚSQUEDA RÁPIDA</p><h2>Deportistas</h2></div><span>{searchedAthletes.length} coincidencias</span></div>
      {searchedAthletes.length
        ? <div className="dashboard-athlete-results">{searchedAthletes.map((athlete) => <Link to="/athletes" key={athlete.id}><span>{athlete.display_name || `${athlete.first_name} ${athlete.last_name}`}</span><small>{athlete.is_competitor ? 'Competidor' : 'Deportista'} · {athlete.category || 'Sin categoría'}</small></Link>)}</div>
        : <p className="dashboard-muted">No hay deportistas que coincidan con la búsqueda.</p>}
    </section>}
    <div className="dashboard-grid dashboard-insights-grid">
      <section className="surface-panel">
        <div className="section-heading"><div><p className="eyebrow">AGENDA PRÓXIMA</p><h2>Clases programadas</h2></div><CalendarDays size={19} /></div>
        {searchedClasses.length ? <div className="agenda-list">{searchedClasses.map((training) => <article className="agenda-row" key={training.id}>
          <div className="agenda-date"><strong>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { day: '2-digit' })}</strong><span>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { month: 'short' })}</span></div>
          <div className="agenda-info"><strong>{training.title}</strong><span>{training.start_time?.slice(0, 5)} · {training.duration_minutes} min · {training.reserved_count || 0}/{training.capacity} cupos</span></div>
          <span className="activity-tag">{training.activity_type}</span>
        </article>)}</div> : <div className="empty-state">{summary ? 'No encontramos clases próximas para ese filtro.' : 'Cargando actividad...'}</div>}
      </section>
      <section className="surface-panel">
        <div className="section-heading"><div><p className="eyebrow">CONTROL DEL CLUB</p><h2>Asistencia reciente</h2></div><ChartNoAxesColumn size={19} /></div>
        <div className="dashboard-chart" role="img" aria-label={`Asistencia últimos ${period} días: ${attendanceCounts.map(({ label, value }) => `${label} ${value}`).join(', ')}`}>
          {attendanceCounts.map(({ key, label, value }) => <div className="dashboard-chart-row" key={key}><span>{label}</span><div className="dashboard-chart-track"><i className={`chart-${key.toLowerCase()}`} style={{ width: `${(value / attendanceMax) * 100}%` }} /></div><strong>{numberFormat.format(value)}</strong></div>)}
        </div>
        <p className="dashboard-chart-caption">{numberFormat.format(attendanceTotal)} registros en el periodo seleccionado.</p>
        <Link className="dashboard-section-link" to="/trainings">Abrir clases y asistencia</Link>
      </section>
    </div>
  </section>;
}
