from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.trainers.models import TrainerProfile


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Test', email='club@test.com')
        self.role_admin = Role.objects.create(name='ADMIN', description='Administrador')
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@test.com',
            password='Password123!',
            role=self.role_admin,
            club=self.club,
        )

    def test_register_new_club_and_admin(self):
        payload = {
            'club_name': 'Nuevo Club',
            'club_email': 'nuevo@club.com',
            'username': 'nuevoadmin',
            'email': 'nuevoadmin@club.com',
            'password': 'Password123!',
            'first_name': 'Renato',
            'last_name': 'Cielo',
        }

        response = self.client.post(reverse('register'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Club.objects.filter(name='Nuevo Club').exists())
        self.assertTrue(User.objects.filter(username='nuevoadmin').exists())

    def test_user_can_fetch_own_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('me'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'adminuser')
        self.assertEqual(response.data['club']['name'], 'Club Test')

    def test_user_cannot_access_other_club_data(self):
        other_club = Club.objects.create(name='Otro Club', email='otro@test.com')
        another_admin = User.objects.create_user(
            username='otheradmin',
            email='other@test.com',
            password='Password123!',
            role=self.role_admin,
            club=other_club,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('club-detail', kwargs={'pk': other_club.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'No tienes permisos para acceder a este club.')

        self.client.force_authenticate(user=another_admin)
        response = self.client.get(reverse('club-detail', kwargs={'pk': self.club.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_athlete_account_and_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'first_name': 'Ana', 'last_name': 'Rojas', 'role': 'ATHLETE', 'category': '60 kg',
            'phone': '+56 9 1234 5678'
        }

        response = self.client.post(reverse('club-members'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = Athlete.objects.get(pk=response.data['profile_id']).user
        self.assertEqual(user.username, 'ana.rojas')
        self.assertEqual(user.email, 'ana.rojas@club-test.com')
        self.assertEqual(user.phone, '+56912345678')
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(response.data['temporary_password']))

    def test_duplicate_member_names_receive_unique_credentials(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {'first_name': 'Ana', 'last_name': 'Rojas', 'role': 'ATHLETE'}

        first_response = self.client.post(reverse('club-members'), payload, format='json')
        second_response = self.client.post(reverse('club-members'), payload, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(first_response.data['user']['username'], second_response.data['user']['username'])
        self.assertNotEqual(first_response.data['user']['email'], second_response.data['user']['email'])

    def test_reject_invalid_phone_and_malformed_name(self):
        self.client.force_authenticate(user=self.admin_user)
        invalid_phone = self.client.post(reverse('club-members'), {
            'first_name': 'Ana', 'last_name': 'Rojas', 'role': 'ATHLETE', 'phone': 'telefono'
        }, format='json')
        invalid_name = self.client.post(reverse('club-members'), {
            'first_name': 'Ana99', 'last_name': 'Rojas', 'role': 'ATHLETE'
        }, format='json')

        self.assertEqual(invalid_phone.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_name.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_create_trainer_account_and_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'username': 'newtrainer', 'email': 'newtrainer@test.com', 'password': 'StrongerPass123!',
            'first_name': 'Luis', 'last_name': 'Vera', 'role': 'TRAINER', 'specialty': 'Técnica'
        }

        response = self.client.post(reverse('club-members'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrainerProfile.objects.get(pk=response.data['profile_id']).user.username, 'luis.vera')

    def test_trainer_cannot_create_club_accounts(self):
        trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        trainer = User.objects.create_user(
            username='trainer', email='trainer@test.com', password='Password123!',
            role=trainer_role, club=self.club,
        )
        self.client.force_authenticate(user=trainer)

        response = self.client.get(reverse('club-members'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_temporary_account_must_change_password(self):
        self.client.force_authenticate(user=self.admin_user)
        create_response = self.client.post(reverse('club-members'), {
            'first_name': 'Luis', 'last_name': 'Vera', 'role': 'TRAINER'
        }, format='json')
        member = User.objects.get(username=create_response.data['user']['username'])
        self.client.force_authenticate(user=member)

        response = self.client.post(reverse('change-password'), {
            'current_password': create_response.data['temporary_password'],
            'new_password': 'NuevaClaveSegura2026!',
        }, format='json')

        member.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(member.must_change_password)
        self.assertTrue(member.check_password('NuevaClaveSegura2026!'))
