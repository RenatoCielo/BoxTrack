from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club


class ClubVerificationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(username='superadmin', email='super@boxtrack.test', password='Password123!')
        self.club = Club.objects.create(name='Club pendiente', legal_rut='11.111.111-1', verification_status='PENDING')
        self.club_admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.club_admin = User.objects.create_user(
            username='clubadmin', email='clubadmin@boxtrack.test', password='Password123!',
            role=self.club_admin_role, club=self.club,
        )

    def test_superuser_can_approve_pending_club(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.patch(reverse('club-review', kwargs={'pk': self.club.pk}), {'verification_status': 'APPROVED', 'verification_note': 'Documentación validada.'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertEqual(self.club.verification_status, 'APPROVED')
        self.assertIsNotNone(self.club.verified_at)
        self.assertEqual(self.club.verified_by, self.superuser)

    def test_club_admin_cannot_review_other_clubs(self):
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.patch(reverse('club-review', kwargs={'pk': self.club.pk}), {'verification_status': 'APPROVED'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.club.refresh_from_db()
        self.assertEqual(self.club.verification_status, 'PENDING')
