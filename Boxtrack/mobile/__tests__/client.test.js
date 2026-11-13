import { ApiError, createClient, extractMessage } from '../src/api/client';

function memoryStorage(initial = {}) {
  const data = { access: initial.access || null, refresh: initial.refresh || null };
  return {
    data,
    getAccess: async () => data.access,
    getRefresh: async () => data.refresh,
    save: async ({ access, refresh }) => {
      if (access) data.access = access;
      if (refresh) data.refresh = refresh;
    },
    clear: async () => {
      data.access = null;
      data.refresh = null;
    }
  };
}

const json = (status, body) => ({
  status,
  ok: status >= 200 && status < 300,
  text: async () => (body === undefined ? '' : JSON.stringify(body))
});

describe('api client', () => {
  test('envía el token Bearer y devuelve JSON', async () => {
    const storage = memoryStorage({ access: 'A1', refresh: 'R1' });
    const fetchImpl = jest.fn().mockResolvedValue(json(200, { ok: true }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await expect(client.get('/trainings/')).resolves.toEqual({ ok: true });
    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://x/api/trainings/');
    expect(options.headers.Authorization).toBe('Bearer A1');
  });

  test('no adjunta token en el login', async () => {
    const storage = memoryStorage({ access: 'A1' });
    const fetchImpl = jest.fn().mockResolvedValue(json(200, { tokens: {} }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await client.post('/auth/login/', { username: 'u', password: 'p' });
    expect(fetchImpl.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  test('renueva el token en 401 y reintenta una vez', async () => {
    const storage = memoryStorage({ access: 'old', refresh: 'R1' });
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(json(401, { detail: 'expired' }))
      .mockResolvedValueOnce(json(200, { access: 'new' }))
      .mockResolvedValueOnce(json(200, { value: 1 }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await expect(client.get('/memberships/')).resolves.toEqual({ value: 1 });
    expect(storage.data.access).toBe('new');
    expect(fetchImpl.mock.calls[2][1].headers.Authorization).toBe('Bearer new');
  });

  test('descarga un comprobante privado usando el token renovado y propaga errores', async () => {
    const storage = memoryStorage({ access: 'old', refresh: 'R1' });
    const blob = { type: 'application/pdf' };
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(json(401, {}))
      .mockResolvedValueOnce(json(200, { access: 'new' }))
      .mockResolvedValueOnce({ status: 200, ok: true, blob: async () => blob })
      .mockResolvedValueOnce(json(403, { detail: 'Sin permiso' }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await expect(client.getBlob('/memberships/1/proof/file/')).resolves.toBe(blob);
    expect(fetchImpl.mock.calls[2][1].headers.Authorization).toBe('Bearer new');
    await expect(client.getBlob('/memberships/1/proof/file/')).rejects.toMatchObject({ status: 403, message: 'Sin permiso' });
  });

  test('si el refresh falla limpia la sesión y avisa la expiración', async () => {
    const storage = memoryStorage({ access: 'old', refresh: 'R1' });
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(json(401, {}))
      .mockResolvedValueOnce(json(401, { detail: 'bad refresh' }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    const expired = jest.fn();
    client.setSessionExpiredHandler(expired);
    await expect(client.get('/memberships/')).rejects.toMatchObject({ code: 'SESSION_EXPIRED', status: 401 });
    expect(expired).toHaveBeenCalledTimes(1);
    expect(storage.data.access).toBeNull();
    expect(storage.data.refresh).toBeNull();
  });

  test('peticiones 401 simultáneas comparten un único refresh', async () => {
    const storage = memoryStorage({ access: 'old', refresh: 'R1' });
    const fetchImpl = jest.fn(async (url, options) => {
      if (url.endsWith('/auth/refresh/')) return json(200, { access: 'new' });
      return options.headers.Authorization === 'Bearer new' ? json(200, { ok: 1 }) : json(401, {});
    });
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await Promise.all([client.get('/a/'), client.get('/b/')]);
    const refreshCalls = fetchImpl.mock.calls.filter(([url]) => url.endsWith('/auth/refresh/'));
    expect(refreshCalls).toHaveLength(1);
  });

  test('errores de red se reportan como isNetwork', async () => {
    const storage = memoryStorage({ access: 'A' });
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl: jest.fn().mockRejectedValue(new Error('Network request failed')) });
    const error = await client.get('/x/').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.isNetwork).toBe(true);
    expect(error.message).toMatch(/No se pudo conectar/);
  });

  test('propaga detail y code del backend (membresía requerida)', async () => {
    const storage = memoryStorage({ access: 'A' });
    const fetchImpl = jest.fn().mockResolvedValue(json(409, { detail: 'Necesitas una membresía activa.', code: 'MEMBERSHIP_REQUIRED' }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    const error = await client.post('/trainings/1/reservations/').catch((e) => e);
    expect(error.status).toBe(409);
    expect(error.code).toBe('MEMBERSHIP_REQUIRED');
    expect(error.message).toBe('Necesitas una membresía activa.');
  });

  test('readCollection recorre las páginas y acepta arreglos simples', async () => {
    const storage = memoryStorage({ access: 'A' });
    const fetchImpl = jest.fn()
      .mockResolvedValueOnce(json(200, { results: [1, 2], next: 'http://x/api/items/?page=2' }))
      .mockResolvedValueOnce(json(200, { results: [3], next: null }));
    const client = createClient({ baseUrl: 'http://x/api', storage, fetchImpl });
    await expect(client.readCollection('/items/')).resolves.toEqual([1, 2, 3]);
    expect(fetchImpl.mock.calls[1][0]).toBe('http://x/api/items/?page=2');

    const plain = createClient({ baseUrl: 'http://x/api', storage, fetchImpl: jest.fn().mockResolvedValue(json(200, [9])) });
    await expect(plain.readCollection('/memberships/')).resolves.toEqual([9]);
  });

  test('extractMessage maneja errores de validación, HTML y 500', () => {
    expect(extractMessage({ athlete: ['Debes indicar el deportista.'] }, 400)).toBe('Debes indicar el deportista.');
    expect(extractMessage('<html>boom</html>', 400)).toMatch(/servidor/);
    expect(extractMessage({ detail: 'x' }, 500)).toMatch(/servidor/);
  });
});
