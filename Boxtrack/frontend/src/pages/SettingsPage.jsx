import { useEffect, useState } from 'react';
import { ChevronDown, KeyRound, Moon, Save, Sun, UserRound, ShieldCheck, ImagePlus, Palette, Sparkles } from 'lucide-react';
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
});

const brandPresets = [
  { name: 'Rojo de ring', primary: '#B21F32', accent: '#D6A94B', surface: '#151518' },
  { name: 'Azul acero', primary: '#285A77', accent: '#E4A84D', surface: '#14232C' },
  { name: 'Verde esquina', primary: '#28604D', accent: '#D6AE65', surface: '#16241E' },
];

const initialBrand = (club) => ({
  name: club?.name || '',
  description: club?.description || '',
  address: club?.address || '',
  phone: club?.phone || '',
  email: club?.email || '',
  website: club?.website || '',
  brand_primary: club?.brand_primary || '#B21F32',
  brand_accent: club?.brand_accent || '#D6A94B',
  brand_surface: club?.brand_surface || '#151518',
});

function hslToHex(h, s, l) {
  const chroma = (1 - Math.abs(2 * l - 1)) * s;
  const section = h / 60;
  const x = chroma * (1 - Math.abs(section % 2 - 1));
  const [red, green, blue] = section < 1 ? [chroma, x, 0]
    : section < 2 ? [x, chroma, 0]
      : section < 3 ? [0, chroma, x]
        : section < 4 ? [0, x, chroma]
          : section < 5 ? [x, 0, chroma] : [chroma, 0, x];
  const match = l - chroma / 2;
  return `#${[red, green, blue].map((channel) => Math.round((channel + match) * 255).toString(16).padStart(2, '0')).join('')}`.toUpperCase();
}

async function recommendPalette(imageFile) {
  const bitmap = await createImageBitmap(imageFile);
  const canvas = document.createElement('canvas');
  canvas.width = 32;
  canvas.height = 32;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('No se pudo analizar la imagen en este navegador.');
  context.drawImage(bitmap, 0, 0, 32, 32);
  bitmap.close();
  const pixels = context.getImageData(0, 0, 32, 32).data;
  const paletteBuckets = new Map();
  for (let index = 0; index < pixels.length; index += 4) {
    const r = pixels[index] / 255;
    const g = pixels[index + 1] / 255;
    const b = pixels[index + 2] / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;
    const lightness = (max + min) / 2;
    const saturation = delta === 0 ? 0 : delta / (1 - Math.abs(2 * lightness - 1));
    if (saturation < 0.24 || lightness < 0.12 || lightness > 0.88) continue;
    let hue = max === r ? 60 * (((g - b) / delta) % 6)
      : max === g ? 60 * ((b - r) / delta + 2)
        : 60 * ((r - g) / delta + 4);
    if (hue < 0) hue += 360;
    const bucket = Math.floor(hue / 20);
    const colorSample = paletteBuckets.get(bucket) || { count: 0, hue: 0, saturation: 0, lightness: 0 };
    colorSample.count += 1;
    colorSample.hue += hue;
    colorSample.saturation += saturation;
    colorSample.lightness += lightness;
    paletteBuckets.set(bucket, colorSample);
  }
  const dominant = [...paletteBuckets.values()].sort((first, second) => second.count - first.count)[0];
  const sample = dominant
    ? { hue: dominant.hue / dominant.count, saturation: dominant.saturation / dominant.count, lightness: dominant.lightness / dominant.count }
    : { hue: 350, saturation: 0.58, lightness: 0.4 };
  const primaryHue = sample.hue;
  return {
    brand_primary: hslToHex(primaryHue, Math.max(0.5, sample.saturation), Math.min(0.42, Math.max(0.3, sample.lightness))),
    brand_accent: hslToHex((primaryHue + 38) % 360, 0.62, 0.62),
    brand_surface: hslToHex(primaryHue, 0.24, 0.12),
  };
}

export function SettingsPage() {
  const { user, theme, setTheme, updateProfile, changePassword } = useAuth();
  const [profile, setProfile] = useState(() => initialProfile(user));
  const [passwords, setPasswords] = useState({ current: '', next: '', confirmation: '' });
  const [busy, setBusy] = useState(false);
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [error, setError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [notice, setNotice] = useState('');
  const [clubIsPublic, setClubIsPublic] = useState(false);
  const [publicationBusy, setPublicationBusy] = useState(false);
  const [publicationError, setPublicationError] = useState('');
  const [publicationNotice, setPublicationNotice] = useState('');
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [profilePhotoPreview, setProfilePhotoPreview] = useState('');
  const [profilePhotoError, setProfilePhotoError] = useState('');
  const [brand, setBrand] = useState(() => initialBrand(user?.club));
  const [brandLogo, setBrandLogo] = useState(null);
  const [brandLogoPreview, setBrandLogoPreview] = useState('');
  const [brandBusy, setBrandBusy] = useState(false);
  const [brandError, setBrandError] = useState('');
  const [brandNotice, setBrandNotice] = useState('');
  const [paletteError, setPaletteError] = useState('');

  const isClubAdmin = user?.role === 'ADMIN';
  const verificationStatus = user?.club?.verification_status;
  const isClubApproved = verificationStatus === 'APPROVED';
  const verificationStatusLabel = {
    PENDING: 'Pendiente',
    APPROVED: 'Aprobado',
    REJECTED: 'Rechazado',
  }[verificationStatus] || 'Sin estado';

  useEffect(() => {
    setProfile(initialProfile(user));
  }, [user]);

  useEffect(() => {
    if (!isClubAdmin) return undefined;
    let active = true;
    api.get('/clubs/brand/')
      .then(({ data }) => {
        if (active) setBrand(initialBrand(data));
      })
      .catch((requestError) => {
        if (active) setBrandError(getErrorMessage(requestError));
      });
    return () => { active = false; };
  }, [isClubAdmin]);

  useEffect(() => {
    if (!brandLogo) {
      setBrandLogoPreview('');
      return undefined;
    }
    const preview = URL.createObjectURL(brandLogo);
    setBrandLogoPreview(preview);
    return () => URL.revokeObjectURL(preview);
  }, [brandLogo]);

  useEffect(() => {
    if (!profilePhoto) {
      setProfilePhotoPreview('');
      return undefined;
    }
    const preview = URL.createObjectURL(profilePhoto);
    setProfilePhotoPreview(preview);
    return () => URL.revokeObjectURL(preview);
  }, [profilePhoto]);

  useEffect(() => {
    if (!isClubAdmin) return undefined;
    let active = true;
    api.get('/clubs/publication/')
      .then(({ data }) => {
        if (active) setClubIsPublic(data.is_public);
      })
      .catch((requestError) => {
        if (active) setPublicationError(getErrorMessage(requestError));
      });
    return () => { active = false; };
  }, [isClubAdmin]);

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
      if (profilePhoto) {
        const formData = new FormData();
        Object.entries(profile).forEach(([key, value]) => formData.append(key, String(value)));
        formData.append('profile_photo', profilePhoto);
        await updateProfile(formData);
        setProfilePhoto(null);
      } else {
        await updateProfile(profile);
      }
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

  const savePublication = async (event) => {
    event.preventDefault();
    setPublicationBusy(true);
    setPublicationError('');
    setPublicationNotice('');
    try {
      const { data } = await api.patch('/clubs/publication/', { is_public: clubIsPublic });
      setClubIsPublic(data.is_public);
      setPublicationNotice(data.is_public ? 'Tu gimnasio aparecerá en el directorio público.' : 'Tu gimnasio ya no aparecerá en el directorio público.');
    } catch (requestError) {
      setPublicationError(getErrorMessage(requestError));
    } finally {
      setPublicationBusy(false);
    }
  };

  const saveBrand = async (event) => {
    event.preventDefault();
    setBrandBusy(true);
    setBrandError('');
    setBrandNotice('');
    try {
      const formData = new FormData();
      Object.entries(brand).forEach(([key, value]) => formData.append(key, value));
      if (brandLogo) formData.append('logo', brandLogo);
      const { data } = await api.patch('/clubs/brand/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setBrand(initialBrand(data));
      setBrandLogo(null);
      setBrandNotice('La página de tu gimnasio quedó actualizada.');
    } catch (requestError) {
      setBrandError(getErrorMessage(requestError));
    } finally {
      setBrandBusy(false);
    }
  };

  const updateBrand = (event) => setBrand((current) => ({ ...current, [event.target.name]: event.target.value }));
  const choosePreset = (preset) => setBrand((current) => ({
    ...current,
    brand_primary: preset.primary,
    brand_accent: preset.accent,
    brand_surface: preset.surface,
  }));
  const chooseLogo = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setBrandError('El logo no puede superar los 5 MB.');
      setBrandLogo(null);
      event.target.value = '';
      return;
    }
    setBrandLogo(file);
    setPaletteError('');
    try {
      const recommendation = await recommendPalette(file);
      setBrand((current) => ({ ...current, ...recommendation }));
    } catch (requestError) {
      setPaletteError(requestError.message || 'No se pudo recomendar una paleta desde esta imagen.');
    }
  };

  const chooseProfilePhoto = (event) => {
    const file = event.target.files?.[0];
    setProfilePhotoError('');
    if (file && file.size > 5 * 1024 * 1024) {
      setProfilePhotoError('La foto no puede superar los 5 MB.');
      setProfilePhoto(null);
      event.target.value = '';
      return;
    }
    setProfilePhoto(file || null);
  };

  const profilePhotoUrl = profilePhotoPreview || user?.profile_photo;

  return <section className="page-stack settings-page">
    <header className="settings-hero">
      <span className="settings-avatar">{profilePhotoUrl ? <img src={profilePhotoUrl} alt="Foto de perfil" /> : (user?.display_name || user?.username || 'B').slice(0, 1).toUpperCase()}</span>
      <div><h1>{user?.display_name || user?.username}</h1><p>@{user?.username}{user?.club?.name ? ` · ${user.club.name}` : ''}</p></div>
    </header>

    <div className="settings-quick" role="group" aria-label="Tema de la aplicación">
      <button type="button" className={`theme-option${theme === 'light' ? ' selected' : ''}`} aria-pressed={theme === 'light'} onClick={() => setTheme('light')}><Sun size={18} /><span>Claro</span></button>
      <button type="button" className={`theme-option${theme === 'dark' ? ' selected' : ''}`} aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}><Moon size={18} /><span>Oscuro</span></button>
    </div>

    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    {error && <div className="notice notice-error" role="alert">{error}</div>}

    {isClubAdmin && <form className="surface-panel club-publication-settings" onSubmit={savePublication}>
      <header className="section-heading"><div><p className="eyebrow">PERFIL DEL GIMNASIO</p><h2>Directorio público</h2></div></header>
      <p className="page-description">Al publicar el gimnasio, los visitantes podrán ver su nombre, logo, descripción, dirección, contacto público y planes activos.</p>
      <div className={`notice${verificationStatus === 'REJECTED' ? ' notice-error' : ''}`} role="status">
        <strong>Verificación: {verificationStatusLabel}.</strong>{' '}
        {verificationStatus === 'PENDING'
          ? 'Tu club está pendiente de verificación y aún no aparece en la portada pública.'
          : verificationStatus === 'REJECTED'
            ? 'El club fue rechazado y no aparece en la portada pública.'
            : 'Tu club está aprobado y puede aparecer en la portada pública.'}
      </div>
      {publicationNotice && <div className="notice notice-success" role="status">{publicationNotice}</div>}
      {publicationError && <div className="notice notice-error" role="alert">{publicationError}</div>}
      <label className="settings-toggle">
        <span><strong>Mostrar mi gimnasio públicamente</strong><small>{isClubApproved ? 'Puedes cambiar esta opción cuando quieras.' : 'Solo puedes cambiar esta opción cuando tu club esté aprobado.'}</small></span>
        <input type="checkbox" checked={clubIsPublic} disabled={!isClubApproved} onChange={(event) => setClubIsPublic(event.target.checked)} />
      </label>
      <div className="settings-save-row"><button className="button primary-btn" disabled={publicationBusy || !isClubApproved}>{publicationBusy ? 'Guardando...' : 'Guardar publicación'}</button></div>
    </form>}

    {isClubAdmin && <form className="surface-panel gym-brand-settings" onSubmit={saveBrand}>
      <header className="section-heading"><div><p className="eyebrow">IDENTIDAD DEL GIMNASIO</p><h2>Personaliza tu página</h2></div><Palette size={20} /></header>
      <p className="page-description">Actualiza la imagen y la información pública. La paleta elegida se aplicará a tu espacio de trabajo y a la ficha pública.</p>
      <div className="gym-brand-preview" style={{ '--preview-primary': brand.brand_primary, '--preview-accent': brand.brand_accent, '--preview-surface': brand.brand_surface }}>
        <div className="gym-brand-preview-logo">{brandLogoPreview || user?.club?.logo ? <img src={brandLogoPreview || user.club.logo} alt="" /> : <span>BX</span>}</div>
        <div><small>VISTA PREVIA · BOXTRACK</small><strong>{brand.name || 'Nombre de tu gimnasio'}</strong><span>{brand.description || 'Tu esencia, tu comunidad y tus próximos combates.'}</span></div>
        <i />
      </div>
      <div className="settings-field-grid">
        <label className="field-label settings-full-width"><span>Nombre del gimnasio</span><input className="control" name="name" required maxLength="200" value={brand.name} onChange={updateBrand} /></label>
        <label className="field-label settings-full-width"><span>Descripción</span><textarea className="control" name="description" rows="3" maxLength="2000" value={brand.description} onChange={updateBrand} placeholder="Qué hace único a tu gimnasio" /></label>
        <label className="field-label"><span>Dirección pública</span><input className="control" name="address" maxLength="255" value={brand.address} onChange={updateBrand} /></label>
        <label className="field-label"><span>Teléfono público</span><input className="control" name="phone" maxLength="30" value={brand.phone} onChange={updateBrand} /></label>
        <label className="field-label"><span>Correo público</span><input className="control" name="email" type="email" value={brand.email} onChange={updateBrand} /></label>
        <label className="field-label"><span>Sitio web</span><input className="control" name="website" type="url" value={brand.website} onChange={updateBrand} placeholder="https://..." /></label>
      </div>
      <div className="gym-brand-upload-row">
        <label className="brand-upload-control"><ImagePlus size={18} /><span><strong>Logo o imagen del gimnasio</strong><small>JPG, PNG o WebP · máximo 5 MB</small></span><input type="file" accept="image/*" onChange={chooseLogo} /></label>
        <span className="page-description">Al elegir una imagen se sugiere una paleta con sus tonos dominantes.</span>
      </div>
      <section className="brand-palette-section">
        <div><p className="eyebrow">PALETA DE COLOR</p><h3>Elige la esencia del club</h3></div>
        <div className="brand-presets">{brandPresets.map((preset) => <button key={preset.name} type="button" className="brand-preset" onClick={() => choosePreset(preset)}><i style={{ background: preset.primary }} /><i style={{ background: preset.accent }} /><i style={{ background: preset.surface }} /><span>{preset.name}</span></button>)}</div>
        <div className="settings-field-grid brand-colors">
          <label className="field-label"><span>Color principal</span><input type="color" name="brand_primary" value={brand.brand_primary} onChange={updateBrand} /></label>
          <label className="field-label"><span>Color de acento</span><input type="color" name="brand_accent" value={brand.brand_accent} onChange={updateBrand} /></label>
          <label className="field-label"><span>Color de identidad oscura</span><input type="color" name="brand_surface" value={brand.brand_surface} onChange={updateBrand} /></label>
        </div>
        {paletteError && <div className="notice" role="status"><Sparkles size={15} />{paletteError}</div>}
      </section>
      {brandNotice && <div className="notice notice-success" role="status">{brandNotice}</div>}
      {brandError && <div className="notice notice-error" role="alert">{brandError}</div>}
      <div className="settings-save-row"><button className="button primary-btn" disabled={brandBusy}><Save size={16} />{brandBusy ? 'Guardando...' : 'Guardar página del gimnasio'}</button></div>
    </form>}

    <form className="settings-layout" onSubmit={saveProfile}>
      <details className="settings-accordion">
        <summary><span className="settings-icon"><UserRound size={19} /></span><span className="settings-summary-text"><strong>Perfil personal</strong><small>Nombre, contacto y apodo</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
        <div className="settings-accordion-body">
        <div className="settings-field-grid">
          <label className="field-label profile-photo-control settings-full-width"><span>Foto de perfil personal</span><input type="file" accept="image/*" onChange={chooseProfilePhoto} /><small>Imagen JPG, PNG o WebP · máximo 5 MB</small>{profilePhotoError && <small className="profile-photo-error">{profilePhotoError}</small>}</label>
          <label className="field-label"><span>Nombre de usuario</span><input className="control" name="username" autoComplete="username" maxLength="150" required value={profile.username} onChange={update} /><small>Lo usarás para iniciar sesión.</small></label>
          <label className="field-label"><span>Correo electrónico</span><input className="control" name="email" type="email" autoComplete="email" value={profile.email} onChange={update} /></label>
          <label className="field-label"><span>Nombre</span><input className="control" name="first_name" autoComplete="given-name" value={profile.first_name} onChange={update} /></label>
          <label className="field-label"><span>Apellido</span><input className="control" name="last_name" autoComplete="family-name" value={profile.last_name} onChange={update} /></label>
          <label className="field-label"><span>Teléfono</span><input className="control" name="phone" type="tel" autoComplete="tel" placeholder="+56912345678" value={profile.phone} onChange={update} /></label>
          <label className="field-label"><span>Apodo</span><input className="control" name="nickname" maxLength="50" value={profile.nickname} onChange={update} placeholder="¿Cómo te dicen en el gimnasio?" /></label>
        </div>
        <label className="settings-toggle">
          <span><strong>Mostrar mi apodo en el club</strong><small>Se usará como nombre visible en clases, listas y pedidos.</small></span>
          <input type="checkbox" name="use_nickname" checked={profile.use_nickname} disabled={!profile.nickname.trim()} onChange={update} />
        </label>
        </div>
      </details>

      <details className="settings-accordion">
        <summary><span className="settings-icon"><ShieldCheck size={19} /></span><span className="settings-summary-text"><strong>Privacidad</strong><small>Qué ve tu club de ti</small></span><ChevronDown size={18} className="settings-chevron" /></summary>
        <div className="settings-accordion-body">
        <label className="settings-toggle">
          <span><strong>Compartir mi teléfono con el club</strong><small>Si lo desactivas, solo tú y los administradores podrán verlo.</small></span>
          <input type="checkbox" name="share_phone" checked={profile.share_phone} onChange={update} />
        </label>
        </div>
      </details>

      <div className="settings-save-row">
        <button className="button primary-btn" disabled={busy}><Save size={16} />{busy ? 'Guardando...' : 'Guardar cambios'}</button>
      </div>
    </form>

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
