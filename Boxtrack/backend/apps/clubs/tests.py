from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club, Plan, PlanMembership
from apps.competitions.models import FightAgreement, FightBout
from apps.store.models import StoreSettings


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

    def test_only_superuser_can_list_pending_clubs(self):
        self.client.force_authenticate(user=self.club_admin)

        response = self.client.get(reverse('club-pending-list'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_superuser_can_update_the_public_fight_promotion(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.patch(reverse('site-showcase-settings'), {
            'headline': 'Noche de boxeo',
            'intro': 'Dos gimnasios, una velada.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['headline'], 'Noche de boxeo')

        self.client.force_authenticate(user=self.club_admin)
        denied = self.client.patch(reverse('site-showcase-settings'), {'headline': 'Otro título'}, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejecting_club_deactivates_all_users_and_blocks_login_clearly(self):
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        athlete = User.objects.create_user(
            username='club-athlete',
            password='Password123!',
            role=athlete_role,
            club=self.club,
        )
        self.club.is_public = True
        self.club.save(update_fields=['is_public'])
        self.client.force_authenticate(user=self.superuser)

        response = self.client.patch(
            reverse('club-review', kwargs={'pk': self.club.pk}),
            {'verification_status': 'REJECTED'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.club.refresh_from_db()
        self.club_admin.refresh_from_db()
        athlete.refresh_from_db()
        self.assertEqual(self.club.verification_status, 'REJECTED')
        self.assertFalse(self.club.is_public)
        self.assertFalse(self.club_admin.is_active)
        self.assertFalse(athlete.is_active)

        self.client.force_authenticate(user=None)
        login_response = self.client.post(
            reverse('login'),
            {'username': 'clubadmin', 'password': 'Password123!'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('fue rechazado', login_response.data['detail'])


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
            verification_status='APPROVED',
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
        StoreSettings.objects.create(
            club=self.public_club,
            bank_transfer_instructions='Banco Demo, cuenta corriente 1234, RUT 12.345.678-9',
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

    def membership_signup_data(self, username='new-boxer', email='new-boxer@test.com'):
        return {
            'plan': str(self.active_plan.pk),
            'username': username,
            'email': email,
            'password': 'Violet!Tiger_4729',
            'first_name': 'Ana',
            'last_name': 'Boxeadora',
            'phone': '+56912345678',
            'proof': SimpleUploadedFile(
                'transfer.pdf',
                b'%PDF-1.7 sample receipt',
                content_type='application/pdf',
            ),
        }

    def tearDown(self):
        for membership in PlanMembership.objects.exclude(payment_proof=''):
            membership.payment_proof.delete(save=False)
        super().tearDown()

    def test_anonymous_visitor_can_read_only_public_clubs_and_safe_fields(self):
        list_response = self.client.get(reverse('public-club-list'))
        detail_response = self.client.get(reverse('public-club-detail', kwargs={'pk': self.public_club.pk}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        listed_clubs = list_response.data.get('results', list_response.data)
        self.assertEqual([club['id'] for club in listed_clubs], [self.public_club.pk])
        self.assertEqual(
            set(listed_clubs[0]),
            {'id', 'name', 'logo', 'address', 'brand_primary', 'brand_accent', 'brand_surface'},
        )
        self.assertEqual(
            set(detail_response.data),
            {
                'id', 'name', 'logo', 'description', 'address', 'phone', 'email',
                'website', 'brand_primary', 'brand_accent', 'brand_surface', 'plans',
                'bank_transfer_instructions',
            },
        )
        self.assertIn('Banco Demo', detail_response.data['bank_transfer_instructions'])
        self.assertNotIn('legal_rut', detail_response.data)
        self.assertNotIn('legal_representative_name', detail_response.data)
        self.assertNotIn('legal_representative_rut', detail_response.data)
        self.assertEqual([plan['id'] for plan in detail_response.data['plans']], [self.active_plan.pk])
        self.assertEqual(
            set(detail_response.data['plans'][0]),
            {'id', 'name', 'description', 'price', 'duration', 'classes_per_week', 'is_premium'},
        )

    def test_public_visitor_can_apply_for_a_plan_with_a_transfer_proof(self):
        response = self.client.post(
            reverse('public-membership-signup', kwargs={'club_id': self.public_club.pk}),
            self.membership_signup_data(),
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')
        membership = PlanMembership.objects.get(user__username='new-boxer')
        self.assertFalse(membership.user.is_active)
        self.assertEqual(membership.athlete.status, 'INACTIVE')
        self.assertTrue(membership.payment_proof)

    def test_plan_request_requires_valid_transfer_proof_and_configured_instructions(self):
        invalid_proof = self.membership_signup_data()
        invalid_proof['proof'] = SimpleUploadedFile(
            'receipt.pdf', b'not a PDF', content_type='application/pdf',
        )
        invalid_response = self.client.post(
            reverse('public-membership-signup', kwargs={'club_id': self.public_club.pk}),
            invalid_proof,
            format='multipart',
        )

        StoreSettings.objects.filter(club=self.public_club).update(bank_transfer_instructions='')
        no_instructions_response = self.client.post(
            reverse('public-membership-signup', kwargs={'club_id': self.public_club.pk}),
            self.membership_signup_data(),
            format='multipart',
        )

        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(no_instructions_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(PlanMembership.objects.count(), 0)

    def test_club_admin_approves_membership_and_sets_contract_dates(self):
        signup = self.client.post(
            reverse('public-membership-signup', kwargs={'club_id': self.public_club.pk}),
            self.membership_signup_data(),
            format='multipart',
        )
        membership = PlanMembership.objects.get(user__username='new-boxer')
        starts_on = timezone.localdate()
        expires_on = starts_on + timedelta(days=30)
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse('membership-review', kwargs={'pk': membership.pk}),
            {
                'decision': 'APPROVE',
                'starts_on': starts_on.isoformat(),
                'expires_on': expires_on.isoformat(),
            },
            format='json',
        )

        self.assertEqual(signup.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'ACTIVE')
        self.assertTrue(membership.user.is_active)
        self.assertEqual(membership.athlete.status, 'ACTIVE')
        self.assertEqual(membership.starts_on, starts_on)
        self.assertEqual(membership.expires_on, expires_on)

        self.client.force_authenticate(user=membership.user)
        current_response = self.client.get(reverse('current-membership'))
        self.assertEqual(current_response.status_code, status.HTTP_200_OK)
        self.assertEqual(current_response.data['plan_name'], self.active_plan.name)

    def test_only_the_club_admin_can_review_and_download_membership_proofs(self):
        self.client.post(
            reverse('public-membership-signup', kwargs={'club_id': self.public_club.pk}),
            self.membership_signup_data(),
            format='multipart',
        )
        membership = PlanMembership.objects.get(user__username='new-boxer')
        self.client.force_authenticate(user=self.other_admin)

        review_response = self.client.post(
            reverse('membership-review', kwargs={'pk': membership.pk}),
            {'decision': 'REJECT', 'note': 'No corresponde.'},
            format='json',
        )
        proof_response = self.client.get(
            reverse('membership-proof', kwargs={'pk': membership.pk}),
        )

        self.assertEqual(review_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(proof_response.status_code, status.HTTP_404_NOT_FOUND)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'PENDING')

    def test_public_home_shows_recent_club_updates_and_confirmed_club_matches_only(self):
        self.hidden_club.is_public = True
        self.hidden_club.verification_status = 'APPROVED'
        self.hidden_club.save(update_fields=['is_public', 'verification_status', 'updated_at'])
        home_boxer = Athlete.objects.create(
            club=self.public_club, first_name='Boxeador', last_name='Local',
            status='ACTIVE', is_competitor=True, category='70 kg',
        )
        away_boxer = Athlete.objects.create(
            club=self.hidden_club, first_name='Boxeador', last_name='Visitante',
            status='ACTIVE', is_competitor=True, category='70 kg',
        )
        agreement = FightAgreement.objects.create(
            proposing_club=self.public_club,
            opponent_club=self.hidden_club,
            proposed_by=self.admin,
            planned_date=timezone.localdate() + timedelta(days=30),
            location='Gimnasio público',
            status='CONFIRMED',
        )
        FightBout.objects.create(
            agreement=agreement,
            home_athlete=home_boxer,
            away_athlete=away_boxer,
            last_suggested_by_club=self.hidden_club,
            status='CONFIRMED',
        )

        response = self.client.get(reverse('public-site-overview'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['featured_fights']), 1)
        fight = response.data['featured_fights'][0]
        self.assertEqual(fight['confirmed_bouts'][0]['category'], '70 kg')
        self.assertNotIn('home_athlete_name', fight['confirmed_bouts'][0])
        self.assertTrue(any(update['id'] == self.public_club.pk for update in response.data['club_updates']))
        self.assertEqual(response.data['promotion']['image'], None)

    def test_public_home_does_not_promote_private_clubs_or_unconfirmed_fights(self):
        response = self.client.get(reverse('public-site-overview'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        update_ids = [update['id'] for update in response.data['club_updates']]
        self.assertIn(self.public_club.pk, update_ids)
        self.assertNotIn(self.hidden_club.pk, update_ids)
        self.assertEqual(response.data['featured_fights'], [])

    def test_pending_and_rejected_clubs_are_hidden_from_public_list_and_detail(self):
        pending = Club.objects.create(
            name='Club pendiente público',
            is_public=True,
            verification_status='PENDING',
        )
        rejected = Club.objects.create(
            name='Club rechazado público',
            is_public=True,
            verification_status='REJECTED',
        )

        list_response = self.client.get(reverse('public-club-list'))
        pending_detail = self.client.get(reverse('public-club-detail', kwargs={'pk': pending.pk}))
        rejected_detail = self.client.get(reverse('public-club-detail', kwargs={'pk': rejected.pk}))

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        listed_clubs = list_response.data.get('results', list_response.data)
        self.assertEqual([club['id'] for club in listed_clubs], [self.public_club.pk])
        self.assertEqual(pending_detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(rejected_detail.status_code, status.HTTP_404_NOT_FOUND)

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
            'duration': 'Mensual',
            'sort_order': 2,
        }, format='json')

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create_response.data['classes_per_week'], 4)
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

    def test_admin_can_customize_club_brand_and_trainer_cannot(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(reverse('club-brand-settings'), {
            'name': 'Club con identidad',
            'brand_primary': '#245A77',
            'brand_accent': '#E4A84D',
            'brand_surface': '#14232C',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.public_club.refresh_from_db()
        self.assertEqual(self.public_club.brand_primary, '#245A77')
        self.assertEqual(response.data['name'], 'Club con identidad')

        trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        trainer = User.objects.create_user(
            username='brand-trainer', password='Password123!',
            role=trainer_role, club=self.public_club,
        )
        self.client.force_authenticate(user=trainer)
        denied = self.client.patch(reverse('club-brand-settings'), {'name': 'Cambio ajeno'}, format='json')

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.public_club.refresh_from_db()
        self.assertEqual(self.public_club.name, 'Club con identidad')

        superuser = User.objects.create_superuser(
            username='brand-superuser', email='brand-superuser@test.com', password='Password123!',
        )
        self.client.force_authenticate(user=superuser)
        superuser_denied = self.client.patch(
            reverse('club-brand-settings'), {'name': 'Cambio global'}, format='json',
        )
        self.assertEqual(superuser_denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_admin_cannot_publish_but_can_manage_plans(self):
        self.public_club.verification_status = 'PENDING'
        self.public_club.is_public = False
        self.public_club.save(update_fields=['verification_status', 'is_public'])
        self.client.force_authenticate(user=self.admin)

        publication_response = self.client.patch(
            reverse('club-publication'),
            {'is_public': True},
            format='json',
        )
        plan_response = self.client.post(reverse('club-plans'), {
            'name': 'Plan mientras espera',
            'price': '35000',
            'duration': 'Mensual',
        }, format='json')

        self.assertEqual(publication_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(plan_response.status_code, status.HTTP_201_CREATED)
        self.public_club.refresh_from_db()
        self.assertFalse(self.public_club.is_public)

    def test_admin_cannot_modify_own_verification_status(self):
        self.client.force_authenticate(user=self.admin)

        review_response = self.client.patch(
            reverse('club-review', kwargs={'pk': self.public_club.pk}),
            {'verification_status': 'REJECTED'},
            format='json',
        )
        publication_response = self.client.patch(
            reverse('club-publication'),
            {'is_public': False, 'verification_status': 'REJECTED'},
            format='json',
        )

        self.assertEqual(review_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(publication_response.status_code, status.HTTP_200_OK)
        self.public_club.refresh_from_db()
        self.assertEqual(self.public_club.verification_status, 'APPROVED')
