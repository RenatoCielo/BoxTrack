import { useEffect, useState } from 'react';
import { AppState, Modal, Platform, Pressable, ScrollView, Switch, Text, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as WebBrowser from 'expo-web-browser';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, EmptyState, Field, KeyValue, ResourceView, Screen, SectionTitle, Segmented } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { colors, font, spacing } from '../theme';
import { formatDate, formatMoney, isMembershipValidFor, label, todayISO, tone } from '../utils/format';
import { openPaymentFor, paymentOutcomeMessage } from '../utils/payment';
import { buildProofForm, openPrivateProof } from '../utils/proof';

async function loadMemberships(user) {
  const [plans, memberships, settings, payments, renewal] = await Promise.all([
    api.readCollection('/memberships/plans/'),
    api.get('/memberships/'),
    api.get('/memberships/settings/'),
    user.role === 'TRAINER' ? Promise.resolve([]) : api.get('/memberships/payments/'),
    user.role === 'ATHLETE' ? api.get('/memberships/renewal/') : Promise.resolve(null)
  ]);
  return { plans, memberships: Array.isArray(memberships) ? memberships : [], settings, payments: Array.isArray(payments) ? payments : [], renewal };
}

function MembershipRow({ membership, showAthlete, children }) {
  return (
    <Card tone={membership.status === 'PENDING' ? 'warn' : undefined}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, marginRight: spacing.sm }}>
          <Text style={font.heading}>{membership.plan_name}</Text>
          {membership.club_name ? <Text style={font.small}>{membership.club_name}</Text> : null}
          {showAthlete ? <Text style={font.small}>{membership.athlete_name}</Text> : null}
          {membership.is_renewal ? <Text style={font.small}>Renovación</Text> : null}
        </View>
        <Badge text={label('membership', membership.status)} tone={tone(membership.status)} />
      </View>
      <View style={{ marginTop: spacing.sm }}>
        <KeyValue label="Monto" value={formatMoney(membership.price_paid, membership.currency)} />
        <KeyValue label="Vigencia" value={membership.start_date ? `${formatDate(membership.start_date)} al ${formatDate(membership.end_date)}` : 'Se define al confirmar el pago'} />
        <KeyValue label="Clases por semana" value={membership.weekly_class_limit ? String(membership.weekly_class_limit) : 'Sin límite'} />
        {membership.review_note ? <KeyValue label="Nota del club" value={membership.review_note} /> : null}
        {membership.days_remaining !== null && membership.days_remaining !== undefined ? <KeyValue label="Días restantes" value={String(membership.days_remaining)} /> : null}
        {membership.payment_status ? <KeyValue label="Último pago" value={`${label('paymentStatus', membership.payment_status)} · ${label('payment', membership.payment_provider)}`} /> : null}
        <KeyValue label="Solicitada" value={formatDate(membership.created_at)} />
      </View>
      {children}
    </Card>
  );
}

function AdminReview({ membership, onDone }) {
  const [note, setNote] = useState('');
  const [mode, setMode] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const send = async (decision) => {
    setBusy(true);
    setError('');
    try {
      await api.post(`/memberships/${membership.id}/review/`, { decision, note });
      await onDone(decision === 'CONFIRM' ? 'Pago confirmado y membresía activada.' : 'Solicitud rechazada.');
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  if (mode === 'REJECT') {
    return (
      <View style={{ marginTop: spacing.md }}>
        <Banner>{error}</Banner>
        <Field label="Motivo del rechazo" value={note} onChangeText={setNote} multiline />
        <Button title="Confirmar rechazo" variant="danger" onPress={() => send('REJECT')} loading={busy} />
        <Button title="Volver" variant="ghost" small onPress={() => setMode(null)} />
      </View>
    );
  }
  return (
    <View style={{ marginTop: spacing.md, gap: 8 }}>
      <Banner>{error}</Banner>
      <Button title="Confirmar pago" onPress={() => send('CONFIRM')} loading={busy} testID={`confirm-${membership.id}`} />
      <Button title="Rechazar" variant="secondary" onPress={() => setMode('REJECT')} disabled={busy} />
    </View>
  );
}

function TransferSettings({ instructions, onSaved }) {
  const [value, setValue] = useState(instructions);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const save = async () => {
    setBusy(true); setError('');
    try {
      const result = await api.patch('/store/checkout-config/', { bank_transfer_instructions: value });
      setValue(result.bank_transfer_instructions);
      onSaved(result.bank_transfer_instructions);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  return <Card>
    <Text style={font.heading}>Datos de transferencia del club</Text>
    <Text style={[font.small, { marginVertical: spacing.sm }]}>Estos datos también se usan en la tienda. Deja el campo vacío para deshabilitar la transferencia.</Text>
    <Field label="Instrucciones para transferir" value={value} onChangeText={setValue} multiline maxLength={2000} placeholder="Banco, cuenta, titular y contacto" />
    <Banner>{error}</Banner>
    <Button title="Guardar datos de transferencia" onPress={save} loading={busy} />
  </Card>;
}

function TransferProof({ membership, isAdmin, onDone }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState('');
  const proof = membership.transfer_proof;
  const run = async (action, message) => {
    setBusy(true); setError('');
    try { if (await action() !== false) await onDone(message); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const upload = () => run(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted && Platform.OS !== 'web') throw new Error('Necesitamos acceso a tus fotos para adjuntar el comprobante.');
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.7 });
    if (result.canceled) return false;
    await api.post(`/memberships/${membership.id}/proof/`, await buildProofForm(result.assets[0]));
    return true;
  }, 'Comprobante enviado. El club lo revisará.');
  const review = (decision) => run(
    () => api.post(`/memberships/${membership.id}/proof/review/`, { decision, note }),
    decision === 'APPROVE' ? 'Comprobante aprobado y membresía confirmada.' : 'Comprobante rechazado.'
  );
  return <View style={{ marginTop: spacing.sm, gap: 8 }}>
    <Text style={font.small}>Transferencia · {proof ? label('proof', proof.status) : 'Sin comprobante'}</Text>
    {proof?.status === 'REJECTED' ? <Text style={font.small}>Motivo: {proof.review_note}</Text> : null}
    <Banner>{error}</Banner>
    {membership.status === 'PENDING' && !isAdmin && proof?.status !== 'SUBMITTED' ? <Button title={proof?.status === 'REJECTED' ? 'Enviar nuevo comprobante' : 'Adjuntar comprobante'} onPress={upload} loading={busy} /> : null}
    {membership.status === 'PENDING' && isAdmin && proof?.status === 'SUBMITTED' ? <>
      <Button title="Ver comprobante" variant="secondary" loading={busy} onPress={() => run(async () => { await openPrivateProof(await api.getBlob(`/memberships/${membership.id}/proof/file/`)); return false; })} />
      {!rejecting ? <><Button title="Aprobar comprobante" loading={busy} onPress={() => review('APPROVE')} /><Button title="Rechazar comprobante" variant="secondary" disabled={busy} onPress={() => setRejecting(true)} /></> : <>
        <Field label="Motivo del rechazo" value={note} onChangeText={setNote} multiline />
        <Button title="Confirmar rechazo" variant="danger" loading={busy} onPress={() => review('REJECT')} />
        <Button title="Volver" variant="ghost" onPress={() => setRejecting(false)} />
      </>}
    </> : null}
  </View>;
}

function PaymentDialog({ choice, onlineAvailable, transbankAvailable, bankInstructions = '', onClose, onChoose }) {
  const [method, setMethod] = useState(bankInstructions.trim() ? 'BANK_TRANSFER' : 'MANUAL');
  if (!choice) return null;
  const { plan, renewal } = choice;
  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: spacing.lg }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center' }}>
          <Card>
            <Text style={font.heading} accessibilityRole="header">Elige cómo pagar</Text>
            <Text style={[font.body, { marginTop: spacing.sm }]}>{renewal ? 'Renovación' : 'Plan'}: {plan.name} · {formatMoney(plan.price, plan.currency)} · {plan.duration_days} días</Text>
            <Text style={[font.small, { marginTop: spacing.sm }]}>El pago online se completa en el proveedor. La membresía se activa solo cuando el pago se confirma.</Text>
            <View style={{ marginTop: spacing.md, gap: 8 }}>
              {[
                { value: 'BANK_TRANSFER', title: `Transferencia bancaria${bankInstructions.trim() ? '' : ' (datos no configurados)'}`, enabled: Boolean(bankInstructions.trim()) },
                { value: 'MANUAL', title: 'Pagar directamente al club', enabled: true },
                { value: 'MERCADO_PAGO', title: `Mercado Pago${onlineAvailable ? '' : ' (no configurado)'}`, enabled: onlineAvailable },
                { value: 'TRANSBANK', title: `Transbank Webpay Plus${transbankAvailable ? '' : ' (no configurado para pruebas)'}`, enabled: transbankAvailable },
              ].map((option) => <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ checked: method === option.value, disabled: !option.enabled }} disabled={!option.enabled} onPress={() => setMethod(option.value)} style={{ paddingVertical: spacing.sm, opacity: option.enabled ? 1 : 0.5 }}>
                <Text style={font.body}>{method === option.value ? '◉' : '○'} {option.title}</Text>
              </Pressable>)}
              {method === 'BANK_TRANSFER' ? <><Text style={font.heading}>Datos para transferir</Text><Text style={font.body}>{bankInstructions}</Text><Text style={font.small}>Después de solicitar el plan, envía el comprobante para que el club lo revise.</Text></> : null}
              {!onlineAvailable && !transbankAvailable ? <Text style={font.small}>El pago online no está configurado en el servidor.</Text> : null}
              <Button title="Continuar" onPress={() => onChoose(method)} />
              <Button title="Volver" variant="ghost" onPress={onClose} />
            </View>
          </Card>
        </ScrollView>
      </View>
    </Modal>
  );
}

export default function MembershipsScreen() {
  const { user } = useAuth();
  const isAdmin = user.role === 'ADMIN';
  const isTrainer = user.role === 'TRAINER';
  const resource = useResource(() => loadMemberships(user), [user.id]);
  useRefreshOnFocus(resource);
  const [notice, setNotice] = useState({ type: 'success', text: '' });
  const [busyPlan, setBusyPlan] = useState(null);
  const [filter, setFilter] = useState('PENDING');
  const [savingSetting, setSavingSetting] = useState(false);
  const [paymentChoice, setPaymentChoice] = useState(null);
  const data = resource.data;
  const today = todayISO();

  // Al volver del navegador de Mercado Pago se consulta el estado real al backend.
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) => { if (state === 'active') resource.refresh(); });
    return () => subscription.remove();
  }, [resource.refresh]);

  const done = async (text) => {
    setNotice({ type: 'success', text });
    await resource.refresh();
  };

  const openCheckout = async (url) => {
    try {
      await WebBrowser.openBrowserAsync(url);
    } finally {
      await resource.refresh();
    }
  };

  const payOnline = async (plan, provider = 'MERCADO_PAGO') => {
    setBusyPlan(plan.id);
    setNotice({ type: 'success', text: '' });
    try {
      const payment = await api.post('/memberships/payments/', { plan: plan.id, provider });
      setNotice({ type: 'success', text: `Completa el pago en ${provider === 'TRANSBANK' ? 'Transbank Webpay Plus' : 'Mercado Pago'}. Tu plan se activará cuando se confirme.` });
      if (payment.checkout_url) await openCheckout(payment.checkout_url);
      else {
        setNotice({ type: 'error', text: 'No se recibió un enlace de pago. Actualiza el estado antes de volver a intentarlo.' });
        await resource.refresh();
      }
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyPlan(null);
    }
  };

  const renew = async (plan, method, provider = 'MERCADO_PAGO', paymentMethod = 'MANUAL') => {
    setBusyPlan(plan?.id || 'renewal');
    setNotice({ type: 'success', text: '' });
    try {
      const result = await api.post('/memberships/renewal/', {
        method,
        ...(plan ? { plan: plan.id } : {}),
        ...(method === 'ONLINE' ? { provider } : { payment_method: paymentMethod })
      });
      if (method === 'ONLINE' && result.payment?.checkout_url) {
        await openCheckout(result.payment.checkout_url);
      } else if (method === 'ONLINE') {
        setNotice({ type: 'error', text: 'No se recibió un enlace de pago. Actualiza el estado antes de volver a intentarlo.' });
        await resource.refresh();
      } else {
        await done(paymentMethod === 'BANK_TRANSFER' ? 'Renovación solicitada. Adjunta tu comprobante de transferencia.' : 'Renovación solicitada al club.');
      }
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyPlan(null);
    }
  };

  const cancelPayment = async (payment) => {
    try {
      await api.del(`/memberships/payments/${payment.id}/`);
      await done('Pago cancelado.');
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    }
  };

  const requestPlan = async (plan, paymentMethod = 'MANUAL') => {
    setBusyPlan(plan.id);
    setNotice({ type: 'success', text: '' });
    try {
      await api.post('/memberships/', { plan: plan.id, payment_method: paymentMethod });
      await done(paymentMethod === 'BANK_TRANSFER' ? 'Solicitud enviada. Adjunta tu comprobante de transferencia.' : 'Solicitud enviada. El club confirmará tu pago para activar el plan.');
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyPlan(null);
    }
  };

  const cancelRequest = async (membership) => {
    try {
      await api.post(`/memberships/${membership.id}/review/`, { decision: 'CANCEL' });
      await done('Solicitud cancelada.');
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    }
  };

  const toggleRequirement = async (value) => {
    setSavingSetting(true);
    try {
      const settings = await api.patch('/memberships/settings/', { require_active_membership: value });
      resource.setData((prev) => ({ ...prev, settings: { ...prev.settings, ...settings } }));
      setNotice({ type: 'success', text: value ? 'Ahora se exige membresía activa para reservar.' : 'Las reservas ya no exigen membresía.' });
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setSavingSetting(false);
    }
  };

  const activePlans = (data?.plans || []).filter((plan) => plan.is_active);
  const memberships = data?.memberships || [];
  const current = memberships.find((m) => isMembershipValidFor(m, today));
  const pendingOne = memberships.find((m) => m.status === 'PENDING');
  const scheduledMembership = memberships.find((m) => m.status === 'SCHEDULED');
  const pendingPayment = openPaymentFor(data?.payments, pendingOne);
  const onlineAvailable = Boolean(data?.settings?.mercado_pago_available);
  const transbankAvailable = Boolean(data?.settings?.transbank_available);
  const lastPayment = (data?.payments || [])[0];
  const visibleAdmin = memberships.filter((m) => filter === 'ALL' || m.status === filter);

  return (
    <Screen eyebrow="PLANES" title="Membresías" subtitle={isAdmin ? 'Planes, pagos y reglas de reserva' : isTrainer ? 'Membresías de tus deportistas asignados' : 'Tu plan y su historial'} onRefresh={resource.refresh} refreshing={resource.refreshing}>
      <Banner type={notice.type} onClose={() => setNotice({ ...notice, text: '' })}>{notice.text}</Banner>
      <ResourceView resource={resource} isEmpty={false}>
        {data ? (
          isAdmin ? (
            <>
              {!onlineAvailable && !transbankAvailable ? <Banner type="warn">El pago online no está configurado en el servidor. Los deportistas pueden solicitar planes y pagar directamente al club.</Banner> : null}
              <TransferSettings instructions={data.settings.bank_transfer_instructions || ''} onSaved={(instructions) => {
                resource.setData((prev) => ({ ...prev, settings: { ...prev.settings, bank_transfer_instructions: instructions } }));
                setNotice({ type: 'success', text: 'Datos de transferencia actualizados para membresías y tienda.' });
              }} />
              <Card>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <View style={{ flex: 1, marginRight: spacing.md }}>
                    <Text style={font.heading}>Exigir membresía activa para reservar clases</Text>
                    <Text style={[font.small, { marginTop: 2 }]}>{data.settings.require_active_membership ? 'Activado' : 'Desactivado'} · solo afecta a tu club</Text>
                  </View>
                  <Switch
                    accessibilityLabel="Exigir membresía activa para reservar clases"
                    value={Boolean(data.settings.require_active_membership)}
                    onValueChange={toggleRequirement}
                    disabled={savingSetting}
                    trackColor={{ true: colors.red, false: colors.line }}
                  />
                </View>
              </Card>

              <SectionTitle>Solicitudes y membresías</SectionTitle>
              <Segmented
                value={filter}
                onChange={setFilter}
                options={[{ value: 'PENDING', label: 'Pendientes' }, { value: 'ACTIVE', label: 'Activas' }, { value: 'EXPIRED', label: 'Vencidas' }, { value: 'ALL', label: 'Todas' }]}
              />
              {visibleAdmin.length === 0 ? (
                <EmptyState icon="card-outline" title="Sin resultados" message="No hay membresías en este estado." />
              ) : visibleAdmin.map((membership) => (
                <MembershipRow key={membership.id} membership={membership} showAthlete>
                  {membership.payment_method === 'BANK_TRANSFER' ? <TransferProof membership={membership} isAdmin onDone={done} /> : null}
                  {membership.status === 'PENDING' && !membership.payment_status && membership.payment_method !== 'BANK_TRANSFER' ? <AdminReview membership={membership} onDone={done} /> : null}
                </MembershipRow>
              ))}

              <SectionTitle>Planes del club</SectionTitle>
              {data.plans.length === 0 ? <EmptyState title="Sin planes" message="Crea planes desde la versión web." /> : data.plans.map((plan) => (
                <Card key={plan.id}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={font.heading}>{plan.name}</Text>
                    <Badge text={plan.is_active ? 'Activo' : 'Inactivo'} tone={plan.is_active ? 'ok' : 'neutral'} />
                  </View>
                  <Text style={font.small}>{formatMoney(plan.price, plan.currency)} · {plan.duration_days} días · {plan.active_members} miembros activos</Text>
                </Card>
              ))}
            </>
          ) : isTrainer ? (
            <>
              <SectionTitle>Membresías de mis deportistas</SectionTitle>
              {memberships.length ? memberships.map((membership) => <MembershipRow key={membership.id} membership={membership} showAthlete />)
                : <EmptyState icon="card-outline" title="Sin membresías" message="Las membresías de tus deportistas asignados aparecerán aquí." />}
            </>
          ) : (
            <>
              <Card tone={pendingOne && !current ? 'warn' : undefined}>
                <Text style={font.small}>Estado actual</Text>
                {current ? (
                  <>
                    <Text style={[font.heading, { marginVertical: 4 }]}>{current.plan_name}</Text>
                    <Badge text="Activa" tone="ok" />
                    <Text style={[font.small, { marginTop: 6 }]}>{current.club_name || user?.club?.name} · {formatMoney(current.price_paid, current.currency)}</Text>
                    <Text style={[font.small, { marginTop: 4 }]}>Vigente del {formatDate(current.start_date)} al {formatDate(current.end_date)} · {current.days_remaining ?? 0} días restantes</Text>
                    {current.payment_status ? <Text style={[font.small, { marginTop: 4 }]}>Pago: {label('paymentStatus', current.payment_status)} ({label('payment', current.payment_provider)})</Text> : null}
                    {pendingOne ? (
                      <View style={{ marginTop: spacing.md, gap: 8 }}>
                        <Text style={font.small}>
                          {pendingOne.is_renewal ? `Renovación de ${pendingOne.plan_name} pendiente. Tu membresía actual sigue vigente hasta el ${formatDate(current.end_date)}.` : `Tienes otra solicitud pendiente de ${pendingOne.plan_name}.`}
                        </Text>
                        {!pendingPayment && pendingOne.payment_method !== 'BANK_TRANSFER' ? <Text style={font.small}>Esta solicitud es para pago al club. Para elegir otro método, cancélala y vuelve a elegir el plan.</Text> : null}
                        {pendingOne.payment_method === 'BANK_TRANSFER' ? <><Text style={font.small}>Datos para transferir: {data.settings.bank_transfer_instructions || 'Consulta con tu club.'}</Text><TransferProof membership={pendingOne} onDone={done} /></> : null}
                        {pendingPayment?.checkout_url ? <Button title="Continuar pago" onPress={() => openCheckout(pendingPayment.checkout_url)} /> : null}
                        {pendingPayment ? <Button title="Actualizar estado" variant="secondary" small onPress={resource.refresh} /> : null}
                        {pendingPayment ? <Button title="Cancelar pago" variant="secondary" small onPress={() => cancelPayment(pendingPayment)} /> : <Button title="Cancelar solicitud" variant="secondary" small onPress={() => cancelRequest(pendingOne)} />}
                      </View>
                    ) : null}
                    {scheduledMembership ? (
                      <Text style={[font.small, { marginTop: spacing.sm }]}>
                        Renovación programada: {scheduledMembership.plan_name}, del {formatDate(scheduledMembership.start_date)} al {formatDate(scheduledMembership.end_date)}.
                      </Text>
                    ) : null}
                  </>
                ) : pendingOne ? (
                  <>
                    <Text style={[font.heading, { marginVertical: 4 }]}>{pendingOne.plan_name}</Text>
                    <Badge text="Pendiente de pago" tone="warn" />
                    <Text style={[font.small, { marginTop: 6 }]}>{pendingPayment ? `Esperando la confirmación de ${label('payment', pendingPayment.payment_provider)}. Tu plan se activa solo cuando el pago se confirma.` : pendingOne.payment_method === 'BANK_TRANSFER' ? `Datos para transferir: ${data.settings.bank_transfer_instructions || 'Consulta con tu club.'}` : 'Paga en tu club; la membresía se activa cuando el administrador confirme el pago.'}</Text>
                    {!pendingPayment && pendingOne.payment_method !== 'BANK_TRANSFER' ? <Text style={[font.small, { marginTop: 4 }]}>Para elegir otro método, cancela esta solicitud y vuelve a elegir el plan.</Text> : null}
                    {pendingOne.payment_method === 'BANK_TRANSFER' ? <TransferProof membership={pendingOne} onDone={done} /> : null}
                    <View style={{ marginTop: spacing.md, gap: 8 }}>
                      {pendingPayment?.checkout_url ? <Button title="Continuar pago" onPress={() => openCheckout(pendingPayment.checkout_url)} /> : null}
                      {pendingPayment ? <Button title="Actualizar estado" variant="secondary" small onPress={resource.refresh} /> : null}
                      {pendingPayment ? <Button title="Cancelar pago" variant="secondary" small onPress={() => cancelPayment(pendingPayment)} /> : <Button title="Cancelar solicitud" variant="secondary" small onPress={() => cancelRequest(pendingOne)} />}
                    </View>
                  </>
                ) : (
                  <>
                    <Text style={[font.body, { marginTop: 4 }]}>No tienes una membresía vigente.</Text>
                    {lastPayment && lastPayment.status !== 'PENDING' ? <Text style={[font.small, { marginTop: 4 }]}>{paymentOutcomeMessage(lastPayment)}</Text> : null}
                  </>
                )}
                {data.settings.require_active_membership ? (
                  <Text style={[font.small, { marginTop: spacing.sm, color: colors.redDark }]}>Tu club exige membresía activa para reservar clases.</Text>
                ) : null}
              </Card>

              {data.renewal?.can_renew ? <Card tone="warn">
                <Text style={font.heading}>{data.renewal.state === 'EXPIRED' ? 'Tu membresía venció' : `Vence en ${data.renewal.days_left} día${data.renewal.days_left === 1 ? '' : 's'}`}</Text>
                <Text style={[font.small, { marginTop: 4 }]}>{data.renewal.state === 'EXPIRED' ? 'La nueva vigencia comienza el día en que se confirme el pago.' : `Si el pago se confirma hasta el día del vencimiento, la nueva vigencia empieza el ${formatDate(data.renewal.next_start_date)} sin perder días. Si se confirma después, empieza el día de la confirmación.`}</Text>
                {data.renewal.plan ? <View style={{ marginTop: spacing.md, gap: 8 }}>
                  <Button title="Elegir cómo renovar" onPress={() => setPaymentChoice({ plan: data.renewal.plan, renewal: true })} disabled={busyPlan !== null} />
                </View> : <Text style={[font.small, { marginTop: spacing.sm }]}>Elige uno de los planes disponibles para renovar.</Text>}
              </Card> : null}

              <SectionTitle>Planes disponibles</SectionTitle>
              {activePlans.length === 0 ? (
                <EmptyState icon="pricetags-outline" title="Sin planes disponibles" message="Tu club aún no publicó planes de membresía." />
              ) : activePlans.map((plan) => (
                <Card key={plan.id}>
                  <Text style={font.heading}>{plan.name}</Text>
                  <Text style={{ fontSize: 22, fontWeight: '800', color: colors.red, marginVertical: 4 }}>{formatMoney(plan.price, plan.currency)}</Text>
                  <Text style={font.small}>{plan.duration_days} días · {plan.weekly_class_limit ? `${plan.weekly_class_limit} clases por semana` : 'Clases sin límite semanal'}</Text>
                  {plan.description ? <Text style={[font.body, { marginTop: 4 }]}>{plan.description}</Text> : null}
                  {plan.benefits ? <Text style={[font.small, { marginTop: 4 }]}>{plan.benefits}</Text> : null}
                  <View style={{ marginTop: spacing.md, gap: 8 }}>
                    <Button title={data.renewal?.can_renew ? 'Elegir cómo renovar' : 'Elegir método de pago'} onPress={() => setPaymentChoice({ plan, renewal: Boolean(data.renewal?.can_renew) })} loading={busyPlan === plan.id} disabled={busyPlan !== null || (!data.renewal?.can_renew && Boolean(pendingOne || current || scheduledMembership))} />
                    {!data.renewal?.can_renew && (pendingOne || current || scheduledMembership) ? <Text style={[font.small, { marginTop: 4 }]}>Ya tienes una membresía {pendingOne ? 'pendiente' : scheduledMembership ? 'programada' : 'vigente'}.</Text> : null}
                  </View>
                </Card>
              ))}

              <SectionTitle>Historial</SectionTitle>
              {memberships.length === 0 ? (
                <EmptyState icon="time-outline" title="Sin historial" message="Tus membresías y pagos aparecerán aquí." />
              ) : memberships.map((membership) => <MembershipRow key={membership.id} membership={membership} />)}

              {(data.payments || []).length > 0 ? (
                <>
                  <SectionTitle>Pagos online</SectionTitle>
                  {data.payments.map((payment) => (
                    <Card key={payment.id}>
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                        <View style={{ flex: 1, marginRight: spacing.sm }}>
                          <Text style={font.heading}>{payment.plan_name}</Text>
                          <Text style={font.small}>{formatMoney(payment.amount, payment.currency)} · {label('payment', payment.payment_provider)} · {formatDate(payment.created_at?.slice(0, 10))}</Text>
                        </View>
                        <Badge text={label('paymentStatus', payment.status)} tone={tone(payment.status)} />
                      </View>
                    </Card>
                  ))}
                </>
              ) : null}
            </>
          )
        ) : null}
      </ResourceView>
      <PaymentDialog key={paymentChoice ? `${paymentChoice.plan.id}-${paymentChoice.renewal}` : 'closed'} choice={paymentChoice} onlineAvailable={onlineAvailable} transbankAvailable={transbankAvailable} bankInstructions={data?.settings?.bank_transfer_instructions || ''} onClose={() => setPaymentChoice(null)} onChoose={(method) => {
        const { plan, renewal: isRenewal } = paymentChoice;
        setPaymentChoice(null);
        const online = ['MERCADO_PAGO', 'TRANSBANK'].includes(method);
        if (isRenewal) renew(plan, online ? 'ONLINE' : 'MANUAL', online ? method : undefined, method);
        else if (online) payOnline(plan, method);
        else requestPlan(plan, method);
      }} />
    </Screen>
  );
}
