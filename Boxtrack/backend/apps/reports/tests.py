import csv
import io

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
        self.role_athlete = Role.objects.create(name='ATHLETE', description='Deportista')
        self.athlete_user = User.objects.create_user(
            username='report-athlete',
            email='report-athlete@club.com',
            password='Password123!',
            role=self.role_athlete,
            club=self.club,
        )
        Athlete.objects.create(club=self.club, first_name='Pedro', last_name='Melo', status='ACTIVE')
        self.client.force_authenticate(user=self.admin)

    def test_report_export_returns_csv(self):
        response = self.client.get(reverse('report-export', kwargs={'model_name': 'athletes'}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/csv')
        content = response.content.decode('utf-8-sig')
        self.assertTrue(content.startswith('id,'))
        self.assertIn('first_name', content)
        self.assertIn('Pedro', content)

    def test_athlete_cannot_export_club_reports(self):
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.get(reverse('report-export', kwargs={'model_name': 'athletes'}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_csv_escapes_spreadsheet_formulas(self):
        Athlete.objects.create(
            club=self.club,
            first_name='=HYPERLINK("https://example.invalid")',
            last_name='Formula',
            status='ACTIVE',
        )

        response = self.client.get(reverse('report-export', kwargs={'model_name': 'athletes'}))
        rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))

        formula_row = next(row for row in rows if row['last_name'] == 'Formula')
        self.assertTrue(formula_row['first_name'].startswith("'="))
