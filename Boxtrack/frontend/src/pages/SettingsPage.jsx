import { useEffect, useState } from 'react';
import { ChevronDown, KeyRound, Moon, Save, Sun, UserRound, ShieldCheck, Palette } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage } from '../services/api';

const initialProfile = (user) => ({
  username: user?.username || '',
  email: user?.email || '',
  first_name: user?.first_name || '',
  last_name: user?.last_name || '',
  phone: user?.phone || '',
  nickname: user?.nickname || '',
  use_nickname: Boolean(user?.use_nickname),
  share_phone: user?.share_phone ?? true,
  discipline: user?.discipline || (user?.club?.disciplines?.length === 1 ? user.club.disciplines[0] : ''),
});

export function SettingsPage() {
  const { user, theme, setTheme, updateProfile, updateClub, changePassword } = useAuth();
  const [profile, setProfile] = useState(() => initialProfile(user));
  const [passwords, setPasswords] = useState({ current: '', next: '', confirmation: '' });
  const [busy, setBusy] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [error, setError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [notice, setNotice] = useState('');
  const [branding, setBranding] = useState({ primary_color: user?.club?.primary_color || '#D7263D', accent_color: user?.club?.accent_color || '#1F2937' });
  const [logo, setLogo] = useState(null);
  const [brandingBusy, setBrandingBusy] = useState(false);
  const [brandingError, setBrandingError] = useState('');
  const [disciplineBusy, setDisciplineBusy] = useState(false);
  const [disciplineError, setDisciplineError] = useState('');
  const disciplines = Array.isArray(user?.club?.disciplines) ? [...new Set(user.club.disciplines.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim()))] : [];

  useEffect(() => {
    setProfile(initialProfile(user));
  }, [user]);

  useEffect(() => {
    setBranding({ primary_color: user?.club?.primary_color || '#D7263D', accent_color: user?.club?.accent_color || '#1F2937' });
  }, [user?.club?.primary_color, user?.club?.accent_color]);

  const update = (event) => {
    const { name, value, checked, type } = event.target;
    if (name === 'nickname' && !value.trim()) {
      setProfile((current) => ({ ...current, nickname: value, use_nickname: false }));
      return;
    }
    setProfile((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const { discipline, ...otherProfile } = profile;
      await updateProfile(discipline && disciplines.includes(discipline) ? { ...otherProfile, discipline } : otherProfile);
      setNotice('Tu perfil y tus preferencias se guardaron.');
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    setPasswordError('');
    if (passwords.next !== passwords.confirmation) {
      setPasswordError('Las contraseñas nuevas no coinciden.');
      return;
    }
    setPasswordBusy(true);
    try {
      await changePassword(passwords.current, passwords.next);
      setPasswords({ current: '', next: '', confirmation: '' });
      setNotice('Tu contraseña se actualizó correctamente.');
    } catch (requestError) {
      setPasswordError(getErrorMessage(requestError));
    } finally {
      setPasswordBusy(false);
    }
  };

  const saveBranding = async (event) => {
    event.preventDefault();
    setBrandingBusy(true);
    setBrandingError('');
    try {
      const form = new FormData();
      form.append('primary_color', branding.primary_color);
      form.append('accent_color', branding.accent_color);
      if (logo) form.append('logo', logo);
      const { data } = await api.patch('/clubs/branding/', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      updateClub(data);
      setLogo(null);
      setNotice('La imagen y los colores del club se guardaron.');
    } catch (requestError) {
      setBrandingError(getErrorMessage(requestError));
    } finally {
      setBrandingBusy(false);
    }
  };

  const initializeDiscipline = async () => {
    setDisciplineBusy(true);
    setDisciplineError('');
    try {
      const { data } = await api.post('/clubs/discipline/initialize/');
      updateClub(data);
      setNotice('Boxeo quedó configurado como disciplina del club.');
    } catch (requestError) {
      setDisciplineError(getErrorMessage(requestError));
    } finally {
      setDisciplineBusy(false);
    }
  };

  return <section className="page-stack settings-page">
    <header className="settings-hero">
      <span className="settings-avatar" aria-hidden="true">{(user?.display_name || user?.username || 'B').slice(0, 1).toUpperCase()}</span>
      <div><h1>{user?.display_name || user?.username}</h1><p>@{user?.username}{user?.club?.name ? ` · ${user.club.name}` : ''}</p></div>
    </header>

    <div className="settings-quick" role="group" aria-label="Tema de la aplicación">
      <button type="button" className={`theme-option${theme === 'light' ? ' selected' : ''}`} aria-pressed={theme === 'light'} onClick={() => setTheme('light')}><Sun size={18} /><span>Claro</span></button>
      <button type="button" className={`theme-option${theme === 'dark' ? ' selected' : ''}`} aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}><Moon size={18} /><span>Oscuro</span></button>
    </div>

    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    {error && <div className="notice notice-error" role="alert">{error}</div>}

    <div className="settings-layout">
      {user?.role === 'ADMIN' && !user?.is_superuser && Array.isArray(user?.club?.disciplines) && user.club.disciplines.length === 0 && <section className="surface-panel">
        <div className="section-heading"><div><p className="eyebrow">DISCIPLINA DEL CLUB</p><h2>Configura tu gimnasio</h2></div></div>
        <p className="page-description">Tu club aún no tiene disciplinas. Configura Boxeo para poder crear cuentas.</p>
        {disciplineError && <div className="notice notice-error" role="alert">{disciplineError}</div>}
        <button type="button" className="button primary-btn" onClick={initializeDiscipline} disabled={disciplineBusy}>{disciplineBusy ? 'Guardando...' : 'Configurar Boxeo'}</button>
      </section>}
      {user?.role === 'ADMIN' && !user?.is_superuser && <details className="settings-accordion" open>
        <summary><span className="settings-icon"><Palette size={19} /></span><span className="settings-summary-text"><strong>Imagen del club</strong><small>Colores y logotipo para las cuentas del equipo</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
        <form className="settings-accordion-body settings-field-grid" onSubmit={saveBranding}>
          <label className="field-label"><span>Color principal</span><input className="control color-control" type="color" value={branding.primary_color} onChange={(event) => setBranding({ ...branding, primary_color: event.target.value })} /></label>
          <label className="field-label"><span>Color de acento</span><input className="control color-control" type="color" value={branding.accent_color} onChange={(event) => setBranding({ ...branding, accent_color: event.target.value })} /></label>
          <label className="field-label field-wide"><span>Logotipo (PNG, JPG o WebP, hasta 2 MB)</span><input className="control" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setLogo(event.target.files?.[0] || null)} /></label>
          {user?.club?.logo && <div className="club-logo-preview"><img src={user.club.logo} alt={`Logotipo de ${user.club.name}`} /><span>Logotipo actual</span></div>}
          {brandingError && <div className="notice notice-error settings-full-width">{brandingError}</div>}
          <div className="settings-full-width settings-save-row"><button className="button primary-btn" disabled={brandingBusy}>{brandingBusy ? 'Guardando...' : 'Guardar imagen del club'}</button></div>
        </form>
      </details>}
      <form className="settings-profile-form" onSubmit={saveProfile}>
      <details className="settings-accordion">
        <summary><span className="settings-icon"><UserRound size={19} /></span><span className="settings-summary-text"><strong>Perfil personal</strong><small>Nombre, contacto y apodo</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
        <div className="settings-accordion-body">
        <div className="settings-field-grid">
          <label className="field-label"><span>Nombre de usuario</span><input className="control" name="username" autoComplete="username" maxLength="150" required value={profile.username} onChange={update} /><small>Lo usarás para iniciar sesión.</small></label>
          <label className="field-label"><span>Correo electrónico</span><input className="control" name="email" type="email" autoComplete="email" value={profile.email} onChange={update} /></label>
          <label className="field-label"><span>Nombre</span><input className="control" name="first_name" autoComplete="given-name" value={profile.first_name} onChange={update} /></label>
          <label className="field-label"><span>Apellido</span><input className="control" name="last_name" autoComplete="family-name" value={profile.last_name} onChange={update} /></label>
          <label className="field-label"><span>Teléfono</span><input className="control" name="phone" type="tel" autoComplete="tel" placeholder="+56912345678" value={profile.phone} onChange={update} /></label>
          {!user?.is_superuser && <label className="field-label"><span>Apodo</span><input className="control" name="nickname" maxLength="50" value={profile.nickname} onChange={update} placeholder="¿Cómo te dicen en el gimnasio?" /></label>}
          {!user?.is_superuser && disciplines.length === 1 && <label className="field-label"><span>Disciplina del club</span><input className="control" value={profile.discipline} readOnly /><small>Es la única disciplina del club.</small></label>}
          {!user?.is_superuser && disciplines.length > 1 && <label className="field-label"><span>Disciplina del club</span><select className="control" name="discipline" value={profile.discipline} onChange={update}><option value="">Seleccionar</option>{disciplines.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>}
        </div>
        {!user?.is_superuser && <label className="settings-toggle">
          <span><strong>Mostrar mi apodo en el club</strong><small>Se usará como nombre visible en clases, listas y pedidos.</small></span>
          <input type="checkbox" name="use_nickname" checked={profile.use_nickname} disabled={!profile.nickname.trim()} onChange={update} />
        </label>}
        </div>
      </details>

      {!user?.is_superuser && <details className="settings-accordion">
        <summary><span className="settings-icon"><ShieldCheck size={19} /></span><span className="settings-summary-text"><strong>Privacidad</strong><small>Qué ve tu club de ti</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
        <div className="settings-accordion-body">
        <label className="settings-toggle">
          <span><strong>Compartir mi teléfono con el club</strong><small>Si lo desactivas, solo tú y los administradores podrán verlo.</small></span>
          <input type="checkbox" name="share_phone" checked={profile.share_phone} onChange={update} />
        </label>
        </div>
      </details>}

      <div className="settings-save-row">
        <button className="button primary-btn" disabled={busy}><Save size={16} />{busy ? 'Guardando...' : 'Guardar cambios'}</button>
      </div>
      </form>
    </div>

    <details className="settings-accordion">
      <summary><span className="settings-icon"><KeyRound size={19} /></span><span className="settings-summary-text"><strong>Seguridad</strong><small>Cambiar contraseña</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
      <form className="settings-field-grid password-settings-form settings-accordion-body" onSubmit={savePassword}>
        <label className="field-label"><span>Contraseña actual</span><input className="control" type="password" autoComplete="current-password" required minLength="8" value={passwords.current} onChange={(event) => setPasswords({ ...passwords, current: event.target.value })} /></label>
        <label className="field-label"><span>Nueva contraseña</span><input className="control" type="password" autoComplete="new-password" required minLength="8" value={passwords.next} onChange={(event) => setPasswords({ ...passwords, next: event.target.value })} /></label>
        <label className="field-label"><span>Repite la contraseña</span><input className="control" type="password" autoComplete="new-password" required minLength="8" value={passwords.confirmation} onChange={(event) => setPasswords({ ...passwords, confirmation: event.target.value })} /></label>
        {passwordError && <div className="notice notice-error settings-full-width" role="alert">{passwordError}</div>}
        <div className="settings-full-width settings-save-row"><button className="button button-secondary" disabled={passwordBusy}><KeyRound size={15} />{passwordBusy ? 'Actualizando...' : 'Cambiar contraseña'}</button></div>
      </form>
    </details>
  </section>;
}
