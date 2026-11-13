import { useEffect, useState } from 'react';
import { AppState, Switch, Text, View } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { Badge, Banner, Button, Card, EmptyState, Field, KeyValue, ResourceView, Screen, SectionTitle, Segmented } from '../components/ui';
import { useRefreshOnFocus, useResource } from '../hooks/useResource';
import { colors, font, spacing } from '../theme';
import { formatDate, formatMoney, isMembershipValidFor, label, todayISO, tone } from '../utils/format';
import { openPaymentFor, paymentOutcomeMessage } from '../utils/payment';

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
      else await resource.refresh();
    } catch (error) {
      setNotice({ type: 'error', text: error.message });
    } finally {
      setBusyPlan(null);
    }
  };

  const renew = async (plan, method, provider = 'MERCADO_PAGO') => {
    setBusyPlan(plan?.id || 'renewal');
    setNotice({ type: 'success', text: '' });
    try {
      const result = await api.post('/memberships/renewal/', {
        method,
        ...(plan ? { plan: plan.id } : {}),
        ...(method === 'ONLINE' ? { provider } : {})
      });
      if (method === 'ONLINE' && result.payment?.checkout_url) {
        await openCheckout(result.payment.checkout_url);
      } else {
        await done(method === 'ONLINE' ? 'Renovación iniciada; se activará al confirmarse el pago.' : 'Renovación solicitada al club.');
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

  const requestPlan = async (plan) => {
    setBusyPlan(plan.id);
    setNotice({ type: 'success', text: '' });
    try {
      await api.post('/memberships/', { plan: plan.id });
      await done('Solicitud enviada. El club confirmará tu pago para activar el plan.');
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
      resource.setData((prev) => ({ ...prev, settings }));
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
                  {membership.status === 'PENDING' ? <AdminReview membership={membership} onDone={done} /> : null}
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
                    <Text style={[font.small, { marginTop: 6 }]}>{pendingPayment ? `Esperando la confirmación de ${label('payment', pendingPayment.payment_provider)}. Tu plan se activa solo cuando el pago se confirma.` : 'Paga en tu club; la membresía se activa cuando el administrador confirme el pago.'}</Text>
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
                  {onlineAvailable ? <Button title="Renovar con Mercado Pago" onPress={() => renew(data.renewal.plan, 'ONLINE', 'MERCADO_PAGO')} loading={busyPlan === 'renewal'} /> : null}
                  {transbankAvailable ? <Button title="Renovar con Transbank Webpay Plus" variant="secondary" onPress={() => renew(data.renewal.plan, 'ONLINE', 'TRANSBANK')} loading={busyPlan === 'renewal'} /> : null}
                  <Button title="Renovar y pagar al club" variant="secondary" onPress={() => renew(data.renewal.plan, 'MANUAL')} loading={busyPlan === 'renewal'} />
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
                    {data.renewal?.can_renew ? <>
                      {onlineAvailable ? <Button title="Renovar con Mercado Pago" onPress={() => renew(plan, 'ONLINE', 'MERCADO_PAGO')} loading={busyPlan === plan.id} /> : null}
                      {transbankAvailable ? <Button title="Renovar con Transbank Webpay Plus" variant="secondary" onPress={() => renew(plan, 'ONLINE', 'TRANSBANK')} loading={busyPlan === plan.id} /> : null}
                      <Button title="Renovar y pagar al club" variant="secondary" onPress={() => renew(plan, 'MANUAL')} loading={busyPlan === plan.id} />
                    </> : <>
                      {onlineAvailable ? <Button title="Pagar con Mercado Pago" onPress={() => payOnline(plan, 'MERCADO_PAGO')} loading={busyPlan === plan.id} disabled={Boolean(pendingOne) || Boolean(current)} /> : null}
                      {transbankAvailable ? <Button title="Pagar con Transbank Webpay Plus" variant="secondary" onPress={() => payOnline(plan, 'TRANSBANK')} loading={busyPlan === plan.id} disabled={Boolean(pendingOne) || Boolean(current)} /> : null}
                      <Button title={onlineAvailable || transbankAvailable ? 'Solicitar y pagar al club' : 'Solicitar plan'} variant={onlineAvailable || transbankAvailable ? 'secondary' : undefined} onPress={() => requestPlan(plan)} loading={busyPlan === plan.id && !onlineAvailable && !transbankAvailable} disabled={Boolean(pendingOne) || Boolean(current)} />
                      {pendingOne || current ? <Text style={[font.small, { marginTop: 4 }]}>Ya tienes una membresía {pendingOne ? 'pendiente' : 'vigente'}.</Text> : null}
                    </>}
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
    </Screen>
  );
}
