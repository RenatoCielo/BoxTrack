from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club


class WeightRecordTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Peso', email='weight@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-weight@test.com')
        role = Role.objects.create(name='ADMIN', description='Administrador')
        user = User.objects.create_user(username='admin-weight', password='Password123!', club=self.club, role=role)
        self.athlete = Athlete.objects.create(club=self.club, first_name='Ana', last_name='Rojas')
        self.other_athlete = Athlete.objects.create(club=self.other_club, first_name='Eva', last_name='Paz')
        self.client.force_authenticate(user=user)

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