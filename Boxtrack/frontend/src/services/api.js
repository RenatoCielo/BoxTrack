import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' }
});

export async function readCollection(path) {
  const rows = [];
  let next = path;
  while (next) {
    const { data } = await api.get(next);
    if (Array.isArray(data)) {
      rows.push(...data);
      break;
    }
    rows.push(...(data.results || []));
    next = data.next;
  }
  return rows;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('boxtrack.access');
  const isAuthenticationRequest = /\/auth\/(?:login|register|refresh)\/?$/i.test(config.url || '');
  if (token && !isAuthenticationRequest) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const refreshToken = localStorage.getItem('boxtrack.refresh');
    const isAuthenticationRequest = /\/auth\/(?:login|register|refresh)\/?$/i.test(originalRequest?.url || '');
    if (error.response?.status !== 401 || !refreshToken || originalRequest?._retried || isAuthenticationRequest) {
      return Promise.reject(error);
    }

    originalRequest._retried = true;
    try {
      const response = await axios.post(`${API_URL}/auth/refresh/`, { refresh: refreshToken });
      localStorage.setItem('boxtrack.access', response.data.access);
      originalRequest.headers.Authorization = `Bearer ${response.data.access}`;
      return api(originalRequest);
    } catch (refreshError) {
      localStorage.removeItem('boxtrack.access');
      localStorage.removeItem('boxtrack.refresh');
      localStorage.removeItem('boxtrack.user');
      window.dispatchEvent(new Event('boxtrack:session-expired'));
      return Promise.reject(refreshError);
    }
  }
);

export function getErrorMessage(error) {
  const data = error.response?.data;
  if (!data) return 'No se pudo conectar con el servidor. Comprueba que el backend esté iniciado.';
  const fallback = 'Revisa los datos e inténtalo nuevamente.';
  const isHtml = (value) => typeof value === 'string' && /^\s*</.test(value);
  if (typeof data === 'string') {
    return isHtml(data)
      ? 'El servidor devolvió una página de error. Reinicia el backend y comprueba que esté usando la base de datos actualizada.'
      : data;
  }
  if (typeof data.detail === 'string') {
    return isHtml(data.detail)
      ? 'El servidor devolvió una página de error. Reinicia el backend y comprueba que esté usando la base de datos actualizada.'
      : data.detail;
  }
  const messages = Object.values(data).flat(Infinity).filter((value) => typeof value === 'string');
  if (messages.some(isHtml)) {
    return 'El servidor devolvió una página de error. Reinicia el backend y comprueba que esté usando la base de datos actualizada.';
  }
  return messages[0] || fallback;
}