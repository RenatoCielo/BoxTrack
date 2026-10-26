import { useState } from 'react';
import { Text, View } from 'react-native';
import { api } from '../api';
import { clubId, isStaff, useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, EmptyState, Field, KeyValue, ResourceView, Screen, SectionTitle, Segmented } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { font, spacing } from '../theme';
import { matchActions, resultOptions } from '../utils/competition';
import { formatDate, label, todayISO, tone } from '../utils/format';

async function loadCompetition(user) {
  const [requests, matches] = await Promise.all([
    api.get('/competitions/competitor-requests/'),
    api.get('/competitions/matches/')
  ]);
  let athletes = [];
  let directory = [];
  if (isStaff(user)) {
    [athletes, directory] = await Promise.all([
      api.readCollection('/athletes/?status=ACTIVE'),
      api.get('/competitions/directory/')
    ]);
  }
  return {
    requests: Array.isArray(requests) ? requests : [],
    matches: Array.isArray(matches) ? matches : [],
    athletes: athletes.filter((athlete) => athlete.status === 'ACTIVE'),
    directory: Array.isArray(directory) ? directory : []
  };
}

function MatchCard({ match, myClub, onAction }) {
  const [panel, setPanel] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { user } = useAuth();
  const actions = matchActions(match, myClub, todayISO(), isStaff(user));
  const hasActions = actions.canRespond || actions.canCancel || actions.canRegisterResult;

  const run = async (action, payload, success) => {
    setBusy(true);
    setError('');
    try {
      await api.post(`/competitions/matches/${match.id}/${action}/`, payload);
      setPanel(null);
      await onAction(success);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card tone={match.status === 'PROPOSED' ? 'warn' : undefined}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Text style={[font.heading, { flex: 1, marginRight: spacing.sm }]}>{match.challenger_athlete_name} vs {match.opponent_athlete_name}</Text>
        <Badge text={label('match', match.status)} tone={tone(match.status)} />
      </View>
      <View style={{ marginTop: spacing.sm }}>
        <KeyValue label="Fecha" value={formatDate(match.fight_date)} />
        <KeyValue label="Clubes" value={`${match.challenger_club_name} / ${match.opponent_club_name}`} />
        {match.event ? <KeyValue label="Evento" value={match.event} /> : null}
        {match.location ? <KeyValue label="Lugar" value={match.location} /> : null}
        {match.category ? <KeyValue label="Categoría" value={match.category} /> : null}
        <KeyValue label="Tipo" value={label('fightType', match.fight_type)} />
        {match.response_note ? <KeyValue label="Nota" value={match.response_note} /> : null}
        {match.status === 'COMPLETED' ? <KeyValue label="Resultado (proponente)" value={label('result', match.challenger_result)} /> : null}
      </View>
      {actions.waitingResponse ? <Text style={[font.small, { marginTop: spacing.sm }]}>Esperando respuesta del club rival.</Text> : null}
      <Banner>{error}</Banner>
      {hasActions && !panel ? (
        <View style={{ marginTop: spacing.md, gap: 8 }}>
          {actions.canRespond ? <Button title="Aceptar combate" onPress={() => run('accept', {}, 'Combate confirmado.')} loading={busy} /> : null}
          {actions.canRespond ? <Button title="Rechazar" variant="secondary" onPress={() => setPanel('decline')} disabled={busy} /> : null}
          {actions.canRegisterResult ? <Button title="Registrar resultado" onPress={() => setPanel('result')} disabled={busy} /> : null}
          {actions.canCancel ? <Button title="Cancelar combate" variant="secondary" onPress={() => setPanel('cancel')} disabled={busy} /> : null}
        </View>
      ) : null}
      {panel === 'result' ? (
        <View style={{ marginTop: spacing.md, gap: 8 }}>
          <Text style={font.heading}>¿Quién ganó?</Text>
          {resultOptions(match).map((option) => (
            <Button key={option.value} title={option.label} variant="secondary" onPress={() => run('result', { result: option.value }, 'Resultado registrado en ambos historiales.')} disabled={busy} />
          ))}
          <Button title="Volver" variant="ghost" small onPress={() => setPanel(null)} />
        </View>
      ) : null}
      {panel === 'decline' || panel === 'cancel' ? (
        <View style={{ marginTop: spacing.md }}>
          <Text style={font.heading}>{panel === 'decline' ? '¿Rechazar la propuesta?' : '¿Cancelar el combate?'}</Text>
          <Button
            title="Sí, confirmar"
            variant="danger"
            loading={busy}
            onPress={() => run(panel, {}, panel === 'decline' ? 'Propuesta rechazada.' : 'Combate cancelado.')}
            style={{ marginTop: spacing.sm }}
          />
          <Button title="Volver" variant="ghost" small onPress={() => setPanel(null)} />
        </View>
      ) : null}
    </Card>
  );
}

function RequestCard({ request, canReview, onAction }) {
  const [mode, setMode] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const send = async (decision) => {
    setBusy(true);
    setError('');
    try {
      await api.post(`/competitions/competitor-requests/${request.id}/review/`, { decision, review_note: note });
      await onAction(decision === 'APPROVE' ? 'Deportista aprobado como competidor.' : 'Solicitud rechazada.');
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <Card tone={request.status === 'PENDING' ? 'warn' : undefined}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={[font.heading, { flex: 1, marginRight: spacing.sm }]}>{request.athlete_name}</Text>
        <Badge text={label('request', request.status)} tone={tone(request.status)} />
      </View>
      {request.request_note ? <Text style={[font.body, { marginTop: 4 }]}>{request.request_note}</Text> : null}
      {request.review_note ? <KeyValue label="Respuesta" value={request.review_note} /> : null}
      <Banner>{error}</Banner>
      {canReview && request.status === 'PENDING' ? (
        mode === 'REJECT' ? (
          <View style={{ marginTop: spacing.md }}>
            <Field label="Motivo (opcional)" value={note} onChangeText={setNote} multiline />
            <Button title="Confirmar rechazo" variant="danger" loading={busy} onPress={() => send('REJECT')} />
            <Button title="Volver" variant="ghost" small onPress={() => setMode(null)} />
          </View>
        ) : (
          <View style={{ marginTop: spacing.md, gap: 8 }}>
            <Button title="Aprobar como competidor" loading={busy} onPress={() => send('APPROVE')} />
            <Button title="Rechazar" variant="secondary" disabled={busy} onPress={() => setMode('REJECT')} />
          </View>
        )
      ) : null}
    </Card>
  );
}

function ProposeForm({ data, user, onDone }) {
  const role = user.role;
  const own = data.athletes.filter((a) => a.is_competitor && (role === 'ADMIN' || a.assigned_trainer === user.id));
  const [form, setForm] = useState({ challenger_athlete: null, opponent_athlete: null, fight_date: '', event: '', location: '', category: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (key) => (value) => setForm((prev) => ({ ...prev, [key]: value }));

  if (!own.length) return <EmptyState icon="people-outline" title="Sin competidores propios" message="Aprueba o solicita a un deportista como competidor para poder proponer combates." />;
  if (!data.directory.length) return <EmptyState icon="shield-outline" title="Sin rivales disponibles" message="Aún no hay competidores activos en otros clubes." />;

  const submit = async () => {
    if (!form.challenger_athlete || !form.opponent_athlete) return setError('Selecciona tu competidor y el rival.');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.fight_date)) return setError('Escribe la fecha con formato AAAA-MM-DD.');
    setBusy(true);
    setError('');
    try {
      await api.post('/competitions/matches/', { ...form, fight_type: 'AMATEUR' });
      await onDone('Propuesta enviada al club rival.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View>
      <Banner>{error}</Banner>
      <SectionTitle>Tu competidor</SectionTitle>
      <Segmented options={own.map((a) => ({ value: a.id, label: a.display_name || a.full_name || a.name || `#${a.id}` }))} value={form.challenger_athlete} onChange={set('challenger_athlete')} />
      <SectionTitle>Rival (otro club)</SectionTitle>
      <Segmented options={data.directory.map((row) => ({ value: row.id, label: `${row.name} · ${row.club_name}` }))} value={form.opponent_athlete} onChange={set('opponent_athlete')} />
      <Field label="Fecha (AAAA-MM-DD)" value={form.fight_date} onChangeText={set('fight_date')} placeholder={todayISO()} autoCapitalize="none" />
      <Field label="Evento" value={form.event} onChangeText={set('event')} />
      <Field label="Lugar" value={form.location} onChangeText={set('location')} />
      <Field label="Categoría" value={form.category} onChangeText={set('category')} />
      <Button title="Enviar propuesta" onPress={submit} loading={busy} />
    </View>
  );
}

export default function CompetitionScreen() {
  const { user } = useAuth();
  const staff = isStaff(user);
  const resource = useResource(() => loadCompetition(user), [user.id]);
  useRefreshOnFocus(resource);
  const [tab, setTab] = useState('matches');
  const [notice, setNotice] = useState('');
  const myClub = clubId(user);
  const data = resource.data;

  const done = async (message) => {
    setNotice(message);
    await resource.silent();
  };

  const tabs = [
    { value: 'matches', label: 'Combates' },
    { value: 'requests', label: 'Solicitudes' },
    ...(staff ? [{ value: 'propose', label: 'Proponer' }] : [])
  ];

  return (
    <Screen
      eyebrow="COMPETENCIA"
      title="Combates entre clubes"
      subtitle={staff ? 'Propón, responde y registra combates con otros clubes.' : 'Consulta tus combates programados y sus resultados.'}
      onRefresh={resource.refresh}
      refreshing={resource.refreshing}
    >
      <Banner type="success" onClose={() => setNotice('')}>{notice}</Banner>
      <Segmented options={tabs} value={tab} onChange={setTab} />
      <ResourceView resource={resource} isEmpty={false}>
        {data && tab === 'matches' ? (
          data.matches.length ? data.matches.map((match) => <MatchCard key={match.id} match={match} myClub={myClub} onAction={done} />)
            : <EmptyState icon="trophy-outline" title="Sin combates" message="Todavía no hay combates propuestos o programados." />
        ) : null}
        {data && tab === 'requests' ? (
          data.requests.length ? data.requests.map((request) => <RequestCard key={request.id} request={request} canReview={user.role === 'ADMIN'} onAction={done} />)
            : <EmptyState icon="document-text-outline" title="Sin solicitudes" message="No hay solicitudes de paso a competidor." />
        ) : null}
        {data && tab === 'propose' && staff ? <ProposeForm data={data} user={user} onDone={async (m) => { setTab('matches'); await done(m); }} /> : null}
      </ResourceView>
    </Screen>
  );
}
