import { useEffect, useState } from 'react';
import { Bell, Check, CheckCheck } from 'lucide-react';
import { api, getErrorMessage, readCollection } from '../services/api';

const typeNames = { INFO: 'General', TRAINING: 'Clases', EVALUATION: 'Evaluaciones', COMPETITION: 'Competencias', ALERT: 'Alertas' };

export function NotificationsPage() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try { setItems(await readCollection('/notifications/')); }
    catch (requestError) { setError(getErrorMessage(requestError)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const markRead = async (item) => {
    try {
      await api.patch(`/notifications/${item.id}/`, { is_read: true });
      setItems((current) => current.map((notification) => notification.id === item.id ? { ...notification, is_read: true } : notification));
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const markAllRead = async () => {
    try {
      await Promise.all(items.filter((item) => !item.is_read).map((item) => api.patch(`/notifications/${item.id}/`, { is_read: true })));
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    } catch (requestError) { setError(getErrorMessage(requestError)); }
  };

  const unreadCount = items.filter((item) => !item.is_read).length;
  return <section className="page-stack">
    <header className="page-heading"><div><p className="eyebrow">CENTRO DE ACTIVIDAD</p><h1>Notificaciones</h1><p className="page-description">Avisos de tus reservas y novedades del club.</p></div>{unreadCount > 0 && <button className="button button-secondary" onClick={markAllRead}><CheckCheck size={15} /> Marcar todas leídas</button>}</header>
    {error && <div className="notice notice-error">{error}</div>}
    <div className="notification-list">{loading ? <div className="empty-state">Cargando notificaciones...</div> : items.length ? items.map((item) => <article className={`notification-row ${item.is_read ? '' : 'unread'}`} key={item.id}>
      <div className="notification-symbol"><Bell size={17} /></div>
      <div className="notification-copy"><div className="notification-meta"><span>{typeNames[item.notification_type] || item.notification_type}</span><time>{new Date(item.created_at).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' })}</time></div><h2>{item.title}</h2><p>{item.message}</p></div>
      {!item.is_read && <button className="icon-button table-action" title="Marcar como leída" aria-label="Marcar como leída" onClick={() => markRead(item)}><Check size={16} /></button>}
    </article>) : <div className="surface-panel empty-state">No tienes notificaciones por ahora.</div>}</div>
  </section>;
}