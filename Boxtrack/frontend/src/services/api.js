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
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const refreshToken = localStorage.getItem('boxtrack.refresh');
    if (error.response?.status !== 401 || !refreshToken || originalRequest?._retried) {
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
  if (typeof data.detail === 'string') return data.detail;
  const firstError = Object.values(data).flat()[0];
  return typeof firstError === 'string' ? firstError : 'Revisa los datos e inténtalo nuevamente.';
}