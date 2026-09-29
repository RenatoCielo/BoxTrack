import { useEffect, useState } from 'react';
import { CalendarDays, Check, Clock3, Pencil, Plus, Users, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const activityLabels = { TECHNICAL: 'Técnica', TACTICAL: 'Táctica', PHYSICAL: 'Preparación física', SPARRING: 'Sparring', COMPETITION: 'Preparación competitiva' };
const statusLabels = { SCHEDULED: 'Programada', CANCELLED: 'Cancelada', COMPLETED: 'Completada' };
const attendanceLabels = { PRESENT: 'Presente', ABSENT: 'Ausente', JUSTIFIED: 'Justificado', LATE: 'Atrasado' };
const today = () => {
  const localDate = new Date();
  localDate.setMinutes(localDate.getMinutes() - localDate.getTimezoneOffset());
  return localDate.toISOString().slice(0, 10);
};

function TrainingForm({ initial, groups, onClose, onSubmit, busy, error }) {
  const [values, setValues] = useState({
    title: '', description: '', activity_type: 'TECHNICAL', group: '', scheduled_date: today(),
    start_time: '18:00', duration_minutes: 60, capacity: 20, status: 'SCHEDULED', objectives: '', ...initial
  });
  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  return <div className="modal-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="training-dialog-title">
      <header className="dialog-heading"><div><p className="eyebrow">AGENDA DEL CLUB</p><h2 id="training-dialog-title">{initial?.id ? 'Editar clase' : 'Programar clase'}</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
      <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSubmit(values); }}>
        <div className="field-grid">
          <label className="field-label field-wide"><span>Nombre de la clase *</span><input className="control" name="title" required value={values.title} onChange={update} /></label>
          <label className="field-label"><span>Actividad</span><select className="control" name="activity_type" value={values.activity_type} onChange={update}>{Object.entries(activityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          <label className="field-label"><span>Grupo</span><select className="control" name="group" value={values.group ?? ''} onChange={update}><option value="">Todos los grupos</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
          <label className="field-label"><span>Fecha *</span><input className="control" type="date" name="scheduled_date" required value={values.scheduled_date} onChange={update} /></label>
          <label className="field-label"><span>Hora *</span><input className="control" type="time" name="start_time" required value={values.start_time} onChange={update} /></label>
          <label className="field-label"><span>Duración (min)</span><input className="control" type="number" min="1" name="duration_minutes" value={values.duration_minutes} onChange={update} /></label>
          <label className="field-label"><span>Cupos máximos</span><input className="control" type="number" min="1" name="capacity" value={values.capacity} onChange={update} /></label>
          {initial?.id && <label className="field-label"><span>Estado</span><select className="control" name="status" value={values.status} onChange={update}>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
          <label className="field-label field-wide"><span>Descripción</span><textarea className="control" name="description" rows="2" value={values.description} onChange={update} /></label>
          <label className="field-label field-wide"><span>Objetivos de la clase</span><textarea className="control" name="objectives" rows="2" value={values.objectives} onChange={update} /></label>
        </div>
        {error && <div className="notice notice-error">{error}</div>}
        <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy}>{busy ? 'Guardando...' : 'Guardar clase'}</button></footer>
      </form>
    </section>
  </div>;
}

export function TrainingPage() {
  const { user } = useAuth();
  const isStaff = ['ADMIN', 'TRAINER'].includes(user?.role);
  const [trainings, setTrainings] = useState([]);
  const [groups, setGroups] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [reservationMap, setReservationMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editor, setEditor] = useState(null);
  const [roster, setRoster] = useState(null);
  const [reserveTarget, setReserveTarget] = useState(null);
  const [athleteId, setAthleteId] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [trainingRows, groupRows, athleteRows, attendanceRows] = await Promise.all([
        readCollection('/trainings/'),
        isStaff ? readCollection('/groups/') : Promise.resolve([]),
        isStaff ? readCollection('/athletes/') : Promise.resolve([]),
        isStaff ? readCollection('/attendance/') : Promise.resolve([])
      ]);
      const scheduledRows = trainingRows.filter((training) => training.status === 'SCHEDULED');
      const reservationEntries = await Promise.all(scheduledRows.map(async (training) => {
        try { return [training.id, await api.get(`/trainings/${training.id}/reservations/`).then((response) => response.data)]; }
        catch { return [training.id, []]; }
      }));
      setTrainings(trainingRows.sort((first, second) => `${first.scheduled_date} ${first.start_time}`.localeCompare(`${second.scheduled_date} ${second.start_time}`)));
      setGroups(groupRows.filter((group) => group.is_active));
      setAthletes(athleteRows.filter((athlete) => athlete.status === 'ACTIVE'));
      setAttendance(attendanceRows);
      setReservationMap(Object.fromEntries(reservationEntries));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const saveTraining = async (values) => {
    setBusy(true);
    setFormError('');
    const payload = { ...values, duration_minutes: Number(values.duration_minutes), capacity: Number(values.capacity), group: values.group ? Number(values.group) : null };
    try {
      if (editor?.id) await api.patch(`/trainings/${editor.id}/`, payload);
      else await api.post('/trainings/', payload);
      setEditor(null);
      setNotice('Clase guardada.');
      await load();
    } catch (requestError) { setFormError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const makeReservation = async (training, selectedAthleteId) => {
    if (!training) return;
    setBusy(true);
    setFormError('');
    try {
      await api.post(`/trainings/${training.id}/reservations/`, isStaff ? { athlete: Number(selectedAthleteId) } : {});
      setReserveTarget(null);
      setAthleteId('');
      setNotice('Cupo reservado correctamente.');
      await load();
    } catch (requestError) { setFormError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const cancelReservation = async (trainingId, reservationId) => {
    try {
      await api.post(`/trainings/${trainingId}/reservations/${reservationId}/cancel/`, {});
      setNotice('Reserva cancelada; el cupo quedó disponible.');
      await load();
      if (roster) setRoster(null);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const markAttendance = async (training, reservation, statusValue) => {
    const existing = attendance.find((item) => item.training === training.id && item.athlete === reservation.athlete);
    const payload = { training: training.id, athlete: reservation.athlete, status: statusValue };
    try {
      if (existing) await api.patch(`/attendance/${existing.id}/`, payload);
      else await api.post('/attendance/', payload);
      setNotice('Asistencia actualizada.');
      const records = await readCollection('/attendance/');
      setAttendance(records);
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const removeTraining = async (training) => {
    if (!window.confirm(`¿Eliminar la clase “${training.title}”?`)) return;
    try { await api.delete(`/trainings/${training.id}/`); await load(); }
    catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const openRoster = (training) => setRoster({ training, reservations: reservationMap[training.id] || [] });
  const planned = trainings.filter((training) => training.status === 'SCHEDULED');
  const otherTrainings = trainings.filter((training) => training.status !== 'SCHEDULED');

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">AGENDA Y RESERVAS</p><h1>Clases y cupos</h1><p className="page-description">Programa las sesiones, administra el aforo y controla la lista del día.</p></div>{isStaff && <button className="button primary-btn" onClick={() => { setEditor({}); setFormError(''); }}><Plus size={16} /> Programar clase</button>}</header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}
    {loading ? <div className="empty-state">Cargando agenda...</div> : planned.length ? <div className="training-grid">{planned.map((training) => {
      const reservations = reservationMap[training.id] || [];
      const ownReservation = reservations[0];
      const full = (training.reserved_count || 0) >= training.capacity;
      return <article className="training-card" key={training.id}>
        <div className="training-card-top"><span className="activity-tag">{activityLabels[training.activity_type] || training.activity_type}</span>{isStaff && <button className="icon-button table-action" title="Editar clase" aria-label="Editar clase" onClick={() => { setEditor(training); setFormError(''); }}><Pencil size={15} /></button>}</div>
        <h2>{training.title}</h2>
        <p className="training-description">{training.description || training.objectives || 'Sesión de entrenamiento del club.'}</p>
        <div className="training-meta"><span><CalendarDays size={15} />{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { weekday: 'short', day: 'numeric', month: 'short' })}</span><span><Clock3 size={15} />{training.start_time?.slice(0, 5)} · {training.duration_minutes} min</span><span><Users size={15} />{training.reserved_count || 0}/{training.capacity} cupos</span></div>
        <div className="capacity-track"><span style={{ width: `${Math.min(100, (training.reserved_count || 0) / Math.max(1, training.capacity) * 100)}%` }} /></div>
        <div className="training-actions">{isStaff && <button className="button button-secondary" onClick={() => openRoster(training)}><Users size={15} /> Lista ({training.reserved_count || 0})</button>}{isStaff ? <><button className="button button-secondary" disabled={full} onClick={() => { setReserveTarget(training); setAthleteId(''); setFormError(''); }}>{full ? 'Completa' : 'Inscribir'}</button><button className="icon-button delete-action" title="Eliminar clase" aria-label="Eliminar clase" onClick={() => removeTraining(training)}><X size={16} /></button></> : ownReservation ? <button className="button button-danger" onClick={() => cancelReservation(training.id, ownReservation.id)}>Cancelar mi cupo</button> : <button className="button primary-btn" disabled={full || busy} onClick={() => makeReservation(training)}>{full ? 'Completa' : 'Reservar cupo'}</button>}</div>
      </article>;
    })}</div> : <div className="surface-panel empty-state">No hay clases programadas.{isStaff && ' Programa la primera para abrir reservas.'}</div>}
    {otherTrainings.length > 0 && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">HISTORIAL</p><h2>Clases cerradas o canceladas</h2></div></div><div className="closed-training-list">{otherTrainings.map((training) => <div key={training.id}><span>{training.title}</span><span>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL')}</span><span className="status-pill">{statusLabels[training.status]}</span>{isStaff && <button className="icon-button delete-action" onClick={() => removeTraining(training)} aria-label="Eliminar clase"><X size={15} /></button>}</div>)}</div></section>}

    {editor && <TrainingForm initial={editor.id ? editor : undefined} groups={groups} onClose={() => setEditor(null)} onSubmit={saveTraining} busy={busy} error={formError} />}
    {reserveTarget && isStaff && <div className="modal-scrim"><section className="form-dialog roster-dialog" role="dialog" aria-modal="true"><header className="dialog-heading"><div><p className="eyebrow">INSCRIPCIÓN A CLASE</p><h2>{reserveTarget.title}</h2></div><button className="icon-button dialog-close" onClick={() => setReserveTarget(null)} aria-label="Cerrar"><X size={19} /></button></header><div className="resource-form"><label className="field-label"><span>Deportista *</span><select className="control" value={athleteId} onChange={(event) => setAthleteId(event.target.value)}><option value="">Seleccionar deportista</option>{athletes.map((athlete) => <option key={athlete.id} value={athlete.id}>{athlete.first_name} {athlete.last_name}</option>)}</select></label>{formError && <div className="notice notice-error">{formError}</div>}<footer className="dialog-actions"><button className="button button-secondary" onClick={() => setReserveTarget(null)}>Cancelar</button><button className="button primary-btn" disabled={!athleteId || busy} onClick={() => makeReservation(reserveTarget, athleteId)}>{busy ? 'Reservando...' : 'Confirmar cupo'}</button></footer></div></section></div>}
    {roster && <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setRoster(null); }}><section className="form-dialog roster-dialog" role="dialog" aria-modal="true"><header className="dialog-heading"><div><p className="eyebrow">PADRÓN DE LA CLASE</p><h2>{roster.training.title}</h2><p className="page-description">{roster.reservations.length} reservas activas · {roster.training.capacity} cupos</p></div><button className="icon-button dialog-close" onClick={() => setRoster(null)} aria-label="Cerrar"><X size={19} /></button></header><div className="roster-list">{roster.reservations.length ? roster.reservations.map((reservation) => {
      const attendanceRecord = attendance.find((item) => item.training === roster.training.id && item.athlete === reservation.athlete);
      return <div className="roster-row" key={reservation.id}><div className="roster-person"><span className="roster-avatar">{reservation.athlete_name?.slice(0, 1) || 'D'}</span><div><strong>{reservation.athlete_name || `Deportista #${reservation.athlete}`}</strong><small>{attendanceRecord ? 'Asistencia registrada' : 'Pendiente de marcar'}</small></div></div><div className="roster-controls">{isStaff ? <select className="control attendance-select" aria-label="Estado de asistencia" value={attendanceRecord?.status || ''} onChange={(event) => markAttendance(roster.training, reservation, event.target.value)}><option value="" disabled>Marcar asistencia</option>{Object.entries(attendanceLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select> : <span className="status-pill">{attendanceLabels[attendanceRecord?.status] || 'Reservado'}</span>}{isStaff && <button className="icon-button delete-action" title="Cancelar reserva" aria-label="Cancelar reserva" onClick={() => cancelReservation(roster.training.id, reservation.id)}><X size={16} /></button>}</div></div>;
    }) : <div className="empty-state">Aún no hay reservas para esta clase.</div>}</div><footer className="dialog-actions roster-footer"><button className="button button-secondary" onClick={() => setRoster(null)}>Cerrar lista</button></footer></section></div>}
  </section>;
}