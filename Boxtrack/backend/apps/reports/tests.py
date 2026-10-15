from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club


class ReportsExportTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Reportes', email='reports@test.com', verification_status='APPROVED')
        self.role_admin = Role.objects.create(name='ADMIN', description='Administrador')
        self.admin = User.objects.create_user(
            username='report-admin',
            email='report-admin@club.com',
            password='Password123!',
            role=self.role_admin,
            club=self.club,
        )
        Athlete.objects.create(club=self.club, first_name='Pedro', last_name='Melo', status='ACTIVE')
        self.client.force_authenticate(user=self.admin)

    def test_report_export_returns_csv(self):
        response = self.client.get(reverse('report-export', kwargs={'model_name': 'athletes'}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/csv')
        content = response.content.decode('utf-8-sig')
        self.assertIn('first_name', content)
        self.assertIn('Pedro', content)
