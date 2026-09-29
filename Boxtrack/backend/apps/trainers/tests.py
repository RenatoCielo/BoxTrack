from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club
from apps.trainers.models import TrainerProfile


class TrainerManagementTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Test', email='club@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@test.com')
        self.admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.admin_user = User.objects.create_user(
            username='admin', email='admin@test.com', password='Password123!',
            club=self.club, role=self.admin_role
        )

    def test_create_trainer_profile_for_current_club(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'user': User.objects.create_user(
                username='trainer1', email='trainer1@test.com', password='Password123!'
            ).id,
            'specialty': 'Preparación física',
            'experience_years': 5,
            'professional_title': 'Profesor de Educación Física',
            'bio': 'Especialista en boxeo amateur'
        }

        response = self.client.post(reverse('trainer-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrainerProfile.objects.filter(club=self.club).count(), 1)

    def test_block_trainer_from_other_club(self):
        other_user = User.objects.create_user(
            username='trainer2', email='trainer2@test.com', password='Password123!',
            club=self.other_club
        )
        trainer = TrainerProfile.objects.create(
            club=self.other_club,
            user=other_user,
            specialty='Boxeo',
            experience_years=3
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('trainer-detail', kwargs={'pk': trainer.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
