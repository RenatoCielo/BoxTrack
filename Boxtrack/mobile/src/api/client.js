export class ApiError extends Error {
  constructor(message, { status = 0, data = null, code = null, isNetwork = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
    this.code = code;
    this.isNetwork = isNetwork;
  }
}

const NETWORK_MESSAGE = 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo nuevamente.';
const SERVER_MESSAGE = 'El servidor no pudo procesar la solicitud. Inténtalo más tarde.';
const FALLBACK_MESSAGE = 'Revisa los datos e inténtalo nuevamente.';

export function extractMessage(data, status) {
  if (status >= 500) return SERVER_MESSAGE;
  if (!data) return FALLBACK_MESSAGE;
  if (typeof data === 'string') return /^\s*</.test(data) ? SERVER_MESSAGE : data;
  if (typeof data.detail === 'string') return data.detail;
  const first = Object.values(data).flat(Infinity).find((value) => typeof value === 'string');
  return first || FALLBACK_MESSAGE;
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function createClient({ baseUrl, storage, fetchImpl = (...args) => fetch(...args), timeoutMs = 15000 }) {
  let onSessionExpired = () => {};
  let refreshing = null;

  const rawFetch = async (path, { method = 'GET', body, headers = {}, token } = {}) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    const finalHeaders = { Accept: 'application/json', ...headers };
    if (body !== undefined && !isForm) finalHeaders['Content-Type'] = 'application/json';
    if (token) finalHeaders.Authorization = `Bearer ${token}`;
    try {
      const url = /^https?:/i.test(path) ? path : `${baseUrl}${path}`;
      return await fetchImpl(url, {
        method,
        headers: finalHeaders,
        body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
        signal: controller.signal
      });
    } catch {
      throw new ApiError(NETWORK_MESSAGE, { isNetwork: true });
    } finally {
      clearTimeout(timer);
    }
  };

  // Un único refresh simultáneo aunque varias peticiones reciban 401 a la vez.
  const refreshAccess = () => {
    if (!refreshing) {
      refreshing = (async () => {
        const refresh = await storage.getRefresh();
        if (!refresh) return null;
        const response = await rawFetch('/auth/refresh/', { method: 'POST', body: { refresh } });
        if (!response.ok) return null;
        const data = await parseBody(response);
        if (!data?.access) return null;
        await storage.save({ access: data.access, refresh: data.refresh });
        return data.access;
      })().finally(() => {
        refreshing = null;
      });
    }
    return refreshing;
  };

  const isAuthPath = (path) => /\/auth\/(login|register|refresh)\/?$/i.test(path);

  const request = async (path, options = {}) => {
    const authenticated = !isAuthPath(path);
    let token = authenticated ? await storage.getAccess() : null;
    let response = await rawFetch(path, { ...options, token });

    if (response.status === 401 && authenticated) {
      const fresh = await refreshAccess().catch(() => null);
      if (fresh) {
        response = await rawFetch(path, { ...options, token: fresh });
      } else {
        await storage.clear();
        onSessionExpired();
        throw new ApiError('Tu sesión expiró. Inicia sesión nuevamente.', { status: 401, code: 'SESSION_EXPIRED' });
      }
    }

    const data = await parseBody(response);
    if (!response.ok) {
      throw new ApiError(extractMessage(data, response.status), {
        status: response.status,
        data,
        code: data && typeof data === 'object' ? data.code || null : null
      });
    }
    return data;
  };

  const readCollection = async (path) => {
    const rows = [];
    let next = path;
    while (next) {
      const data = await request(next);
      if (Array.isArray(data)) {
        rows.push(...data);
        break;
      }
      rows.push(...(data?.results || []));
      next = data?.next || null;
    }
    return rows;
  };

  return {
    request,
    readCollection,
    get: (path) => request(path),
    post: (path, body = {}) => request(path, { method: 'POST', body }),
    patch: (path, body = {}) => request(path, { method: 'PATCH', body }),
    del: (path) => request(path, { method: 'DELETE' }),
    postForm: (path, form) => request(path, { method: 'POST', body: form }),
    setSessionExpiredHandler: (handler) => {
      onSessionExpired = handler || (() => {});
    }
  };
}
