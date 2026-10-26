import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import { api } from '../api';
import { Banner, Button, Card, EmptyState, ResourceView, Screen, SectionTitle, Segmented } from '../components/ui';
import { useCart } from '../cart/CartContext';
import { cartLines, cartTotal, toOrderItems } from '../cart/cartLogic';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { colors, font, radius, spacing } from '../theme';
import { formatMoney, label } from '../utils/format';
import OrdersPanel from './OrdersPanel';

function Stepper({ value, onChange, max }) {
  const btn = { width: 40, height: 40, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.paper };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <Pressable accessibilityRole="button" accessibilityLabel="Quitar una unidad" style={btn} onPress={() => onChange(value - 1)}><Text style={font.heading}>−</Text></Pressable>
      <Text style={[font.heading, { minWidth: 36, textAlign: 'center' }]}>{value}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Agregar una unidad" style={[btn, value >= max && { opacity: 0.4 }]} disabled={value >= max} onPress={() => onChange(value + 1)}><Text style={font.heading}>+</Text></Pressable>
    </View>
  );
}

function Catalog({ products, cart, add }) {
  if (!products.length) return <EmptyState icon="storefront-outline" title="Sin productos" message="Tu club aún no publicó productos en la tienda." />;
  return products.map((product) => {
    const inCart = cart[product.id] || 0;
    const soldOut = product.stock < 1;
    return (
      <Card key={product.id}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <View style={{ flex: 1, marginRight: spacing.sm }}>
            <Text style={font.heading}>{product.name}</Text>
            {product.category ? <Text style={font.small}>{label('category', product.category)}</Text> : null}
          </View>
          <Text style={font.heading}>{formatMoney(product.price)}</Text>
        </View>
        {product.description ? <Text style={[font.body, { marginTop: 4 }]}>{product.description}</Text> : null}
        <Text style={[font.small, { marginTop: 6 }]}>{soldOut ? 'Agotado' : `${product.stock} disponibles`}{inCart ? ` · ${inCart} en tu carrito` : ''}</Text>
        <Button title={soldOut ? 'Agotado' : 'Agregar al carrito'} disabled={soldOut || inCart >= Math.min(product.stock, 20)} onPress={() => add(product, 1)} style={{ marginTop: spacing.sm }} />
      </Card>
    );
  });
}

function CartPanel({ products, config, onOrdered }) {
  const { cart, setQty, clear } = useCart();
  const [method, setMethod] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lines = cartLines(cart, products);

  const methods = [
    { value: 'MERCADO_PAGO', label: 'Mercado Pago', enabled: config.mercado_pago_available },
    { value: 'BANK_TRANSFER', label: 'Transferencia', enabled: Boolean(config.bank_transfer_instructions) },
    { value: 'RESERVE', label: 'Reservar y pagar al retirar', enabled: true }
  ].filter((m) => m.enabled);
  const selected = method || methods[0]?.value;

  if (!lines.length) return <EmptyState icon="cart-outline" title="Tu carrito está vacío" message="Agrega productos desde el catálogo." />;

  const checkout = async () => {
    setBusy(true);
    setError('');
    try {
      const order = await api.post('/store/orders/', { payment_method: selected, items: toOrderItems(cart) });
      clear();
      if (order.checkout_url) await WebBrowser.openBrowserAsync(order.checkout_url);
      onOrdered(selected === 'MERCADO_PAGO'
        ? 'Pedido creado. El pago se confirma cuando Mercado Pago lo notifique al club.'
        : selected === 'BANK_TRANSFER' ? 'Pedido creado. Adjunta tu comprobante en "Pedidos".' : 'Pedido reservado. Págalo al retirarlo.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View>
      <Banner>{error}</Banner>
      {lines.map(({ product, quantity, subtotal }) => (
        <Card key={product.id}>
          <Text style={font.heading}>{product.name}</Text>
          <Text style={font.small}>{formatMoney(product.price)} c/u · {formatMoney(subtotal)}</Text>
          <View style={{ marginTop: spacing.sm, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Stepper value={quantity} max={Math.min(product.stock, 20)} onChange={(q) => setQty(product.id, q)} />
            <Button title="Quitar" variant="ghost" small onPress={() => setQty(product.id, 0)} />
          </View>
        </Card>
      ))}
      <SectionTitle>Método de pago</SectionTitle>
      <Segmented options={methods} value={selected} onChange={setMethod} />
      {selected === 'BANK_TRANSFER' ? <Card><Text style={font.body}>{config.bank_transfer_instructions}</Text></Card> : null}
      {!config.mercado_pago_available ? <Text style={[font.small, { marginBottom: spacing.sm }]}>El pago online no está habilitado en este club.</Text> : null}
      <Text style={[font.heading, { marginVertical: spacing.sm }]}>Total: {formatMoney(cartTotal(lines))}</Text>
      <Button title={`Confirmar pedido · ${label('payment', selected)}`} onPress={checkout} loading={busy} />
    </View>
  );
}

export default function StoreScreen() {
  const { count, sync } = useCart();
  const resource = useResource(async () => {
    const [products, config] = await Promise.all([
      api.readCollection('/store/products/'),
      api.get('/store/checkout-config/')
    ]);
    return { products, config };
  }, []);
  useRefreshOnFocus(resource);
  const [tab, setTab] = useState('catalog');
  const [notice, setNotice] = useState('');
  const { cart, add } = useCart();

  useEffect(() => {
    if (resource.data) sync(resource.data.products);
  }, [resource.data]);

  const tabs = [
    { value: 'catalog', label: 'Productos' },
    { value: 'cart', label: count ? `Carrito (${count})` : 'Carrito' },
    { value: 'orders', label: 'Pedidos' }
  ];

  return (
    <Screen eyebrow="TIENDA" title="Tienda del club" subtitle="Productos, carrito y pedidos" onRefresh={resource.refresh} refreshing={resource.refreshing}>
      <Banner type="success" onClose={() => setNotice('')}>{notice}</Banner>
      <Segmented options={tabs} value={tab} onChange={(next) => { setTab(next); if (next !== 'orders') resource.silent(); }} />
      {tab === 'orders' ? <OrdersPanel onNotice={setNotice} /> : (
        <ResourceView resource={resource} isEmpty={false}>
          {resource.data && tab === 'catalog' ? <Catalog products={resource.data.products} cart={cart} add={add} /> : null}
          {resource.data && tab === 'cart' ? (
            <CartPanel products={resource.data.products} config={resource.data.config} onOrdered={(message) => { setNotice(message); setTab('orders'); resource.silent(); }} />
          ) : null}
        </ResourceView>
      )}
    </Screen>
  );
}
