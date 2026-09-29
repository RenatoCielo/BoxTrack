from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club


class EvaluationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Evaluación', email='eval@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-eval@test.com')
        role = Role.objects.create(name='ADMIN', description='Administrador')
        self.user = User.objects.create_user(username='admin-eval', password='Password123!', club=self.club, role=role)
        self.athlete = Athlete.objects.create(club=self.club, first_name='Ana', last_name='Rojas')
        self.other_athlete = Athlete.objects.create(club=self.other_club, first_name='Eva', last_name='Paz')
        self.client.force_authenticate(user=self.user)

    def test_create_evaluation_for_club_athlete(self):
        response = self.client.post(reverse('evaluation-list-create'), {
            'athlete': self.athlete.pk,
            'evaluation_date': '2026-09-28',
            'technical': 8,
            'defense': 7,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['club'], self.club.pk)

    def test_reject_cross_club_athlete(self):
        response = self.client.post(reverse('evaluation-list-create'), {
            'athlete': self.other_athlete.pk,
            'evaluation_date': '2026-09-28',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_score_above_ten(self):
        response = self.client.post(reverse('evaluation-list-create'), {
            'athlete': self.athlete.pk,
            'evaluation_date': '2026-09-28',
            'technical': 11,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)