from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.memberships.models import Membership, MembershipPlan
from apps.notifications.models import Notification
from apps.trainings.models import Training, TrainingReservation


class MembershipBase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Demo', email='demo@club.com')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@club.com')
        admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        self.admin = User.objects.create_user(username='admin', email='a@demo.com', password='Password123!', club=self.club, role=admin_role)
        self.trainer = User.objects.create_user(username='trainer', email='t@demo.com', password='Password123!', club=self.club, role=trainer_role)
        self.athlete_user = User.objects.create_user(username='athlete', email='d@demo.com', password='Password123!', club=self.club, role=athlete_role)
        self.other_admin = User.objects.create_user(username='admin2', email='a2@demo.com', password='Password123!', club=self.other_club, role=admin_role)
        self.athlete = Athlete.objects.create(club=self.club, user=self.athlete_user, first_name='Mateo', last_name='Rojas', status='ACTIVE')
        self.plan = MembershipPlan.objects.create(club=self.club, name='Mensual', price=30000, duration_days=30)
        self.other_plan = MembershipPlan.objects.create(club=self.other_club, name='Mensual', price=1, duration_days=30)

    def request_plan(self, plan=None):
        self.client.force_authenticate(user=self.athlete_user)
        return self.client.post(reverse('membership-list-create'), {'plan': (plan or self.plan).id, 'price_paid': 1}, format='json')

    def make_training(self, day, title='Clase'):
        return Training.objects.create(club=self.club, title=title, scheduled_date=day, start_time='18:00:00', capacity=10)

    def activate(self, limit=None, days_left=30):
        self.plan.weekly_class_limit = limit
        self.plan.save()
        return Membership.objects.create(
            club=self.club, athlete=self.athlete, plan=self.plan, plan_name='Mensual', price_paid=30000,
            duration_days=30, weekly_class_limit=limit, status='ACTIVE',
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=days_left),
        )

    def reserve(self, training, user=None, athlete=None):
        self.client.force_authenticate(user=user or self.athlete_user)
        data = {'athlete': athlete.pk} if athlete else {}
        return self.client.post(reverse('training-reservations', kwargs={'training_id': training.pk}), data, format='json')


class MembershipTests(MembershipBase):
    def test_admin_creates_plan_and_athlete_only_sees_active_plans_of_own_club(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(reverse('membership-plan-list-create'), {'name': 'Trimestral', 'price': '80000', 'duration_days': 90}, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data['club'], self.club.id)
        self.client.patch(reverse('membership-plan-detail', kwargs={'pk': self.plan.pk}), {'is_active': False}, format='json')

        self.client.force_authenticate(user=self.athlete_user)
        names = [row['name'] for row in self.client.get(reverse('membership-plan-list-create')).data['results']]
        self.assertEqual(names, ['Trimestral'])

    def test_athlete_and_trainer_cannot_manage_plans(self):
        for user in (self.athlete_user, self.trainer):
            self.client.force_authenticate(user=user)
            response = self.client.post(reverse('membership-plan-list-create'), {'name': 'Gratis', 'price': '1', 'duration_days': 30}, format='json')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_touch_plans_of_other_club(self):
        self.client.force_authenticate(user=self.other_admin)
        response = self.client.patch(reverse('membership-plan-detail', kwargs={'pk': self.plan.pk}), {'price': '1'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_price_comes_from_server_and_request_is_pending(self):
        response = self.request_plan()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(str(response.data['price_paid']), '30000.00')

    def test_cannot_request_plan_of_another_club(self):
        self.assertEqual(self.request_plan(self.other_plan).status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_open_membership_is_rejected(self):
        self.request_plan()
        self.assertEqual(self.request_plan().status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Membership.objects.count(), 1)

    def test_athlete_cannot_confirm_own_payment(self):
        membership_id = self.request_plan().data['id']
        response = self.client.post(reverse('membership-review', kwargs={'pk': membership_id}), {'decision': 'CONFIRM'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Membership.objects.get(pk=membership_id).status, 'PENDING')

    def test_admin_confirms_and_membership_activates_once(self):
        membership_id = self.request_plan().data['id']
        self.client.force_authenticate(user=self.admin)
        url = reverse('membership-review', kwargs={'pk': membership_id})
        response = self.client.post(url, {'decision': 'CONFIRM'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ACTIVE')
        self.assertEqual(response.data['end_date'], str(timezone.localdate() + timedelta(days=30)))
        self.assertEqual(self.client.post(url, {'decision': 'CONFIRM'}, format='json').status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Notification.objects.filter(user=self.athlete_user).count(), 1)

    def test_other_club_admin_cannot_review(self):
        membership_id = self.request_plan().data['id']
        self.client.force_authenticate(user=self.other_admin)
        response = self.client.post(reverse('membership-review', kwargs={'pk': membership_id}), {'decision': 'CONFIRM'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reject_requires_note_and_allows_new_request(self):
        membership_id = self.request_plan().data['id']
        self.client.force_authenticate(user=self.admin)
        url = reverse('membership-review', kwargs={'pk': membership_id})
        self.assertEqual(self.client.post(url, {'decision': 'REJECT'}, format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(url, {'decision': 'REJECT', 'note': 'Pago no recibido'}, format='json').status_code, status.HTTP_200_OK)
        self.assertEqual(self.request_plan().status_code, status.HTTP_201_CREATED)

    def test_overdue_membership_becomes_expired_and_plan_edit_does_not_change_history(self):
        membership = Membership.objects.create(
            club=self.club, athlete=self.athlete, plan=self.plan, plan_name='Mensual', price_paid=30000, duration_days=30,
            status='ACTIVE', start_date=timezone.localdate() - timedelta(days=40), end_date=timezone.localdate() - timedelta(days=10),
        )
        self.plan.price = 99999
        self.plan.save()
        self.client.force_authenticate(user=self.athlete_user)
        rows = self.client.get(reverse('membership-list-create')).data
        self.assertEqual(rows[0]['status'], 'EXPIRED')
        self.assertEqual(str(rows[0]['price_paid']), '30000.00')
        self.assertEqual(self.request_plan().status_code, status.HTTP_201_CREATED)
        self.assertEqual(Membership.objects.get(pk=membership.pk).status, 'EXPIRED')

    def test_athlete_only_sees_own_memberships(self):
        other_user = User.objects.create_user(username='ath2', email='x@demo.com', password='Password123!', club=self.club, role=self.athlete_user.role)
        other = Athlete.objects.create(club=self.club, user=other_user, first_name='Otro', last_name='Dep', status='ACTIVE')
        Membership.objects.create(club=self.club, athlete=other, plan=self.plan, plan_name='Mensual', price_paid=30000, duration_days=30)
        self.client.force_authenticate(user=self.athlete_user)
        self.assertEqual(self.client.get(reverse('membership-list-create')).data, [])

class WeeklyLimitReservationTests(MembershipBase):
    def test_limit_blocks_extra_class_in_same_week_but_not_next_week(self):
        self.activate(2)
        monday = timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()))
        first, second, third = (self.make_training(monday + timedelta(days=i)) for i in (0, 2, 4))
        next_week = self.make_training(monday + timedelta(days=7))
        self.assertEqual(self.reserve(first).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.reserve(second).status_code, status.HTTP_201_CREATED)
        blocked = self.reserve(third)
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('2 clase(s) por semana', blocked.data['detail'])
        self.assertEqual(self.reserve(next_week).status_code, status.HTTP_201_CREATED)

    def test_cancelling_frees_a_weekly_slot(self):
        self.activate(1)
        monday = timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()))
        first, second = self.make_training(monday), self.make_training(monday + timedelta(days=1))
        reservation_id = self.reserve(first).data['id']
        self.assertEqual(self.reserve(second).status_code, status.HTTP_409_CONFLICT)
        self.client.post(reverse('training-reservation-cancel', kwargs={'training_id': first.pk, 'reservation_id': reservation_id}), {}, format='json')
        self.assertEqual(self.reserve(second).status_code, status.HTTP_201_CREATED)

    def test_no_limit_or_no_membership_keeps_previous_behavior(self):
        monday = timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()))
        trainings = [self.make_training(monday + timedelta(days=i)) for i in range(3)]
        self.assertTrue(all(self.reserve(t).status_code == status.HTTP_201_CREATED for t in trainings))

    def test_expired_membership_does_not_apply_limit(self):
        membership = self.activate(1)
        membership.end_date = timezone.localdate() - timedelta(days=1)
        membership.save()
        monday = timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()))
        first, second = self.make_training(monday), self.make_training(monday + timedelta(days=1))
        self.assertEqual(self.reserve(first).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.reserve(second).status_code, status.HTTP_201_CREATED)


class RequireMembershipSettingTests(MembershipBase):
    def next_monday(self):
        return timezone.localdate() + timedelta(days=(7 - timezone.localdate().weekday()))

    def set_required(self, value, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.patch(reverse('membership-settings'), {'require_active_membership': value}, format='json')

    def test_default_is_disabled_and_reservations_work_as_before(self):
        self.client.force_authenticate(user=self.athlete_user)
        self.assertFalse(self.client.get(reverse('membership-settings')).data['require_active_membership'])
        self.assertEqual(self.reserve(self.make_training(self.next_monday())).status_code, status.HTTP_201_CREATED)

    def test_only_club_admin_can_change_setting(self):
        for user in (self.athlete_user, self.trainer):
            self.assertEqual(self.set_required(True, user).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.set_required('si').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.set_required(True).status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=self.athlete_user)
        self.assertTrue(self.client.get(reverse('membership-settings')).data['require_active_membership'])

    def test_enabled_blocks_athlete_without_membership_with_clear_message(self):
        self.set_required(True)
        response = self.reserve(self.make_training(self.next_monday()))
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['code'], 'MEMBERSHIP_REQUIRED')
        self.assertIn('Membresías', response.data['detail'])
        self.assertEqual(TrainingReservation.objects.count(), 0)

    def test_enabled_blocks_pending_expired_and_membership_ending_before_class(self):
        self.set_required(True)
        training = self.make_training(self.next_monday())
        pending = self.request_plan()
        self.assertIn('pendiente de pago', self.reserve(training).data['detail'])
        Membership.objects.filter(pk=pending.data['id']).update(status='ACTIVE', start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=1))
        self.assertEqual(self.reserve(training).status_code, status.HTTP_409_CONFLICT)
        Membership.objects.filter(pk=pending.data['id']).update(end_date=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.reserve(training).status_code, status.HTTP_409_CONFLICT)

    def test_enabled_allows_active_membership_and_still_applies_weekly_limit(self):
        self.set_required(True)
        self.activate(limit=1)
        monday = self.next_monday()
        self.assertEqual(self.reserve(self.make_training(monday)).status_code, status.HTTP_201_CREATED)
        blocked = self.reserve(self.make_training(monday + timedelta(days=1)))
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn('code', blocked.data)

    def test_enabled_also_applies_when_staff_enrolls_the_athlete(self):
        self.set_required(True)
        training = self.make_training(self.next_monday())
        self.assertEqual(self.reserve(training, user=self.admin, athlete=self.athlete).status_code, status.HTTP_409_CONFLICT)
        self.activate()
        self.assertEqual(self.reserve(training, user=self.admin, athlete=self.athlete).status_code, status.HTTP_201_CREATED)

    def test_setting_only_affects_its_own_club(self):
        other_athlete_user = User.objects.create_user(username='ath3', email='y@demo.com', password='Password123!', club=self.other_club, role=self.athlete_user.role)
        Athlete.objects.create(club=self.other_club, user=other_athlete_user, first_name='Otra', last_name='Persona', status='ACTIVE')
        other_training = Training.objects.create(club=self.other_club, title='Clase', scheduled_date=self.next_monday(), start_time='18:00:00', capacity=5)
        self.set_required(True)
        self.assertEqual(self.reserve(other_training, user=other_athlete_user).status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=self.other_admin)
        self.assertFalse(self.client.get(reverse('membership-settings')).data['require_active_membership'])

    def test_disabling_restores_previous_behavior(self):
        self.set_required(True)
        training = self.make_training(self.next_monday())
        self.assertEqual(self.reserve(training).status_code, status.HTTP_409_CONFLICT)
        self.set_required(False)
        self.assertEqual(self.reserve(training).status_code, status.HTTP_201_CREATED)