import { useEffect, useState } from 'react';
import { Pencil, Plus, Save, Tags, X } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

const blankPlan = {
  name: '',
  description: '',
  price: '',
  duration: 'Mensual',
  classes_per_week: 4,
  is_premium: false,
  is_active: true,
  sort_order: 0
};

const formatCLP = (amount) => new Intl.NumberFormat('es-CL', {
  style: 'currency',
  currency: 'CLP',
  maximumFractionDigits: 0
}).format(Number(amount));

export function PlansPage() {
  const [plans, setPlans] = useState([]);
  const [values, setValues] = useState(blankPlan);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const loadPlans = async () => {
    setPlans(await readCollection('/clubs/plans/'));
  };

  useEffect(() => {
    let active = true;
    readCollection('/clubs/plans/')
      .then((data) => {
        if (active) setPlans(data);
      })
      .catch((requestError) => {
        if (active) setError(getErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const resetForm = () => {
    setValues(blankPlan);
    setEditingId(null);
  };

  const editPlan = (plan) => {
    setValues({
      name: plan.name,
      description: plan.description || '',
      price: plan.price,
      duration: plan.duration,
      classes_per_week: plan.classes_per_week ?? '',
      is_premium: Boolean(plan.is_premium),
      is_active: plan.is_active,
      sort_order: plan.sort_order
    });
    setEditingId(plan.id);
    setNotice('');
    setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setNotice('');
    try {
      if (editingId) {
        await api.patch(`/clubs/plans/${editingId}/`, values);
        setNotice('El plan se actualizó.');
      } else {
        await api.post('/clubs/plans/', values);
        setNotice('El plan se creó.');
      }
      await loadPlans();
      resetForm();
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (plan) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api.patch(`/clubs/plans/${plan.id}/`, { is_active: !plan.is_active });
      await loadPlans();
      setNotice(plan.is_active ? 'El plan se desactivó.' : 'El plan se activó.');
    } catch (requestError) {
      setError(getErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">ADMINISTRACIÓN DEL CLUB</p>
          <h1>Planes del gimnasio</h1>
          <p className="page-description">Crea y actualiza los planes que los visitantes podrán consultar.</p>
        </div>
      </header>

      {notice && <div className="notice notice-success" role="status">{notice}</div>}
      {error && <div className="notice notice-error" role="alert">{error}</div>}

      <div className="surface-panel plan-admin-layout">
        <div className="plan-admin-list">
          <div className="section-heading"><h2>Planes creados</h2><span>{plans.length}</span></div>
          {loading && <div className="empty-state">Cargando planes...</div>}
          {!loading && !plans.length && <div className="empty-state">Aún no hay planes. Crea el primero.</div>}
          {plans.map((plan) => (
            <article className="plan-admin-row" key={plan.id}>
              <div>
                <span className={`status-tag${plan.is_active ? '' : ' plan-inactive'}`}>{plan.is_active ? 'Activo' : 'Inactivo'}</span>
                <h3>{plan.name}</h3>
                <p>{plan.duration} · {formatCLP(plan.price)}</p>
                <small>{plan.classes_per_week == null ? 'Reservas ilimitadas · Premium' : `${plan.classes_per_week} clases por semana`}</small>
                {plan.description && <small>{plan.description}</small>}
              </div>
              <div className="plan-admin-actions">
                <button type="button" className="button button-secondary" onClick={() => editPlan(plan)} disabled={busy} aria-label={`Editar ${plan.name}`}><Pencil size={15} />Editar</button>
                <button type="button" className="button button-secondary" onClick={() => toggleActive(plan)} disabled={busy}>{plan.is_active ? 'Desactivar' : 'Activar'}</button>
              </div>
            </article>
          ))}
        </div>

        <form className="resource-form plan-admin-form" onSubmit={submit}>
          <div className="section-heading">
            <h2>{editingId ? 'Editar plan' : 'Nuevo plan'}</h2>
            {editingId
              ? <button type="button" className="icon-button" onClick={resetForm} aria-label="Cancelar edición"><X size={18} /></button>
              : <Tags size={18} />}
          </div>
          <label className="field-label"><span>Nombre</span><input className="control" required maxLength="120" value={values.name} onChange={(event) => setValues({ ...values, name: event.target.value })} placeholder="Plan mensual" /></label>
          <label className="field-label"><span>Duración del plan</span><select className="control" required value={values.duration} onChange={(event) => setValues({ ...values, duration: event.target.value })}>{['Por clase', 'Diario', 'Semanal', 'Mensual', 'Anual'].map((duration) => <option key={duration} value={duration}>{duration}</option>)}</select></label>
          <label className="field-label"><span>Clases por semana</span><input className="control" type="number" min="1" step="1" required={!values.is_premium} value={values.classes_per_week ?? ''} onChange={(event) => setValues({ ...values, classes_per_week: event.target.value === '' ? null : Number(event.target.value) })} placeholder={values.is_premium ? 'Ilimitadas' : 'Ej. 4'} /><small>{values.is_premium ? 'Un plan premium puede dejar este límite vacío.' : 'Todos los planes estándar deben tener un límite.'}</small></label>
          <label className="checkbox-control"><input type="checkbox" checked={values.is_premium} onChange={(event) => setValues({ ...values, is_premium: event.target.checked, classes_per_week: !event.target.checked && values.classes_per_week == null ? 4 : values.classes_per_week })} /> Plan premium (puede permitir clases ilimitadas)</label>
          <label className="field-label"><span>Precio en CLP</span><input className="control" type="number" min="0" step="1" required value={values.price} onChange={(event) => setValues({ ...values, price: event.target.value })} /></label>
          <label className="field-label"><span>Qué incluye</span><textarea className="control" rows="4" value={values.description} onChange={(event) => setValues({ ...values, description: event.target.value })} /></label>
          <label className="field-label"><span>Orden de publicación</span><input className="control" type="number" min="0" step="1" value={values.sort_order} onChange={(event) => setValues({ ...values, sort_order: Number(event.target.value) })} /></label>
          <label className="checkbox-control"><input type="checkbox" checked={values.is_active} onChange={(event) => setValues({ ...values, is_active: event.target.checked })} /> Mostrar este plan públicamente</label>
          <div className="settings-save-row">
            <button className="button primary-btn" disabled={busy}><Save size={16} />{busy ? 'Guardando...' : editingId ? 'Guardar cambios' : <><Plus size={16} />Crear plan</>}</button>
          </div>
        </form>
      </div>
    </section>
  );
}
