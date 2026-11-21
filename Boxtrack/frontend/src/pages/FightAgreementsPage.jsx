import { useEffect, useState } from 'react';
import { CalendarDays, Check, Clock3, Handshake, MapPin, Plus, Send, ShieldX, Swords, Users, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const firstAvailableDate = () => {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
};

const statusLabels = {
  PENDING: 'Esperando respuesta',
  CONFIRMED: 'Combate acordado',
  DECLINED: 'No aceptado',
  CANCELLED: 'Cancelado',
};
const genderLabels = { M: 'Masculino', F: 'Femenino', X: 'Otro' };

const formatDate = (date) => new Date(`${date}T12:00:00`).toLocaleDateString('es-CL', {
  weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
});

const fightCount = (athlete) => athlete?.recorded_fights ?? (athlete?.fight_record
  ? athlete.fight_record.split('-').reduce((total, result) => total + Number(result || 0), 0)
  : 0);

function FighterCard({ name, category, weight, gender, fightRecord, recordedFights, side }) {
  return <div className={`fight-pair-side fight-pair-${side}`}>
    <span>{side === 'home' ? 'GIMNASIO LOCAL' : 'GIMNASIO RIVAL'}</span>
    <strong>{name || 'Pendiente de sugerencia'}</strong>
    <small>{[genderLabels[gender], category || 'Categoría por definir', weight ? `${weight} kg` : null].filter(Boolean).join(' · ')}</small>
    {name && <small>Récord {fightRecord || '0-0-0'} · {recordedFights ?? 0} peleas</small>}
  </div>;
}

function CompetitorGenderPrompt({ athlete, onSaved }) {
  const [gender, setGender] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setGender('');
    setError('');
  }, [athlete?.id]);

  if (!athlete || athlete.gender) return null;

  const save = async () => {
    if (!gender) return;
    setBusy(true);
    setError('');
    try {
      const { data } = await api.patch(`/athletes/${athlete.id}/`, { gender });
      onSaved(data);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return <div className="gender-completion">
    <div><strong>Falta completar el género de {athlete.display_name}.</strong><p>Este dato permite mostrar solo rivales compatibles.</p></div>
    <div className="gender-completion-actions">
      <label className="field-label"><span>Género</span><select className="control" required value={gender} onChange={(event) => setGender(event.target.value)}><option value="">Selecciona una opción</option>{Object.entries(genderLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
      <button type="button" className="button primary-btn" disabled={busy || !gender} onClick={save}>{busy ? 'Guardando...' : 'Guardar y continuar'}</button>
    </div>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
  </div>;
}

function FightBoutCard({ agreement, bout, user, onChange, setNotice }) {
  const ownField = agreement.is_incoming ? 'away_athlete' : 'home_athlete';
  const ownClubId = user?.club?.id;
  const [competitors, setCompetitors] = useState([]);
  const [selection, setSelection] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ownSelected = ownField === 'home_athlete' ? bout.home_athlete : bout.away_athlete;

  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({ club: String(ownClubId || '') });
    if (bout.home_athlete) query.set('home_athlete', bout.home_athlete);
    api.get(`/competitions/agreements/${agreement.id}/competitors/?${query.toString()}`)
      .then(({ data }) => {
        if (active) setCompetitors(Array.isArray(data) ? data : data.results || []);
      })
      .catch((requestError) => {
        if (active) setError(getErrorMessage(requestError));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [agreement.id, bout.home_athlete, ownClubId]);

  const send = async (payload, message) => {
    setBusy(true);
    setError('');
    try {
      await api.patch(`/competitions/agreements/${agreement.id}/bouts/${bout.id}/`, payload);
      setSelection('');
      setNotice(message);
      await onChange();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const selectedFighter = competitors.find((competitor) => String(competitor.id) === selection);
  const ownSelectedName = ownField === 'home_athlete' ? bout.home_athlete_name : bout.away_athlete_name;
  const awaitingResponse = bout.last_suggested_by_club_id === ownClubId;

  return <article className={`fight-pair-card fight-pair-status-${bout.status.toLowerCase()}`}>
    <div className="fight-pair-grid">
      <FighterCard name={bout.home_athlete_name} category={bout.home_athlete_category} weight={bout.home_athlete_weight} gender={bout.home_athlete_gender} fightRecord={bout.home_athlete_fight_record} recordedFights={bout.home_athlete_recorded_fights} side="home" />
      <span className="fight-pair-vs">VS</span>
      <FighterCard name={bout.away_athlete_name} category={bout.away_athlete_category} weight={bout.away_athlete_weight} gender={bout.away_athlete_gender} fightRecord={bout.away_athlete_fight_record} recordedFights={bout.away_athlete_recorded_fights} side="away" />
    </div>
    <div className="fight-pair-record">
      <span className={`agreement-status agreement-${bout.status.toLowerCase()}`}>
        {({ PENDING: 'Propuesta inicial', COUNTERED: 'Contrapropuesta', CONFIRMED: 'Emparejamiento acordado', DECLINED: 'No aceptado', CANCELLED: 'Cancelado' })[bout.status]}
      </span>
      {bout.home_athlete_category && bout.away_athlete_category && <small>{bout.home_athlete_category === bout.away_athlete_category ? 'Misma categoría' : 'Categorías distintas; revisen compatibilidad'}</small>}
    </div>
    {['PENDING', 'COUNTERED'].includes(bout.status) && <div className="fight-counter-controls">
      <label className="field-label">
        <span>{ownSelectedName ? 'Proponer otro competidor de tu gimnasio' : 'Sugiere un competidor de tu gimnasio'}</span>
        <select className="control" value={selection} onChange={(event) => setSelection(event.target.value)} disabled={loading}>
          <option value="">{loading ? 'Cargando plantel...' : 'Selecciona un competidor'}</option>
          {competitors.map((competitor) => <option key={competitor.id} value={competitor.id}>
            {competitor.display_name} · {genderLabels[competitor.gender] || 'Género pendiente'} · Récord {competitor.fight_record} · {competitor.recorded_fights} peleas
          </option>)}
        </select>
      </label>
      {selectedFighter && <div className="match-recommendation"><Users size={15} /><span><strong>{genderLabels[selectedFighter.gender]}</strong> · Récord {selectedFighter.fight_record} · {selectedFighter.recorded_fights} peleas · {selectedFighter.match_reasons?.join(' · ') || selectedFighter.experience_level}</span></div>}
      <div className="fight-agreement-actions">
        {bout.is_incoming && <>
          <button type="button" className="button button-secondary" disabled={busy} onClick={() => send({ status: 'DECLINED' }, 'Se rechazó este emparejamiento.')}><ShieldX size={15} /> Rechazar cruce</button>
          <button type="button" className="button primary-btn" disabled={busy || !bout.home_athlete || !bout.away_athlete} onClick={() => send({ status: 'CONFIRMED' }, 'Se confirmó el emparejamiento.')}><Check size={15} /> Aceptar cruce</button>
        </>}
        {selection && !awaitingResponse && <button type="button" className="button primary-btn" disabled={busy} onClick={() => send({ [ownField]: Number(selection) }, 'Se envió una contrapropuesta de boxeador.')}>{busy ? 'Enviando...' : 'Proponer este competidor'}</button>}
        {awaitingResponse && !bout.is_incoming && <span className="agreement-hint">Tu gimnasio ya sugirió un boxeador. Esperando respuesta.</span>}
      </div>
    </div>}
    {bout.status === 'CONFIRMED' && <div className="fight-agreement-actions">
      <button type="button" className="button button-secondary" disabled={busy} onClick={() => send({ status: 'CANCELLED' }, 'Se canceló el emparejamiento acordado.')}><X size={15} /> Cancelar cruce</button>
    </div>}
    {error && <div className="notice notice-error" role="alert">{error}</div>}
  </article>;
}

function AdditionalBoutForm({ agreement, competitors, onChange, onClose, onAthleteUpdated, setNotice }) {
  const [homeAthlete, setHomeAthlete] = useState('');
  const [awayAthlete, setAwayAthlete] = useState('');
  const [rivalCompetitors, setRivalCompetitors] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const selectedHome = competitors.find((athlete) => String(athlete.id) === homeAthlete);

  useEffect(() => {
    if (!selectedHome?.gender) {
      setRivalCompetitors([]);
      setAwayAthlete('');
      return undefined;
    }
    let active = true;
    const query = new URLSearchParams({ home_athlete: homeAthlete });
    api.get(`/competitions/rivals/${agreement.opponent_club_id}/competitors/?${query.toString()}`)
      .then(({ data }) => { if (active) setRivalCompetitors(Array.isArray(data) ? data : data.results || []); })
      .catch((requestError) => { if (active) setError(getErrorMessage(requestError)); });
    return () => { active = false; };
  }, [agreement.opponent_club_id, homeAthlete, selectedHome?.gender]);

  const save = async (event) => {
    event.preventDefault();
    if (!selectedHome?.gender) {
      setError('Completa el género de tu competidor antes de agregar el cruce.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.post(`/competitions/agreements/${agreement.id}/bouts/`, {
        home_athlete: Number(homeAthlete),
        away_athlete: awayAthlete ? Number(awayAthlete) : null,
      });
      setNotice('Se agregó otro cruce a la propuesta.');
      await onChange();
      onClose();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return <form className="fight-add-bout-form" onSubmit={save}>
    <label className="field-label"><span>Tu competidor</span><select className="control" required value={homeAthlete} onChange={(event) => setHomeAthlete(event.target.value)}><option value="">Selecciona un boxeador/a</option>{competitors.map((athlete) => <option key={athlete.id} value={athlete.id}>{athlete.display_name} · {genderLabels[athlete.gender] || 'Género pendiente'} · Récord {athlete.fight_record || '0-0-0'} · {fightCount(athlete)} peleas</option>)}</select></label>
    <CompetitorGenderPrompt athlete={selectedHome} onSaved={onAthleteUpdated} />
    <label className="field-label"><span>Sugerir rival (opcional)</span><select className="control" value={awayAthlete} disabled={!selectedHome?.gender} onChange={(event) => setAwayAthlete(event.target.value)}><option value="">{selectedHome?.gender ? 'Esperar sugerencia del gimnasio rival' : 'Completa el género para buscar rivales'}</option>{rivalCompetitors.map((athlete) => <option key={athlete.id} value={athlete.id}>{genderLabels[athlete.gender]} · {athlete.display_name} · Récord {athlete.fight_record} · {athlete.recorded_fights} peleas · {athlete.match_score ?? '—'}% compatible</option>)}</select></label>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    <div className="fight-agreement-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cerrar</button><button className="button primary-btn" disabled={busy || !selectedHome?.gender}><Plus size={15} />{busy ? 'Agregando...' : 'Agregar cruce'}</button></div>
  </form>;
}

export function FightAgreementsPage() {
  const { user } = useAuth();
  const [rivals, setRivals] = useState([]);
  const [agreements, setAgreements] = useState([]);
  const [myCompetitors, setMyCompetitors] = useState([]);
  const [rivalCompetitors, setRivalCompetitors] = useState([]);
  const [values, setValues] = useState({
    opponent_club: '', planned_date: '', location: '', notes: '',
    initial_home_athlete: '', initial_away_athlete: '',
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [actionId, setActionId] = useState(null);
  const [addingBoutId, setAddingBoutId] = useState(null);
  const [error, setError] = useState('');
  const [formError, setFormError] = useState('');
  const [notice, setNotice] = useState('');
  const selectedHome = myCompetitors.find((athlete) => String(athlete.id) === values.initial_home_athlete);

  const updateMyCompetitor = (updatedAthlete) => {
    setMyCompetitors((current) => current.map((athlete) => (
      athlete.id === updatedAthlete.id ? { ...athlete, ...updatedAthlete } : athlete
    )));
    setValues((current) => ({ ...current, initial_away_athlete: '' }));
    setNotice(`Se guardó el género de ${updatedAthlete.display_name}. Ya puedes elegir un rival compatible.`);
  };

  const load = async () => {
    setError('');
    try {
      const [clubRows, agreementRows] = await Promise.all([
        readCollection('/competitions/rivals/'),
        readCollection('/competitions/agreements/'),
      ]);
      setRivals(clubRows);
      setAgreements(agreementRows);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    let active = true;
    readCollection('/athletes/?is_competitor=true')
      .then((rows) => { if (active) setMyCompetitors(rows.filter((athlete) => athlete.status === 'ACTIVE')); })
      .catch((requestError) => { if (active) setFormError(getErrorMessage(requestError)); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!values.opponent_club || !selectedHome?.gender) {
      setRivalCompetitors([]);
      return undefined;
    }
    let active = true;
    const query = new URLSearchParams({ home_athlete: values.initial_home_athlete });
    api.get(`/competitions/rivals/${values.opponent_club}/competitors/?${query.toString()}`)
      .then(({ data }) => {
        if (active) setRivalCompetitors(Array.isArray(data) ? data : data.results || []);
      })
      .catch((requestError) => { if (active) setFormError(getErrorMessage(requestError)); });
    return () => { active = false; };
  }, [values.opponent_club, values.initial_home_athlete, selectedHome?.gender]);

  const propose = async (event) => {
    event.preventDefault();
    if (!selectedHome?.gender) {
      setFormError('Completa el género de tu competidor para continuar.');
      return;
    }
    setBusy(true);
    setFormError('');
    setNotice('');
    try {
      await api.post('/competitions/agreements/', {
        ...values,
        opponent_club: Number(values.opponent_club),
        initial_home_athlete: Number(values.initial_home_athlete),
        initial_away_athlete: values.initial_away_athlete ? Number(values.initial_away_athlete) : null,
      });
      setValues({ opponent_club: '', planned_date: '', location: '', notes: '', initial_home_athlete: '', initial_away_athlete: '' });
      setNotice('Propuesta enviada con el primer emparejamiento. El gimnasio rival podrá aceptarlo o sugerir otro boxeador.');
      await load();
    } catch (requestError) {
      setFormError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const updateStatus = async (agreement, status) => {
    setActionId(agreement.id);
    setError('');
    setNotice('');
    try {
      await api.patch(`/competitions/agreements/${agreement.id}/`, { status });
      setNotice(status === 'CONFIRMED' ? 'Combate confirmado con el otro gimnasio.' : 'La propuesta se actualizó.');
      await load();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setActionId(null);
    }
  };

  const incoming = agreements.filter((agreement) => agreement.is_incoming);
  const outgoing = agreements.filter((agreement) => !agreement.is_incoming);

  const renderAgreement = (agreement) => {
    const otherClub = agreement.is_incoming ? agreement.proposing_club_name : agreement.opponent_club_name;
    return <article className={`fight-agreement-card status-${agreement.status.toLowerCase()}`} key={agreement.id}>
      <header className="fight-agreement-card-header">
        <div className="fight-agreement-opponent"><span className="agreement-emblem"><Swords size={19} /></span><div><small>{agreement.is_incoming ? 'PROPUESTA RECIBIDA DE' : 'GIMNASIO INVITADO'}</small><h3>{otherClub}</h3></div></div>
        <span className={`agreement-status agreement-${agreement.status.toLowerCase()}`}>{statusLabels[agreement.status]}</span>
      </header>
      <div className="fight-agreement-details">
        <span><CalendarDays size={16} />{formatDate(agreement.planned_date)}</span>
        <span><MapPin size={16} />{agreement.location}</span>
      </div>
      {agreement.notes && <p className="fight-agreement-notes">{agreement.notes}</p>}
      {agreement.bouts?.length > 0 && <section className="fight-pair-list">
        <header><p className="eyebrow">EMPAREJAMIENTOS PROPUESTOS</p><span>{agreement.bouts.length}</span></header>
        {agreement.bouts.map((bout) => <FightBoutCard key={bout.id} agreement={agreement} bout={bout} user={user} onChange={load} setNotice={setNotice} />)}
        {!agreement.is_incoming && agreement.status === 'PENDING' && <button type="button" className="button button-secondary fight-add-bout-trigger" onClick={() => setAddingBoutId(addingBoutId === agreement.id ? null : agreement.id)}><Plus size={15} /> Agregar otro emparejamiento</button>}
        {addingBoutId === agreement.id && <AdditionalBoutForm agreement={agreement} competitors={myCompetitors.filter((athlete) => !agreement.bouts.some((bout) => bout.home_athlete === athlete.id))} onChange={load} onClose={() => setAddingBoutId(null)} onAthleteUpdated={updateMyCompetitor} setNotice={setNotice} />}
      </section>}
      {agreement.status === 'PENDING' && <p className="agreement-hint"><Clock3 size={14} />{agreement.is_incoming ? 'Revisa la fecha y responde a la propuesta.' : 'A la espera de respuesta del gimnasio invitado.'}</p>}
      <footer className="fight-agreement-actions">
        {agreement.status === 'PENDING' && agreement.is_incoming && <>
          <button type="button" className="button button-secondary" disabled={actionId === agreement.id} onClick={() => updateStatus(agreement, 'DECLINED')}><ShieldX size={15} /> Rechazar evento</button>
          <button type="button" className="button primary-btn" disabled={actionId === agreement.id} onClick={() => updateStatus(agreement, 'CONFIRMED')}><Check size={16} /> Acordar fecha y lugar</button>
        </>}
        {agreement.status === 'PENDING' && !agreement.is_incoming && <button type="button" className="button button-secondary" disabled={actionId === agreement.id} onClick={() => updateStatus(agreement, 'CANCELLED')}><X size={15} /> Retirar propuesta</button>}
        {agreement.status === 'CONFIRMED' && <button type="button" className="button button-secondary" disabled={actionId === agreement.id} onClick={() => updateStatus(agreement, 'CANCELLED')}><X size={15} /> Cancelar evento</button>}
      </footer>
    </article>;
  };

  return <section className="page-stack fight-agreements-page">
    <header className="fight-agreements-hero">
      <div><p className="eyebrow">ALIANZAS Y COMPETENCIA</p><h1>Combates entre gimnasios</h1><p className="page-description">Coordina un encuentro y empareja a tus competidores con propuestas que el otro gimnasio puede aceptar o contrapropone.</p></div>
      <span className="fight-hero-icon"><Handshake size={29} /></span>
    </header>

    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    {error && <div className="notice notice-error" role="alert">{error}</div>}

    <form className="surface-panel fight-proposal-panel" onSubmit={propose}>
      <header className="section-heading"><div><p className="eyebrow">NUEVO ENCUENTRO</p><h2>Invita a un gimnasio</h2></div><Send size={19} /></header>
      <p className="page-description">Elige a tu boxeador y, si quieres, sugiere un rival. Las recomendaciones comparan categoría, peso y combates registrados; no son filtros obligatorios.</p>
      <div className="fight-proposal-fields">
        <label className="field-label"><span>Gimnasio rival *</span><select className="control" required value={values.opponent_club} onChange={(event) => setValues({ ...values, opponent_club: event.target.value, initial_away_athlete: '' })}><option value="">Selecciona un gimnasio</option>{rivals.map((club) => <option value={club.id} key={club.id}>{club.name}</option>)}</select></label>
        <label className="field-label"><span>Fecha propuesta *</span><input className="control" type="date" min={firstAvailableDate()} required value={values.planned_date} onChange={(event) => setValues({ ...values, planned_date: event.target.value })} /></label>
        <div className="fight-matchup-picker">
          <label className="field-label"><span>Tu competidor *</span><select className="control" required value={values.initial_home_athlete} onChange={(event) => { setValues({ ...values, initial_home_athlete: event.target.value, initial_away_athlete: '' }); setFormError(''); }}><option value="">Selecciona a tu boxeador/a</option>{myCompetitors.map((athlete) => <option value={athlete.id} key={athlete.id}>{athlete.display_name} · {genderLabels[athlete.gender] || 'Género pendiente'} · Récord {athlete.fight_record || '0-0-0'} · {fightCount(athlete)} peleas</option>)}</select></label>
          <label className="field-label"><span>Sugerir boxeador/a rival (opcional)</span><select className="control" value={values.initial_away_athlete} disabled={!selectedHome?.gender || !values.opponent_club} onChange={(event) => setValues({ ...values, initial_away_athlete: event.target.value })}><option value="">{selectedHome?.gender ? 'Que el gimnasio rival elija o contraproponga' : values.initial_home_athlete ? 'Completa el género de tu competidor para buscar rivales' : 'Primero elige tu competidor'}</option>{rivalCompetitors.map((athlete) => <option value={athlete.id} key={athlete.id}>{athlete.display_name} · {genderLabels[athlete.gender]} · Récord {athlete.fight_record} · {athlete.recorded_fights} peleas · {athlete.match_score ?? '—'}% compatible</option>)}</select></label>
          {selectedHome && !selectedHome.gender && <CompetitorGenderPrompt athlete={selectedHome} onSaved={updateMyCompetitor} />}
          {selectedHome?.gender && <div className="match-recommendation"><Swords size={16} /><span>Emparejamiento del mismo género: {genderLabels[selectedHome.gender]}. Récord {selectedHome.fight_record || '0-0-0'} · {fightCount(selectedHome)} peleas. Las recomendaciones también comparan categoría, peso y experiencia.</span></div>}
          {values.opponent_club && selectedHome?.gender && rivalCompetitors.length === 0 && <small className="fight-no-rivals">Ese gimnasio aún no registra competidores activos con género coincidente; puedes enviar la propuesta para que sugiera uno.</small>}
          {!myCompetitors.length && <small className="fight-no-rivals">Registra competidores activos en tu gimnasio antes de enviar una propuesta.</small>}
        </div>
        <label className="field-label fight-location-field"><span>Lugar del encuentro *</span><input className="control" maxLength="200" required placeholder="Gimnasio anfitrión, dirección o recinto" value={values.location} onChange={(event) => setValues({ ...values, location: event.target.value })} /></label>
        <label className="field-label fight-notes-field"><span>Detalles opcionales</span><textarea className="control" rows="2" maxLength="2000" placeholder="Reglas, número de combates o logística" value={values.notes} onChange={(event) => setValues({ ...values, notes: event.target.value })} /></label>
      </div>
      {formError && <div className="notice notice-error" role="alert">{formError}</div>}
      <div className="settings-save-row"><button className="button primary-btn" disabled={busy || !rivals.length || !myCompetitors.length || !selectedHome?.gender}><Send size={15} />{busy ? 'Enviando...' : 'Enviar propuesta de combate'}</button></div>
      {!loading && !rivals.length && <p className="page-description">Aún no hay gimnasios aprobados disponibles para invitar.</p>}
    </form>

    {loading ? <div className="empty-state">Cargando propuestas...</div> : <div className="fight-agreement-columns">
      <section className="fight-agreement-section"><header><div><p className="eyebrow">BANDEJA DE ENTRADA</p><h2>Propuestas recibidas <span>{incoming.length}</span></h2></div></header>
        {incoming.length ? <div className="fight-agreement-list">{incoming.map(renderAgreement)}</div> : <div className="surface-panel empty-state">Las nuevas invitaciones de otros gimnasios aparecerán aquí.</div>}
      </section>
      <section className="fight-agreement-section"><header><div><p className="eyebrow">SEGUIMIENTO</p><h2>Enviadas y acuerdos <span>{outgoing.length}</span></h2></div></header>
        {outgoing.length ? <div className="fight-agreement-list">{outgoing.map(renderAgreement)}</div> : <div className="surface-panel empty-state">Todavía no enviaste propuestas.</div>}
      </section>
    </div>}
  </section>;
}
