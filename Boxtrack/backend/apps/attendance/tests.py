from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.clubs.models import Club
from apps.groups.models import Group
from apps.trainings.models import Training


class AttendanceTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Demo', email='demo@club.com')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@club.com')
        self.admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')

        self.admin_user = User.objects.create_user(
            username='admin', email='admin@demo.com', password='Password123!',
            club=self.club, role=self.admin_role
        )
        self.trainer_user = User.objects.create_user(
            username='trainer', email='trainer@demo.com', password='Password123!',
            club=self.club, role=self.trainer_role
        )
        self.group = Group.objects.create(club=self.club, name='Grupo A', schedule='Lunes 18:00')
        self.athlete = Athlete.objects.create(
            club=self.club,
            first_name='Mateo',
            last_name='Rojas',
            status='ACTIVE',
            group=self.group,
            assigned_trainer=self.trainer_user,
        )
        self.training = Training.objects.create(
            club=self.club,
            title='Trabajo técnico',
            scheduled_date='2026-10-10',
            start_time='18:00:00',
            duration_minutes=90,
            trainer=self.trainer_user,
            group=self.group,
        )

    def test_register_attendance_for_same_club(self):
        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'athlete': self.athlete.id,
            'training': self.training.id,
            'status': 'PRESENT',
            'notes': 'Asistió puntual'
        }

        response = self.client.post(reverse('attendance-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.filter(training=self.training).count(), 1)

    def test_block_attendance_from_other_club(self):
        other_athlete = Athlete.objects.create(
            club=self.other_club,
            first_name='Pedro',
            last_name='Lopez',
            status='ACTIVE',
        )
        other_training = Training.objects.create(
            club=self.other_club,
            title='Entrenamiento ajeno',
            scheduled_date='2026-10-12',
            start_time='19:00:00',
            duration_minutes=60,
            trainer=self.trainer_user,
        )

        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'athlete': other_athlete.id,
            'training': other_training.id,
            'status': 'ABSENT'
        }

        response = self.client.post(reverse('attendance-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
