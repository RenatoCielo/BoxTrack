import { useState } from 'react';
import { Platform, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as WebBrowser from 'expo-web-browser';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, EmptyState, Field, KeyValue, ResourceView } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { font, spacing } from '../theme';
import { formatDateTime, formatMoney, label, tone } from '../utils/format';
import { buildProofForm } from '../utils/proof';

function OrderCard({ order, isAdmin, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState('');

  const run = async (fn, message) => {
    setBusy(true);
    setError('');
    try {
      await fn();
      await onChanged(message);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const pickProof = () => run(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted && Platform.OS !== 'web') throw new Error('Necesitamos acceso a tus fotos para adjuntar el comprobante.');
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.7 });
    if (result.canceled) return;
    await api.post(`/store/orders/${order.id}/proof/`, await buildProofForm(result.assets[0]));
  }, 'Comprobante enviado. El gimnasio lo revisará.');

  const pending = order.status === 'PENDING';
  const canSendProof = pending && order.payment_method === 'BANK_TRANSFER' && order.proof_status !== 'SUBMITTED' && !isAdmin;
  const awaitingReview = isAdmin && pending && order.proof_status === 'SUBMITTED';

  return (
    <Card tone={awaitingReview ? 'warn' : undefined}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <View style={{ flex: 1, marginRight: spacing.sm }}>
          <Text style={font.heading}>Pedido #{order.id}</Text>
          {isAdmin && order.buyer_name ? <Text style={font.small}>{order.buyer_name}</Text> : null}
        </View>
        <Badge text={label('order', order.status)} tone={tone(order.status)} />
      </View>
      <View style={{ marginTop: spacing.sm }}>
        {(order.items || []).map((item) => (
          <KeyValue key={item.id} label={`${item.quantity} × ${item.product_name}`} value={formatMoney(item.subtotal)} />
        ))}
        <KeyValue label="Total" value={formatMoney(order.total)} />
        <KeyValue label="Pago" value={label('payment', order.payment_method)} />
        {order.payment_method === 'BANK_TRANSFER' ? <KeyValue label="Comprobante" value={label('proof', order.proof_status)} /> : null}
        {order.proof_review_note ? <KeyValue label="Nota del club" value={order.proof_review_note} /> : null}
        <KeyValue label="Creado" value={formatDateTime(order.created_at)} />
      </View>
      {pending && ['MERCADO_PAGO', 'TRANSBANK'].includes(order.payment_method) ? (
        <Text style={[font.small, { marginTop: spacing.sm }]}>{order.payment_method === 'TRANSBANK' ? 'Transbank confirma la transacción al regresar desde Webpay. Actualiza esta lista para ver el estado real.' : 'Mercado Pago confirma el pago al club. Actualiza esta lista para ver el estado real.'}</Text>
      ) : null}
      <Banner>{error}</Banner>
      <View style={{ marginTop: spacing.md, gap: 8 }}>
        {pending && order.checkout_url && !isAdmin ? <Button title={`Ir a pagar con ${label('payment', order.payment_method)}`} onPress={() => WebBrowser.openBrowserAsync(order.checkout_url)} /> : null}
        {canSendProof ? <Button title={order.proof_status === 'REJECTED' ? 'Enviar nuevo comprobante' : 'Adjuntar comprobante'} onPress={pickProof} loading={busy} /> : null}
        {awaitingReview && !rejecting ? <Button title="Aprobar comprobante" loading={busy} onPress={() => run(() => api.post(`/store/orders/${order.id}/proof/review/`, { decision: 'APPROVE' }), 'Comprobante aprobado.')} /> : null}
        {awaitingReview && !rejecting ? <Button title="Rechazar comprobante" variant="secondary" onPress={() => setRejecting(true)} disabled={busy} /> : null}
        {rejecting ? (
          <View>
            <Field label="Motivo del rechazo" value={note} onChangeText={setNote} multiline />
            <Button title="Confirmar rechazo" variant="danger" loading={busy} onPress={() => run(() => api.post(`/store/orders/${order.id}/proof/review/`, { decision: 'REJECT', note }), 'Comprobante rechazado.')} />
            <Button title="Volver" variant="ghost" small onPress={() => setRejecting(false)} />
          </View>
        ) : null}
        {isAdmin && order.status === 'PAID' ? <Button title="Marcar lista para retirar" loading={busy} onPress={() => run(() => api.patch(`/store/orders/${order.id}/`, { status: 'READY' }), 'Pedido listo para retirar.')} /> : null}
        {isAdmin && order.status === 'READY' ? <Button title="Marcar como retirada" loading={busy} onPress={() => run(() => api.patch(`/store/orders/${order.id}/`, { status: 'COMPLETED' }), 'Pedido entregado.')} /> : null}
        {pending && !rejecting ? <Button title="Cancelar pedido" variant="secondary" disabled={busy} onPress={() => run(() => api.patch(`/store/orders/${order.id}/`, { status: 'CANCELLED' }), 'Pedido cancelado.')} /> : null}
      </View>
    </Card>
  );
}

export default function OrdersPanel({ onNotice }) {
  const { user } = useAuth();
  const isAdmin = user.role === 'ADMIN';
  const resource = useResource(async () => {
    const rows = await api.get('/store/orders/');
    return Array.isArray(rows) ? rows : [];
  }, [user.id]);
  useRefreshOnFocus(resource);
  const orders = resource.data || [];

  return (
    <View>
      <Button title="Actualizar pedidos" variant="secondary" small onPress={resource.refresh} loading={resource.refreshing} />
      <View style={{ height: spacing.md }} />
      <ResourceView
        resource={resource}
        isEmpty={orders.length === 0}
        empty={<EmptyState icon="receipt-outline" title="Sin pedidos" message={isAdmin ? 'Aún no hay pedidos en tu club.' : 'Cuando compres productos verás aquí el estado de tus pedidos.'} />}
      >
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} isAdmin={isAdmin} onChanged={async (message) => { onNotice?.(message); await resource.silent(); }} />
        ))}
      </ResourceView>
    </View>
  );
}
