import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../auth/AuthContext';
import { Card, Screen } from '../components/ui';
import { colors, font, radius, spacing } from '../theme';

// Entradas del menú "Más"; cada una declara los roles que la pueden ver.
export const MORE_ITEMS = [
  { route: 'Profile', title: 'Mi perfil', icon: 'person-circle-outline', roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { route: 'Club', title: 'Mi club y disciplinas', icon: 'business-outline', roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { route: 'Store', title: 'Tienda y pedidos', icon: 'bag-handle-outline', roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { route: 'Competition', title: 'Combates entre clubes', icon: 'trophy-outline', roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { route: 'Notifications', title: 'Notificaciones', icon: 'notifications-outline', roles: ['ADMIN', 'TRAINER', 'ATHLETE'] }
];

export default function MoreScreen({ navigation }) {
  const { user } = useAuth();
  const items = MORE_ITEMS.filter((item) => item.roles.includes(user.role));
  return (
    <Screen eyebrow="MENÚ" title="Más opciones">
      <Card style={{ padding: 0 }}>
        {items.map((item, index) => (
          <Pressable
            key={item.route}
            accessibilityRole="button"
            onPress={() => navigation.navigate(item.route)}
            style={({ pressed }) => [styles.row, index > 0 && styles.divider, pressed && { backgroundColor: colors.canvas }]}
          >
            <View style={styles.icon}><Ionicons name={item.icon} size={20} color={colors.red} /></View>
            <Text style={[font.body, { flex: 1, fontWeight: '600' }]}>{item.title}</Text>
            <Ionicons name="chevron-forward" size={18} color={colors.inkSoft} />
          </Pressable>
        ))}
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', padding: spacing.lg, minHeight: 56, borderRadius: radius.lg },
  divider: { borderTopWidth: 1, borderTopColor: colors.line },
  icon: { width: 36, height: 36, borderRadius: radius.md, backgroundColor: colors.redSoft, alignItems: 'center', justifyContent: 'center', marginRight: spacing.md }
});
