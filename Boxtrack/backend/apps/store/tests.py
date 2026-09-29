from decimal import Decimal
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club
from apps.notifications.models import Notification
from apps.store.models import Order, Product, StoreSettings


class StoreTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Tienda', email='store@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-store@test.com')
        admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        self.admin = User.objects.create_user(username='store-admin', password='Password123!', club=self.club, role=admin_role)
        self.athlete = User.objects.create_user(username='store-athlete', password='Password123!', club=self.club, role=athlete_role)
        self.other_athlete = User.objects.create_user(username='other-store-athlete', password='Password123!', club=self.other_club, role=athlete_role)
        StoreSettings.objects.create(club=self.club, bank_transfer_instructions='Banco Demo, cuenta corriente 123456, RUT 12.345.678-9')
        self.product = Product.objects.create(
            club=self.club, name='Guantes 14 oz', category='GLOVES', price=Decimal('45000'), stock=4
        )
        self.other_product = Product.objects.create(
            club=self.other_club, name='Vendas', category='WRAPS', price=Decimal('5000'), stock=4
        )

    def tearDown(self):
        for order in Order.objects.exclude(payment_proof=''):
            if order.payment_proof:
                order.payment_proof.delete(save=False)

    def test_admin_can_manage_stock_but_athlete_is_read_only(self):
        self.client.force_authenticate(user=self.athlete)
        list_response = self.client.get(reverse('store-products'))
        write_response = self.client.post(reverse('store-products'), {
            'name': 'Guantes nuevos', 'price': '10000', 'stock': 2,
        }, format='json')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(write_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_non_positive_product_price(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('store-products'), {
            'name': 'Guantes defectuosos', 'category': 'GLOVES', 'price': '-10', 'stock': 2,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_reserves_stock_and_persists_snapshot(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'RESERVE',
            'items': [{'product': self.product.pk, 'quantity': 2}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total'], '90000.00')
        self.assertEqual(response.data['items'][0]['product_name'], 'Guantes 14 oz')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_reject_order_for_other_club_product(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'RESERVE',
            'items': [{'product': self.other_product.pk, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.exists())

    def test_reject_order_exceeding_stock(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'RESERVE',
            'items': [{'product': self.product.pk, 'quantity': 5}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_cancel_pending_order_releases_stock(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'BANK_TRANSFER',
            'items': [{'product': self.product.pk, 'quantity': 2}],
        }, format='json')
        order_id = response.data['id']

        cancel_response = self.client.patch(reverse('store-order-detail', kwargs={'pk': order_id}), {'status': 'CANCELLED'}, format='json')

        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_user_cannot_view_other_users_order(self):
        order = Order.objects.create(club=self.other_club, user=self.other_athlete, payment_method='RESERVE')
        self.client.force_authenticate(user=self.athlete)

        response = self.client.get(reverse('store-order-detail', kwargs={'pk': order.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_online_checkout_requires_real_provider_configuration(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'MERCADO_PAGO',
            'items': [{'product': self.product.pk, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(Order.objects.exists())

    def test_transfer_order_requires_club_bank_instructions(self):
        StoreSettings.objects.filter(club=self.club).update(bank_transfer_instructions='')
        self.client.force_authenticate(user=self.athlete)

        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'BANK_TRANSFER',
            'items': [{'product': self.product.pk, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.exists())

    def test_only_admin_can_update_transfer_instructions(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.patch(reverse('store-checkout-config'), {
            'bank_transfer_instructions': 'Cuenta ajena'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_configure_transfer_instructions(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(reverse('store-checkout-config'), {
            'bank_transfer_instructions': 'Banco BOX, cuenta corriente 1234'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bank_transfer_instructions'], 'Banco BOX, cuenta corriente 1234')

    def test_transfer_order_is_available_after_admin_configuration(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'BANK_TRANSFER',
            'items': [{'product': self.product.pk, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_method'], 'BANK_TRANSFER')

    def create_transfer_order(self):
        self.client.force_authenticate(user=self.athlete)
        response = self.client.post(reverse('store-orders'), {
            'payment_method': 'BANK_TRANSFER',
            'items': [{'product': self.product.pk, 'quantity': 1}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.data['id']

    def upload_sample_proof(self, order_id):
        return self.client.post(
            reverse('store-order-proof-upload', kwargs={'pk': order_id}),
            {'proof': SimpleUploadedFile('transfer.pdf', b'%PDF-1.7 sample receipt', content_type='application/pdf')},
            format='multipart',
        )

    def test_upload_proof_notifies_student_and_admin_and_admin_can_approve(self):
        order_id = self.create_transfer_order()
        upload_response = self.upload_sample_proof(order_id)

        self.assertEqual(upload_response.status_code, status.HTTP_200_OK)
        self.assertEqual(upload_response.data['proof_status'], 'SUBMITTED')
        self.assertTrue(upload_response.data['has_payment_proof'])
        self.assertTrue(Notification.objects.filter(user=self.athlete, title='Comprobante en revisión').exists())
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Comprobante pendiente de revisión').exists())

        self.client.force_authenticate(user=self.admin)
        proof_response = self.client.get(reverse('store-order-proof-download', kwargs={'pk': order_id}))
        review_response = self.client.post(reverse('store-order-proof-review', kwargs={'pk': order_id}), {
            'decision': 'APPROVE',
        }, format='json')

        self.assertEqual(proof_response.status_code, status.HTTP_200_OK)
        self.assertEqual(proof_response['Content-Type'], 'application/pdf')
        proof_response.close()
        self.assertEqual(review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(review_response.data['status'], 'PAID')
        self.assertEqual(review_response.data['proof_status'], 'APPROVED')
        self.assertTrue(Notification.objects.filter(user=self.athlete, title='Pago aprobado').exists())

    def test_rejected_proof_notifies_student_and_can_be_replaced(self):
        order_id = self.create_transfer_order()
        self.assertEqual(self.upload_sample_proof(order_id).status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(reverse('store-order-proof-review', kwargs={'pk': order_id}), {
            'decision': 'REJECT', 'note': 'El monto no coincide.'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['proof_status'], 'REJECTED')
        self.assertEqual(response.data['proof_review_note'], 'El monto no coincide.')
        self.assertTrue(Notification.objects.filter(user=self.athlete, title='Comprobante rechazado').exists())

        self.client.force_authenticate(user=self.athlete)
        replacement_response = self.upload_sample_proof(order_id)
        self.assertEqual(replacement_response.status_code, status.HTTP_200_OK)
        self.assertEqual(replacement_response.data['proof_status'], 'SUBMITTED')

    def test_bank_transfer_cannot_be_marked_paid_without_approved_proof(self):
        order_id = self.create_transfer_order()
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(reverse('store-order-detail', kwargs={'pk': order_id}), {
            'status': 'PAID'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.get(pk=order_id).status, 'PENDING')

    def test_only_order_owner_can_upload_proof(self):
        order_id = self.create_transfer_order()
        self.client.force_authenticate(user=self.other_athlete)

        response = self.upload_sample_proof(order_id)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_expired_online_checkout_releases_stock(self):
        order = Order.objects.create(
            club=self.club,
            user=self.athlete,
            payment_method='MERCADO_PAGO',
            expires_at=timezone.now() - timedelta(minutes=1),
            total=Decimal('90000'),
        )
        from apps.store.models import OrderItem
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            subtotal=Decimal('90000'),
        )
        self.product.stock = 2
        self.product.save(update_fields=['stock'])
        self.client.force_authenticate(user=self.athlete)

        response = self.client.get(reverse('store-orders'))

        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(order.status, 'CANCELLED')
        self.assertEqual(self.product.stock, 4)