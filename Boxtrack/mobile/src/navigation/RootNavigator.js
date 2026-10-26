import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, Text, View } from 'react-native';
import { useAuth } from '../auth/AuthContext';
import { Button } from '../components/ui';
import { colors, font, spacing } from '../theme';
import ClassesScreen from '../screens/ClassesScreen';
import ClubScreen from '../screens/ClubScreen';
import CompetitionScreen from '../screens/CompetitionScreen';
import HomeScreen from '../screens/HomeScreen';
import LoginScreen from '../screens/LoginScreen';
import MembershipsScreen from '../screens/MembershipsScreen';
import MoreScreen from '../screens/MoreScreen';
import NotificationsScreen from '../screens/NotificationsScreen';
import ProfileScreen from '../screens/ProfileScreen';
import StoreScreen from '../screens/StoreScreen';

const Tab = createBottomTabNavigator();
const MoreStack = createNativeStackNavigator();

const navTheme = { ...DefaultTheme, colors: { ...DefaultTheme.colors, background: colors.canvas, primary: colors.red, card: colors.paper, text: colors.ink, border: colors.line } };
const stackOptions = { headerTintColor: colors.red, headerTitleStyle: { color: colors.ink }, headerBackTitle: 'Atrás' };

function MoreNavigator() {
  return (
    <MoreStack.Navigator screenOptions={stackOptions}>
      <MoreStack.Screen name="MoreHome" component={MoreScreen} options={{ headerShown: false }} />
      <MoreStack.Screen name="Profile" component={ProfileScreen} options={{ title: 'Mi perfil', headerShown: false }} />
      <MoreStack.Screen name="Club" component={ClubScreen} options={{ title: 'Mi club' }} />
      <MoreStack.Screen name="Store" component={StoreScreen} options={{ title: 'Tienda' }} />
      <MoreStack.Screen name="Competition" component={CompetitionScreen} options={{ title: 'Combates' }} />
      <MoreStack.Screen name="Notifications" component={NotificationsScreen} options={{ title: 'Notificaciones' }} />
    </MoreStack.Navigator>
  );
}

const icons = {
  HomeTab: ['home', 'home-outline'],
  ClassesTab: ['calendar', 'calendar-outline'],
  MembershipsTab: ['card', 'card-outline'],
  MoreTab: ['menu', 'menu-outline']
};

function MainTabs() {
  const { user } = useAuth();
  const hasMemberships = user.role === 'ADMIN' || user.role === 'ATHLETE';
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.red,
        tabBarInactiveTintColor: colors.inkSoft,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        tabBarIcon: ({ focused, color, size }) => <Ionicons name={icons[route.name][focused ? 0 : 1]} size={size} color={color} />
      })}
    >
      <Tab.Screen name="HomeTab" component={HomeScreen} options={{ title: 'Inicio' }} />
      <Tab.Screen name="ClassesTab" component={ClassesScreen} options={{ title: 'Clases' }} />
      {hasMemberships ? <Tab.Screen name="MembershipsTab" component={MembershipsScreen} options={{ title: 'Membresías' }} /> : null}
      <Tab.Screen name="MoreTab" component={MoreNavigator} options={{ title: 'Más' }} />
    </Tab.Navigator>
  );
}

function CenterMessage({ children }) {
  return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.dark, padding: spacing.xl }}>{children}</View>;
}

export default function RootNavigator() {
  const { status, retry, logout } = useAuth();

  if (status === 'loading') {
    return (
      <CenterMessage>
        <ActivityIndicator size="large" color={colors.red} />
        <Text style={[font.small, { color: '#8d9198', marginTop: spacing.md }]}>Iniciando BoxTrack…</Text>
      </CenterMessage>
    );
  }
  if (status === 'offline') {
    return (
      <CenterMessage>
        <Text style={{ color: colors.white, fontSize: 18, fontWeight: '700', textAlign: 'center' }}>Sin conexión con el servidor</Text>
        <Text style={{ color: '#8d9198', textAlign: 'center', marginVertical: spacing.md }}>
          Tu sesión sigue guardada. Revisa tu conexión e inténtalo nuevamente.
        </Text>
        <Button title="Reintentar" onPress={retry} />
        <Button title="Cerrar sesión" variant="ghost" onPress={logout} />
      </CenterMessage>
    );
  }
  return (
    <NavigationContainer theme={navTheme}>
      {status === 'signedIn' ? <MainTabs /> : <LoginScreen />}
    </NavigationContainer>
  );
}
