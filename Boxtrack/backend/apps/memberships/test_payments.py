import hashlib
import hmac
import os
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.error import URLError

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.athletes.models import Athlete
from apps.memberships.models import Membership, MembershipPayment
from apps.memberships.tests import MembershipBase
from apps.notifications.models import Notification
from apps.store.models import Order

SECRET = 'test-webhook-secret'
ENV = {
    'MERCADOPAGO_ACCESS_TOKEN': 'TEST-token-de-prueba',
    'MERCADOPAGO_WEBHOOK_SECRET': SECRET,
    'MERCADOPAGO_NOTIFICATION_URL': 'https://example.test/api/store/payments/mercadopago/webhook/',
}
PREFERENCE = 'apps.memberships.payments.post_mercadopago_preference'
FETCH = 'apps.store.views.fetch_mercadopago_payment'


def signed_webhook(client, data_id, secret=SECRET, request_id='req-1', ts='1700000000'):
    manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
    signature = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return client.post(
        f'{reverse("mercadopago-webhook")}?data.id={data_id}', {'data': {'id': data_id}}, format='json',
        HTTP_X_SIGNATURE=f'ts={ts},v1={signature}', HTTP_X_REQUEST_ID=request_id,
    )


class MembershipPaymentBase(MembershipBase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.anon = APIClient()

    def start(self, plan=None, user=None, body=None):
        self.client.force_authenticate(user=user or self.athlete_user)
        data = body if body is not None else {'plan': (plan or self.plan).id}
        with mock.patch(PREFERENCE, return_value=('https://mp.test/checkout/abc', 'pref-1')) as preference:
            response = self.client.post(reverse('membership-payment-list-create'), data, format='json')
        return response, preference

    def provider_payment(self, payment, status_='approved', amount=None, currency=None, pid='9001'):
        return {
            'id': pid, 'status': status_, 'external_reference': f'membership:{payment.pk}',
            'transaction_amount': float(amount if amount is not None else payment.amount),
            'currency_id': currency or payment.currency,
        }

    def notify(self, provider_payment, data_id=None):
        with mock.patch(FETCH, return_value=provider_payment):
            return signed_webhook(self.anon, data_id or provider_payment['id'])

    def purchase(self):
        response, _ = self.start()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return MembershipPayment.objects.get(pk=response.data['id'])


class CheckoutCreationTests(MembershipPaymentBase):
    def test_creates_pending_payment_and_membership_with_server_price(self):
        response, preference = self.start(body={'plan': self.plan.id, 'amount': 1, 'price': 1, 'price_paid': 1, 'club': self.other_club.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = MembershipPayment.objects.get()
        self.assertEqual(payment.amount, Decimal('30000'))
        self.assertEqual((payment.club_id, payment.user_id, payment.plan_id), (self.club.id, self.athlete_user.id, self.plan.id))
        self.assertEqual(payment.status, 'PENDING')
        self.assertEqual(payment.membership.status, 'PENDING')
        self.assertEqual(response.data['checkout_url'], 'https://mp.test/checkout/abc')
        payload = preference.call_args.args[0]
        self.assertEqual(payload['items'][0]['unit_price'], 30000.0)
        self.assertEqual(payload['external_reference'], f'membership:{payment.pk}')
        self.assertEqual(payload['notification_url'], ENV['MERCADOPAGO_NOTIFICATION_URL'])

    def test_rejects_plan_from_other_club_inactive_plan_and_bad_input(self):
        response, preference = self.start(plan=self.other_plan)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.plan.is_active = False
        self.plan.save()
        self.assertEqual(self.start()[0].status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.start(body={})[0].status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.start(body={'plan': 'abc'})[0].status_code, status.HTTP_400_BAD_REQUEST)
        preference.assert_not_called()
        self.assertFalse(MembershipPayment.objects.exists())
        self.assertFalse(Membership.objects.exists())

    def test_only_athletes_can_buy_and_staff_cannot_use_athlete_endpoint(self):
        for user in (self.admin, self.trainer):
            response, _ = self.start(user=user)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(MembershipPayment.objects.exists())

    def test_unconfigured_mercado_pago_is_unavailable_and_creates_nothing(self):
        with mock.patch.dict(os.environ, {'MERCADOPAGO_ACCESS_TOKEN': ''}):
            response, preference = self.start()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        preference.assert_not_called()
        self.assertFalse(Membership.objects.exists())

    def test_provider_failure_cancels_purchase_and_allows_retry(self):
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch(PREFERENCE, side_effect=URLError('sin red')):
            response = self.client.post(reverse('membership-payment-list-create'), {'plan': self.plan.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(MembershipPayment.objects.get().status, 'CANCELLED')
        self.assertEqual(Membership.objects.get().status, 'CANCELLED')
        retry, _ = self.start()
        self.assertEqual(retry.status_code, status.HTTP_201_CREATED)

    def test_repeated_start_reuses_the_open_checkout(self):
        first, _ = self.start()
        second, preference = self.start()
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['id'], second.data['id'])
        preference.assert_not_called()
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(MembershipPayment.objects.count(), 1)

    def test_other_plan_or_existing_membership_conflicts(self):
        self.start()
        from apps.memberships.models import MembershipPlan
        other = MembershipPlan.objects.create(club=self.club, name='Anual', price=200000, duration_days=365)
        self.assertEqual(self.start(plan=other)[0].status_code, status.HTTP_409_CONFLICT)
        MembershipPayment.objects.all().delete()
        Membership.objects.all().delete()
        self.activate()
        self.assertEqual(self.start()[0].status_code, status.HTTP_409_CONFLICT)

    def test_manual_pending_request_blocks_online_purchase_and_manual_flow_still_works(self):
        self.assertEqual(self.request_plan().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.start()[0].status_code, status.HTTP_409_CONFLICT)
        membership = Membership.objects.get()
        self.client.force_authenticate(user=self.admin)
        confirm = self.client.post(reverse('membership-review', kwargs={'pk': membership.pk}), {'decision': 'CONFIRM'}, format='json')
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'ACTIVE')

    def test_settings_expose_availability_without_secrets(self):
        self.client.force_authenticate(user=self.athlete_user)
        data = self.client.get(reverse('membership-settings')).data
        self.assertTrue(data['mercado_pago_available'])
        with mock.patch.dict(os.environ, {'MERCADOPAGO_WEBHOOK_SECRET': ''}):
            self.assertFalse(self.client.get(reverse('membership-settings')).data['mercado_pago_available'])
        self.assertNotIn(SECRET, str(data))


class WebhookTests(MembershipPaymentBase):
    def test_invalid_signature_is_rejected_without_calling_provider(self):
        payment = self.purchase()
        with mock.patch(FETCH) as fetch:
            response = signed_webhook(self.anon, '9001', secret='otro-secreto')
            missing = self.anon.post(f'{reverse("mercadopago-webhook")}?data.id=9001', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(missing.status_code, status.HTTP_401_UNAUTHORIZED)
        fetch.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

    def test_provider_unreachable_returns_502_and_changes_nothing(self):
        payment = self.purchase()
        with mock.patch(FETCH, side_effect=URLError('caído')):
            response = signed_webhook(self.anon, '9001')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'PENDING')

    def test_provider_timeout_or_unexpected_body_returns_502_and_changes_nothing(self):
        payment = self.purchase()
        for failure in ({'side_effect': TimeoutError('lento')}, {'return_value': ['no', 'es', 'objeto']}, {'return_value': None}):
            with mock.patch(FETCH, **failure):
                response = signed_webhook(self.anon, '9001')
            self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

    def merchant_order_post(self, secret=SECRET, id_='5555', via='body'):
        manifest = f'id:{id_};request-id:req-9;ts:1700000000;'
        signature = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        url = f'{reverse("mercadopago-webhook")}?data.id={id_}'
        payload = {'type': 'merchant_order', 'data': {'id': id_}}
        if via == 'query':
            url += '&topic=merchant_order'
            payload = {'data': {'id': id_}}
        return self.anon.post(url, payload, format='json',
                              HTTP_X_SIGNATURE=f'ts=1700000000,v1={signature}', HTTP_X_REQUEST_ID='req-9')

    def test_merchant_order_is_acknowledged_without_lookup_or_state_change(self):
        payment = self.purchase()
        order_count = Order.objects.count()
        for via in ('body', 'query'):
            with mock.patch(FETCH) as fetch:
                response = self.merchant_order_post(via=via)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data.get('ignored'), 'merchant_order')
            fetch.assert_not_called()
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))
        self.assertEqual(Order.objects.count(), order_count)

    def test_merchant_order_with_invalid_signature_is_still_rejected(self):
        with mock.patch(FETCH) as fetch:
            response = self.merchant_order_post(secret='otro-secreto')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        fetch.assert_not_called()

    def test_payment_topic_is_still_verified_and_approved_once(self):
        payment = self.purchase()
        provider = self.provider_payment(payment)
        manifest = 'id:9001;request-id:req-1;ts:1700000000;'
        signature = hmac.new(SECRET.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        for _ in range(2):
            with mock.patch(FETCH, return_value=provider) as fetch:
                response = self.anon.post(
                    f'{reverse("mercadopago-webhook")}?data.id=9001', {'type': 'payment', 'data': {'id': '9001'}},
                    format='json', HTTP_X_SIGNATURE=f'ts=1700000000,v1={signature}', HTTP_X_REQUEST_ID='req-1')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            fetch.assert_called_once()
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('APPROVED', 'ACTIVE'))
        self.assertEqual(Membership.objects.filter(status='ACTIVE', athlete=payment.membership.athlete).count(), 1)

    def test_responses_and_logs_do_not_leak_credentials(self):
        payment = self.purchase()
        with self.assertLogs('apps.memberships.payments', level='WARNING') as logs:
            bad = self.provider_payment(payment, amount=1)
            response = self.notify(bad)
        self.client.force_authenticate(user=self.athlete_user)
        listing = self.client.get(reverse('membership-payment-list-create'))
        settings_response = self.client.get(reverse('membership-settings'))
        blob = ' '.join([str(response.data), str(listing.data), str(settings_response.data), *logs.output])
        for secret in (SECRET, ENV['MERCADOPAGO_ACCESS_TOKEN'], ENV['MERCADOPAGO_NOTIFICATION_URL']):
            self.assertNotIn(secret, blob)
        self.assertNotIn('provider_payment_id', listing.data[0])
        self.assertNotIn('payment_reference', listing.data[0])

    def test_approved_payment_activates_membership_once(self):
        payment = self.purchase()
        provider = self.provider_payment(payment)
        first = self.notify(provider)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        membership = payment.membership
        self.assertEqual((payment.status, payment.provider_payment_id), ('APPROVED', '9001'))
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(membership.status, 'ACTIVE')
        self.assertEqual(membership.end_date, timezone.localdate() + timedelta(days=30))
        notifications = Notification.objects.filter(user=self.athlete_user, title='Membresía activada').count()

        membership.end_date = timezone.localdate() + timedelta(days=5)
        membership.save()
        for _ in range(3):
            self.assertEqual(self.notify(provider).status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertEqual(membership.end_date, timezone.localdate() + timedelta(days=5))
        self.assertEqual(Membership.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.athlete_user, title='Membresía activada').count(), notifications)

    def test_second_approved_charge_for_same_purchase_is_flagged_not_applied(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, pid='9001'))
        response = self.notify(self.provider_payment(payment, pid='9002'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.provider_payment_id, '9001')
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Posible cobro duplicado').exists())

    def test_pending_payment_does_not_activate(self):
        payment = self.purchase()
        for state in ('pending', 'in_process'):
            self.assertEqual(self.notify(self.provider_payment(payment, state)).status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))
        self.assertEqual(payment.provider_status, 'in_process')

    def test_rejected_payment_does_not_activate_and_allows_new_purchase(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, 'rejected'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('REJECTED', 'CANCELLED'))
        again, _ = self.start()
        self.assertEqual(again.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(again.data['id'], payment.id)

    def test_cancelled_provider_payment_does_not_activate(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, 'cancelled'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('CANCELLED', 'CANCELLED'))

    def test_amount_or_currency_mismatch_is_rejected(self):
        payment = self.purchase()
        self.assertEqual(self.notify(self.provider_payment(payment, amount=1)).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.notify(self.provider_payment(payment, currency='USD')).status_code, status.HTTP_400_BAD_REQUEST)
        bad = self.provider_payment(payment)
        bad['transaction_amount'] = 'no-es-numero'
        self.assertEqual(self.notify(bad).status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

    def test_unknown_or_malformed_reference_is_rejected(self):
        payment = self.purchase()
        unknown = self.provider_payment(payment)
        unknown['external_reference'] = 'membership:99999'
        self.assertEqual(self.notify(unknown).status_code, status.HTTP_400_BAD_REQUEST)
        malformed = self.provider_payment(payment)
        malformed['external_reference'] = 'membership:abc'
        self.assertEqual(self.notify(malformed).status_code, status.HTTP_400_BAD_REQUEST)

    def test_provider_payment_cannot_be_reused_for_another_purchase(self):
        first = self.purchase()
        self.notify(self.provider_payment(first, pid='9001'))
        first.membership.status = 'CANCELLED'
        first.membership.save()
        second = self.purchase()
        response = self.notify(self.provider_payment(second, pid='9001'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        second.refresh_from_db()
        self.assertEqual(second.status, 'PENDING')

    def test_plan_changes_after_checkout_do_not_alter_the_charge(self):
        payment = self.purchase()
        self.plan.price = Decimal('99999')
        self.plan.is_active = False
        self.plan.save()
        self.assertEqual(self.notify(self.provider_payment(payment, amount=99999)).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.notify(self.provider_payment(payment)).status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.membership.status, 'ACTIVE')
        self.assertEqual(payment.membership.price_paid, Decimal('30000'))

    def test_refund_cancels_active_membership(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment))
        self.notify(self.provider_payment(payment, 'refunded'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('REFUNDED', 'CANCELLED'))
        self.assertEqual(self.notify(self.provider_payment(payment)).status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'REFUNDED')

    def test_refund_notification_for_unapproved_payment_is_ignored(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, 'refunded'))
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'PENDING')

    def test_late_approval_after_rejected_attempt_activates_when_athlete_is_free(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, 'rejected', pid='8000'))
        self.notify(self.provider_payment(payment, 'approved', pid='8001'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('APPROVED', 'ACTIVE'))

    def test_late_approval_with_another_open_membership_requires_review(self):
        payment = self.purchase()
        self.notify(self.provider_payment(payment, 'rejected', pid='8000'))
        self.activate()
        self.notify(self.provider_payment(payment, 'approved', pid='8001'))
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'REVIEW')
        self.assertEqual(Membership.objects.filter(status='ACTIVE').count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Pago aprobado que requiere revisión').exists())

    def test_membership_required_club_allows_reservation_only_after_confirmed_payment(self):
        from apps.memberships.models import MembershipSettings
        MembershipSettings.objects.create(club=self.club, require_active_membership=True)
        training = self.make_training(timezone.localdate() + timedelta(days=2))
        payment = self.purchase()
        self.assertEqual(self.reserve(training).status_code, status.HTTP_409_CONFLICT)
        self.notify(self.provider_payment(payment))
        self.assertEqual(self.reserve(training).status_code, status.HTTP_201_CREATED)

    def test_expired_checkout_is_closed_and_late_payment_is_not_lost(self):
        payment = self.purchase()
        MembershipPayment.objects.filter(pk=payment.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.client.force_authenticate(user=self.athlete_user)
        listing = self.client.get(reverse('membership-payment-list-create'))
        self.assertEqual(listing.data[0]['status'], 'EXPIRED')
        self.assertEqual(listing.data[0]['checkout_url'], '')
        self.assertEqual(Membership.objects.get().status, 'CANCELLED')
        self.notify(self.provider_payment(payment))
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'APPROVED')


class PaymentAccessTests(MembershipPaymentBase):
    def setUp(self):
        super().setUp()
        role = self.athlete_user.role
        self.other_athlete_user = User.objects.create_user(username='athlete2', email='d2@demo.com', password='Password123!', club=self.other_club, role=role)
        Athlete.objects.create(club=self.other_club, user=self.other_athlete_user, first_name='Ana', last_name='Pérez', status='ACTIVE')

    def test_users_only_see_authorized_payments_and_link_only_for_buyer(self):
        payment = self.purchase()
        url = reverse('membership-payment-detail', kwargs={'pk': payment.pk})
        self.client.force_authenticate(user=self.athlete_user)
        self.assertTrue(self.client.get(url).data['checkout_url'])
        self.client.force_authenticate(user=self.admin)
        admin_view = self.client.get(url)
        self.assertEqual(admin_view.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_view.data['checkout_url'], '')
        self.assertEqual(len(self.client.get(reverse('membership-payment-list-create')).data), 1)
        for outsider in (self.other_admin, self.other_athlete_user):
            self.client.force_authenticate(user=outsider)
            self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
            self.assertIn(self.client.delete(url).status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
            self.assertEqual(self.client.get(reverse('membership-payment-list-create')).data, [])
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('membership-payment-list-create')).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_cancel_buyer_payment_and_buyer_can_cancel_own_pending(self):
        payment = self.purchase()
        url = reverse('membership-payment-detail', kwargs={'pk': payment.pk})
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.athlete_user)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('CANCELLED', 'CANCELLED'))
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_409_CONFLICT)

    def test_manual_cancellation_or_review_closes_open_online_payment(self):
        payment = self.purchase()
        self.client.force_authenticate(user=self.athlete_user)
        cancel = self.client.post(reverse('membership-review', kwargs={'pk': payment.membership_id}), {'decision': 'CANCEL'}, format='json')
        self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'CANCELLED')

    def test_athletes_cannot_mark_payments_as_paid_through_the_api(self):
        payment = self.purchase()
        url = reverse('membership-payment-detail', kwargs={'pk': payment.pk})
        self.client.force_authenticate(user=self.athlete_user)
        self.assertEqual(self.client.patch(url, {'status': 'APPROVED'}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.put(url, {'status': 'APPROVED'}, format='json').status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'PENDING')
        confirm = self.client.post(reverse('membership-review', kwargs={'pk': payment.membership_id}), {'decision': 'CONFIRM'}, format='json')
        self.assertEqual(confirm.status_code, status.HTTP_403_FORBIDDEN)


class StoreWebhookRegressionTests(MembershipPaymentBase):
    """El webhook compartido sigue procesando los pedidos de la tienda como antes."""

    def make_order(self):
        return Order.objects.create(club=self.club, user=self.athlete_user, payment_method='MERCADO_PAGO', total=Decimal('25000'))

    def test_store_order_is_paid_by_verified_webhook(self):
        order = self.make_order()
        provider = {'id': '7001', 'status': 'approved', 'external_reference': str(order.pk), 'transaction_amount': 25000, 'currency_id': 'CLP'}
        self.assertEqual(self.notify(provider).status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment_reference), ('PAID', '7001'))
        self.assertEqual(self.notify(provider).status_code, status.HTTP_200_OK)

    def test_store_order_amount_mismatch_and_bad_signature_are_rejected(self):
        order = self.make_order()
        provider = {'id': '7001', 'status': 'approved', 'external_reference': str(order.pk), 'transaction_amount': 1, 'currency_id': 'CLP'}
        self.assertEqual(self.notify(provider).status_code, status.HTTP_400_BAD_REQUEST)
        with mock.patch(FETCH):
            self.assertEqual(signed_webhook(self.anon, '7001', secret='x').status_code, status.HTTP_401_UNAUTHORIZED)
        order.refresh_from_db()
        self.assertEqual(order.status, 'PENDING')

    def test_store_order_does_not_touch_memberships(self):
        order = self.make_order()
        provider = {'id': '7002', 'status': 'approved', 'external_reference': str(order.pk), 'transaction_amount': 25000, 'currency_id': 'CLP'}
        self.notify(provider)
        self.assertFalse(MembershipPayment.objects.exists())
        self.assertFalse(Membership.objects.exists())
