from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.weight_tracking.models import WeightRecord


class WeightRecordTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Peso', email='weight@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-weight@test.com')
        role = Role.objects.create(name='ADMIN', description='Administrador')
        trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        self.admin = User.objects.create_user(username='admin-weight', password='Password123!', club=self.club, role=role)
        self.trainer = User.objects.create_user(username='trainer-weight', password='Password123!', club=self.club, role=trainer_role)
        self.athlete = Athlete.objects.create(club=self.club, first_name='Ana', last_name='Rojas', assigned_trainer=self.trainer)
        self.unassigned_athlete = Athlete.objects.create(club=self.club, first_name='Paz', last_name='Vera')
        self.other_athlete = Athlete.objects.create(club=self.other_club, first_name='Eva', last_name='Paz')
        self.client.force_authenticate(user=self.admin)

    def test_create_weight_record_for_club_athlete(self):
        response = self.client.post(reverse('weight-list-create'), {
            'athlete': self.athlete.pk,
            'weight': '59.80',
            'recorded_date': '2026-09-28',
            'notes': 'Control semanal',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['club'], self.club.pk)

    def test_reject_weight_record_for_other_club(self):
        response = self.client.post(reverse('weight-list-create'), {
            'athlete': self.other_athlete.pk,
            'weight': '59.80',
            'recorded_date': '2026-09-28',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trainer_only_sees_and_records_weight_for_assigned_athletes(self):
        self.client.force_authenticate(user=self.admin)
        WeightRecord.objects.create(
            club=self.club, athlete=self.athlete, weight='60.00', recorded_date='2026-09-28'
        )
        WeightRecord.objects.create(
            club=self.club, athlete=self.unassigned_athlete, weight='72.00', recorded_date='2026-09-28'
        )
        self.client.force_authenticate(user=self.trainer)

        list_response = self.client.get(reverse('weight-list-create'))
        create_response = self.client.post(reverse('weight-list-create'), {
            'athlete': self.unassigned_athlete.pk,
            'weight': '72.50',
            'recorded_date': '2026-09-29',
        }, format='json')

        self.assertEqual([row['athlete'] for row in list_response.data['results']], [self.athlete.pk])
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)