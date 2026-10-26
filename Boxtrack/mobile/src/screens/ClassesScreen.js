import { useState } from 'react';
import { Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, EmptyState, ResourceView, Screen, Segmented } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { colors, font, spacing } from '../theme';
import { formatDate, formatTime, label, todayISO, tone } from '../utils/format';
import { reservationState } from '../utils/reservation';

const MAX_RESERVATION_LOOKUPS = 40;

async function loadClasses(user) {
  const isAthlete = user.role === 'ATHLETE';
  const [trainings, settings, memberships] = await Promise.all([
    api.readCollection('/trainings/'),
    api.get('/memberships/settings/').catch(() => ({ require_active_membership: false })),
    isAthlete ? api.get('/memberships/').catch(() => []) : Promise.resolve([])
  ]);
  const today = todayISO();
  const upcoming = trainings.filter((t) => t.status === 'SCHEDULED' && t.scheduled_date >= today).slice(0, MAX_RESERVATION_LOOKUPS);
  const entries = await Promise.all(
    upcoming.map(async (t) => [t.id, await api.get(`/trainings/${t.id}/reservations/`).catch(() => [])])
  );
  return {
    trainings,
    settings,
    memberships: Array.isArray(memberships) ? memberships : [],
    reservations: Object.fromEntries(entries)
  };
}

// Mismos criterios que el backend; la decisión final siempre la toma la API.
function ClassCard({ training, data, user, onChanged }) {
  const navigation = useNavigation();
  const isAthlete = user.role === 'ATHLETE';
  const reservations = data.reservations[training.id] || [];
  const state = reservationState({ training, reservations, settings: data.settings, memberships: data.memberships, isAthlete });
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState({ type: 'error', text: '', membership: false });
  const [showRoster, setShowRoster] = useState(false);
  const freeSpots = Math.max(training.capacity - training.reserved_count, 0);

  const reserve = async () => {
    setBusy(true);
    setFeedback({ type: 'error', text: '', membership: false });
    try {
      await api.post(`/trainings/${training.id}/reservations/`, {});
      setFeedback({ type: 'success', text: 'Cupo reservado correctamente.', membership: false });
      await onChanged();
    } catch (error) {
      setFeedback({ type: 'error', text: error.message, membership: error.code === 'MEMBERSHIP_REQUIRED' });
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (reservation) => {
    setBusy(true);
    setFeedback({ type: 'error', text: '', membership: false });
    try {
      await api.post(`/trainings/${training.id}/reservations/${reservation.id}/cancel/`, {});
      setFeedback({ type: 'success', text: 'Reserva cancelada.', membership: false });
      await onChanged();
    } catch (error) {
      setFeedback({ type: 'error', text: error.message, membership: false });
    } finally {
      setBusy(false);
    }
  };

  const showPlansLink = state.needsMembership || feedback.membership;

  return (
    <Card>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, marginRight: spacing.sm }}>
          <Text style={font.heading}>{training.title}</Text>
          <Text style={font.small}>{label('activity', training.activity_type)}</Text>
        </View>
        <Badge text={label('training', training.status)} tone={tone(training.status)} />
      </View>
      <Text style={[font.body, { marginTop: spacing.sm }]}>{formatDate(training.scheduled_date)} · {formatTime(training.start_time)} · {training.duration_minutes} min</Text>
      <Text style={[font.small, { marginTop: 2 }]}>
        {training.reserved_count}/{training.capacity} cupos ocupados · {freeSpots} disponibles
      </Text>
      {training.description ? <Text style={[font.small, { marginTop: 4 }]}>{training.description}</Text> : null}

      <View style={{ marginTop: spacing.md }}>
        <Banner type={feedback.type} onClose={() => setFeedback({ ...feedback, text: '' })}>{feedback.text}</Banner>
        {isAthlete ? (
          state.own ? (
            <>
              <Badge text="Tienes un cupo reservado" tone="ok" />
              <View style={{ height: spacing.sm }} />
              <Button title="Cancelar reserva" variant="secondary" onPress={() => cancel(state.own)} loading={busy} />
            </>
          ) : (
            <>
              {state.blockedMessage ? <Text style={[font.small, { color: colors.redDark, marginBottom: spacing.sm }]}>{state.blockedMessage}</Text> : null}
              <Button
                title={state.full ? 'Clase llena' : 'Reservar cupo'}
                onPress={reserve}
                loading={busy}
                disabled={state.full || state.needsMembership}
                testID={`reserve-${training.id}`}
              />
              {showPlansLink ? (
                <Button title="Ver planes disponibles" variant="ghost" small onPress={() => navigation.navigate('MembershipsTab')} />
              ) : null}
            </>
          )
        ) : (
          <>
            <Button title={showRoster ? 'Ocultar inscritos' : `Ver inscritos (${reservations.length})`} variant="secondary" small onPress={() => setShowRoster((v) => !v)} />
            {showRoster ? (
              <View style={{ marginTop: spacing.sm }}>
                {reservations.length === 0 ? <Text style={font.small}>Aún no hay deportistas inscritos.</Text> : null}
                {reservations.map((reservation) => (
                  <View key={reservation.id} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 4 }}>
                    <Text style={[font.body, { flex: 1 }]}>{reservation.athlete_name || `Deportista #${reservation.athlete}`}</Text>
                    <Button title="Quitar" variant="ghost" small onPress={() => cancel(reservation)} disabled={busy} />
                  </View>
                ))}
              </View>
            ) : null}
          </>
        )}
      </View>
    </Card>
  );
}

export default function ClassesScreen() {
  const { user } = useAuth();
  const resource = useResource(() => loadClasses(user), [user.id]);
  useRefreshOnFocus(resource);
  const [view, setView] = useState('upcoming');
  const data = resource.data;
  const today = todayISO();
  const rows = (data?.trainings || []).filter((t) => (view === 'upcoming' ? t.scheduled_date >= today && t.status === 'SCHEDULED' : t.scheduled_date < today || t.status !== 'SCHEDULED'));
  const sorted = view === 'upcoming' ? rows : [...rows].reverse();

  return (
    <Screen
      eyebrow="AGENDA"
      title="Clases y cupos"
      subtitle={data?.settings?.require_active_membership && user.role === 'ATHLETE' ? 'Este club exige membresía activa para reservar.' : undefined}
      onRefresh={resource.refresh}
      refreshing={resource.refreshing}
    >
      <Segmented
        value={view}
        onChange={setView}
        options={[{ value: 'upcoming', label: 'Próximas' }, { value: 'past', label: 'Anteriores' }]}
      />
      <ResourceView
        resource={resource}
        isEmpty={sorted.length === 0}
        empty={<EmptyState icon="calendar-outline" title={view === 'upcoming' ? 'No hay clases próximas' : 'Sin clases anteriores'} message="Cuando el club programe clases las verás aquí." />}
      >
        {data ? sorted.map((training) => <ClassCard key={training.id} training={training} data={data} user={user} onChanged={resource.refresh} />) : null}
      </ResourceView>
    </Screen>
  );
}
