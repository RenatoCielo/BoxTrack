import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Check, Copy, Pencil, Plus, Search, Trash2, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { api, getErrorMessage, readCollection } from '../services/api';

const resourceConfig = {
  athletes: {
    title: 'Deportistas', eyebrow: 'PLANTEL', description: 'Deportistas de entrenamiento general del gimnasio.', endpoint: '/athletes/', listEndpoint: '/athletes/?is_competitor=false',
    fields: [
      { name: 'first_name', label: 'Nombre', required: true },
      { name: 'last_name', label: 'Apellido', required: true },
      { name: 'phone', label: 'Teléfono', type: 'tel', placeholder: '+56912345678' },
      { name: 'status', label: 'Estado', type: 'select', options: [['ACTIVE', 'Activo'], ['INACTIVE', 'Inactivo']] },
      { name: 'is_competitor', label: 'Integrar equipo competitivo', type: 'checkbox', defaultValue: false },
      { name: 'group', label: 'Grupo', type: 'relation', endpoint: '/groups/', optionLabel: 'name' },
      { name: 'category', label: 'Categoría' },
      { name: 'registered_weight', label: 'Peso registrado (kg)', type: 'number', step: '0.01' },
      { name: 'guard', label: 'Guardia', type: 'select', options: [['RIGHT', 'Diestra'], ['LEFT', 'Zurda']] },
      { name: 'birth_date', label: 'Fecha de nacimiento', type: 'date' },
      { name: 'experience', label: 'Experiencia', type: 'textarea' },
      { name: 'observations', label: 'Observaciones', type: 'textarea' }
    ],
    columns: [
      { label: 'Deportista', value: (row) => `${row.first_name} ${row.last_name}` },
      { label: 'Grupo', value: (row, context) => context.groups.find((item) => item.id === row.group)?.name || 'Sin grupo' },
      { label: 'Categoría', key: 'category' },
      { label: 'Peso', value: (row) => row.registered_weight ? `${row.registered_weight} kg` : '—' },
      { label: 'Estado', value: (row) => <span className={`status-pill ${row.status === 'ACTIVE' ? 'is-active' : ''}`}>{row.status === 'ACTIVE' ? 'Activo' : 'Inactivo'}</span> }
    ],
    search: (row) => `${row.first_name} ${row.last_name} ${row.category || ''}`
  },
  competitors: {
    title: 'Boxeadores competidores', eyebrow: 'EQUIPO COMPETITIVO', description: 'Atletas con preparación competitiva y récord de combates actualizado.', endpoint: '/athletes/', listEndpoint: '/athletes/?is_competitor=true',
    fields: [
      { name: 'first_name', label: 'Nombre', required: true },
      { name: 'last_name', label: 'Apellido', required: true },
      { name: 'category', label: 'Categoría de competencia' },
      { name: 'registered_weight', label: 'Peso actual (kg)', type: 'number', step: '0.01' },
      { name: 'group', label: 'Grupo de preparación', type: 'relation', endpoint: '/groups/', optionLabel: 'name' },
      { name: 'status', label: 'Estado', type: 'select', options: [['ACTIVE', 'Activo'], ['INACTIVE', 'Inactivo']] },
      { name: 'is_competitor', label: 'Equipo competitivo', type: 'checkbox', defaultValue: true }
    ],
    columns: [
      { label: 'Boxeador', value: (row) => `${row.first_name} ${row.last_name}` },
      { label: 'Categoría', key: 'category' },
      { label: 'Peso', value: (row) => row.registered_weight ? `${row.registered_weight} kg` : '—' },
      { label: 'Récord', value: (row) => <strong className="fight-record">{row.fight_record || '0-0-0'}</strong> },
      { label: 'Preparación', value: (row, context) => context.groups.find((group) => group.id === row.group)?.name || 'Sin grupo' },
      { label: 'Estado', value: (row) => <span className={`status-pill ${row.status === 'ACTIVE' ? 'is-active' : ''}`}>{row.status === 'ACTIVE' ? 'Activo' : 'Inactivo'}</span> }
    ],
    search: (row) => `${row.first_name} ${row.last_name} ${row.category || ''}`
  },
  groups: {
    title: 'Grupos', eyebrow: 'ORGANIZACIÓN', description: 'Organiza el plantel por nivel, horario o equipo.', endpoint: '/groups/',
    fields: [
      { name: 'name', label: 'Nombre del grupo', required: true },
      { name: 'schedule', label: 'Horario' },
      { name: 'description', label: 'Descripción', type: 'textarea' },
      { name: 'is_active', label: 'Estado', type: 'select', options: [['true', 'Activo'], ['false', 'Inactivo']] }
    ],
    columns: [
      { label: 'Grupo', key: 'name' },
      { label: 'Horario', key: 'schedule' },
      { label: 'Deportistas', value: (row, context) => context.athletes.filter((item) => item.group === row.id).length },
      { label: 'Estado', value: (row) => <span className={`status-pill ${row.is_active ? 'is-active' : ''}`}>{row.is_active ? 'Activo' : 'Inactivo'}</span> }
    ],
    search: (row) => `${row.name} ${row.schedule || ''}`
  },
  trainers: {
    title: 'Entrenadores', eyebrow: 'EQUIPO TÉCNICO', description: 'Perfiles técnicos asociados a cuentas del club.', endpoint: '/trainers/',
    fields: [
      { name: 'professional_title', label: 'Cargo o título' },
      { name: 'specialty', label: 'Especialidad' },
      { name: 'experience_years', label: 'Años de experiencia', type: 'number', min: '0' },
      { name: 'bio', label: 'Biografía', type: 'textarea' }
    ],
    columns: [
      { label: 'Entrenador', value: (row) => row.user_name || row.user_username || `Usuario #${row.user}` },
      { label: 'Cargo', key: 'professional_title' },
      { label: 'Especialidad', key: 'specialty' },
      { label: 'Experiencia', value: (row) => `${row.experience_years || 0} años` }
    ],
    search: (row) => `${row.user_name || ''} ${row.user_username || ''} ${row.professional_title || ''} ${row.specialty || ''}`
  },
  fights: {
    title: 'Historial de combates', eyebrow: 'TRAYECTORIA', description: 'Resultados competitivos vinculados a cada deportista.', endpoint: '/competitions/fights/',
    fields: [
      { name: 'athlete', label: 'Deportista', type: 'relation', endpoint: '/athletes/', optionLabel: (item) => `${item.first_name} ${item.last_name}`, required: true },
      { name: 'opponent_name', label: 'Rival', required: true },
      { name: 'fight_date', label: 'Fecha', type: 'date', required: true },
      { name: 'event', label: 'Evento' },
      { name: 'category', label: 'Categoría' },
      { name: 'result', label: 'Resultado', type: 'select', options: [['WIN', 'Victoria'], ['LOSS', 'Derrota'], ['DRAW', 'Empate']] },
      { name: 'fight_type', label: 'Tipo de combate', type: 'select', options: [['AMATEUR', 'Amateur'], ['PRO', 'Profesional'], ['SPARRING', 'Sparring']] },
      { name: 'notes', label: 'Notas', type: 'textarea' }
    ],
    columns: [
      { label: 'Fecha', key: 'fight_date' },
      { label: 'Deportista', value: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return athlete ? `${athlete.first_name} ${athlete.last_name}` : `#${row.athlete}`; } },
      { label: 'Rival', key: 'opponent_name' },
      { label: 'Evento', key: 'event' },
      { label: 'Resultado', value: (row) => <span className={`result-pill result-${(row.result || '').toLowerCase()}`}>{({ WIN: 'Victoria', LOSS: 'Derrota', DRAW: 'Empate' })[row.result] || '—'}</span> }
    ],
    search: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return `${row.opponent_name || ''} ${row.event || ''} ${athlete?.first_name || ''} ${athlete?.last_name || ''}`; }
  },
  attendance: {
    title: 'Asistencia', eyebrow: 'CONTROL DE CLASE', description: 'Marca y actualiza la asistencia efectiva de cada deportista.', endpoint: '/attendance/',
    fields: [
      { name: 'athlete', label: 'Deportista', type: 'relation', endpoint: '/athletes/', optionLabel: (item) => `${item.first_name} ${item.last_name}`, required: true },
      { name: 'training', label: 'Clase', type: 'relation', endpoint: '/trainings/', optionLabel: 'title', required: true },
      { name: 'status', label: 'Asistencia', type: 'select', options: [['PRESENT', 'Presente'], ['ABSENT', 'Ausente'], ['JUSTIFIED', 'Justificado'], ['LATE', 'Atrasado']] },
      { name: 'notes', label: 'Observación', type: 'textarea' }
    ],
    columns: [
      { label: 'Deportista', value: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return athlete ? `${athlete.first_name} ${athlete.last_name}` : `#${row.athlete}`; } },
      { label: 'Clase', value: (row, context) => context.trainings.find((item) => item.id === row.training)?.title || `#${row.training}` },
      { label: 'Estado', value: (row) => <span className="status-pill">{({ PRESENT: 'Presente', ABSENT: 'Ausente', JUSTIFIED: 'Justificado', LATE: 'Atrasado' })[row.status] || row.status}</span> },
      { label: 'Registrado', value: (row) => row.registered_at ? new Date(row.registered_at).toLocaleDateString('es-CL') : '—' }
    ],
    search: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); const training = context.trainings.find((item) => item.id === row.training); return `${athlete?.first_name || ''} ${athlete?.last_name || ''} ${training?.title || ''} ${row.status}`; }
  },
  evaluations: {
    title: 'Evaluaciones', eyebrow: 'SEGUIMIENTO TÉCNICO', description: 'Registra la evolución deportiva por deportista.', endpoint: '/evaluations/',
    fields: [
      { name: 'athlete', label: 'Deportista', type: 'relation', endpoint: '/athletes/', optionLabel: (item) => `${item.first_name} ${item.last_name}`, required: true },
      { name: 'evaluation_date', label: 'Fecha de evaluación', type: 'date', required: true },
      ...['technical', 'defense', 'speed', 'endurance', 'power', 'coordination', 'mobility', 'general_condition'].map((name) => ({ name, label: ({ technical: 'Técnica', defense: 'Defensa', speed: 'Velocidad', endurance: 'Resistencia', power: 'Potencia', coordination: 'Coordinación', mobility: 'Movilidad', general_condition: 'Condición general' })[name], type: 'number', min: 0, max: 10 })),
      { name: 'strengths', label: 'Fortalezas', type: 'textarea' },
      { name: 'improvement_areas', label: 'Áreas de mejora', type: 'textarea' },
      { name: 'next_goals', label: 'Próximos objetivos', type: 'textarea' },
      { name: 'observations', label: 'Observaciones', type: 'textarea' }
    ],
    columns: [
      { label: 'Fecha', key: 'evaluation_date' },
      { label: 'Deportista', value: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return athlete ? `${athlete.first_name} ${athlete.last_name}` : `#${row.athlete}`; } },
      { label: 'Técnica', key: 'technical' }, { label: 'Defensa', key: 'defense' },
      { label: 'Velocidad', key: 'speed' }, { label: 'Resistencia', key: 'endurance' },
      { label: 'Condición', key: 'general_condition' }
    ],
    search: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return `${athlete?.first_name || ''} ${athlete?.last_name || ''} ${row.evaluation_date}`; }
  },
  weight: {
    title: 'Control de peso', eyebrow: 'CATEGORÍA Y PREPARACIÓN', description: 'Mantén el historial de peso de cada deportista.', endpoint: '/weight/',
    fields: [
      { name: 'athlete', label: 'Deportista', type: 'relation', endpoint: '/athletes/', optionLabel: (item) => `${item.first_name} ${item.last_name}`, required: true },
      { name: 'weight', label: 'Peso (kg)', type: 'number', min: '0.01', step: '0.01', required: true },
      { name: 'recorded_date', label: 'Fecha de registro', type: 'date', required: true },
      { name: 'notes', label: 'Observaciones', type: 'textarea' }
    ],
    columns: [
      { label: 'Fecha', key: 'recorded_date' },
      { label: 'Deportista', value: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return athlete ? `${athlete.first_name} ${athlete.last_name}` : `#${row.athlete}`; } },
      { label: 'Peso', value: (row) => `${row.weight} kg` }, { label: 'Observaciones', key: 'notes' }
    ],
    search: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return `${athlete?.first_name || ''} ${athlete?.last_name || ''} ${row.recorded_date}`; }
  },
  alerts: {
    title: 'Alertas', eyebrow: 'SEGUIMIENTO DEL CLUB', description: 'Registra incidencias y marca las que ya fueron resueltas.', endpoint: '/alerts/',
    fields: [
      { name: 'title', label: 'Título', required: true },
      { name: 'level', label: 'Prioridad', type: 'select', options: [['INFO', 'Información'], ['WARNING', 'Advertencia'], ['CRITICAL', 'Crítica']] },
      { name: 'athlete', label: 'Deportista relacionado', type: 'relation', endpoint: '/athletes/', optionLabel: (item) => `${item.first_name} ${item.last_name}` },
      { name: 'source', label: 'Origen' },
      { name: 'message', label: 'Detalle', type: 'textarea', required: true },
      { name: 'is_resolved', label: 'Estado', type: 'select', options: [['false', 'Pendiente'], ['true', 'Resuelta']] }
    ],
    columns: [
      { label: 'Alerta', key: 'title' },
      { label: 'Deportista', value: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return athlete ? `${athlete.first_name} ${athlete.last_name}` : 'Club'; } },
      { label: 'Nivel', value: (row) => <span className={`result-pill result-${row.level === 'CRITICAL' ? 'loss' : row.level === 'WARNING' ? 'draw' : 'win'}`}>{({ INFO: 'Información', WARNING: 'Advertencia', CRITICAL: 'Crítica' })[row.level] || row.level}</span> },
      { label: 'Creada', value: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('es-CL') : '—' },
      { label: 'Estado', value: (row) => <span className={`status-pill ${row.is_resolved ? 'is-active' : ''}`}>{row.is_resolved ? 'Resuelta' : 'Pendiente'}</span> }
    ],
    search: (row, context) => { const athlete = context.athletes.find((item) => item.id === row.athlete); return `${row.title} ${row.message} ${athlete?.first_name || ''} ${athlete?.last_name || ''}`; }
  }
};

function emptyValues(fields) {
  return Object.fromEntries(fields.map(({ name, type, defaultValue }) => [name, type === 'checkbox' ? Boolean(defaultValue) : '']));
}

function formErrorMessage(error, fields) {
  const data = error.response?.data;
  if (!data || typeof data !== 'object') return getErrorMessage(error);
  const messages = [];
  for (const field of fields) {
    const value = data[field.name];
    if (value) messages.push(`${field.label}: ${Array.isArray(value) ? value.join(' ') : value}`);
  }
  const general = data.detail || data.non_field_errors;
  if (general) messages.push(Array.isArray(general) ? general.join(' ') : general);
  return messages.length ? messages.join(' ') : getErrorMessage(error);
}

function memberConfig(section) {
  const isAthlete = section !== 'trainers';
  return {
    title: isAthlete ? 'acceso de deportista' : 'acceso de entrenador',
    description: 'El nombre de usuario, correo institucional y contraseña temporal se generarán al guardar.',
    fields: [
      { name: 'first_name', label: 'Nombre', required: true },
      { name: 'last_name', label: 'Apellido', required: true },
      { name: 'phone', label: 'Teléfono', type: 'tel', placeholder: '+56912345678' },
      ...(isAthlete
        ? [
            { name: 'category', label: 'Categoría deportiva' },
            { name: 'is_competitor', label: 'Integrar equipo de competidores', type: 'checkbox', defaultValue: section === 'competitors' }
          ]
        : [
            { name: 'professional_title', label: 'Cargo o título' },
            { name: 'specialty', label: 'Especialidad' },
            { name: 'experience_years', label: 'Años de experiencia', type: 'number', min: '0' },
            { name: 'bio', label: 'Biografía', type: 'textarea' }
          ])
    ]
  };
}

function ResourceForm({ config, initial, relations, onClose, onSubmit, busy, error }) {
  const [values, setValues] = useState(() => ({ ...emptyValues(config.fields), ...initial }));
  const update = (event) => setValues({ ...values, [event.target.name]: event.target.value });

  return (
    <div className="modal-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="form-dialog" role="dialog" aria-modal="true" aria-labelledby="form-dialog-title">
        <header className="dialog-heading"><div><p className="eyebrow">{initial?.id ? 'ACTUALIZAR REGISTRO' : 'NUEVO REGISTRO'}</p><h2 id="form-dialog-title">{initial?.id ? 'Editar' : 'Agregar'} {config.title.toLowerCase()}</h2></div><button className="icon-button dialog-close" onClick={onClose} aria-label="Cerrar"><X size={19} /></button></header>
        {config.description && <p className="member-form-description">{config.description}</p>}
        <form className="resource-form" onSubmit={(event) => { event.preventDefault(); onSubmit(values); }}>
          <div className="field-grid">{config.fields.map((field) => <label className={`field-label ${field.type === 'textarea' ? 'field-wide' : ''}`} key={field.name}>
            <span>{field.label}{field.required && <i> *</i>}</span>
            {field.type === 'checkbox' ? <span className="checkbox-control"><input type="checkbox" name={field.name} checked={Boolean(values[field.name])} onChange={(event) => setValues({ ...values, [field.name]: event.target.checked })} /><span>{field.label}</span></span>
              : field.type === 'textarea' ? <textarea className="control" name={field.name} required={field.required} value={values[field.name] ?? ''} onChange={update} rows="3" />
              : field.type === 'select' || field.type === 'relation' ? <select className="control" name={field.name} required={field.required} value={values[field.name] ?? ''} onChange={update}>
                <option value="">Seleccionar</option>
                {(field.type === 'relation' ? (relations[field.name] || []).map((item) => [String(item.id), typeof field.optionLabel === 'function' ? field.optionLabel(item) : item[field.optionLabel]]) : field.options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
                : <input className="control" type={field.type || 'text'} name={field.name} required={field.required} min={field.min} step={field.step} maxLength={field.maxLength} pattern={field.pattern} placeholder={field.placeholder} value={values[field.name] ?? ''} onChange={update} />}
            {field.help && <small>{field.help}</small>}
          </label>)}</div>
          {error && <div className="notice notice-error">{error}</div>}
          <footer className="dialog-actions"><button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button><button className="button primary-btn" disabled={busy}>{busy ? 'Guardando...' : 'Guardar'}</button></footer>
        </form>
      </section>
    </div>
  );
}

function MemberCredentialsDialog({ credentials, onClose }) {
  const [copied, setCopied] = useState(false);
  const copyCredentials = async () => {
    const text = `BOXTRACK - acceso inicial\nNombre: ${credentials.user.first_name} ${credentials.user.last_name}\nUsuario: ${credentials.user.username}\nCorreo: ${credentials.user.email}\nContraseña temporal: ${credentials.temporary_password}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return <div className="modal-scrim"><section className="form-dialog credentials-dialog" role="dialog" aria-modal="true" aria-labelledby="credentials-title">
    <header className="dialog-heading"><div><p className="eyebrow">CUENTA CREADA</p><h2 id="credentials-title">Entrega estos datos</h2></div><span className="success-mark"><Check size={18} /></span></header>
    <div className="credentials-content"><p>La contraseña temporal solo se muestra ahora. La persona deberá cambiarla al iniciar sesión.</p>
      <dl className="credentials-list"><div><dt>Nombre de usuario</dt><dd>{credentials.user.username}</dd></div><div><dt>Correo institucional</dt><dd>{credentials.user.email}</dd></div><div className="credential-password"><dt>Contraseña temporal</dt><dd>{credentials.temporary_password}</dd></div></dl>
      <p className="credentials-warning">Entrega estos datos de forma privada. BOXTRACK no volverá a mostrar la contraseña.</p>
      <footer className="dialog-actions"><button className="button button-secondary" onClick={onClose}>Cerrar</button><button className="button primary-btn" onClick={copyCredentials}><Copy size={15} />{copied ? 'Copiado' : 'Copiar datos'}</button></footer>
    </div>
  </section></div>;
}

export function ResourcePage({ section: providedSection }) {
  const routeParams = useParams();
  const section = providedSection || routeParams.section;
  const config = resourceConfig[section];
  const [rows, setRows] = useState([]);
  const [relations, setRelations] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [accountDialog, setAccountDialog] = useState(false);
  const [createdCredentials, setCreatedCredentials] = useState(null);
    const [orphanAthleteAccounts, setOrphanAthleteAccounts] = useState([]); 
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const { user } = useAuth();
  const trainerWriteSections = ['attendance', 'fights', 'evaluations', 'weight', 'alerts'];
  const canManage = user?.role === 'ADMIN' || (user?.role === 'TRAINER' && trainerWriteSections.includes(section));
  const accountManagedSection = ['athletes', 'competitors', 'trainers'].includes(section);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [items, ...relationRows] = await Promise.all([
        readCollection(config.listEndpoint || config.endpoint),
        ...[...new Set(config.fields.filter((field) => field.type === 'relation').map((field) => field.endpoint))].map((endpoint) => readCollection(endpoint))
      ]);
      setRows(items);
      const relationFields = config.fields.filter((field) => field.type === 'relation');
      setRelations(Object.fromEntries(relationFields.map((field) => [field.name, relationRows[[...new Set(relationFields.map((item) => item.endpoint))].indexOf(field.endpoint)].filter((row) => !field.relationFilter || field.relationFilter(row))])));
      if (section === 'athletes' && user?.role === 'ADMIN') {
        const [accounts, allAthletes] = await Promise.all([
          readCollection('/auth/members/'),
          readCollection('/athletes/')
        ]);
        const linkedUserIds = new Set(allAthletes.map((athlete) => athlete.user).filter(Boolean));
        setOrphanAthleteAccounts(accounts.filter((account) => account.role === 'ATHLETE' && !linkedUserIds.has(account.id)));
      } else {
        setOrphanAthleteAccounts([]);
      }
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [config.listEndpoint || config.endpoint, section, user?.role]);

  const context = useMemo(() => ({ athletes: relations.athlete || [], groups: relations.group || [], trainings: relations.training || [] }), [relations]);
  const filtered = rows.filter((row) => config.search(row, context).toLowerCase().includes(query.toLowerCase()));

  const save = async (values) => {
    setSaving(true);
    setFormError('');
    const payload = Object.fromEntries(config.fields.map((field) => [field.name, values[field.name]]).filter(([, value]) => value !== '' && value !== undefined));
    for (const field of config.fields) {
      if (payload[field.name] === '' && !field.required) delete payload[field.name];
      else if ((field.type === 'number' || field.type === 'relation') && payload[field.name] !== '') payload[field.name] = Number(payload[field.name]);
      else if (field.name === 'is_active' && payload[field.name] !== '') payload[field.name] = payload[field.name] === 'true';
    }
    try {
      if (editing?.id) await api.patch(`${config.endpoint}${editing.id}/`, payload);
      else await api.post(config.endpoint, payload);
      setEditing(null);
      await load();
    } catch (requestError) {
      setFormError(formErrorMessage(requestError, config.fields));
    } finally {
      setSaving(false);
    }
  };

  const createMember = async (values) => {
    setSaving(true);
    setFormError('');
    const payload = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== ''));
    payload.role = section === 'trainers' ? 'TRAINER' : 'ATHLETE';
    if (payload.experience_years) payload.experience_years = Number(payload.experience_years);
    try {
      const { data } = await api.post('/auth/members/', payload);
      setAccountDialog(false);
      setCreatedCredentials(data);
      await load();
    } catch (requestError) {
      setFormError(formErrorMessage(requestError, memberConfig(section).fields));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row) => {
    const confirmation = section === 'athletes'
      ? `¿Dar de baja a ${row.first_name} ${row.last_name}? Se conservará su historial y se bloqueará su cuenta.`
      : '¿Eliminar este registro? Esta acción no se puede deshacer.';
    if (!window.confirm(confirmation)) return;
    try {
      await api.delete(`${config.endpoint}${row.id}/`);
      await load();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    }
  };

  const restoreOrphanAthlete = async (account) => {
    setError('');
    try {
      await api.post('/athletes/', {
        user: account.id,
        first_name: account.first_name,
        last_name: account.last_name,
        phone: account.phone || '',
        status: account.is_active ? 'ACTIVE' : 'INACTIVE'
      });
      await load();
    } catch (requestError) {
      setError(formErrorMessage(requestError, [
        { name: 'user', label: 'Cuenta' },
        { name: 'first_name', label: 'Nombre' },
        { name: 'last_name', label: 'Apellido' }
      ]));
    }
  };

  if (!config) return <div className="notice notice-error">Este módulo no está disponible.</div>;

  return (
    <section className="page-stack">
      <header className="page-heading"><div><p className="eyebrow">{config.eyebrow}</p><h1>{config.title}</h1><p className="page-description">{config.description}</p></div><div className="heading-actions">{user?.role === 'ADMIN' && accountManagedSection && <button className="button primary-btn" onClick={() => { setAccountDialog(true); setFormError(''); }}><Plus size={16} /> Crear cuenta</button>}{canManage && !accountManagedSection && <button className="button primary-btn" onClick={() => { setEditing(emptyValues(config.fields)); setFormError(''); }}><Plus size={16} /> Nuevo registro</button>}</div></header>
      <div className="table-toolbar"><label className="search-field"><Search size={16} /><input aria-label={`Buscar en ${config.title}`} placeholder="Buscar..." value={query} onChange={(event) => setQuery(event.target.value)} /></label><span className="table-count">{filtered.length} registros</span></div>
      {error && <div className="notice notice-error">{error}</div>}
      {section === 'athletes' && user?.role === 'ADMIN' && orphanAthleteAccounts.length > 0 && <section className="orphan-accounts-panel"><div><p className="eyebrow">CUENTAS SIN FICHA</p><h2>Deportistas que puedes recuperar</h2><p>Estas cuentas aún existen, pero no tienen una ficha en el plantel. Recupera su perfil para volver a administrarlas.</p></div><div className="orphan-account-list">{orphanAthleteAccounts.map((account) => <div key={account.id}><span><strong>{account.first_name} {account.last_name}</strong><small>{account.username} · {account.is_active ? 'Cuenta activa' : 'Cuenta bloqueada'}</small></span><button className="button button-secondary" onClick={() => restoreOrphanAthlete(account)}>Recuperar ficha</button></div>)}</div></section>}
      <div className="table-wrap"><table className="data-table"><thead><tr>{config.columns.map((column) => <th key={column.label}>{column.label}</th>)}{canManage && <th className="actions-heading">Acciones</th>}</tr></thead><tbody>
        {loading ? <tr><td colSpan={config.columns.length + Number(canManage)} className="table-empty">Cargando registros...</td></tr>
          : filtered.length ? filtered.map((row) => <tr key={row.id}>{config.columns.map((column) => <td data-label={column.label} key={column.label}>{column.value ? column.value(row, context) : row[column.key] || '—'}</td>)}{canManage && <td data-label="Acciones"><div className="row-actions"><button className="icon-button table-action" title="Editar" aria-label="Editar" onClick={() => { setEditing(row); setFormError(''); }}><Pencil size={15} /></button><button className="icon-button table-action delete-action" title={section === 'athletes' ? 'Dar de baja' : 'Eliminar'} aria-label={section === 'athletes' ? 'Dar de baja deportista' : 'Eliminar'} onClick={() => remove(row)}><Trash2 size={15} /></button></div></td>}</tr>)
            : <tr><td colSpan={config.columns.length + Number(canManage)} className="table-empty">{query ? 'No hay coincidencias.' : 'Aún no hay registros.'}</td></tr>}
      </tbody></table></div>
      {editing && <ResourceForm config={config} initial={editing} relations={relations} onClose={() => setEditing(null)} onSubmit={save} busy={saving} error={formError} />}
      {accountDialog && <ResourceForm config={memberConfig(section)} initial={emptyValues(memberConfig(section).fields)} relations={{}} onClose={() => setAccountDialog(false)} onSubmit={createMember} busy={saving} error={formError} />}
      {createdCredentials && <MemberCredentialsDialog credentials={createdCredentials} onClose={() => setCreatedCredentials(null)} />}
    </section>
  );
}