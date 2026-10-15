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
        self.club = Club.objects.create(name='Club Test', email='club@test.com', verification_status='APPROVED')
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
            'club_rut': '11.111.111-1',
            'legal_representative_name': 'Renato Cielo',
            'legal_representative_rut': '11.111.111-1',
            'club_email': 'nuevo@club.com',
            'disciplines': ['Boxeo', 'Crossfit'],
            'username': 'nuevoadmin',
            'email': 'nuevoadmin@club.com',
            'password': 'Password123!',
            'first_name': 'Renato',
            'last_name': 'Cielo',
        }

        response = self.client.post(reverse('register'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Club.objects.filter(name='Nuevo Club', legal_rut='111111111').exists())
        self.assertEqual(Club.objects.get(name='Nuevo Club').verification_status, 'PENDING')
        self.assertTrue(User.objects.filter(username='nuevoadmin').exists())

    def test_register_rejects_invalid_company_rut(self):
        payload = {
            'club_name': 'Club Inválido',
            'club_rut': '12.345.678-0',
            'legal_representative_name': 'Persona Responsable',
            'legal_representative_rut': '11.111.111-1',
            'username': 'invalidclubadmin',
            'email': 'invalidclubadmin@club.com',
            'password': 'Password123!'
        }

        response = self.client.post(reverse('register'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('club_rut', response.data)

    def test_user_can_fetch_own_profile(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('me'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'adminuser')
        self.assertEqual(response.data['club']['name'], 'Club Test')

    def test_existing_active_user_can_still_login(self):
        response = self.client.post(reverse('login'), {
            'username': 'adminuser',
            'password': 'Password123!',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['tokens'])
        self.assertEqual(response.data['user']['club']['name'], 'Club Test')

    def test_existing_user_can_login_with_case_insensitive_username(self):
        response = self.client.post(reverse('login'), {
            'username': 'ADMINUSER',
            'password': 'Password123!',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'adminuser')

    def test_existing_user_can_login_with_email(self):
        response = self.client.post(reverse('login'), {
            'username': 'admin@test.com',
            'password': 'Password123!',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'adminuser')

    def test_ambiguous_legacy_email_does_not_authenticate_wrong_account(self):
        User.objects.create_user(
            username='another-admin',
            email=self.admin_user.email,
            password='AnotherPassword123!',
            role=self.role_admin,
            club=self.club,
        )

        response = self.client.post(reverse('login'), {
            'username': self.admin_user.email,
            'password': 'Password123!',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_cannot_login_until_admin_reactivates_profile(self):
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        inactive_user = User.objects.create_user(
            username='inactive-boxer',
            email='inactive@test.com',
            password='Password123!',
            role=athlete_role,
            club=self.club,
            is_active=False,
        )
        self.client.force_authenticate(user=self.admin_user)
        athlete = Athlete.objects.create(
            club=self.club,
            user=inactive_user,
            first_name='Boxeador',
            last_name='Inactivo',
            status='INACTIVE',
        )
        self.client.force_authenticate(user=None)

        denied_response = self.client.post(reverse('login'), {
            'username': 'inactive-boxer', 'password': 'Password123!'
        }, format='json')
        self.assertEqual(denied_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(user=self.admin_user)
        active_response = self.client.patch(
            reverse('athlete-detail', kwargs={'pk': athlete.pk}),
            {'status': 'ACTIVE'},
            format='json',
        )
        self.assertEqual(active_response.status_code, status.HTTP_200_OK)

        inactive_user.refresh_from_db()
        self.assertTrue(inactive_user.is_active)
        self.client.force_authenticate(user=None)
        login_response = self.client.post(reverse('login'), {
            'username': 'inactive-boxer', 'password': 'Password123!'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

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
