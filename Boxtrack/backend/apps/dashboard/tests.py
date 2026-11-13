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
        self.role_athlete = Role.objects.create(name='ATHLETE', description='Deportista')
        self.athlete_user = User.objects.create_user(
            username='dashboard-athlete',
            email='dashboard-athlete@club.com',
            password='Password123!',
            role=self.role_athlete,
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

    def test_athlete_cannot_view_staff_dashboard(self):
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.get(reverse('dashboard-summary'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GlobalDashboardTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='global', password='Password123!')
        self.admin_role = Role.objects.create(name='ADMIN')
        self.club = Club.objects.create(name='Norte', verification_status='APPROVED')
        self.other_club = Club.objects.create(name='Sur', verification_status='PENDING', is_active=False)
        self.admin = User.objects.create_user(
            username='norte-admin', password='Password123!', club=self.club, role=self.admin_role,
            email='private@example.com', phone='123456',
        )
        self.inactive = User.objects.create_user(
            username='sur-user', password='Password123!', club=self.other_club, is_active=False,
        )

    def test_global_endpoints_require_superuser(self):
        for user in [None, self.admin]:
            if user:
                self.client.force_authenticate(user=user)
            for name in ['global-dashboard-summary', 'global-dashboard-clubs', 'global-dashboard-users']:
                with self.subTest(user=user, endpoint=name):
                    self.assertIn(self.client.get(reverse(name)).status_code, [401, 403])
        self.admin.is_staff = True
        self.admin.save()
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(reverse('global-dashboard-users')).status_code, 403)

    def test_summary_counts_all_clubs_and_users_by_status_and_role(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(reverse('global-dashboard-summary'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['clubs'], {'total': 2, 'active': 1})
        self.assertEqual(response.data['users'], {'total': 3, 'active': 2})
        self.assertEqual(
            {item['verification_status']: item['count'] for item in response.data['clubs_by_status']},
            {'APPROVED': 1, 'PENDING': 1},
        )
        self.assertEqual(
            {item['group']: item['count'] for item in response.data['users_by_role']},
            {'SUPERUSER': 1, 'ADMIN': 1, 'OTHER': 1},
        )

    def test_lists_are_paginated_searchable_and_exclude_sensitive_fields(self):
        for number in range(21):
            Club.objects.create(name=f'Extra {number:02}')
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(reverse('global-dashboard-clubs'))
        self.assertEqual(response.data['count'], 23)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        response = self.client.get(reverse('global-dashboard-clubs'), {'search': 'Norte'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['user_count'], 1)
        self.assertNotIn('legal_rut', response.data['results'][0])
        response = self.client.get(reverse('global-dashboard-users'), {'search': 'Norte'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['username'], 'norte-admin')
        self.assertEqual(response.data['results'][0]['club_name'], 'Norte')
        self.assertNotIn('email', response.data['results'][0])
        self.assertNotIn('phone', response.data['results'][0])
        for number in range(21):
            User.objects.create_user(username=f'extra-{number:02}', password='Password123!')
        response = self.client.get(reverse('global-dashboard-users'))
        self.assertEqual(response.data['count'], 24)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        response = self.client.get(reverse('global-dashboard-users'), {'page': 2})
        self.assertEqual(len(response.data['results']), 4)
        self.assertIsNotNone(response.data['previous'])
        for name in ['global-dashboard-clubs', 'global-dashboard-users']:
            self.assertEqual(self.client.post(reverse(name), {}, format='json').status_code, 405)
