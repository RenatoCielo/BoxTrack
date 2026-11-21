import { useEffect, useState } from 'react';
import { CalendarDays, Check, Clock3, Pencil, Plus, Users, X, Repeat2, Pause, Play } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const activityLabels = { TECHNICAL: 'Técnica', TACTICAL: 'Táctica', PHYSICAL: 'Preparación física', SPARRING: 'Sparring', COMPETITION: 'Preparación competitiva' };
const statusLabels = { SCHEDULED: 'Programada', CANCELLED: 'Cancelada', COMPLETED: 'Completada' };
const attendanceLabels = { PRESENT: 'Presente', ABSENT: 'Ausente', JUSTIFIED: 'Justificado', LATE: 'Atrasado' };
const weekdayOptions = [
  ['0', 'Lunes'], ['1', 'Martes'], ['2', 'Miércoles'], ['3', 'Jueves'],
  ['4', 'Viernes'], ['5', 'Sábado'], ['6', 'Domingo']
];
const today = () => {
  const localDate = new Date();
  localDate.setMinutes(localDate.getMinutes() - localDate.getTimezoneOffset());
  return localDate.toISOString().slice(0, 10);
};
const currentMonday = () => {
  const date = new Date(`${today()}T12:00:00`);
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
};

function nextWeekdayDate(weekday) {
  const date = new Date(`${today()}T12:00:00`);
  const targetDay = (weekday + 1) % 7;
  const delta = (targetDay - date.getDay() + 7) % 7;
  date.setDate(date.getDate() + delta);
  return date.toISOString().slice(0, 10);
}

function TrainingForm({ initial, groups, trainers, isTrainer, weekly, onClose, onSubmit, busy, error }) {
  const [values, setValues] = useState(() => {
    const defaultWeekday = (new Date(`${today()}T12:00:00`).getDay() + 6) % 7;
    const initialValues = {
      title: '', description: '', activity_type: 'TECHNICAL', group: '', trainer: '',
      scheduled_date: today(), weekdays: [String(defaultWeekday)], starts_on: today(),
      ends_on: '', start_time: '18:00', duration_minutes: 60, capacity: 20,
      status: 'SCHEDULED', objectives: '', ...initial
    };
    return {
      ...initialValues,
      group: initialValues.group ? String(initialValues.group) : '',
      trainer: initialValues.trainer ? String(initialValues.trainer) : '',
      weekdays: (initialValues.weekdays || []).map(String)
    };
  });
  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });
  const toggleWeekday = (weekday) => setValues((current) => ({
    ...current,
    weekdays: current.weekdays.includes(weekday)
      ? current.weekdays.filter((day) => day !== weekday)
      : [...current.weekdays, weekday]
  }));
  return <div className="modal-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="training-dialog-title">
      <header className="dialog-heading"><div><p className="eyebrow">AGENDA DEL CLUB</p><h2 id="training-dialog-title">{weekly ? initial?.id ? 'Editar horario semanal' : 'Crear horario semanal' : initial?.id ? 'Editar clase' : 'Programar clase'}</h2><p className="page-description">{weekly ? 'Las clases se crearán automáticamente; sin fecha de término, el horario sigue activo. Los cambios afectan las clases futuras que aún no se generaron.' : 'Elige una actividad y completa el día, hora y cupos.'}</p></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
      <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSubmit(values, weekly); }}>
        <div className="field-grid">
          <label className="field-label field-wide"><span>Nombre de la clase *</span><input className="control" name="title" required value={values.title} onChange={update} /></label>
          <label className="field-label"><span>Actividad</span><select className="control" name="activity_type" value={values.activity_type} onChange={update}>{Object.entries(activityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
          {weekly
            ? <fieldset className="weekday-picker field-wide"><legend>Días de la semana *</legend><div>{weekdayOptions.map(([value, label]) => <label key={value}><input type="checkbox" checked={values.weekdays.includes(value)} onChange={() => toggleWeekday(value)} /><span>{label}</span></label>)}</div></fieldset>
            : <label className="field-label"><span>Fecha *</span><input className="control" type="date" name="scheduled_date" required value={values.scheduled_date} onChange={update} /></label>}
          {weekly && <label className="field-label"><span>Vigente desde *</span><input className="control" type="date" name="starts_on" required value={values.starts_on} onChange={update} /></label>}
          {weekly && <label className="field-label"><span>Vigente hasta <small>(opcional)</small></span><input className="control" type="date" name="ends_on" min={values.starts_on} value={values.ends_on || ''} onChange={update} /></label>}
          <label className="field-label"><span>Hora *</span><input className="control" type="time" name="start_time" required value={values.start_time} onChange={update} /></label>
          <label className="field-label"><span>Duración (min)</span><input className="control" type="number" min="1" name="duration_minutes" value={values.duration_minutes} onChange={update} /></label>
          <label className="field-label"><span>Cupos máximos</span><input className="control" type="number" min="1" name="capacity" value={values.capacity} onChange={update} /></label>
          <label className="field-label"><span>Grupo</span><select className="control" name="group" value={values.group || ''} onChange={update}><option value="">Todos los grupos</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
          {!isTrainer && <label className="field-label"><span>Entrenador</span><select className="control" name="trainer" value={values.trainer || ''} onChange={update}><option value="">Sin asignar</option>{trainers.map((trainer) => <option key={trainer.user} value={trainer.user}>{trainer.user_name || trainer.user_username || `Entrenador #${trainer.user}`}</option>)}</select></label>}
          {initial?.id && !weekly && <label className="field-label"><span>Estado</span><select className="control" name="status" value={values.status} onChange={update}>{Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
          <label className="field-label field-wide"><span>Descripción</span><textarea className="control" name="description" rows="2" value={values.description} onChange={update} /></label>
          <label className="field-label field-wide"><span>Objetivos de la clase</span><textarea className="control" name="objectives" rows="2" value={values.objectives} onChange={update} /></label>
        </div>
        {error && <div className="notice notice-error">{error}</div>}
        <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy || (weekly && values.weekdays.length === 0)}>{busy ? 'Guardando...' : weekly ? 'Guardar horario semanal' : 'Guardar clase'}</button></footer>
      </form>
    </section>
  </div>;
}

export function TrainingPage() {
  const { user } = useAuth();
  const isStaff = ['ADMIN', 'TRAINER'].includes(user?.role);
  const [staffView, setStaffView] = useState(() => localStorage.getItem('boxtrack.staffTrainingView') || 'WEEK');
  const [staffDate, setStaffDate] = useState(today);
  const [agendaQuery, setAgendaQuery] = useState('');
  const [activityFilter, setActivityFilter] = useState('ALL');
  const [weekStart, setWeekStart] = useState(currentMonday);
  const [membership, setMembership] = useState(null);
  const [trainings, setTrainings] = useState([]);
  const [groups, setGroups] = useState([]);
  const [trainers, setTrainers] = useState([]);
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editor, setEditor] = useState(null);
  const [roster, setRoster] = useState(null);
  const [rosterLoading, setRosterLoading] = useState(false);
  const [attendanceSavingId, setAttendanceSavingId] = useState(null);
  const [reserveTarget, setReserveTarget] = useState(null);
  const [athleteId, setAthleteId] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const load = async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const [trainingRows, groupRows, athleteRows, attendanceRows, scheduleRows, trainerRows] = await Promise.all([
        readCollection(isStaff ? '/trainings/' : `/trainings/?week_start=${weekStart}`),
        isStaff ? readCollection('/groups/') : Promise.resolve([]),
        isStaff ? readCollection('/athletes/') : Promise.resolve([]),
        isStaff ? readCollection('/attendance/') : Promise.resolve([]),
        isStaff ? readCollection('/trainings/weekly-schedules/') : Promise.resolve([]),
        user?.role === 'ADMIN' ? readCollection('/trainers/') : Promise.resolve([])
      ]);
      const membershipResponse = !isStaff ? await api.get(`/clubs/memberships/current/?week_start=${weekStart}`) : null;
      setTrainings(trainingRows.sort((first, second) => `${first.scheduled_date} ${first.start_time}`.localeCompare(`${second.scheduled_date} ${second.start_time}`)));
      setGroups(groupRows.filter((group) => group.is_active));
      setWeeklySchedules(scheduleRows);
      setTrainers(trainerRows);
      setAthletes(athleteRows.filter((athlete) => athlete.status === 'ACTIVE'));
      setAttendance(attendanceRows);
      setMembership(membershipResponse?.data || null);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const refresh = () => { if (document.visibilityState === 'visible') load({ silent: true }); };
    const timer = setInterval(refresh, 15000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [weekStart]);
  useEffect(() => {
    localStorage.setItem('boxtrack.staffTrainingView', staffView);
  }, [staffView]);

  const saveTraining = async (values, weekly) => {
    setBusy(true);
    setFormError('');
    const payload = {
      ...values,
      duration_minutes: Number(values.duration_minutes),
      capacity: Number(values.capacity),
      group: values.group ? Number(values.group) : null,
      trainer: values.trainer ? Number(values.trainer) : null
    };
    if (weekly) {
      payload.weekdays = values.weekdays.map(Number);
      payload.ends_on = values.ends_on || null;
      delete payload.scheduled_date;
      delete payload.status;
      delete payload.weekly;
    } else {
      delete payload.weekdays;
      delete payload.starts_on;
      delete payload.ends_on;
    }
    try {
      if (editor?.id) await api.patch(`${weekly ? '/trainings/weekly-schedules/' : '/trainings/'}${editor.id}/`, payload);
      else await api.post(weekly ? '/trainings/weekly-schedules/' : '/trainings/', payload);
      setEditor(null);
      setNotice(weekly ? 'Horario semanal guardado; las clases se generan automáticamente.' : 'Clase guardada.');
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
    setError('');
    setAttendanceSavingId(reservation.id);
    try {
      const response = existing
        ? await api.patch(`/attendance/${existing.id}/`, payload)
        : await api.post('/attendance/', payload);
      setAttendance((current) => existing
        ? current.map((item) => item.id === existing.id ? response.data : item)
        : [...current, response.data]);
      setNotice(statusValue === 'PRESENT'
        ? 'Presente: el cupo semanal de la membresía quedó consumido.'
        : 'Ausente: se liberó el cupo semanal de la membresía.');
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setAttendanceSavingId(null);
    }
  };

  const removeTraining = async (training) => {
    if (!window.confirm(training.weekly_schedule
      ? `¿Cancelar la clase “${training.title}”? El horario semanal seguirá activo.`
      : `¿Eliminar la clase “${training.title}”?`)) return;
    try {
      if (training.weekly_schedule) await api.patch(`/trainings/${training.id}/`, { status: 'CANCELLED' });
      else await api.delete(`/trainings/${training.id}/`);
      await load();
    }
    catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const openRoster = async (training) => {
    setError('');
    setRoster({ training, reservations: [] });
    setRosterLoading(true);
    try {
      const { data } = await api.get(`/trainings/${training.id}/reservations/`);
      setRoster({ training, reservations: data });
    } catch (requestError) {
      setRoster(null);
      setError(getErrorMessage(requestError));
    } finally {
      setRosterLoading(false);
    }
  };
  const toggleWeeklySchedule = async (schedule) => {
    setError('');
    try {
      await api.patch(`/trainings/weekly-schedules/${schedule.id}/`, { is_active: !schedule.is_active });
      setNotice(schedule.is_active ? 'Horario pausado; las clases ya creadas se mantienen en agenda.' : 'Horario semanal reactivado.');
      await load();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    }
  };
  const useScheduleForOneOff = (schedule) => {
    setEditor({
      title: schedule.title,
      description: schedule.description,
      activity_type: schedule.activity_type,
      group: schedule.group || '',
      trainer: schedule.trainer || '',
      scheduled_date: nextWeekdayDate(schedule.weekdays[0]),
      start_time: schedule.start_time,
      duration_minutes: schedule.duration_minutes,
      capacity: schedule.capacity,
      objectives: schedule.objectives,
      status: 'SCHEDULED'
    });
    setFormError('');
  };
  const editWeeklySchedule = (schedule) => {
    setEditor({ ...schedule, weekly: true });
    setFormError('');
  };
  const planned = trainings.filter((training) => training.status === 'SCHEDULED');
  const otherTrainings = trainings.filter((training) => training.status !== 'SCHEDULED');
  const agendaMonday = new Date(`${staffDate}T12:00:00`);
  agendaMonday.setDate(agendaMonday.getDate() - ((agendaMonday.getDay() + 6) % 7));
  const agendaWeekStart = agendaMonday.toISOString().slice(0, 10);
  const agendaWeekEndDate = new Date(agendaMonday);
  agendaWeekEndDate.setDate(agendaWeekEndDate.getDate() + 7);
  const agendaWeekEnd = agendaWeekEndDate.toISOString().slice(0, 10);
  const filteredPlanned = planned.filter((training) => {
    if (staffView === 'DAY' && training.scheduled_date !== staffDate) return false;
    if (staffView === 'WEEK' && (training.scheduled_date < agendaWeekStart || training.scheduled_date >= agendaWeekEnd)) return false;
    if (staffView === 'UPCOMING' && training.scheduled_date < staffDate) return false;
    if (activityFilter !== 'ALL' && training.activity_type !== activityFilter) return false;
    return `${training.title} ${training.description || ''}`.toLowerCase().includes(agendaQuery.toLowerCase());
  });
  const weekDates = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(`${weekStart}T12:00:00`);
    date.setDate(date.getDate() + index);
    return date.toISOString().slice(0, 10);
  });
  const athleteCalendar = membership ? <>
    <section className="member-plan-summary">
      <div><p className="eyebrow">TU PLAN ACTIVO</p><h2>{membership.plan_name}</h2><p>{membership.plan_duration} · {membership.classes_per_week == null ? 'Clases ilimitadas por semana' : `${membership.classes_per_week} clases por semana`}</p><small className="member-plan-usage">{membership.classes_used_this_week || 0} clases asistidas esta semana</small></div>
      <div className="member-plan-expiry"><span>Vence el</span><strong>{new Date(`${membership.expires_on}T12:00:00`).toLocaleDateString('es-CL')}</strong></div>
      <div className="member-plan-remaining"><span>{membership.classes_per_week == null ? 'Cupos esta semana' : 'Disponibles para reservar'}</span><strong>{membership.classes_per_week == null ? 'Ilimitados' : membership.classes_remaining_this_week}</strong><small>{membership.classes_per_week != null ? `${membership.classes_reserved_this_week || 0} usados o reservados` : ''}</small></div>
    </section>
    <section className="surface-panel member-calendar-panel">
      <header className="member-calendar-heading">
        <div><p className="eyebrow">RESERVA DE CLASES</p><h2>Tu semana</h2><p>{new Date(`${weekDates[0]}T12:00:00`).toLocaleDateString('es-CL', { day: 'numeric', month: 'long' })} – {new Date(`${weekDates[6]}T12:00:00`).toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' })}</p></div>
        <div className="member-week-controls"><button className="button button-secondary" onClick={() => { const date = new Date(`${weekStart}T12:00:00`); date.setDate(date.getDate() - 7); setWeekStart(date.toISOString().slice(0, 10)); }}>Semana anterior</button><button className="button button-secondary" onClick={() => setWeekStart(currentMonday())}>Esta semana</button><button className="button button-secondary" onClick={() => { const date = new Date(`${weekStart}T12:00:00`); date.setDate(date.getDate() + 7); setWeekStart(date.toISOString().slice(0, 10)); }}>Semana siguiente</button></div>
      </header>
      <div className="member-calendar-scroll"><div className="member-week-grid">{weekDates.map((dateValue) => {
        const dayTrainings = planned.filter((training) => training.scheduled_date === dateValue);
        const date = new Date(`${dateValue}T12:00:00`);
        return <section className="member-week-day" key={dateValue}>
          <header><span>{date.toLocaleDateString('es-CL', { weekday: 'short' })}</span><strong>{date.getDate()}</strong></header>
          <div className="member-day-classes">{dayTrainings.length ? dayTrainings.map((training) => {
            const ownReservationId = training.own_reservation_id;
            const full = (training.reserved_count || 0) >= training.capacity;
            return <article className={`member-class-card${ownReservationId ? ' reserved' : ''}`} key={training.id}>
              <span className="activity-tag">{activityLabels[training.activity_type] || training.activity_type}</span>
              <strong>{training.title}</strong>
              <small><Clock3 size={13} /> {training.start_time?.slice(0, 5)} · {training.duration_minutes} min</small>
              <small><Users size={13} /> {Math.max(0, training.capacity - (training.reserved_count || 0))} cupos disponibles</small>
              {ownReservationId
                ? <button className="button button-danger" onClick={() => cancelReservation(training.id, ownReservationId)}>Cancelar cupo</button>
                : <button className="button primary-btn" disabled={full || busy || (membership.classes_per_week != null && membership.classes_remaining_this_week <= 0)} onClick={() => makeReservation(training)}>{full ? 'Completa' : 'Reservar'}</button>}
            </article>;
          }) : <p className="member-day-empty">Sin clases</p>}</div>
        </section>;
      })}</div></div>
    </section>
  </> : <div className="surface-panel empty-state">No tienes un plan activo disponible para reservas. Contacta al administrador de tu gimnasio.</div>;

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">AGENDA Y RESERVAS</p><h1>Clases y cupos</h1><p className="page-description">Programa las sesiones, administra el aforo y controla la lista del día.</p></div>{isStaff && <div className="heading-actions"><button className="button button-secondary" onClick={() => { setEditor({ weekly: true }); setFormError(''); }}><Repeat2 size={16} /> Horario semanal</button><button className="button primary-btn" onClick={() => { setEditor({}); setFormError(''); }}><Plus size={16} /> Programar clase</button></div>}</header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}
    {isStaff && weeklySchedules.length > 0 && <details className="surface-panel weekly-schedules-panel"><summary className="weekly-schedules-summary"><span><p className="eyebrow">HORARIOS REUTILIZABLES</p><strong>Programación semanal ({weeklySchedules.length})</strong></span><span>Mostrar / ocultar</span></summary><div className="weekly-schedule-list">{weeklySchedules.map((schedule) => <article className="weekly-schedule-row" key={schedule.id}><div><strong>{schedule.title}</strong><span>{schedule.weekdays.map((day) => weekdayOptions.find(([value]) => Number(value) === day)?.[1]).filter(Boolean).join(', ')} · {schedule.start_time.slice(0, 5)} · {schedule.capacity} cupos</span><small>{schedule.ends_on ? `Vigente hasta ${new Date(`${schedule.ends_on}T12:00:00`).toLocaleDateString('es-CL')}` : 'Sin fecha de término'} · {schedule.is_active ? 'Activo' : 'Pausado'}</small></div><div className="weekly-schedule-actions"><button className="button button-secondary" onClick={() => editWeeklySchedule(schedule)}><Pencil size={15} />Editar</button><button className="button button-secondary" onClick={() => useScheduleForOneOff(schedule)}>Usar para una clase</button><button className="button button-secondary" onClick={() => toggleWeeklySchedule(schedule)}>{schedule.is_active ? <Pause size={15} /> : <Play size={15} />}{schedule.is_active ? 'Pausar' : 'Reanudar'}</button></div></article>)}</div></details>}
    {isStaff && <div className="training-agenda-filters">
      <label className="search-field"><input aria-label="Buscar clases" placeholder="Buscar por nombre o descripción..." value={agendaQuery} onChange={(event) => setAgendaQuery(event.target.value)} /></label>
      <label className="field-label"><span>Vista</span><select className="control" value={staffView} onChange={(event) => setStaffView(event.target.value)}><option value="DAY">Un día</option><option value="WEEK">Una semana</option><option value="UPCOMING">Desde esta fecha</option></select></label>
      <label className="field-label"><span>Fecha de referencia</span><input className="control" type="date" value={staffDate} onChange={(event) => setStaffDate(event.target.value)} /></label>
      <label className="field-label"><span>Actividad</span><select className="control" value={activityFilter} onChange={(event) => setActivityFilter(event.target.value)}><option value="ALL">Todas</option>{Object.entries(activityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      <span className="table-count">{filteredPlanned.length} clases</span>
    </div>}
    {loading ? <div className="empty-state">Cargando agenda...</div> : !isStaff ? athleteCalendar : filteredPlanned.length ? <div className="training-grid">{filteredPlanned.map((training) => {
      const ownReservationId = training.own_reservation_id;
      const full = (training.reserved_count || 0) >= training.capacity;
      return <article className="training-card" key={training.id}>
        <div className="training-card-top"><span className="activity-tag">{activityLabels[training.activity_type] || training.activity_type}</span>{isStaff && <button className="icon-button table-action" title="Editar clase" aria-label="Editar clase" onClick={() => { setEditor(training); setFormError(''); }}><Pencil size={15} /></button>}</div>
        <h2>{training.title}</h2>
        <p className="training-description">{training.description || training.objectives || 'Sesión de entrenamiento del club.'}</p>
        <div className="training-meta"><span><CalendarDays size={15} />{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL', { weekday: 'short', day: 'numeric', month: 'short' })}</span><span><Clock3 size={15} />{training.start_time?.slice(0, 5)} · {training.duration_minutes} min</span><span><Users size={15} />{training.reserved_count || 0}/{training.capacity} cupos</span></div>
        <div className="capacity-track"><span style={{ width: `${Math.min(100, (training.reserved_count || 0) / Math.max(1, training.capacity) * 100)}%` }} /></div>
        <div className="training-actions">{isStaff && <><button className="button button-secondary" onClick={() => openRoster(training)}><Check size={15} /> Asistencia</button><button className="button button-secondary" disabled={full} onClick={() => { setReserveTarget(training); setAthleteId(''); setFormError(''); }}>{full ? 'Completa' : 'Inscribir'}</button><button className="icon-button delete-action" title={training.weekly_schedule ? 'Cancelar clase' : 'Eliminar clase'} aria-label={training.weekly_schedule ? 'Cancelar clase' : 'Eliminar clase'} onClick={() => removeTraining(training)}><X size={16} /></button></>}{!isStaff && (ownReservationId ? <button className="button button-danger" onClick={() => cancelReservation(training.id, ownReservationId)}>Cancelar mi cupo</button> : <button className="button primary-btn" disabled={full || busy} onClick={() => makeReservation(training)}>{full ? 'Completa' : 'Reservar cupo'}</button>)}</div>
      </article>;
    })}</div> : <div className="surface-panel empty-state">{planned.length ? 'No hay clases que coincidan con los filtros.' : 'No hay clases programadas.'}{isStaff && !planned.length && ' Programa la primera para abrir reservas.'}</div>}
    {otherTrainings.length > 0 && <details className="surface-panel training-history-panel"><summary><span><p className="eyebrow">HISTORIAL</p><strong>Clases cerradas o canceladas ({otherTrainings.length})</strong></span><span>Mostrar / ocultar</span></summary><div className="closed-training-list">{otherTrainings.map((training) => <div key={training.id}><span>{training.title}</span><span>{new Date(`${training.scheduled_date}T12:00:00`).toLocaleDateString('es-CL')} · {training.start_time?.slice(0, 5)}</span><span className="status-pill">{statusLabels[training.status]}</span>{isStaff && <button className="icon-button delete-action" onClick={() => removeTraining(training)} aria-label="Eliminar clase"><X size={15} /></button>}</div>)}</div></details>}

    {editor && <TrainingForm initial={editor.id || Object.keys(editor).length > 1 ? editor : undefined} groups={groups} trainers={trainers} isTrainer={user?.role === 'TRAINER'} weekly={Boolean(editor.weekly)} onClose={() => setEditor(null)} onSubmit={saveTraining} busy={busy} error={formError} />}
    {reserveTarget && isStaff && <div className="modal-scrim"><section className="form-dialog roster-dialog" role="dialog" aria-modal="true"><header className="dialog-heading"><div><p className="eyebrow">INSCRIPCIÓN A CLASE</p><h2>{reserveTarget.title}</h2></div><button className="icon-button dialog-close" onClick={() => setReserveTarget(null)} aria-label="Cerrar"><X size={19} /></button></header><div className="resource-form"><label className="field-label"><span>Deportista *</span><select className="control" value={athleteId} onChange={(event) => setAthleteId(event.target.value)}><option value="">Seleccionar deportista</option>{athletes.map((athlete) => <option key={athlete.id} value={athlete.id}>{athlete.display_name || `${athlete.first_name} ${athlete.last_name}`}</option>)}</select></label>{formError && <div className="notice notice-error">{formError}</div>}<footer className="dialog-actions"><button className="button button-secondary" onClick={() => setReserveTarget(null)}>Cancelar</button><button className="button primary-btn" disabled={!athleteId || busy} onClick={() => makeReservation(reserveTarget, athleteId)}>{busy ? 'Reservando...' : 'Confirmar cupo'}</button></footer></div></section></div>}
    {roster && <div className="modal-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setRoster(null); }}><section className="form-dialog roster-dialog" role="dialog" aria-modal="true" aria-labelledby="attendance-dialog-title"><header className="dialog-heading"><div><p className="eyebrow">ASISTENCIA DE LA CLASE</p><h2 id="attendance-dialog-title">{roster.training.title}</h2><p className="page-description">{roster.reservations.length} alumnos inscritos · {roster.training.capacity} cupos</p></div><button className="icon-button dialog-close" onClick={() => setRoster(null)} aria-label="Cerrar"><X size={19} /></button></header>{error && <div className="notice notice-error" role="alert">{error}</div>}<div className="roster-list">{rosterLoading ? <div className="empty-state">Cargando alumnos inscritos...</div> : roster.reservations.length ? roster.reservations.map((reservation) => {
      const attendanceRecord = attendance.find((item) => item.training === roster.training.id && item.athlete === reservation.athlete);
      const savingAttendance = attendanceSavingId === reservation.id;
      return <div className="roster-row" key={reservation.id}><div className="roster-person"><span className="roster-avatar">{reservation.athlete_name?.slice(0, 1) || 'D'}</span><div><strong>{reservation.athlete_name || `Deportista #${reservation.athlete}`}</strong><small>{attendanceRecord ? `Estado: ${attendanceLabels[attendanceRecord.status]}` : 'Pendiente de asistencia'}</small></div></div><div className="roster-controls"><button type="button" className={`button attendance-choice${attendanceRecord?.status === 'PRESENT' ? ' selected-present' : ''}`} disabled={savingAttendance || attendanceRecord?.status === 'PRESENT'} onClick={() => markAttendance(roster.training, reservation, 'PRESENT')}>{savingAttendance ? 'Guardando...' : 'Presente'}</button><button type="button" className={`button attendance-choice${attendanceRecord?.status === 'ABSENT' ? ' selected-absent' : ''}`} disabled={savingAttendance || attendanceRecord?.status === 'ABSENT'} onClick={() => markAttendance(roster.training, reservation, 'ABSENT')}>Ausente</button><button className="icon-button delete-action" title="Cancelar inscripción" aria-label="Cancelar inscripción" onClick={() => cancelReservation(roster.training.id, reservation.id)}><X size={16} /></button></div></div>;
    }) : <div className="empty-state">Aún no hay alumnos inscritos en esta clase.</div>}</div><footer className="dialog-actions roster-footer"><button className="button button-secondary" onClick={() => setRoster(null)}>Cerrar asistencia</button></footer></section></div>}
  </section>;
}