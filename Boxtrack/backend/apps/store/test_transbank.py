import os
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from rest_framework import status

from apps.memberships.models import Membership, MembershipPayment
from apps.memberships.test_payments import MembershipPaymentBase
from apps.notifications.models import Notification
from apps.store.models import Order, Product


TRANSBANK_ENV = {
    'TRANSBANK_ENVIRONMENT': 'TEST',
    'TRANSBANK_COMMERCE_CODE': '597055555532',
    'TRANSBANK_API_KEY': 'test-api-key',
}
CREATE_MEMBERSHIP = 'apps.memberships.payments.webpay_transaction'
CREATE_ORDER = 'apps.store.views.webpay_transaction'


class TransbankTests(MembershipPaymentBase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(club=self.club, name='Guantes de prueba', price=45000, stock=4)

    def start_membership(self, plan=None, sdk_error=None):
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch.dict(os.environ, TRANSBANK_ENV):
            with mock.patch(CREATE_MEMBERSHIP) as transaction_factory:
                if sdk_error:
                    transaction_factory.return_value.create.side_effect = sdk_error
                else:
                    transaction_factory.return_value.create.return_value = {
                        'token': 'tbk-membership-token', 'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
                    }
                response = self.client.post(reverse('membership-payment-list-create'), {
                    'plan': (plan or self.plan).pk, 'provider': 'TRANSBANK',
                }, format='json')
        return response, transaction_factory

    def callback(self, token, result, method='POST'):
        sdk = mock.Mock()
        sdk.commit.return_value = result
        with mock.patch.dict(os.environ, TRANSBANK_ENV):
            with mock.patch(CREATE_ORDER, return_value=sdk):
                path = reverse('transbank-return')
                if method == 'GET':
                    response = self.anon.get(path, {'token_ws': token})
                else:
                    response = self.anon.post(path, {'token_ws': token}, format='multipart')
        return response, sdk

    @staticmethod
    def approved_result(buy_order, session_id, amount='30000.00'):
        return {
            'status': 'AUTHORIZED', 'response_code': 0, 'amount': amount,
            'buy_order': buy_order, 'session_id': session_id, 'authorization_code': '123456',
        }

    def test_membership_stays_pending_until_sdk_commit_and_get_return_is_supported(self):
        response, sdk_factory = self.start_membership()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = MembershipPayment.objects.get()
        self.assertEqual((payment.payment_provider, payment.status, payment.membership.status), ('TRANSBANK', 'PENDING', 'PENDING'))
        self.assertIn('/payments/transbank/checkout/', response.data['checkout_url'])
        sdk_factory.return_value.create.assert_called_once()

        self.client.get(reverse('transbank-checkout', args=[payment.transbank_token]))
        result = self.approved_result(payment.transbank_buy_order, payment.transbank_session_id)
        returned, sdk = self.callback(payment.transbank_token, result, method='GET')
        self.assertEqual(returned.status_code, 302)
        self.assertIn('/memberships?payment=success', returned['Location'])
        sdk.commit.assert_called_once_with(payment.transbank_token)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('APPROVED', 'ACTIVE'))
        self.assertEqual(payment.transbank_authorization_code, '123456')

    def test_checkout_form_posts_token_to_the_provider(self):
        self.start_membership()
        payment = MembershipPayment.objects.get()
        response = self.anon.get(reverse('transbank-checkout', args=[payment.transbank_token]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="token_ws"', response.content)
        self.assertIn(payment.transbank_token.encode(), response.content)
        self.assertIn(payment.transbank_url.encode(), response.content)

    def test_admin_cannot_activate_unconfirmed_online_membership(self):
        self.start_membership()
        payment = MembershipPayment.objects.get()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('membership-review', kwargs={'pk': payment.membership_id}), {'decision': 'CONFIRM'}, format='json')
        payment.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

    def test_amount_mismatch_is_held_for_review_and_does_not_activate(self):
        self.start_membership()
        payment = MembershipPayment.objects.get()
        result = self.approved_result(payment.transbank_buy_order, payment.transbank_session_id, amount='30001')
        self.callback(payment.transbank_token, result)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status, payment.provider_status), ('REVIEW', 'PENDING', 'AMOUNT_MISMATCH'))
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Pago Transbank en revisión').exists())

    def test_late_renewal_authorization_preserves_current_membership_and_schedules_next_term(self):
        current = self.activate(days_left=4)
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch.dict(os.environ, TRANSBANK_ENV):
            with mock.patch(CREATE_MEMBERSHIP) as transaction_factory:
                transaction_factory.return_value.create.return_value = {
                    'token': 'tbk-renewal-token', 'url': 'https://webpay3gint.transbank.cl/init',
                }
                started = self.client.post(reverse('membership-renewal'), {
                    'method': 'ONLINE', 'provider': 'TRANSBANK',
                }, format='json')
        self.assertEqual(started.status_code, status.HTTP_201_CREATED, started.data)
        payment = MembershipPayment.objects.get(pk=started.data['payment']['id'])
        MembershipPayment.objects.filter(pk=payment.pk).update(status='EXPIRED')
        Membership.objects.filter(pk=payment.membership_id).update(status='CANCELLED')

        result = self.approved_result(payment.transbank_buy_order, payment.transbank_session_id)
        self.callback(payment.transbank_token, result)
        payment.refresh_from_db()
        payment.membership.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status, current.status), ('APPROVED', 'SCHEDULED', 'ACTIVE'))
        self.assertEqual(payment.membership.start_date, current.end_date + timedelta(days=1))

    def test_rejected_and_failed_commit_do_not_activate_membership(self):
        self.start_membership()
        payment = MembershipPayment.objects.get()
        rejected = self.approved_result(payment.transbank_buy_order, payment.transbank_session_id)
        rejected.update(status='FAILED', response_code=4)
        self.callback(payment.transbank_token, rejected)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('REJECTED', 'CANCELLED'))

    def test_provider_initialization_failure_leaves_no_open_membership(self):
        response, _ = self.start_membership(sdk_error=OSError('provider unavailable'))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        payment = MembershipPayment.objects.get()
        self.assertEqual((payment.status, payment.membership.status), ('CANCELLED', 'CANCELLED'))

    def test_store_order_is_paid_only_after_transbank_commit(self):
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch.dict(os.environ, TRANSBANK_ENV):
            with mock.patch(CREATE_ORDER) as transaction_factory:
                transaction_factory.return_value.create.return_value = {
                    'token': 'tbk-order-token', 'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
                }
                response = self.client.post(reverse('store-orders'), {
                    'payment_method': 'TRANSBANK', 'items': [{'product': self.product.pk, 'quantity': 1}],
                }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual((order.status, order.total, order.stock_released), ('PENDING', Decimal('45000.00'), False))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        self.client.force_authenticate(user=self.admin)
        forbidden = self.client.patch(reverse('store-order-detail', kwargs={'pk': order.pk}), {'status': 'PAID'}, format='json')
        self.assertEqual(forbidden.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'PENDING')

        result = self.approved_result(order.transbank_buy_order, order.transbank_session_id, amount='45000.00')
        callback, _ = self.callback(order.transbank_token, result)
        self.assertIn('/store?payment=success', callback['Location'])
        order.refresh_from_db()
        self.assertEqual((order.status, order.stock_released), ('PAID', False))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_cancelled_order_with_late_authorization_is_flagged_for_admin(self):
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch.dict(os.environ, TRANSBANK_ENV):
            with mock.patch(CREATE_ORDER) as transaction_factory:
                transaction_factory.return_value.create.return_value = {'token': 'tbk-late-token', 'url': 'https://webpay3gint.transbank.cl/init'}
                response = self.client.post(reverse('store-orders'), {
                    'payment_method': 'TRANSBANK', 'items': [{'product': self.product.pk, 'quantity': 1}],
                }, format='json')
        order = Order.objects.get(pk=response.data['id'])
        self.client.patch(reverse('store-order-detail', kwargs={'pk': order.pk}), {'status': 'CANCELLED'}, format='json')
        order.refresh_from_db()
        result = self.approved_result(order.transbank_buy_order, order.transbank_session_id, amount='45000')
        self.callback(order.transbank_token, result)
        order.refresh_from_db()
        self.assertEqual(order.status, 'PAYMENT_REVIEW')
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Pago tardío Transbank').exists())
