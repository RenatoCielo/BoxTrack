import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Bell, CalendarDays, KeyRound, LayoutDashboard, LogOut, Menu, Settings, X,
  Shield, ShieldCheck, Swords, Users, ClipboardCheck, ShoppingBag,
  ClipboardList
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage } from '../services/api';
import { brandColorOnLightSurface, brandSurfaceWithReadableText } from '../utils/brandColors';

function PasswordDialog({ required, onClose }) {
  const { changePassword } = useAuth();
  const [values, setValues] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (values.new_password !== values.confirm_password) {
      setError('Las contraseñas nuevas no coinciden.');
      return;
    }
    setBusy(true);
    try {
      await changePassword(values.current_password, values.new_password);
      onClose();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return <div className="modal-scrim"><section className="form-dialog password-dialog" role="dialog" aria-modal="true" aria-labelledby="password-dialog-title">
    <header className="dialog-heading"><div><p className="eyebrow">SEGURIDAD DE LA CUENTA</p><h2 id="password-dialog-title">{required ? 'Crea tu contraseña personal' : 'Cambiar contraseña'}</h2></div>{!required && <button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button>}</header>
    <form className="resource-form" onSubmit={submit}>
      {required && <p className="member-form-description">Esta cuenta se creó con una clave temporal. Debes reemplazarla para continuar.</p>}
      <label className="field-label"><span>Contraseña actual</span><input className="control" type="password" autoComplete="current-password" required minLength="8" value={values.current_password} onChange={(event) => setValues({ ...values, current_password: event.target.value })} /></label>
      <label className="field-label"><span>Nueva contraseña</span><input className="control" type="password" autoComplete="new-password" required minLength="8" value={values.new_password} onChange={(event) => setValues({ ...values, new_password: event.target.value })} /><small>Usa una contraseña segura de al menos 8 caracteres.</small></label>
      <label className="field-label"><span>Repite la nueva contraseña</span><input className="control" type="password" autoComplete="new-password" required minLength="8" value={values.confirm_password} onChange={(event) => setValues({ ...values, confirm_password: event.target.value })} /></label>
      {error && <div className="notice notice-error">{error}</div>}
      <footer className="dialog-actions">{!required && <button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button>}<button className="button primary-btn" disabled={busy}>{busy ? 'Actualizando...' : 'Guardar contraseña'}</button></footer>
    </form>
  </section></div>;
}

const navigation = [
  { to: '/dashboard', label: 'Resumen', icon: LayoutDashboard, roles: ['ADMIN', 'TRAINER'], end: true },
  { to: '/global-admin', label: 'Clubes pendientes', icon: ShieldCheck, roles: ['ADMIN'] },
  { to: '/athletes', label: 'Mis deportistas', icon: Users, roles: ['ADMIN', 'TRAINER'] },
  { to: '/trainers', label: 'Entrenadores', icon: Shield, roles: ['ADMIN'] },
  { to: '/trainings', label: 'Clases y cupos', icon: CalendarDays, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { to: '/fights', label: 'Combates', icon: Swords, roles: ['ADMIN', 'TRAINER'] },
  { to: '/notifications', label: 'Notificaciones', icon: Bell, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { to: '/store', label: 'Tienda', icon: ShoppingBag, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { to: '/plans', label: 'Planes del gimnasio', icon: ClipboardCheck, roles: ['ADMIN'] },
  { to: '/memberships', label: 'Solicitudes de ingreso', icon: ClipboardList, roles: ['ADMIN'] },
  { to: '/settings', label: 'Configuración', icon: Settings, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] }
];

const visibleNavigation = (user) => {
  if (user?.is_superuser) return navigation.filter((item) => item.to === '/global-admin');
  const role = user?.role;
  return navigation.filter((item) => {
    if (item.to === '/global-admin') return false;
    if (item.to === '/plans') return user?.role === 'ADMIN' && Boolean(user?.club);
    if (item.to === '/memberships') return user?.role === 'ADMIN' && Boolean(user?.club);
    return item.roles.includes(role);
  });
};

export function WorkspaceLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationCountError, setNotificationCountError] = useState('');
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(Boolean(user?.must_change_password));
  const fullName = user?.display_name || [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username;
  const avatar = user?.profile_photo
    ? <img src={user.profile_photo} alt="" />
    : (fullName || 'B').slice(0, 1).toUpperCase();
  const clubBrand = user?.club ? {
    '--forest': brandColorOnLightSurface(user.club.brand_primary, '#B21F32'),
    '--boxing-red': brandColorOnLightSurface(user.club.brand_primary, '#B21F32'),
    '--gold': brandColorOnLightSurface(user.club.brand_accent, '#A67825'),
    '--forest-dark': brandSurfaceWithReadableText(user.club.brand_surface, '#151518'),
  } : undefined;

  useEffect(() => {
    if (user?.must_change_password) setPasswordDialogOpen(true);
  }, [user?.must_change_password]);

  useEffect(() => {
    if (!user || user.is_superuser) {
      setUnreadCount(0);
      return undefined;
    }
    let active = true;
    const refreshCount = async () => {
      try {
        const { data } = await api.get('/notifications/unread-count/');
        if (active) {
          setUnreadCount(data.count);
          setNotificationCountError('');
        }
      } catch (requestError) {
        if (active) setNotificationCountError(getErrorMessage(requestError));
      }
    };
    const refreshOnChange = () => { refreshCount(); };
    refreshCount();
    window.addEventListener('boxtrack:notifications-changed', refreshOnChange);
    return () => {
      active = false;
      window.removeEventListener('boxtrack:notifications-changed', refreshOnChange);
    };
  }, [user?.id, user?.is_superuser]);

  const [logoutDialogOpen, setLogoutDialogOpen] = useState(false);
  const signOut = () => {
    setMobileMenuOpen(false);
    setLogoutDialogOpen(true);
  };
  const confirmSignOut = () => {
    setLogoutDialogOpen(false);
    logout();
    navigate('/login', { replace: true });
  };
  const tabLabels = { '/dashboard': 'Resumen', '/athletes': 'Plantel', '/trainings': 'Clases', '/store': 'Tienda', '/notifications': 'Avisos', '/global-admin': 'Clubes' };
  const mobilePaths = user?.is_superuser
    ? ['/global-admin']
    : ['/dashboard', '/athletes', '/trainings', '/notifications', '/store'];
  const mobileTabs = mobilePaths
    .map((path) => visibleNavigation(user).find(({ to }) => to === path))
    .filter(Boolean)
    .slice(0, 4);

  return (
    <div className="workspace-shell" style={clubBrand}>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          {user?.club?.logo ? <img className="brand-mark brand-logo" src={user.club.logo} alt="" /> : <span className="brand-mark">BX</span>}
          <div><strong>BOXTRACK</strong><small>{user?.is_superuser ? 'ADMINISTRACIÓN GLOBAL' : 'CLUB MANAGEMENT'}</small></div>
        </div>
        <div className="club-badge"><span className="club-dot" />{user?.is_superuser ? 'Revisión de clubes' : user?.club?.name || 'Mi club'}</div>
        <nav className="workspace-nav" aria-label="Navegación principal">
          <span className="nav-caption">GESTIÓN</span>
          {visibleNavigation(user).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>{to === '/notifications' && unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? '99+' : unreadCount}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {notificationCountError && <small className="notification-count-error" role="status" title={notificationCountError}>No se pudo actualizar el contador de avisos.</small>}
          <div className="user-chip">
            <span className="user-avatar">{avatar}</span>
            <div className="user-meta"><strong>{fullName}</strong><small>{user?.is_superuser ? 'Superadministrador' : user?.role || 'Usuario'}</small></div>
            <button className="icon-button logout-button" onClick={() => setPasswordDialogOpen(true)} title="Cambiar contraseña" aria-label="Cambiar contraseña"><KeyRound size={17} /></button>
            <button className="icon-button logout-button" onClick={signOut} title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-topbar">
          <button className="icon-button mobile-menu-toggle" onClick={() => setMobileMenuOpen((open) => !open)} aria-label={mobileMenuOpen ? 'Cerrar navegación' : 'Abrir navegación'} aria-expanded={mobileMenuOpen}>
            {mobileMenuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
          <div className="mobile-brand"><span className="brand-mark">BX</span><strong>BOXTRACK</strong></div>
          <div className="topbar-club">{user?.is_superuser ? 'Administración global' : user?.club?.name || 'Mi club'}</div>
          {!user?.is_superuser && <NavLink to="/settings" className={({ isActive }) => `icon-button settings-shortcut${isActive ? ' active' : ''}`} aria-label="Abrir configuración" title="Configuración">
            <Settings size={20} />
          </NavLink>}
        </header>
        <main className="workspace-content"><Outlet /></main>
      </div>
      {mobileMenuOpen && <div className="mobile-nav-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setMobileMenuOpen(false); }}>
        <nav className="mobile-nav-drawer" aria-label="Navegación móvil">
          <div className="mobile-nav-heading"><span>{user?.is_superuser ? 'Administración global' : user?.club?.name || 'Mi club'}</span><button className="icon-button mobile-nav-close" onClick={() => setMobileMenuOpen(false)} aria-label="Cerrar navegación"><X size={20} /></button></div>
          <div className="mobile-nav-links">{visibleNavigation(user).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setMobileMenuOpen(false)} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>{to === '/notifications' && unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? '99+' : unreadCount}</span>}
            </NavLink>
          ))}</div>
          <div className="mobile-nav-account"><span className="user-avatar">{avatar}</span><div className="user-meta"><strong>{fullName}</strong><small>{user?.is_superuser ? 'Superadministrador' : user?.role || 'Usuario'}</small></div><button className="icon-button" onClick={() => { setMobileMenuOpen(false); setPasswordDialogOpen(true); }} title="Cambiar contraseña" aria-label="Cambiar contraseña"><KeyRound size={18} /></button><button className="icon-button" onClick={signOut} title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={18} /></button></div>
        </nav>
      </div>}
      <nav className="bottom-tabbar" aria-label="Navegación rápida">
        {mobileTabs.map(({ to, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `bottom-tab${isActive ? ' active' : ''}`}>
            <span className="bottom-tab-icon"><Icon size={22} strokeWidth={1.9} />{to === '/notifications' && unreadCount > 0 && <span className="notification-count">{unreadCount > 99 ? '99+' : unreadCount}</span>}</span><span>{tabLabels[to]}</span>
          </NavLink>
        ))}
        <button type="button" className={`bottom-tab${mobileMenuOpen ? ' active' : ''}`} onClick={() => setMobileMenuOpen((open) => !open)} aria-expanded={mobileMenuOpen}>
          <Menu size={22} strokeWidth={1.9} /><span>Más</span>
        </button>
      </nav>
      {logoutDialogOpen && <div className="modal-scrim confirm-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setLogoutDialogOpen(false); }}>
        <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="logout-title" aria-describedby="logout-text">
          <span className="confirm-icon"><LogOut size={24} /></span>
          <h2 id="logout-title">¿Cerrar sesión?</h2>
          <p id="logout-text">Tendrás que ingresar de nuevo para volver a usar BOXTRACK.</p>
          <div className="confirm-actions">
            <button type="button" className="button button-secondary" onClick={() => setLogoutDialogOpen(false)} autoFocus>Cancelar</button>
            <button type="button" className="button primary-btn" onClick={confirmSignOut}>Sí, cerrar sesión</button>
          </div>
        </section>
      </div>}
      {passwordDialogOpen && <PasswordDialog required={Boolean(user?.must_change_password)} onClose={() => setPasswordDialogOpen(false)} />}
    </div>
  );
}