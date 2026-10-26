import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/AuthContext';
import { Banner, Button, Field } from '../components/ui';
import { API_URL } from '../config';
import { colors, font, radius, spacing } from '../theme';

export default function LoginScreen() {
  const { login, notice } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const next = {};
    if (!username.trim()) next.username = 'Ingresa tu usuario o correo.';
    if (!password) next.password = 'Ingresa tu contraseña.';
    setErrors(next);
    if (Object.keys(next).length) return;
    setBusy(true);
    setError('');
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.brand}>
            <View style={styles.logo}><Text style={styles.logoText}>BX</Text></View>
            <Text style={styles.brandName}>BOXTRACK</Text>
            <Text style={styles.brandTag}>CLUB MANAGEMENT</Text>
          </View>
          <View style={styles.card}>
            <Text style={font.title}>Ingresa a tu club</Text>
            <Text style={[font.small, { marginBottom: spacing.lg, marginTop: 2 }]}>Usa la misma cuenta que en la web.</Text>
            <Banner type="warn">{notice}</Banner>
            <Banner>{error}</Banner>
            <Field
              label="Usuario o correo electrónico"
              value={username}
              onChangeText={setUsername}
              autoCapitalize="none"
              autoCorrect={false}
              textContentType="username"
              returnKeyType="next"
              error={errors.username}
            />
            <Field
              label="Contraseña"
              value={password}
              onChangeText={setPassword}
              secureTextEntry={!showPassword}
              autoCapitalize="none"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={submit}
              error={errors.password}
            />
            <Button title={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'} variant="ghost" small onPress={() => setShowPassword((v) => !v)} />
            <Button title="Entrar al club" onPress={submit} loading={busy} style={{ marginTop: spacing.sm }} testID="login-submit" />
          </View>
          {__DEV__ ? <Text style={styles.devHint}>Servidor: {API_URL}</Text> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.dark },
  content: { flexGrow: 1, justifyContent: 'center', padding: spacing.xl },
  brand: { alignItems: 'center', marginBottom: spacing.xl },
  logo: { width: 64, height: 64, borderRadius: radius.lg, backgroundColor: colors.red, alignItems: 'center', justifyContent: 'center' },
  logoText: { color: colors.white, fontSize: 24, fontWeight: '900' },
  brandName: { color: colors.white, fontSize: 24, fontWeight: '900', letterSpacing: 3, marginTop: spacing.md },
  brandTag: { color: '#ff6575', fontSize: 11, letterSpacing: 3, marginTop: 2 },
  card: { backgroundColor: colors.paper, borderRadius: radius.lg, padding: spacing.xl },
  devHint: { color: '#8d9198', fontSize: 11, textAlign: 'center', marginTop: spacing.lg }
});
