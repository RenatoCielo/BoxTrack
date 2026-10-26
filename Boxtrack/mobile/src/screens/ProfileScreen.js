import { useState } from 'react';
import { Text, View } from 'react-native';
import { useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, Field, KeyValue, Screen, SectionTitle } from '../components/ui';
import { api } from '../api';
import { font, spacing } from '../theme';
import { label } from '../utils/format';

export default function ProfileScreen() {
  const { user, updateProfile, logout } = useAuth();
  const [form, setForm] = useState({
    first_name: user.first_name || '',
    last_name: user.last_name || '',
    email: user.email || '',
    phone: user.phone || '',
    nickname: user.nickname || ''
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: 'success', text: '' });
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm: '' });
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState({ type: 'success', text: '' });

  const set = (key) => (value) => setForm((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true);
    setMessage({ type: 'success', text: '' });
    try {
      await updateProfile(form);
      setMessage({ type: 'success', text: 'Perfil actualizado.' });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async () => {
    if (!passwords.current_password || !passwords.new_password) {
      setPasswordMessage({ type: 'error', text: 'Completa la contraseña actual y la nueva.' });
      return;
    }
    if (passwords.new_password !== passwords.confirm) {
      setPasswordMessage({ type: 'error', text: 'La confirmación no coincide con la nueva contraseña.' });
      return;
    }
    setPasswordBusy(true);
    try {
      await api.post('/auth/password/', {
        current_password: passwords.current_password,
        new_password: passwords.new_password
      });
      setPasswords({ current_password: '', new_password: '', confirm: '' });
      setPasswordMessage({ type: 'success', text: 'Contraseña actualizada correctamente.' });
    } catch (error) {
      setPasswordMessage({ type: 'error', text: error.message });
    } finally {
      setPasswordBusy(false);
    }
  };

  return (
    <Screen eyebrow="CUENTA" title="Mi perfil" subtitle={user.display_name}>
      {user.must_change_password ? <Banner type="warn">Tu administrador pidió que cambies tu contraseña.</Banner> : null}
      <Card>
        <KeyValue label="Usuario" value={user.username} />
        <KeyValue label="Rol" value={label('role', user.role)} />
        <KeyValue label="Club" value={user.club?.name || '—'} />
      </Card>

      <SectionTitle>Datos personales</SectionTitle>
      <Card>
        <Banner type={message.type} onClose={() => setMessage({ ...message, text: '' })}>{message.text}</Banner>
        <Field label="Nombre" value={form.first_name} onChangeText={set('first_name')} />
        <Field label="Apellido" value={form.last_name} onChangeText={set('last_name')} />
        <Field label="Correo electrónico" value={form.email} onChangeText={set('email')} keyboardType="email-address" autoCapitalize="none" />
        <Field label="Teléfono" value={form.phone} onChangeText={set('phone')} keyboardType="phone-pad" />
        <Field label="Apodo" value={form.nickname} onChangeText={set('nickname')} />
        <Button title="Guardar cambios" onPress={save} loading={saving} />
      </Card>

      <SectionTitle>Cambiar contraseña</SectionTitle>
      <Card>
        <Banner type={passwordMessage.type} onClose={() => setPasswordMessage({ ...passwordMessage, text: '' })}>{passwordMessage.text}</Banner>
        <Field label="Contraseña actual" secureTextEntry value={passwords.current_password} onChangeText={(v) => setPasswords({ ...passwords, current_password: v })} autoCapitalize="none" />
        <Field label="Nueva contraseña" secureTextEntry value={passwords.new_password} onChangeText={(v) => setPasswords({ ...passwords, new_password: v })} autoCapitalize="none" />
        <Field label="Repetir nueva contraseña" secureTextEntry value={passwords.confirm} onChangeText={(v) => setPasswords({ ...passwords, confirm: v })} autoCapitalize="none" />
        <Button title="Actualizar contraseña" variant="secondary" onPress={changePassword} loading={passwordBusy} />
      </Card>

      <View style={{ marginTop: spacing.lg }}>
        <Button title="Cerrar sesión" variant="danger" icon="log-out-outline" onPress={logout} testID="logout" />
        <Text style={[font.small, { textAlign: 'center', marginTop: spacing.md }]}>BoxTrack móvil · comparte cuenta y datos con la web</Text>
      </View>
    </Screen>
  );
}
