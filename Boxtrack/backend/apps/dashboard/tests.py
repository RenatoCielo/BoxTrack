from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.clubs.models import Club
from apps.groups.models import Group
from apps.trainings.models import Training


class DashboardSummaryTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Dashboard', email='dashboard@test.com', verification_status='APPROVED')
        self.role_admin = Role.objects.create(name='ADMIN', description='Administrador')
        self.admin = User.objects.create_user(
            username='dashboard-admin',
            email='dashboard-admin@club.com',
            password='Password123!',
            role=self.role_admin,
            club=self.club,
        )
        self.group = Group.objects.create(club=self.club, name='Grupo principal', is_active=True)
        self.athlete = Athlete.objects.create(
            club=self.club,
            first_name='Ana',
            last_name='García',
            status='ACTIVE',
            group=self.group,
        )
        self.training_scheduled = Training.objects.create(
            club=self.club,
            title='Clase técnica',
            scheduled_date='2026-10-02',
            start_time='18:00:00',
            status='SCHEDULED',
            trainer=self.admin,
            group=self.group,
        )
        self.training_completed = Training.objects.create(
            club=self.club,
            title='Clase finalizada',
            scheduled_date='2026-10-01',
            start_time='17:00:00',
            status='COMPLETED',
            trainer=self.admin,
            group=self.group,
        )
        Attendance.objects.create(
            club=self.club,
            athlete=self.athlete,
            training=self.training_scheduled,
            status='PRESENT',
        )
        self.client.force_authenticate(user=self.admin)

    def test_dashboard_summary_returns_key_metrics(self):
        response = self.client.get(reverse('dashboard-summary'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['athletes_active'], 1)
        self.assertEqual(response.data['trainings_scheduled'], 1)
        self.assertEqual(response.data['attendance_records'], 1)
        self.assertEqual(response.data['groups_active'], 1)
