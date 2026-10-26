import { Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Badge, Button, Card, Screen, SectionTitle } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { colors, font, spacing } from '../theme';
import { formatDate, formatTime, isMembershipValidFor, label, todayISO, tone } from '../utils/format';

function useHomeData(user) {
  return useResource(async () => {
    const today = todayISO();
    const staff = user.role !== 'ATHLETE';
    const needsMemberships = user.role !== 'TRAINER';
    const [trainings, notifications, memberships] = await Promise.all([
      api.readCollection('/trainings/'),
      api.readCollection('/notifications/').catch(() => []),
      needsMemberships ? api.get('/memberships/').catch(() => []) : Promise.resolve([])
    ]);
    const upcoming = trainings
      .filter((item) => item.status === 'SCHEDULED' && item.scheduled_date >= today)
      .sort((a, b) => `${a.scheduled_date}${a.start_time}`.localeCompare(`${b.scheduled_date}${b.start_time}`));
    return {
      upcoming: upcoming.slice(0, 3),
      unread: notifications.filter((item) => item.is_read === false).length,
      memberships: Array.isArray(memberships) ? memberships : [],
      pendingMemberships: staff ? (Array.isArray(memberships) ? memberships.filter((m) => m.status === 'PENDING').length : 0) : 0
    };
  }, [user.id]);
}

export default function HomeScreen() {
  const { user } = useAuth();
  const navigation = useNavigation();
  const resource = useHomeData(user);
  useRefreshOnFocus(resource);
  const data = resource.data;
  const isAthlete = user.role === 'ATHLETE';
  const current = data?.memberships.find((m) => isMembershipValidFor(m, todayISO()))
    || data?.memberships.find((m) => m.status === 'PENDING')
    || data?.memberships[0];

  return (
    <Screen
      eyebrow={user.club?.name?.toUpperCase() || 'BOXTRACK'}
      title={`Hola, ${user.first_name || user.display_name || user.username}`}
      subtitle={label('role', user.role)}
      onRefresh={resource.refresh}
      refreshing={resource.refreshing}
    >
      {resource.error && !data ? (
        <Card tone="bad">
          <Text style={font.body}>{resource.error}</Text>
          <View style={{ marginTop: spacing.md }}><Button title="Reintentar" variant="secondary" onPress={resource.reload} /></View>
        </Card>
      ) : null}

      {data ? (
        <>
          <Card>
            <Text style={font.small}>Notificaciones sin leer</Text>
            <Text style={{ fontSize: 28, fontWeight: '800', color: data.unread ? colors.red : colors.ink }}>{data.unread}</Text>
            <Button title="Ver notificaciones" variant="secondary" small onPress={() => navigation.navigate('MoreTab', { screen: 'Notifications' })} />
          </Card>

          {isAthlete ? (
            <Card tone={current?.status === 'PENDING' ? 'warn' : undefined}>
              <Text style={font.small}>Mi membresía</Text>
              {current ? (
                <>
                  <Text style={[font.heading, { marginVertical: 4 }]}>{current.plan_name}</Text>
                  <Badge text={label('membership', current.status)} tone={tone(current.status)} />
                  {current.end_date ? <Text style={[font.small, { marginTop: 6 }]}>Vence el {formatDate(current.end_date)}</Text> : null}
                </>
              ) : (
                <Text style={[font.body, { marginTop: 4 }]}>Aún no tienes una membresía.</Text>
              )}
              <View style={{ marginTop: spacing.md }}>
                <Button title="Ver planes" variant="secondary" small onPress={() => navigation.navigate('MembershipsTab')} />
              </View>
            </Card>
          ) : user.role === 'ADMIN' ? (
            <Card tone={data.pendingMemberships ? 'warn' : undefined}>
              <Text style={font.small}>Membresías por revisar</Text>
              <Text style={{ fontSize: 28, fontWeight: '800', color: colors.ink }}>{data.pendingMemberships}</Text>
              <Button title="Revisar membresías" variant="secondary" small onPress={() => navigation.navigate('MembershipsTab')} />
            </Card>
          ) : null}

          <SectionTitle>Próximas clases</SectionTitle>
          {data.upcoming.length ? data.upcoming.map((item) => (
            <Card key={item.id}>
              <Text style={font.heading}>{item.title}</Text>
              <Text style={font.small}>{formatDate(item.scheduled_date)} · {formatTime(item.start_time)} · {item.duration_minutes} min</Text>
              <Text style={[font.small, { marginTop: 2 }]}>{item.reserved_count}/{item.capacity} cupos ocupados</Text>
            </Card>
          )) : (
            <Card><Text style={font.small}>No hay clases programadas próximamente.</Text></Card>
          )}
          <Button title="Ver todas las clases" variant="secondary" onPress={() => navigation.navigate('ClassesTab')} />
        </>
      ) : null}
    </Screen>
  );
}
