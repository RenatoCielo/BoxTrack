from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club


class FightRecordTests(APITestCase):
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
        self.athlete = Athlete.objects.create(
            club=self.club,
            first_name='Mateo',
            last_name='Silva',
            status='ACTIVE',
            assigned_trainer=self.trainer_user,
        )
        self.other_athlete = Athlete.objects.create(
            club=self.other_club,
            first_name='Pedro',
            last_name='Mora',
            status='ACTIVE',
        )

    def test_trainer_can_create_fight_record(self):
        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'athlete': self.athlete.id,
            'opponent_name': 'Rafael Torres',
            'fight_date': '2025-03-10',
            'event': 'Torneo Regional',
            'category': '64 kg',
            'result': 'WIN',
            'fight_type': 'AMATEUR',
            'notes': 'Buen manejo de distancia.',
        }

        response = self.client.post(reverse('fight-record-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['opponent_name'], 'Rafael Torres')

    def test_other_club_cannot_access_fight_record(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('fight-record-list-create') + f'?athlete={self.other_athlete.id}')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
