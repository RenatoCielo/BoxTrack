import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CircleCheck, ShieldCheck, Swords } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { getErrorMessage } from '../services/api';

export function LoginPage() {
  const navigate = useNavigate();
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [values, setValues] = useState({
    username: '',
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    club_name: '',
    club_rut: '',
    legal_representative_name: '',
    legal_representative_rut: '',
    club_email: '',
    disciplines: ['Boxeo']
  });

  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const sessionUser = mode === 'login'
        ? await login(values.username, values.password)
        : await register(values);
      navigate(sessionUser.is_superuser ? '/global-admin' : sessionUser.role === 'ATHLETE' ? '/trainings' : '/dashboard', { replace: true });
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-intro">
        <div className="auth-brand"><span className="brand-mark">BX</span><span>BOXTRACK</span></div>
        <div className="auth-copy">
          <p className="eyebrow">Gestión de club, en tu esquina</p>
          <h1>El progreso se entrena.<br /><em>El orden también.</em></h1>
          <p>Organiza deportistas, clases, cupos y asistencia desde un solo lugar.</p>
        </div>
        <div className="auth-footnote"><ShieldCheck size={16} /> Datos separados y protegidos por club</div>
      </section>
      <section className="auth-panel">
        <div className="auth-panel-heading">
          <p className="eyebrow">Acceso seguro</p>
          <h2>{mode === 'login' ? 'Inicia sesión' : 'Registra tu club'}</h2>
          <p>{mode === 'login' ? 'Ingresa con tu nombre de usuario o correo.' : 'Crea la cuenta administradora de tu club.'}</p>
        </div>
        <div className="auth-tabs" role="tablist" aria-label="Tipo de acceso">
          <button type="button" className={mode === 'login' ? 'selected' : ''} onClick={() => { setMode('login'); setError(''); }}>Iniciar sesión</button>
          <button type="button" className={mode === 'register' ? 'selected' : ''} onClick={() => { setMode('register'); setError(''); }}>Crear club</button>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === 'register' && <>
            <label><span>Nombre del club</span><input required name="club_name" value={values.club_name} onChange={update} autoComplete="organization" /></label>
            <label><span>RUT de la organización</span><input required name="club_rut" value={values.club_rut} onChange={update} placeholder="12.345.678-5" autoComplete="off" /></label>
            <div className="form-row">
              <label><span>Representante legal</span><input required name="legal_representative_name" value={values.legal_representative_name} onChange={update} autoComplete="name" /></label>
              <label><span>RUT del representante</span><input required name="legal_representative_rut" value={values.legal_representative_rut} onChange={update} placeholder="12.345.678-5" autoComplete="off" /></label>
            </div>
            <label><span>Correo del club <small>Opcional</small></span><input type="email" name="club_email" value={values.club_email} onChange={update} /></label>
            <section className="club-discipline-card" aria-label="Disciplina del gimnasio">
              <span className="club-discipline-icon"><Swords size={21} aria-hidden="true" /></span>
              <div><span className="club-discipline-caption">DISCIPLINA DE TU GIMNASIO</span><strong>Boxeo</strong><small>Seleccionada automáticamente · Única disciplina disponible por ahora</small></div>
              <CircleCheck size={19} className="club-discipline-check" aria-label="Seleccionada" />
            </section>
            <div className="form-row">
              <label><span>Nombre</span><input name="first_name" value={values.first_name} onChange={update} autoComplete="given-name" /></label>
              <label><span>Apellido</span><input name="last_name" value={values.last_name} onChange={update} autoComplete="family-name" /></label>
            </div>
            <label><span>Correo personal</span><input required type="email" name="email" value={values.email} onChange={update} autoComplete="email" /></label>
          </>}
          <label><span>{mode === 'login' ? 'Usuario o correo electrónico' : 'Nombre de usuario'}</span><input required name="username" value={values.username} onChange={update} autoComplete="username" /></label>
          <label><span>Contraseña</span><input required type="password" name="password" value={values.password} onChange={update} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="primary-btn" disabled={busy}>
            {busy ? 'Conectando...' : mode === 'login' ? 'Entrar al club' : 'Crear cuenta'}
            {!busy && <ArrowRight size={17} />}
          </button>
        </form>
        <p className="auth-hint">La cuenta inicial del registro queda como administradora del club.</p>
      </section>
    </main>
  );
}
