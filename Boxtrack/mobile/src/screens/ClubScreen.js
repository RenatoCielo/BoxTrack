import { Image, Text, View } from 'react-native';
import { api } from '../api';
import { API_ORIGIN } from '../config';
import { useAuth } from '../auth/AuthContext';
import { Badge, Card, EmptyState, KeyValue, ResourceView, Screen } from '../components/ui';
import { useResource } from '../hooks/useResource';
import { font, spacing } from '../theme';

function disciplinesOf(club) {
  const raw = club?.disciplines;
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') return raw.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

export default function ClubScreen() {
  const { user } = useAuth();
  const resource = useResource(async () => {
    const data = await api.readCollection('/clubs/');
    return data[0] || null;
  }, [user?.club?.id]);
  const club = resource.data;
  const disciplines = disciplinesOf(club);
  const logoUri = club?.logo ? (/^https?:\/\//i.test(club.logo) ? club.logo : `${API_ORIGIN}${club.logo}`) : '';

  return (
    <Screen eyebrow="MI CLUB" title={club?.name || user.club?.name || 'Club'} onRefresh={resource.refresh} refreshing={resource.refreshing}>
      <ResourceView resource={resource} isEmpty={!club} empty={<EmptyState title="Sin club asignado" message="Tu cuenta no está asociada a un club." />}>
        {club ? (
          <>
            <Card>
              {logoUri ? <Image source={{ uri: logoUri }} accessibilityLabel={`Logotipo de ${club.name}`} resizeMode="contain" style={{ width: '100%', height: 110, marginBottom: spacing.md }} /> : null}
              <View style={{ flexDirection: 'row', gap: 8, marginBottom: spacing.md }}>
                <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: club.primary_color || '#c51f35' }} />
                <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: club.accent_color || '#151518' }} />
              </View>
              {club.description ? <Text style={[font.body, { marginBottom: spacing.md }]}>{club.description}</Text> : null}
              <KeyValue label="Dirección" value={club.address} />
              <KeyValue label="Teléfono" value={club.phone} />
              <KeyValue label="Correo" value={club.email} />
              <KeyValue label="Sitio web" value={club.website} />
            </Card>
            <Text style={[font.heading, { marginBottom: spacing.sm }]}>Disciplinas</Text>
            <Card>
              {disciplines.length ? (
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {disciplines.map((item) => <Badge key={item} text={item} tone="info" />)}
                </View>
              ) : (
                <Text style={font.small}>El club aún no registra disciplinas.</Text>
              )}
            </Card>
          </>
        ) : null}
      </ResourceView>
    </Screen>
  );
}
