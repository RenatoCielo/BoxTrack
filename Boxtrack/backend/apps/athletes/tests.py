from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.competitions.models import Competition
from apps.groups.models import Group


class AthleteManagementTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Deportivo', email='club@demo.com')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@demo.com')
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

    def test_create_athlete_for_same_club(self):
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'first_name': 'Carlos',
            'last_name': 'Pérez',
            'birth_date': '2010-05-11',
            'status': 'ACTIVE',
            'assigned_trainer': self.trainer_user.id,
            'group': self.group.id,
            'category': 'Peso medio',
            'guard': 'RIGHT',
            'experience': '3 años',
        }

        response = self.client.post(reverse('athlete-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Athlete.objects.filter(club=self.club).count(), 1)
        self.assertEqual(response.data['first_name'], 'Carlos')

    def test_block_athlete_from_other_club(self):
        other_group = Group.objects.create(club=self.other_club, name='Grupo B', schedule='Martes 18:00')
        athlete = Athlete.objects.create(
            club=self.other_club,
            first_name='Juan',
            last_name='González',
            group=other_group,
            status='ACTIVE'
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('athlete-detail', kwargs={'pk': athlete.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_invalid_athlete_phone(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('athlete-list-create'), {
            'first_name': 'Carlos', 'last_name': 'Pérez', 'phone': '123abc'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_trainer_can_view_but_cannot_create_athlete(self):
        self.client.force_authenticate(user=self.trainer_user)

        list_response = self.client.get(reverse('athlete-list-create'))
        create_response = self.client.post(reverse('athlete-list-create'), {
            'first_name': 'Nuevo', 'last_name': 'Deportista'
        }, format='json')

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trainer_cannot_update_athlete_profile(self):
        athlete = Athlete.objects.create(
            club=self.club,
            first_name='Ana',
            last_name='Rojas',
            status='ACTIVE',
        )
        self.client.force_authenticate(user=self.trainer_user)

        response = self.client.patch(
            reverse('athlete-detail', kwargs={'pk': athlete.pk}),
            {'last_name': 'Modificada'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleting_athlete_deactivates_profile_and_login_instead_of_removing_history(self):
        athlete_user = User.objects.create_user(
            username='boxer-delete', email='boxer-delete@test.com', password='Password123!',
            club=self.club, role=Role.objects.create(name='ATHLETE', description='Deportista')
        )
        athlete = Athlete.objects.create(
            club=self.club, user=athlete_user, first_name='Carlos', last_name='Pérez', status='ACTIVE'
        )
        self.client.force_authenticate(user=self.admin_user)

        delete_response = self.client.delete(reverse('athlete-detail', kwargs={'pk': athlete.pk}))

        athlete.refresh_from_db()
        athlete_user.refresh_from_db()
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Athlete.objects.filter(pk=athlete.pk).exists())
        self.assertEqual(athlete.status, 'INACTIVE')
        self.assertFalse(athlete_user.is_active)
        self.client.force_authenticate(user=None)
        login_response = self.client.post(reverse('login'), {'username': 'boxer-delete', 'password': 'Password123!'}, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reactivating_athlete_profile_reactivates_account(self):
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        athlete_user = User.objects.create_user(
            username='boxer-reactivate', email='boxer-reactivate@test.com', password='Password123!',
            club=self.club, role=athlete_role, is_active=False
        )
        athlete = Athlete.objects.create(
            club=self.club, user=athlete_user, first_name='Eva', last_name='Paz', status='INACTIVE'
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            reverse('athlete-detail', kwargs={'pk': athlete.pk}),
            {'status': 'ACTIVE'},
            format='json',
        )

        athlete_user.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(athlete_user.is_active)

    def test_admin_can_relink_existing_athlete_account_without_profile(self):
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        orphan_user = User.objects.create_user(
            username='orphan-boxer', email='orphan@test.com', password='Password123!',
            first_name='Marco', last_name='Díaz', phone='+56912345678', club=self.club, role=athlete_role
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(reverse('athlete-list-create'), {
            'user': orphan_user.pk,
            'first_name': orphan_user.first_name,
            'last_name': orphan_user.last_name,
            'phone': orphan_user.phone,
            'status': 'ACTIVE',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Athlete.objects.get(user=orphan_user).pk, response.data['id'])

    def test_competitor_filter_and_fight_record(self):
        competitor = Athlete.objects.create(
            club=self.club,
            first_name='Camila',
            last_name='Vera',
            status='ACTIVE',
            is_competitor=True,
        )
        regular_athlete = Athlete.objects.create(
            club=self.club,
            first_name='Diego',
            last_name='Soto',
            status='ACTIVE',
        )
        Competition.objects.create(club=self.club, athlete=competitor, result='WIN', fight_type='AMATEUR')
        Competition.objects.create(club=self.club, athlete=competitor, result='LOSS', fight_type='PRO')
        Competition.objects.create(club=self.club, athlete=competitor, result='WIN', fight_type='SPARRING')
        self.client.force_authenticate(user=self.trainer_user)

        competitor_response = self.client.get(reverse('athlete-list-create'), {'is_competitor': 'true'})
        regular_response = self.client.get(reverse('athlete-list-create'), {'is_competitor': 'false'})

        self.assertEqual([item['id'] for item in competitor_response.data['results']], [competitor.pk])
        self.assertEqual(competitor_response.data['results'][0]['fight_record'], '1-1-0')
        self.assertEqual([item['id'] for item in regular_response.data['results']], [regular_athlete.pk])
        self.assertEqual(regular_response.data['results'][0]['fight_record'], '0-0-0')
