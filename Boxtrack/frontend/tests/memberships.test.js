import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { fetchMembershipSections } from '../src/services/membershipData.js';

let server;
let PaymentDialog;
let React;
let renderToStaticMarkup;

before(async () => {
  process.env.NODE_ENV = 'production';
  ({ default: React } = await import('react'));
  ({ renderToStaticMarkup } = await import('react-dom/server'));
  const { createServer } = await import('vite');
  server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, include: [] } });
  ({ PaymentDialog } = await server.ssrLoadModule('/src/pages/MembershipsPage.jsx'));
});

after(async () => { await server?.close(); });

test('un fallo del estado de renovación no oculta los planes disponibles', async () => {
  const plans = [{ id: 1, name: 'Mensual' }];
  const renewalError = new Error('No se pudo consultar la renovación');
  const [catalog, details] = await fetchMembershipSections({
    role: 'ATHLETE',
    readCollection: async () => plans,
    get: async (path) => {
      if (path === '/memberships/renewal/') throw renewalError;
      return [];
    },
  });
  assert.equal(catalog.status, 'fulfilled');
  assert.deepEqual(catalog.value, plans);
  assert.equal(details.status, 'rejected');
  assert.equal(details.reason, renewalError);
});

test('un fallo del catálogo no se confunde con una lista vacía', async () => {
  const catalogError = new Error('No se pudo consultar el catálogo');
  const [catalog, details] = await fetchMembershipSections({
    role: 'TRAINER',
    readCollection: async () => { throw catalogError; },
    get: async () => [],
  });
  assert.equal(catalog.status, 'rejected');
  assert.equal(catalog.reason, catalogError);
  assert.equal(details.status, 'fulfilled');
});

test('el selector informa falta de configuración y conserva el pago manual', () => {
  const html = renderToStaticMarkup(React.createElement(PaymentDialog, {
    plan: { name: 'Mensual', price: 30000, currency: 'CLP', duration_days: 30 },
    onlineAvailable: false, transbankAvailable: false,
  }));
  assert.match(html, /pago online no está configurado/);
  assert.match(html, /Pagar directamente al club/);
  assert.match(html, /disabled="" value="BANK_TRANSFER"/);
  assert.match(html, /disabled="" value="MERCADO_PAGO"/);
});

test('el selector muestra los proveedores configurados y los datos de renovación', () => {
  const html = renderToStaticMarkup(React.createElement(PaymentDialog, {
    plan: { name: 'Mensual', price: 30000, currency: 'CLP', duration_days: 30 },
    renewal: true, onlineAvailable: true, transbankAvailable: true, bankInstructions: 'Banco de prueba',
  }));
  assert.match(html, /Renovación.*Mensual/);
  assert.match(html, /Banco de prueba/);
  assert.match(html, /checked="" value="BANK_TRANSFER"/);
  assert.match(html, /value="MERCADO_PAGO"/);
  assert.match(html, /value="TRANSBANK"/);
  assert.match(html, /Pagar directamente al club/);
  assert.doesNotMatch(html, /pago online no está configurado/);
});
