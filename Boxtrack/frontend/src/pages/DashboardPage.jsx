import { useEffect, useState } from 'react';
import { Activity, CalendarDays, ClipboardCheck, Dumbbell, Users } from 'lucide-react';
import { readCollection } from '../services/api';

const numberFormat = new Intl.NumberFormat('es-CL');

export function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    Promise.all([
      readCollection('/athletes/'),
      readCollection('/trainings/'),
      readCollection('/attendance/'),
      readCollection('/groups/')
    ]).then(([athletes, trainings, attendance, groups]) => {
      if (!active) return;
      setSummary({ athletes, trainings, attendance, groups });
    }).catch(() => {
      if (active) setError('No fue posible cargar el resumen del club.');
    });
    return () => { active = false; };
  }, []);

  const cards = [
    { label: 'Deportistas activos', value: summary?.athletes.filter((item) => item.status === 'ACTIVE').length, icon: Users, tone: 'red' },
    { label: 'Clases programadas', value: summary?.trainings.filter((item) => item.status === 'SCHEDULED').length, icon: CalendarDays, tone: 'green' },
    { label: 'Registros de asistencia', value: summary?.attendance.length, icon: ClipboardCheck, tone: 'blue' },
    { label: 'Grupos activos', value: summary?.groups.filter((item) => item.is_active).length, icon: Activity, tone: 'yellow' }
  ];
  const upcoming = summary?.trainings
    .filter((item) => item.status === 'SCHEDULED')
    .sort((first, second) => `${first.scheduled_date} ${first.start_time}`.localeCompare(`${second.scheduled_date} ${second.start_time}`))
    .slice(0, 5) || [];

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div><p className="eyebrow">PANEL DEL CLUB</p><h1>Resumen</h1><p className="page-description">Actividad real de tu club, en una sola vista.</p></div>
      </header>
      {error && <div className="notice notice-error">{error}</div>}
      <div className="metric-grid">
        {cards.map(({ label, value, icon: Icon, tone }) => (
          <article className="metric-card" key={label}>
            <div className={`metric-icon tone-${tone}`}><Icon size={19} /></div>
            <div><span>{label}</span><strong>{value === undefined ? '—' : numberFormat.format(value)}</strong></div>
          </article>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="surface-panel">
          <div className="section-heading"><div><p className="eyebrow">AGENDA</p><h2>Próximas clases</h2></div><Dumbbell size={19} /></div>
          {upcoming.length ? <div className="agenda-list">{upcoming.map((training) => <article className="agenda-row" key={training.id}>
            <div className="agenda-date"><strong>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { day: '2-digit' })}</strong><span>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { month: 'short' })}</span></div>
            <div className="agenda-info"><strong>{training.title}</strong><span>{training.start_time?.slice(0, 5)} · {training.duration_minutes} min</span></div>
            <span className="activity-tag">{training.activity_type}</span>
          </article>)}</div> : <div className="empty-state">{summary ? 'No hay clases programadas.' : 'Cargando actividad...'}</div>}
        </section>
        <section className="surface-panel compact-panel">
          <div className="section-heading"><div><p className="eyebrow">ASISTENCIA</p><h2>Resumen de lista</h2></div><ClipboardCheck size={19} /></div>
          <div className="attendance-summary">
            <span className="attendance-total">{summary ? numberFormat.format(summary.attendance.length) : '—'}</span>
            <p>registros acumulados</p>
            <div className="attendance-breakdown">
              {['PRESENT', 'ABSENT', 'LATE'].map((status) => <div key={status}><span>{status === 'PRESENT' ? 'Presentes' : status === 'ABSENT' ? 'Ausentes' : 'Atrasos'}</span><strong>{summary ? summary.attendance.filter((record) => record.status === status).length : '—'}</strong></div>)}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
