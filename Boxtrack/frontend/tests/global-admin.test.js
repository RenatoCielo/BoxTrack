import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

process.env.NODE_ENV = 'production';
const { default: React } = await import('react');
const { renderToStaticMarkup } = await import('react-dom/server');
const { MemoryRouter } = await import('react-router-dom');
const { createServer } = await import('vite');

let server;
let App;

before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } });
  ({ default: App } = await server.ssrLoadModule('/src/App.jsx'));
});

after(async () => {
  await server?.close();
});

function render(user, path) {
  const savedStorage = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (key) => key === 'boxtrack.user' ? JSON.stringify(user) : null,
  };
  try {
    return renderToStaticMarkup(
      React.createElement(MemoryRouter, { initialEntries: [path] }, React.createElement(App)),
    );
  } finally {
    globalThis.localStorage = savedStorage;
  }
}

test('superuser sees only global administration and personal settings', () => {
  const user = { username: 'global', role: 'ADMIN', is_superuser: true, club: null };
  const page = render(user, '/global-admin');
  assert.match(page, /Panel global/);
  assert.match(page, /Clubes pendientes/);
  assert.match(page, /Gimnasios inscritos/);
  assert.match(page, /Usuarios registrados/);
  assert.match(page, /Administración global/);
  assert.match(page, /Configuración/);
  assert.doesNotMatch(page, /Deportistas|Entrenadores|Combates entre clubes/);

  const settings = render(user, '/settings');
  assert.match(settings, /Perfil personal/);
  assert.match(settings, /Seguridad/);
  assert.doesNotMatch(settings, /Imagen del club|Mostrar mi apodo en el club/);
});

test('club administrator retains club navigation and branding settings', () => {
  const user = { username: 'admin', role: 'ADMIN', is_superuser: false, club: { id: 1, name: 'Club' } };
  const page = render(user, '/dashboard');
  assert.match(page, /Deportistas/);
  assert.match(page, /Combates entre clubes/);
  assert.doesNotMatch(page, /Panel global/);
  assert.match(render(user, '/settings'), /Imagen del club/);
});
