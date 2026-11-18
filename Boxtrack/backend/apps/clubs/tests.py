from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club, Plan


class ClubVerificationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(username='superadmin', email='super@boxtrack.test', password='Password123!')
        self.club = Club.objects.create(name='Club pendiente', legal_rut='11.111.111-1', verification_status='PENDING')
        self.club_admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.club_admin = User.objects.create_user(
            username='clubadmin', email='clubadmin@boxtrack.test', password='Password123!',
            role=self.club_admin_role, club=self.club,
        )

    def test_superuser_can_approve_pending_club(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.patch(reverse('club-review', kwargs={'pk': self.club.pk}), {'verification_status': 'APPROVED', 'verification_note': 'Documentación validada.'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.assertEqual(self.club.verification_status, 'APPROVED')
        self.assertIsNotNone(self.club.verified_at)
        self.assertEqual(self.club.verified_by, self.superuser)

    def test_club_admin_cannot_review_other_clubs(self):
        self.client.force_authenticate(user=self.club_admin)
        response = self.client.patch(reverse('club-review', kwargs={'pk': self.club.pk}), {'verification_status': 'APPROVED'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.club.refresh_from_db()
        self.assertEqual(self.club.verification_status, 'PENDING')


class PublicClubAndPlanTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.public_club = Club.objects.create(
            name='Club público',
            legal_rut='22.222.222-2',
            legal_representative_name='Representante privado',
            legal_representative_rut='11.111.111-1',
            description='Boxeo para todos los niveles.',
            address='Av. Ejemplo 123, Santiago',
            phone='+56912345678',
            email='contacto@club.test',
            website='https://club.test',
            is_public=True,
        )
        self.hidden_club = Club.objects.create(name='Club privado', is_public=False)
        self.admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.admin = User.objects.create_user(
            username='public-club-admin',
            password='Password123!',
            club=self.public_club,
            role=self.admin_role,
        )
        self.other_admin = User.objects.create_user(
            username='hidden-club-admin',
            password='Password123!',
            club=self.hidden_club,
            role=self.admin_role,
        )
        self.active_plan = Plan.objects.create(
            club=self.public_club,
            name='Plan mensual',
            description='Clases ilimitadas.',
            price='35000',
            duration='Mensual',
        )
        self.inactive_plan = Plan.objects.create(
            club=self.public_club,
            name='Plan antiguo',
            price='25000',
            duration='Mensual',
            is_active=False,
        )
        self.other_plan = Plan.objects.create(
            club=self.hidden_club,
            name='Plan privado',
            price='30000',
            duration='Mensual',
        )

    def test_anonymous_visitor_can_read_only_public_clubs_and_safe_fields(self):
        list_response = self.client.get(reverse('public-club-list'))
        detail_response = self.client.get(reverse('public-club-detail', kwargs={'pk': self.public_club.pk}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        listed_clubs = list_response.data.get('results', list_response.data)
        self.assertEqual([club['id'] for club in listed_clubs], [self.public_club.pk])
        self.assertEqual(set(listed_clubs[0]), {'id', 'name', 'logo', 'address'})
        self.assertEqual(
            set(detail_response.data),
            {'id', 'name', 'logo', 'description', 'address', 'phone', 'email', 'website', 'plans'},
        )
        self.assertNotIn('legal_rut', detail_response.data)
        self.assertNotIn('legal_representative_name', detail_response.data)
        self.assertNotIn('legal_representative_rut', detail_response.data)
        self.assertEqual([plan['id'] for plan in detail_response.data['plans']], [self.active_plan.pk])
        self.assertEqual(
            set(detail_response.data['plans'][0]),
            {'id', 'name', 'description', 'price', 'duration'},
        )

    def test_anonymous_visitor_cannot_create_or_edit_public_club_data(self):
        create_response = self.client.post(reverse('public-club-list'), {'name': 'Club no autorizado'}, format='json')
        edit_response = self.client.patch(
            reverse('public-club-detail', kwargs={'pk': self.public_club.pk}),
            {'name': 'Nombre cambiado'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(edit_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.public_club.refresh_from_db()
        self.assertEqual(self.public_club.name, 'Club público')

    def test_private_clubs_are_not_accessible_through_public_detail(self):
        response = self.client.get(reverse('public-club-detail', kwargs={'pk': self.hidden_club.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_cannot_modify_another_clubs_plan(self):
        self.client.force_authenticate(user=self.other_admin)
        response = self.client.patch(
            reverse('club-plan-detail', kwargs={'pk': self.active_plan.pk}),
            {'price': '1'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.active_plan.refresh_from_db()
        self.assertEqual(str(self.active_plan.price), '35000')

    def test_admin_can_create_update_and_deactivate_own_plan(self):
        self.client.force_authenticate(user=self.admin)
        create_response = self.client.post(reverse('club-plans'), {
            'name': 'Promo 2x1',
            'description': 'Dos personas entrenan.',
            'price': '50000',
            'duration': '2x1 mensual',
            'sort_order': 2,
        }, format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        plan_id = create_response.data['id']
        update_response = self.client.patch(
            reverse('club-plan-detail', kwargs={'pk': plan_id}),
            {'is_active': False},
            format='json',
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertFalse(update_response.data['is_active'])

    def test_admin_can_change_publication_setting_for_own_club(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(reverse('club-publication'), {'is_public': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.public_club.refresh_from_db()
        self.assertFalse(self.public_club.is_public)
