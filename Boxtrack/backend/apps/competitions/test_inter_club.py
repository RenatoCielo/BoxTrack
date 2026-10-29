from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.competitions.models import Competition, FightMatch
from apps.notifications.models import Notification


class InterClubBase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club_a = Club.objects.create(name='Club A', email='a@club.com', verification_status='APPROVED')
        self.club_b = Club.objects.create(name='Club B', email='b@club.com', verification_status='APPROVED')
        self.club_c = Club.objects.create(name='Club C', email='c@club.com', verification_status='APPROVED')
        roles = {name: Role.objects.create(name=name, description=name) for name in ('ADMIN', 'TRAINER', 'ATHLETE')}

        def user(name, club, role):
            return User.objects.create_user(username=name, email=f'{name}@x.com', password='Password123!', club=club, role=roles[role])

        self.admin_a = user('admina', self.club_a, 'ADMIN')
        self.trainer_a = user('trainera', self.club_a, 'TRAINER')
        self.other_trainer_a = user('trainera2', self.club_a, 'TRAINER')
        self.admin_b = user('adminb', self.club_b, 'ADMIN')
        self.admin_c = user('adminc', self.club_c, 'ADMIN')
        self.athlete_user_a = user('athletea', self.club_a, 'ATHLETE')
        self.athlete_user_b = user('athleteb', self.club_b, 'ATHLETE')
        self.fighter_a = Athlete.objects.create(club=self.club_a, user=self.athlete_user_a, first_name='Ana', last_name='A', assigned_trainer=self.trainer_a, is_competitor=True)
        self.fighter_b = Athlete.objects.create(club=self.club_b, user=self.athlete_user_b, first_name='Beto', last_name='B', is_competitor=True)
        self.novice_a = Athlete.objects.create(club=self.club_a, first_name='Nico', last_name='N', assigned_trainer=self.trainer_a)

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def propose(self, user=None, **extra):
        self.as_user(user or self.admin_a)
        payload = {
            'challenger_athlete': self.fighter_a.id, 'opponent_club': self.club_b.id, 'opponent_athlete': self.fighter_b.id,
            'fight_date': str(timezone.localdate() + timedelta(days=10)), 'event': 'Velada',
        }
        payload.update(extra)
        return self.client.post(reverse('fight-match-list-create'), payload, format='json')

    def act(self, user, match_id, action, payload=None):
        self.as_user(user)
        return self.client.post(reverse('fight-match-action', args=[match_id, action]), payload or {}, format='json')


class CompetitorRequestTests(InterClubBase):
    def request(self, user=None, athlete=None):
        self.as_user(user or self.trainer_a)
        return self.client.post(reverse('competitor-request-list-create'), {'athlete': (athlete or self.novice_a).id, 'request_note': 'Listo'}, format='json')

    def test_trainer_requests_and_admin_approves(self):
        response = self.request()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Notification.objects.filter(user=self.admin_a, notification_type='COMPETITION').exists())
        self.assertFalse(Athlete.objects.get(pk=self.novice_a.pk).is_competitor)
        self.as_user(self.admin_a)
        approved = self.client.post(reverse('competitor-request-review', args=[response.data['id']]), {'decision': 'APPROVE'}, format='json')
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.novice_a.refresh_from_db()
        self.assertTrue(self.novice_a.is_competitor)
        self.assertEqual(Athlete.objects.filter(club=self.club_a).count(), 2)
        self.assertTrue(Notification.objects.filter(user=self.trainer_a, title='Solicitud de competidor resuelta').exists())

    def test_rejection_keeps_athlete_and_record(self):
        request_id = self.request().data['id']
        self.as_user(self.admin_a)
        self.client.post(reverse('competitor-request-review', args=[request_id]), {'decision': 'REJECT', 'review_note': 'Falta preparación'}, format='json')
        self.novice_a.refresh_from_db()
        self.assertFalse(self.novice_a.is_competitor)
        listed = self.client.get(reverse('competitor-request-list-create'))
        self.assertEqual(listed.data[0]['status'], 'REJECTED')
        self.assertEqual(listed.data[0]['review_note'], 'Falta preparación')

    def test_duplicates_and_permissions(self):
        self.assertEqual(self.request().status_code, 201)
        self.assertEqual(self.request().status_code, 409)
        self.assertEqual(self.request(self.other_trainer_a).status_code, 403)
        self.assertEqual(self.request(self.admin_a).status_code, 403)
        self.assertEqual(self.request(athlete=self.fighter_a).status_code, 400)

    def test_only_admin_of_same_club_reviews(self):
        request_id = self.request().data['id']
        for user in (self.trainer_a, self.admin_b, self.athlete_user_a):
            self.as_user(user)
            response = self.client.post(reverse('competitor-request-review', args=[request_id]), {'decision': 'APPROVE'}, format='json')
            self.assertIn(response.status_code, (403, 404))
        self.novice_a.refresh_from_db()
        self.assertFalse(self.novice_a.is_competitor)


class FightMatchTests(InterClubBase):
    def test_full_flow_creates_single_record_and_histories(self):
        match_id = self.propose().data['id']
        self.assertTrue(Notification.objects.filter(user=self.admin_b, title='Nueva propuesta de combate').exists())
        self.assertEqual(self.act(self.admin_b, match_id, 'accept').data['status'], 'ACCEPTED')
        FightMatch.objects.filter(pk=match_id).update(fight_date=timezone.localdate())
        done = self.act(self.admin_a, match_id, 'result', {'result': 'WIN'})
        self.assertEqual(done.status_code, 200)
        self.assertEqual(FightMatch.objects.count(), 1)
        self.assertEqual(Competition.objects.get(athlete=self.fighter_a).result, 'WIN')
        self.assertEqual(Competition.objects.get(athlete=self.fighter_b).result, 'LOSS')
        self.assertEqual(self.act(self.admin_b, match_id, 'result', {'result': 'LOSS'}).status_code, 409)
        self.assertEqual(Competition.objects.count(), 2)

    def test_both_competitors_and_only_them_see_the_match(self):
        self.propose()
        for user in (self.athlete_user_a, self.athlete_user_b, self.admin_a, self.admin_b, self.trainer_a):
            self.as_user(user)
            self.assertEqual(len(self.client.get(reverse('fight-match-list-create')).data), 1, user.username)
        for user in (self.admin_c, self.other_trainer_a):
            self.as_user(user)
            self.assertEqual(self.client.get(reverse('fight-match-list-create')).data, [])

    def test_validations(self):
        self.assertEqual(self.propose(opponent_athlete=self.novice_a.id).status_code, 400)
        self.assertEqual(self.propose(fight_date=str(timezone.localdate() - timedelta(days=1))).status_code, 400)
        self.assertEqual(self.propose(self.admin_b).status_code, 403)
        self.assertEqual(self.propose(self.other_trainer_a).status_code, 403)
        self.assertEqual(self.propose().status_code, 201)
        self.assertEqual(self.propose().status_code, 409)
        self.assertEqual(FightMatch.objects.count(), 1)

    def test_unapproved_club_cannot_be_challenged(self):
        self.club_b.verification_status = 'PENDING'
        self.club_b.save()
        self.assertEqual(self.propose().status_code, 400)

    def test_selected_rival_club_must_match_fighter_and_be_explicit(self):
        self.assertEqual(self.propose(opponent_club=self.club_c.id).status_code, 400)
        self.assertEqual(self.propose(opponent_club=None).status_code, 400)
        self.assertEqual(self.propose().status_code, 201)

    def test_response_permissions(self):
        match_id = self.propose().data['id']
        self.assertEqual(self.act(self.admin_a, match_id, 'accept').status_code, 403)
        self.assertEqual(self.act(self.admin_c, match_id, 'accept').status_code, 404)
        self.assertEqual(self.act(self.athlete_user_b, match_id, 'accept').status_code, 404)
        self.assertEqual(self.act(self.admin_b, match_id, 'result', {'result': 'WIN'}).status_code, 409)
        self.assertEqual(self.act(self.admin_b, match_id, 'decline').data['status'], 'DECLINED')
        self.assertEqual(self.act(self.admin_b, match_id, 'accept').status_code, 409)
        self.assertEqual(Competition.objects.count(), 0)

    def test_cancel_and_future_result_blocked(self):
        match_id = self.propose().data['id']
        self.act(self.admin_b, match_id, 'accept')
        self.assertEqual(self.act(self.admin_a, match_id, 'result', {'result': 'WIN'}).status_code, 400)
        self.assertEqual(self.act(self.admin_a, match_id, 'cancel').data['status'], 'CANCELLED')
        self.assertTrue(Notification.objects.filter(user=self.admin_b, title='Combate cancelado').exists())

    def test_directory_lists_only_other_clubs_competitors(self):
        self.as_user(self.admin_a)
        rows = self.client.get(reverse('competitor-directory')).data
        self.assertEqual([row['id'] for row in rows], [self.fighter_b.id])
        self.as_user(self.athlete_user_a)
        self.assertEqual(self.client.get(reverse('competitor-directory')).status_code, 403)

    def test_rival_club_directory_includes_approved_club_without_competitors(self):
        self.as_user(self.admin_a)
        rows = self.client.get(reverse('rival-club-directory')).data
        self.assertEqual([row['id'] for row in rows], [self.club_b.id, self.club_c.id])
        self.assertEqual(rows[0]['competitor_count'], 1)
        self.assertEqual(rows[1]['competitor_count'], 0)
        self.as_user(self.athlete_user_a)
        self.assertEqual(self.client.get(reverse('rival-club-directory')).status_code, 403)

    def test_directory_can_be_filtered_to_the_selected_rival_club(self):
        self.as_user(self.admin_a)
        response = self.client.get(reverse('competitor-directory'), {'club': self.club_b.id})
        self.assertEqual([row['id'] for row in response.data], [self.fighter_b.id])
        self.assertEqual(self.client.get(reverse('competitor-directory'), {'club': self.club_c.id}).data, [])
        self.assertEqual(self.client.get(reverse('competitor-directory'), {'club': 'invalid'}).status_code, 400)
