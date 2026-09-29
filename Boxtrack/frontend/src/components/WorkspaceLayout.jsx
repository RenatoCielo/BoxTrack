import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Activity, Bell, CalendarDays, Dumbbell, FileSpreadsheet, KeyRound, LayoutDashboard, LogOut, Menu, X,
  Scale, Shield, Swords, Users, ClipboardCheck, Trophy, ShoppingBag
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { getErrorMessage } from '../services/api';

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
  { to: '/athletes', label: 'Deportistas', icon: Users, roles: ['ADMIN', 'TRAINER'] },
  { to: '/competitors', label: 'Boxeadores competidores', icon: Trophy, roles: ['ADMIN', 'TRAINER'] },
  { to: '/trainers', label: 'Entrenadores', icon: Shield, roles: ['ADMIN'] },
  { to: '/groups', label: 'Grupos', icon: Activity, roles: ['ADMIN', 'TRAINER'] },
  { to: '/trainings', label: 'Clases y cupos', icon: CalendarDays, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { to: '/attendance', label: 'Asistencia', icon: ClipboardCheck, roles: ['ADMIN', 'TRAINER'] },
  { to: '/fights', label: 'Historial de combates', icon: Swords, roles: ['ADMIN', 'TRAINER'] },
  { to: '/evaluations', label: 'Evaluaciones', icon: Dumbbell, roles: ['ADMIN', 'TRAINER'] },
  { to: '/weight', label: 'Control de peso', icon: Scale, roles: ['ADMIN', 'TRAINER'] },
  { to: '/alerts', label: 'Alertas', icon: Bell, roles: ['ADMIN', 'TRAINER'] },
  { to: '/reports', label: 'Reportes', icon: FileSpreadsheet, roles: ['ADMIN'] },
  { to: '/notifications', label: 'Notificaciones', icon: Bell, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] },
  { to: '/store', label: 'Tienda', icon: ShoppingBag, roles: ['ADMIN', 'TRAINER', 'ATHLETE'] }
];

const visibleNavigation = (role) => navigation.filter((item) => item.roles.includes(role));

export function WorkspaceLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(Boolean(user?.must_change_password));
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username;

  useEffect(() => {
    if (user?.must_change_password) setPasswordDialogOpen(true);
  }, [user?.must_change_password]);

  const signOut = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar">
        <div className="workspace-brand">
          <span className="brand-mark">BX</span>
          <div><strong>BOXTRACK</strong><small>CLUB MANAGEMENT</small></div>
        </div>
        <div className="club-badge"><span className="club-dot" />{user?.club?.name || 'Mi club'}</div>
        <nav className="workspace-nav" aria-label="Navegación principal">
          <span className="nav-caption">GESTIÓN</span>
          {visibleNavigation(user?.role).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="user-chip">
            <span className="user-avatar">{(fullName || 'B').slice(0, 1).toUpperCase()}</span>
            <div className="user-meta"><strong>{fullName}</strong><small>{user?.role || 'Usuario'}</small></div>
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
          <div className="topbar-club">{user?.club?.name || 'Mi club'}</div>
        </header>
        <main className="workspace-content"><Outlet /></main>
      </div>
      {mobileMenuOpen && <div className="mobile-nav-scrim" onMouseDown={(event) => { if (event.target === event.currentTarget) setMobileMenuOpen(false); }}>
        <nav className="mobile-nav-drawer" aria-label="Navegación móvil">
          <div className="mobile-nav-heading"><span>{user?.club?.name || 'Mi club'}</span><button className="icon-button mobile-nav-close" onClick={() => setMobileMenuOpen(false)} aria-label="Cerrar navegación"><X size={20} /></button></div>
          <div className="mobile-nav-links">{visibleNavigation(user?.role).map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setMobileMenuOpen(false)} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
              <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
            </NavLink>
          ))}</div>
          <div className="mobile-nav-account"><span className="user-avatar">{(fullName || 'B').slice(0, 1).toUpperCase()}</span><div className="user-meta"><strong>{fullName}</strong><small>{user?.role || 'Usuario'}</small></div><button className="icon-button" onClick={() => { setMobileMenuOpen(false); setPasswordDialogOpen(true); }} title="Cambiar contraseña" aria-label="Cambiar contraseña"><KeyRound size={18} /></button><button className="icon-button" onClick={signOut} title="Cerrar sesión" aria-label="Cerrar sesión"><LogOut size={18} /></button></div>
        </nav>
      </div>}
      {passwordDialogOpen && <PasswordDialog required={Boolean(user?.must_change_password)} onClose={() => setPasswordDialogOpen(false)} />}
    </div>
  );
}