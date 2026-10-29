import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { api } from '../api';
import { Badge, Banner, Button, Card, EmptyState, ResourceView, Screen } from '../components/ui';
import { useResource } from '../hooks/useResource';
import { colors, font, spacing } from '../theme';
import { formatDateTime } from '../utils/format';

export default function NotificationsScreen() {
  const navigation = useNavigation();
  const resource = useResource(() => api.readCollection('/notifications/'), []);
  const [error, setError] = useState('');
  const items = resource.data || [];
  const unread = items.filter((item) => item.is_read === false);

  const markRead = async (item) => {
    if (item.is_read) return;
    setError('');
    try {
      await api.patch(`/notifications/${item.id}/`, { is_read: true });
      resource.setData((prev) => prev.map((row) => (row.id === item.id ? { ...row, is_read: true } : row)));
    } catch (err) {
      setError(err.message);
    }
  };

  const markAll = async () => {
    setError('');
    try {
      await Promise.all(unread.map((item) => api.patch(`/notifications/${item.id}/`, { is_read: true })));
      resource.setData((prev) => prev.map((row) => ({ ...row, is_read: true })));
    } catch (err) {
      setError(err.message);
      resource.reload();
    }
  };

  const openNotification = async (item) => {
    await markRead(item);
    if (/membres[ií]a|membres[ií]as/i.test(`${item.title} ${item.message}`)) {
      navigation.getParent()?.navigate('MembershipsTab');
    }
  };

  return (
    <Screen eyebrow="AVISOS" title="Notificaciones" subtitle={`${unread.length} sin leer`} onRefresh={resource.refresh} refreshing={resource.refreshing}>
      <Banner onClose={() => setError('')}>{error}</Banner>
      <ResourceView
        resource={resource}
        isEmpty={items.length === 0}
        empty={<EmptyState icon="notifications-off-outline" title="Sin notificaciones" message="Cuando haya novedades en tu club las verás aquí." />}
      >
        {unread.length ? <View style={{ marginBottom: spacing.md }}><Button title="Marcar todas como leídas" variant="secondary" small onPress={markAll} /></View> : null}
        {items.map((item) => (
          <Pressable key={item.id} onPress={() => openNotification(item)} accessibilityRole="button" accessibilityHint="Abre la membresía o marca la notificación como leída">
            <Card tone={item.is_read ? undefined : 'bad'}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text style={[font.heading, { flex: 1, marginRight: spacing.sm }, item.is_read && { color: colors.inkSoft }]}>{item.title}</Text>
                {item.is_read ? null : <Badge text="Nueva" tone="bad" />}
              </View>
              <Text style={[font.body, { marginTop: 4 }]}>{item.message}</Text>
              {/membres[ií]a|membres[ií]as/i.test(`${item.title} ${item.message}`) ? <Text style={[font.small, { marginTop: 6, color: colors.red }]}>Toca para ver tu membresía o renovarla.</Text> : null}
              <Text style={[font.small, { marginTop: 6 }]}>{formatDateTime(item.created_at)}</Text>
            </Card>
          </Pressable>
        ))}
      </ResourceView>
    </Screen>
  );
}
