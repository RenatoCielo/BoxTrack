from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest import mock

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.memberships.models import Membership, MembershipTransferProof
from apps.memberships.tests import MembershipBase
from apps.notifications.models import Notification
from apps.store.models import StoreSettings


class MembershipTransferTests(MembershipBase):
    def setUp(self):
        super().setUp()
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = mock.patch.object(MembershipTransferProof._meta.get_field('payment_proof'), 'storage', FileSystemStorage(location=directory.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        StoreSettings.objects.create(club=self.club, bank_transfer_instructions='Banco de prueba, cuenta 123')

    def start_transfer(self):
        self.client.force_authenticate(user=self.athlete_user)
        return self.client.post(reverse('membership-list-create'), {'plan': self.plan.pk, 'payment_method': 'BANK_TRANSFER', 'price_paid': 1}, format='json')

    def upload(self, membership, content=b'%PDF-1.7 prueba'):
        return self.client.post(reverse('membership-proof', args=[membership]), {'proof': SimpleUploadedFile('proof.pdf', content, content_type='application/pdf')}, format='multipart')

    def test_requires_club_instructions_and_does_not_trust_price(self):
        StoreSettings.objects.filter(club=self.club).update(bank_transfer_instructions='  ')
        self.assertEqual(self.start_transfer().status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Membership.objects.exists())
        StoreSettings.objects.filter(club=self.club).update(bank_transfer_instructions='Banco de prueba')
        result = self.start_transfer()
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        self.assertEqual((result.data['payment_method'], str(result.data['price_paid']), result.data['status']), ('BANK_TRANSFER', '30000.00', 'PENDING'))
        self.assertEqual(self.start_transfer().status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.client.get(reverse('membership-settings')).data['bank_transfer_instructions'], 'Banco de prueba')

    def test_review_reject_retry_and_approval_preserve_history(self):
        membership_id = self.start_transfer().data['id']
        self.assertEqual(self.upload(membership_id, b'invalido').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.upload(membership_id).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.upload(membership_id).status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.post(reverse('membership-review', args=[membership_id]), {'decision': 'CONFIRM'}, format='json').status_code, status.HTTP_409_CONFLICT)
        review = reverse('membership-proof-review', args=[membership_id])
        self.assertEqual(self.client.post(review, {'decision': 'REJECT', 'note': 'No legible'}, format='json').status_code, status.HTTP_200_OK)
        self.assertEqual(Membership.objects.get(pk=membership_id).status, 'PENDING')
        self.client.force_authenticate(user=self.athlete_user)
        self.assertEqual(self.upload(membership_id).status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(review, {'decision': 'APPROVE'}, format='json')
        self.assertEqual((response.status_code, response.data['status']), (status.HTTP_200_OK, 'ACTIVE'))
        self.assertEqual(list(MembershipTransferProof.objects.values_list('proof_status', flat=True)), ['APPROVED', 'REJECTED'])
        self.assertEqual(self.client.post(review, {'decision': 'APPROVE'}, format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Comprobante rechazado').exists())
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Membresía activada').exists())

    def test_proof_is_private_and_scoped_to_own_club(self):
        membership_id = self.start_transfer().data['id']
        self.upload(membership_id)
        file_url = reverse('membership-proof-file', args=[membership_id])
        review_url = reverse('membership-proof-review', args=[membership_id])
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(review_url, {'decision': 'APPROVE'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.other_admin)
        self.assertEqual(self.client.get(file_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(review_url, {'decision': 'APPROVE'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(file_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response.close()

    def test_renewal_activates_only_on_proof_approval(self):
        current = self.activate(days_left=3)
        self.client.force_authenticate(user=self.athlete_user)
        result = self.client.post(reverse('membership-renewal'), {'method': 'MANUAL', 'payment_method': 'BANK_TRANSFER', 'plan': self.plan.pk}, format='json')
        self.assertEqual(result.status_code, status.HTTP_201_CREATED)
        membership_id = result.data['membership']['id']
        self.assertEqual(self.upload(membership_id).status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=self.admin)
        approved = self.client.post(reverse('membership-proof-review', args=[membership_id]), {'decision': 'APPROVE'}, format='json')
        self.assertEqual(approved.data['status'], 'SCHEDULED')
        self.assertEqual(approved.data['start_date'], str(current.end_date + timedelta(days=1)))
