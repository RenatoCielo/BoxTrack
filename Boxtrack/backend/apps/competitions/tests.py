from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.competitions.models import Competition


class FightRecordTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Demo', email='demo@club.com', verification_status='APPROVED')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@club.com', verification_status='APPROVED')
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
        self.rival_admin = User.objects.create_user(
            username='rival-admin', password='Password123!',
            club=self.other_club, role=self.admin_role,
        )
        self.athlete = Athlete.objects.create(
            club=self.club,
            first_name='Mateo',
            last_name='Silva',
            gender='M',
            status='ACTIVE',
            is_competitor=True,
            category='70 kg',
            registered_weight='70.00',
            assigned_trainer=self.trainer_user,
        )
        self.other_athlete = Athlete.objects.create(
            club=self.other_club,
            first_name='Pedro',
            last_name='Mora',
            gender='M',
            status='ACTIVE',
            is_competitor=True,
            category='70 kg',
            registered_weight='71.00',
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

    def test_trainer_only_lists_and_creates_fights_for_assigned_athletes(self):
        unassigned_athlete = Athlete.objects.create(
            club=self.club, first_name='No', last_name='Asignado', status='ACTIVE'
        )
        self.client.force_authenticate(user=self.trainer_user)
        self.client.post(reverse('fight-record-list-create'), {
            'athlete': self.athlete.pk,
            'opponent_name': 'Rival',
            'result': 'WIN',
            'fight_type': 'AMATEUR',
        }, format='json')

        list_response = self.client.get(reverse('fight-record-list-create'))
        create_response = self.client.post(reverse('fight-record-list-create'), {
            'athlete': unassigned_athlete.pk,
            'opponent_name': 'Otro rival',
            'result': 'LOSS',
            'fight_type': 'AMATEUR',
        }, format='json')

        self.assertEqual([row['athlete'] for row in list_response.data['results']], [self.athlete.pk])
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_club_admin_can_propose_and_confirm_a_future_interclub_fight(self):
        self.client.force_authenticate(user=self.admin_user)
        planned_date = (timezone.localdate() + timedelta(days=20)).isoformat()
        response = self.client.post(reverse('fight-agreement-list-create'), {
            'opponent_club': self.other_club.pk,
            'planned_date': planned_date,
            'location': 'Gimnasio Central',
            'notes': 'Tres combates amateur.',
            'initial_home_athlete': self.athlete.pk,
            'initial_away_athlete': self.other_athlete.pk,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        agreement_id = response.data['id']
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(response.data['bouts'][0]['home_athlete_name'], 'Mateo Silva')
        self.assertEqual(response.data['bouts'][0]['away_athlete_name'], 'Pedro Mora')
        self.assertEqual(self.other_club.notifications.count(), 1)

        self.client.force_authenticate(user=self.rival_admin)
        incoming = self.client.get(reverse('fight-agreement-list-create'))
        self.assertEqual(incoming.status_code, status.HTTP_200_OK)
        row = incoming.data['results'][0]
        self.assertTrue(row['is_incoming'])
        self.assertEqual(row['proposing_club_name'], self.club.name)
        bout = row['bouts'][0]
        counter = self.client.patch(
            reverse('fight-agreement-bout-detail', kwargs={
                'agreement_id': agreement_id, 'pk': bout['id'],
            }),
            {'away_athlete': self.other_athlete.pk},
            format='json',
        )
        self.assertEqual(counter.status_code, status.HTTP_200_OK)
        self.assertEqual(counter.data['status'], 'COUNTERED')

        self.client.force_authenticate(user=self.admin_user)
        accepted = self.client.patch(
            reverse('fight-agreement-bout-detail', kwargs={
                'agreement_id': agreement_id, 'pk': bout['id'],
            }),
            {'status': 'CONFIRMED'},
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data['status'], 'CONFIRMED')
        self.assertEqual(self.rival_admin.notifications.count(), 2)
        self.assertEqual(self.admin_user.notifications.count(), 1)

    def test_only_club_admin_can_create_interclub_agreements_and_date_must_be_future(self):
        self.client.force_authenticate(user=self.trainer_user)
        denied = self.client.post(reverse('fight-agreement-list-create'), {
            'opponent_club': self.other_club.pk,
            'planned_date': (timezone.localdate() + timedelta(days=5)).isoformat(),
            'location': 'Ring central',
        }, format='json')
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.admin_user)
        past = self.client.post(reverse('fight-agreement-list-create'), {
            'opponent_club': self.other_club.pk,
            'planned_date': timezone.localdate().isoformat(),
            'location': 'Ring central',
            'initial_home_athlete': self.athlete.pk,
        }, format='json')
        self.assertEqual(past.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('planned_date', past.data)

    def test_rival_candidates_are_suggested_by_category_weight_and_competitive_experience(self):
        best = self.other_athlete
        best.category = self.athlete.category
        best.registered_weight = '70.50'
        best.save(update_fields=['category', 'registered_weight'])
        Competition.objects.create(
            club=self.other_club, athlete=best, result='WIN', fight_type='AMATEUR'
        )
        Competition.objects.create(
            club=self.other_club, athlete=best, result='WIN', fight_type='PRO'
        )
        Competition.objects.create(
            club=self.other_club, athlete=best, result='LOSS', fight_type='AMATEUR'
        )
        Competition.objects.create(
            club=self.other_club, athlete=best, result='WIN', fight_type='SPARRING'
        )
        far = Athlete.objects.create(
            club=self.other_club, first_name='Carlos', last_name='Rival',
            gender='M', status='ACTIVE', is_competitor=True, category='85 kg', registered_weight='85.00',
        )
        different_gender = Athlete.objects.create(
            club=self.other_club, first_name='Lucía', last_name='Rival',
            gender='F', status='ACTIVE', is_competitor=True, category='70 kg', registered_weight='70.50',
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse('fight-rival-competitors', kwargs={'club_id': self.other_club.pk})
            + f'?home_athlete={self.athlete.pk}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['id'], best.pk)
        self.assertIn('Misma categoría', response.data[0]['match_reasons'])
        self.assertIn('Peso muy cercano', response.data[0]['match_reasons'])
        self.assertEqual(response.data[0]['fight_record'], '2-1-0')
        self.assertEqual(response.data[0]['recorded_fights'], 3)
        self.assertEqual(response.data[1]['id'], far.pk)
        self.assertNotIn(different_gender.pk, [row['id'] for row in response.data])

    def test_interclub_proposals_reject_opposite_gender_competitors(self):
        rival_woman = Athlete.objects.create(
            club=self.other_club, first_name='Lucía', last_name='Rival',
            gender='F', status='ACTIVE', is_competitor=True,
        )
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            'opponent_club': self.other_club.pk,
            'planned_date': (timezone.localdate() + timedelta(days=12)).isoformat(),
            'location': 'Ring central',
            'initial_home_athlete': self.athlete.pk,
        }
        mismatched_initial = self.client.post(
            reverse('fight-agreement-list-create'),
            {**payload, 'initial_away_athlete': rival_woman.pk},
            format='json',
        )
        self.assertEqual(mismatched_initial.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('initial_away_athlete', mismatched_initial.data)

        proposal = self.client.post(
            reverse('fight-agreement-list-create'), payload, format='json'
        )
        self.assertEqual(proposal.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=self.rival_admin)
        bout_id = proposal.data['bouts'][0]['id']
        mismatched_counter = self.client.patch(
            reverse('fight-agreement-bout-detail', kwargs={
                'agreement_id': proposal.data['id'], 'pk': bout_id,
            }),
            {'away_athlete': rival_woman.pk},
            format='json',
        )
        self.assertEqual(mismatched_counter.status_code, status.HTTP_403_FORBIDDEN)

    def test_fight_pair_can_only_be_accepted_after_the_other_club_suggests_a_boxer(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('fight-agreement-list-create'), {
            'opponent_club': self.other_club.pk,
            'planned_date': (timezone.localdate() + timedelta(days=8)).isoformat(),
            'location': 'Ring central',
            'initial_home_athlete': self.athlete.pk,
        }, format='json')
        bout_id = response.data['bouts'][0]['id']
        premature = self.client.patch(
            reverse('fight-agreement-bout-detail', kwargs={
                'agreement_id': response.data['id'], 'pk': bout_id,
            }),
            {'status': 'CONFIRMED'},
            format='json',
        )
        self.assertEqual(premature.status_code, status.HTTP_403_FORBIDDEN)
