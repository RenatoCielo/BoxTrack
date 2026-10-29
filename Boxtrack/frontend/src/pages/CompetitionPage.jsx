import { useEffect, useState } from 'react';
import { Swords, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const requestLabels = { PENDING: 'Pendiente', APPROVED: 'Aprobada', REJECTED: 'Rechazada' };
const matchLabels = { PROPOSED: 'Propuesto', ACCEPTED: 'Confirmado', DECLINED: 'Rechazado', CANCELLED: 'Cancelado', COMPLETED: 'Realizado' };
const resultLabels = { WIN: 'Victoria', LOSS: 'Derrota', DRAW: 'Empate' };
const inverseResult = { WIN: 'LOSS', LOSS: 'WIN', DRAW: 'DRAW' };
const dateLabel = (value) => (value ? new Date(`${value}T12:00:00`).toLocaleDateString('es-CL') : '—');
const today = () => new Date().toLocaleDateString('en-CA');

export function CompetitionPage() {
  const { user } = useAuth();
  const role = user?.role;
  const isStaff = role === 'ADMIN' || role === 'TRAINER';
  const [requests, setRequests] = useState([]);
  const [matches, setMatches] = useState([]);
  const [athletes, setAthletes] = useState([]);
  const [rivalClubs, setRivalClubs] = useState([]);
  const [directory, setDirectory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reviewing, setReviewing] = useState(null);
  const [reviewNote, setReviewNote] = useState('');
  const [matchPanel, setMatchPanel] = useState(null);
  const [requestForm, setRequestForm] = useState({ athlete: '', request_note: '' });
  const [matchForm, setMatchForm] = useState({ challenger_athlete: '', opponent_club: '', opponent_athlete: '', fight_date: '', event: '', location: '', category: '', fight_type: 'AMATEUR', notes: '' });

  const load = async () => {
    setError('');
    try {
      const [requestRows, matchRows] = await Promise.all([
        api.get('/competitions/competitor-requests/').then((response) => response.data),
        api.get('/competitions/matches/').then((response) => response.data)
      ]);
      setRequests(requestRows);
      setMatches(matchRows);
      if (isStaff) {
        const [athleteRows, clubRows] = await Promise.all([
          readCollection('/athletes/?status=ACTIVE'),
          api.get('/competitions/rival-clubs/').then((response) => response.data)
        ]);
        setAthletes(athleteRows.filter((athlete) => athlete.status === 'ACTIVE'));
        setRivalClubs(clubRows);
      }
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    setDirectory([]);
    if (!matchForm.opponent_club) return undefined;
    let cancelled = false;
    api.get(`/competitions/directory/?club=${encodeURIComponent(matchForm.opponent_club)}`)
      .then((response) => { if (!cancelled) setDirectory(response.data); })
      .catch((requestError) => { if (!cancelled) setError(getErrorMessage(requestError)); });
    return () => { cancelled = true; };
  }, [matchForm.opponent_club]);

  const run = async (action, success) => {
    setBusy(true);
    setError('');
    try {
      await action();
      setNotice(success);
      await load();
    } catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setBusy(false); }
  };

  const submitRequest = (event) => {
    event.preventDefault();
    run(async () => {
      await api.post('/competitions/competitor-requests/', requestForm);
      setRequestForm({ athlete: '', request_note: '' });
    }, 'Solicitud enviada al administrador.');
  };
  const reviewRequest = (item, decision) => {
    run(async () => {
      await api.post(`/competitions/competitor-requests/${item.id}/review/`, { decision, review_note: reviewNote });
      setReviewing(null);
      setReviewNote('');
    }, decision === 'APPROVE' ? 'Deportista aprobado como competidor.' : 'Solicitud rechazada.');
  };
  const submitMatch = (event) => {
    event.preventDefault();
    run(async () => {
      await api.post('/competitions/matches/', matchForm);
      setMatchForm({ ...matchForm, opponent_club: '', opponent_athlete: '', event: '', location: '', notes: '' });
    }, 'Propuesta enviada al club rival.');
  };
  const matchAction = (match, action, success, payload = {}) => run(async () => {
    await api.post(`/competitions/matches/${match.id}/${action}/`, payload);
    setMatchPanel(null);
  }, success);
  const registerResult = (match, outcome) => matchAction(match, 'result', 'Resultado registrado en ambos historiales.', { result: outcome });

  const requestable = athletes.filter((athlete) => !athlete.is_competitor && !requests.some((item) => item.athlete === athlete.id && item.status === 'PENDING')
    && (role !== 'TRAINER' || athlete.assigned_trainer === user.id));
  const ownCompetitors = athletes.filter((athlete) => athlete.is_competitor && (role === 'ADMIN' || athlete.assigned_trainer === user.id));
  const rivalAthletes = directory;
  const pending = requests.filter((item) => item.status === 'PENDING');
  const myClub = typeof user?.club === 'object' ? user.club?.id : user?.club;

  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">EQUIPO COMPETITIVO</p><h1>Competidores y combates</h1><p className="page-description">{isStaff ? 'Solicita el paso de deportistas a competidor y coordina combates con otros clubes.' : 'Consulta tus combates programados y sus resultados.'}</p></div></header>
    {notice && <div className="notice notice-success" role="status">{notice}<button className="icon-button" onClick={() => setNotice('')} aria-label="Cerrar aviso"><X size={15} /></button></div>}
    {error && <div className="notice notice-error">{error}</div>}
    {loading ? <div className="empty-state">Cargando...</div> : <>
      {role !== 'ATHLETE' && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">PASO A COMPETIDOR</p><h2>Solicitudes{role === 'ADMIN' ? ` (${pending.length} pendientes)` : ''}</h2></div></div>
        {role === 'TRAINER' && <form className="competition-form" onSubmit={submitRequest}>
          <label className="field-label"><span>Deportista asignado</span><select className="control" required value={requestForm.athlete} onChange={(event) => setRequestForm({ ...requestForm, athlete: event.target.value })}><option value="">Selecciona...</option>{requestable.map((athlete) => <option key={athlete.id} value={athlete.id}>{`${athlete.first_name} ${athlete.last_name}`}</option>)}</select></label>
          <label className="field-label"><span>Motivo</span><input className="control" value={requestForm.request_note} onChange={(event) => setRequestForm({ ...requestForm, request_note: event.target.value })} /></label>
          <button className="button primary-btn" disabled={busy || !requestForm.athlete}>Solicitar paso a competidor</button>
        </form>}
        <div className="closed-training-list competition-list">{requests.map((item) => <div key={item.id}>
          <strong>{item.athlete_name}</strong> <span className="status-pill">{requestLabels[item.status]}</span>
          <span> Solicitó: {item.requested_by_name || '—'} · {dateLabel(item.created_at?.slice(0, 10))}</span>
          {item.request_note && <span> · {item.request_note}</span>}{item.review_note && <span> · Respuesta: {item.review_note}</span>}
          {role === 'ADMIN' && item.status === 'PENDING' && (reviewing?.id === item.id
            ? <span className="inline-review"><input className="control" aria-label="Nota (opcional)" placeholder="Nota (opcional)" value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} /><button className="button primary-btn" disabled={busy} onClick={() => reviewRequest(item, reviewing.decision)}>{reviewing.decision === 'APPROVE' ? 'Confirmar aprobación' : 'Confirmar rechazo'}</button><button className="button button-secondary" disabled={busy} onClick={() => { setReviewing(null); setReviewNote(''); }}>Volver</button></span>
            : <><button className="button primary-btn" disabled={busy} onClick={() => { setReviewing({ id: item.id, decision: 'APPROVE' }); setReviewNote(''); }}>Aprobar</button><button className="button button-secondary" disabled={busy} onClick={() => { setReviewing({ id: item.id, decision: 'REJECT' }); setReviewNote(''); }}>Rechazar</button></>)}
        </div>)}{!requests.length && <div className="empty-state">No hay solicitudes.</div>}</div>
      </section>}

      {isStaff && <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">COMBATES ENTRE CLUBES</p><h2>Proponer combate</h2></div></div>
        <form className="competition-form" onSubmit={submitMatch}>
          <label className="field-label"><span>Mi competidor</span><select className="control" required value={matchForm.challenger_athlete} onChange={(event) => setMatchForm({ ...matchForm, challenger_athlete: event.target.value })}><option value="">Selecciona...</option>{ownCompetitors.map((athlete) => <option key={athlete.id} value={athlete.id}>{`${athlete.first_name} ${athlete.last_name}`}</option>)}</select></label>
          <label className="field-label"><span>Club rival</span><select className="control" required value={matchForm.opponent_club} onChange={(event) => setMatchForm({ ...matchForm, opponent_club: event.target.value, opponent_athlete: '' })}><option value="">Selecciona un club...</option>{rivalClubs.map((club) => <option key={club.id} value={club.id}>{club.name} ({club.competitor_count})</option>)}</select></label>
          <label className="field-label"><span>Peleador rival</span><select className="control" required disabled={!matchForm.opponent_club || !rivalAthletes.length} value={matchForm.opponent_athlete} onChange={(event) => setMatchForm({ ...matchForm, opponent_athlete: event.target.value })}><option value="">Selecciona un peleador...</option>{rivalAthletes.map((row) => <option key={row.id} value={row.id}>{row.name}{row.category ? ` (${row.category})` : ''}</option>)}</select></label>
          <label className="field-label"><span>Fecha</span><input className="control" type="date" required min={today()} value={matchForm.fight_date} onChange={(event) => setMatchForm({ ...matchForm, fight_date: event.target.value })} /></label>
          <label className="field-label"><span>Tipo</span><select className="control" value={matchForm.fight_type} onChange={(event) => setMatchForm({ ...matchForm, fight_type: event.target.value })}><option value="AMATEUR">Amateur</option><option value="PRO">Profesional</option><option value="SPARRING">Sparring</option></select></label>
          <label className="field-label"><span>Evento</span><input className="control" value={matchForm.event} onChange={(event) => setMatchForm({ ...matchForm, event: event.target.value })} /></label>
          <label className="field-label"><span>Lugar</span><input className="control" value={matchForm.location} onChange={(event) => setMatchForm({ ...matchForm, location: event.target.value })} /></label>
          <button className="button primary-btn" disabled={busy}><Swords size={15} /> Proponer combate</button>
        </form>
        {!rivalClubs.length && <p className="page-description">No hay otros clubes aprobados y activos disponibles para proponer un combate.</p>}
        {matchForm.opponent_club && !rivalAthletes.length && <p className="page-description">Este club todavía no tiene peleadores activos aprobados como competidores.</p>}
      </section>}

      <section className="surface-panel"><div className="section-heading"><div><p className="eyebrow">AGENDA</p><h2>Combates</h2></div></div>
        <div className="closed-training-list competition-list">{matches.map((match) => {
          const mine = match.challenger_club === myClub;
          const canRespond = isStaff && !mine && match.status === 'PROPOSED';
          const canCancel = isStaff && ['PROPOSED', 'ACCEPTED'].includes(match.status) && (mine || match.status === 'ACCEPTED');
          const canResult = isStaff && match.status === 'ACCEPTED' && match.fight_date <= today();
          const result = match.challenger_result && (mine ? match.challenger_result : inverseResult[match.challenger_result]);
          return <div key={match.id}>
            <strong>{match.challenger_athlete_name} ({match.challenger_club_name}) vs {match.opponent_athlete_name} ({match.opponent_club_name})</strong>
            <span className="status-pill">{matchLabels[match.status]}</span>
            <span> {dateLabel(match.fight_date)}{match.event ? ` · ${match.event}` : ''}{match.location ? ` · ${match.location}` : ''}</span>
            {result && <span> · Resultado del club: {resultLabels[result]}</span>}
            {canRespond && <><button className="button primary-btn" disabled={busy} onClick={() => matchAction(match, 'accept', 'Combate confirmado.')}>Aceptar</button><button className="button button-secondary" disabled={busy} onClick={() => matchAction(match, 'decline', 'Propuesta rechazada.')}>Rechazar</button></>}
            {canResult && (matchPanel?.id === match.id && matchPanel.type === 'result'
              ? <span className="inline-review"><strong>¿Quién ganó?</strong><button className="button primary-btn" disabled={busy} onClick={() => registerResult(match, 'WIN')}>{match.challenger_athlete_name}</button><button className="button primary-btn" disabled={busy} onClick={() => registerResult(match, 'LOSS')}>{match.opponent_athlete_name}</button><button className="button button-secondary" disabled={busy} onClick={() => registerResult(match, 'DRAW')}>Empate</button><button className="button button-secondary" onClick={() => setMatchPanel(null)}>Volver</button></span>
              : <button className="button primary-btn" disabled={busy} onClick={() => setMatchPanel({ id: match.id, type: 'result' })}>Registrar resultado</button>)}
            {canCancel && (matchPanel?.id === match.id && matchPanel.type === 'cancel'
              ? <span className="inline-review"><strong>¿Cancelar este combate?</strong><button className="button button-secondary" disabled={busy} onClick={() => matchAction(match, 'cancel', 'Combate cancelado.')}>Sí, cancelar</button><button className="button button-secondary" onClick={() => setMatchPanel(null)}>No</button></span>
              : <button className="button button-secondary" disabled={busy} onClick={() => setMatchPanel({ id: match.id, type: 'cancel' })}>Cancelar</button>)}
          </div>;
        })}{!matches.length && <div className="empty-state">Todavía no hay combates entre clubes.</div>}</div>
      </section>
    </>}
  </section>;
}
