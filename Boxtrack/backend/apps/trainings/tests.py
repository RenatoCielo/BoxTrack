from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club, Plan, PlanMembership
from apps.groups.models import Group
from apps.trainings.models import Training, TrainingReservation, WeeklyTrainingSchedule


class TrainingTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Demo', email='demo@club.com', verification_status='APPROVED')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@club.com', verification_status='APPROVED')
        self.admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        self.athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')

        self.admin_user = User.objects.create_user(
            username='admin', email='admin@demo.com', password='Password123!',
            club=self.club, role=self.admin_role
        )
        self.trainer_user = User.objects.create_user(
            username='trainer', email='trainer@demo.com', password='Password123!',
            club=self.club, role=self.trainer_role
        )
        self.athlete_user = User.objects.create_user(
            username='athlete', email='athlete@demo.com', password='Password123!',
            club=self.club, role=self.athlete_role
        )
        self.group = Group.objects.create(club=self.club, name='Grupo A', schedule='Lunes 18:00')
        self.athlete = Athlete.objects.create(
            club=self.club,
            user=self.athlete_user,
            first_name='Mateo',
            last_name='Rojas',
            status='ACTIVE',
            group=self.group,
        )
        self.plan = Plan.objects.create(
            club=self.club,
            name='Plan de prueba',
            price='30000',
            duration='Mensual',
            classes_per_week=4,
        )
        PlanMembership.objects.create(
            club=self.club,
            plan=self.plan,
            user=self.athlete_user,
            athlete=self.athlete,
            price_at_signup=self.plan.price,
            status='ACTIVE',
            starts_on=timezone.localdate() - timedelta(days=30),
            expires_on=timezone.localdate() + timedelta(days=365),
        )

    def create_training(self, capacity=20, club=None):
        return Training.objects.create(
            club=club or self.club,
            title='Clase técnica',
            scheduled_date=timezone.localdate(),
            start_time='18:00:00',
            duration_minutes=60,
            capacity=capacity,
            trainer=self.trainer_user,
        )

    def test_create_training_for_same_club(self):
        self.client.force_authenticate(user=self.trainer_user)
        payload = {
            'title': 'Sparring técnico',
            'description': 'Trabajo de distancia y defensa',
            'activity_type': 'SPARRING',
            'trainer': self.trainer_user.id,
            'group': self.group.id,
            'scheduled_date': '2026-10-10',
            'start_time': '18:00:00',
            'duration_minutes': 90,
            'status': 'SCHEDULED',
        }

        response = self.client.post(reverse('training-list-create'), payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Training.objects.filter(club=self.club).count(), 1)

    def test_trainer_creating_a_class_is_assigned_to_their_own_account(self):
        self.client.force_authenticate(user=self.trainer_user)

        response = self.client.post(reverse('training-list-create'), {
            'title': 'Clase programada por entrenador',
            'scheduled_date': '2026-10-10',
            'start_time': '18:00:00',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['trainer'], self.trainer_user.id)

    def test_weekly_schedule_generates_future_classes_and_reuses_them(self):
        self.client.force_authenticate(user=self.admin_user)
        today = timezone.localdate()
        weekdays = [today.weekday(), (today.weekday() + 2) % 7]

        response = self.client.post(reverse('weekly-training-schedule-list-create'), {
            'title': 'Boxeo de la semana',
            'weekdays': weekdays,
            'starts_on': today.isoformat(),
            'start_time': '18:00:00',
            'trainer': self.trainer_user.id,
            'group': self.group.id,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        schedule = WeeklyTrainingSchedule.objects.get(pk=response.data['id'])
        self.assertIsNone(schedule.ends_on)
        expected_dates = {
            today + timedelta(days=offset)
            for offset in range(84)
            if (today + timedelta(days=offset)).weekday() in weekdays
        }
        self.assertEqual(
            set(schedule.occurrences.values_list('scheduled_date', flat=True)),
            expected_dates,
        )

        future_window_start = today + timedelta(days=84)
        expected_next_dates = {
            today + timedelta(days=offset)
            for offset in range(84, 168)
            if (today + timedelta(days=offset)).weekday() in weekdays
        }
        with patch('apps.trainings.views.timezone.localdate', return_value=future_window_start):
            self.client.get(reverse('training-list-create'))
            self.client.get(reverse('training-list-create'))

        self.assertTrue(schedule.occurrences.filter(scheduled_date=future_window_start).exists())
        self.assertEqual(
            schedule.occurrences.values('scheduled_date').distinct().count(),
            len(expected_dates) + len(expected_next_dates),
        )

    def test_trainer_can_create_a_weekly_schedule_for_their_own_classes(self):
        self.client.force_authenticate(user=self.trainer_user)

        response = self.client.post(reverse('weekly-training-schedule-list-create'), {
            'title': 'Técnica semanal',
            'weekdays': [timezone.localdate().weekday()],
            'starts_on': timezone.localdate().isoformat(),
            'start_time': '19:00:00',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['trainer'], self.trainer_user.id)
        self.assertTrue(WeeklyTrainingSchedule.objects.filter(club=self.club, trainer=self.trainer_user).exists())

    def test_weekly_schedule_rejects_invalid_days_and_end_dates(self):
        self.client.force_authenticate(user=self.admin_user)
        today = timezone.localdate()

        invalid_days_response = self.client.post(reverse('weekly-training-schedule-list-create'), {
            'title': 'Horario inválido',
            'weekdays': [7],
            'starts_on': today.isoformat(),
            'start_time': '18:00:00',
        }, format='json')
        invalid_range_response = self.client.post(reverse('weekly-training-schedule-list-create'), {
            'title': 'Fechas inválidas',
            'weekdays': [today.weekday()],
            'starts_on': today.isoformat(),
            'ends_on': (today - timedelta(days=1)).isoformat(),
            'start_time': '18:00:00',
        }, format='json')

        self.assertEqual(invalid_days_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_range_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(WeeklyTrainingSchedule.objects.count(), 0)

    def test_admin_can_create_groups_and_trainings_while_club_is_pending(self):
        self.club.verification_status = 'PENDING'
        self.club.save(update_fields=['verification_status'])
        self.client.force_authenticate(user=self.admin_user)

        group_response = self.client.post(reverse('group-list-create'), {
            'name': 'Preparación inicial',
            'schedule': 'Lunes 18:00',
        }, format='json')
        training_response = self.client.post(reverse('training-list-create'), {
            'title': 'Boxeo técnico',
            'group': group_response.data.get('id'),
            'scheduled_date': '2026-10-10',
            'start_time': '18:00:00',
        }, format='json')

        self.assertEqual(group_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(training_response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.trainer_user)
        trainer_group_response = self.client.post(reverse('group-list-create'), {
            'name': 'Grupo no autorizado',
        }, format='json')
        trainer_training_response = self.client.post(reverse('training-list-create'), {
            'title': 'Clase no autorizada',
            'scheduled_date': '2026-10-10',
            'start_time': '19:00:00',
        }, format='json')

        self.assertEqual(trainer_group_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(trainer_training_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_athlete_sees_classes_while_club_is_pending(self):
        self.club.verification_status = 'PENDING'
        self.club.save(update_fields=['verification_status'])
        training = self.create_training()

        self.client.force_authenticate(user=self.athlete_user)
        response = self.client.get(reverse('training-list-create'))
        rows = response.data.get('results', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(training.id, [row['id'] for row in rows])

    def test_cross_club_training_blocked(self):
        other_group = Group.objects.create(club=self.other_club, name='Grupo B', schedule='Martes 18:00')
        training = Training.objects.create(
            club=self.other_club,
            title='Entrenamiento ajeno',
            scheduled_date='2026-10-12',
            start_time='19:00:00',
            duration_minutes=60,
            group=other_group,
            trainer=self.trainer_user,
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('training-detail', kwargs={'pk': training.pk}))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_athlete_cannot_create_or_edit_training(self):
        training = self.create_training()
        self.client.force_authenticate(user=self.athlete_user)

        create_response = self.client.post(reverse('training-list-create'), {
            'title': 'Clase no autorizada',
            'scheduled_date': '2026-10-10',
            'start_time': '18:00:00',
        }, format='json')
        update_response = self.client.patch(
            reverse('training-detail', kwargs={'pk': training.pk}),
            {'title': 'Modificada por atleta'},
            format='json',
        )

        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        training.refresh_from_db()
        self.assertEqual(training.title, 'Clase técnica')

    def test_athlete_can_reserve_and_view_own_class(self):
        training = self.create_training(capacity=1)
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.post(reverse('training-reservations', kwargs={'training_id': training.pk}), {}, format='json')
        roster_response = self.client.get(reverse('training-reservations', kwargs={'training_id': training.pk}))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(roster_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(roster_response.data), 1)
        self.assertEqual(roster_response.data[0]['athlete'], self.athlete.pk)

    def test_athlete_calendar_is_limited_to_the_selected_week(self):
        this_week_training = self.create_training()
        next_week_training = self.create_training()
        next_week_training.scheduled_date += timedelta(days=7)
        next_week_training.save(update_fields=['scheduled_date'])
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.get(
            f"{reverse('training-list-create')}?week_start={week_start.isoformat()}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row['id'] for row in response.data['results']], [this_week_training.pk])

    def test_athlete_calendar_rejects_a_week_that_does_not_start_on_monday(self):
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.get(
            f"{reverse('training-list-create')}?week_start={timezone.localdate().isoformat()}"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('week_start', response.data)

    def test_athlete_reservations_follow_the_active_plan_weekly_limit(self):
        self.plan.classes_per_week = 1
        self.plan.save(update_fields=['classes_per_week'])
        first_training = self.create_training()
        second_training = self.create_training()
        second_training.start_time = '19:00:00'
        second_training.save(update_fields=['start_time'])
        self.client.force_authenticate(user=self.athlete_user)

        first = self.client.post(
            reverse('training-reservations', kwargs={'training_id': first_training.pk}),
            {},
            format='json',
        )
        over_limit = self.client.post(
            reverse('training-reservations', kwargs={'training_id': second_training.pk}),
            {},
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(over_limit.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('permite hasta 1', over_limit.data['detail'])

    def test_present_attendance_consumes_membership_class_and_updates_balance(self):
        self.plan.classes_per_week = 1
        self.plan.save(update_fields=['classes_per_week'])
        first_training = self.create_training()
        second_training = self.create_training()
        second_training.start_time = '19:00:00'
        second_training.save(update_fields=['start_time'])
        reservation_url = reverse('training-reservations', kwargs={'training_id': first_training.pk})
        self.client.force_authenticate(user=self.athlete_user)
        reservation = self.client.post(reservation_url, {}, format='json')
        self.assertEqual(reservation.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.admin_user)
        attendance = self.client.post(reverse('attendance-list-create'), {
            'athlete': self.athlete.pk,
            'training': first_training.pk,
            'status': 'PRESENT',
        }, format='json')
        self.assertEqual(attendance.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.athlete_user)
        over_limit = self.client.post(
            reverse('training-reservations', kwargs={'training_id': second_training.pk}),
            {},
            format='json',
        )
        membership = self.client.get(
            f"{reverse('current-membership')}?week_start="
            f"{timezone.localdate() - timedelta(days=timezone.localdate().weekday())}"
        )

        self.assertEqual(over_limit.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(membership.status_code, status.HTTP_200_OK)
        self.assertEqual(membership.data['classes_used_this_week'], 1)
        self.assertEqual(membership.data['classes_reserved_this_week'], 1)
        self.assertEqual(membership.data['classes_remaining_this_week'], 0)

    def test_present_without_reservation_still_consumes_membership_class(self):
        self.plan.classes_per_week = 1
        self.plan.save(update_fields=['classes_per_week'])
        attended_training = self.create_training()
        next_training = self.create_training()
        next_training.start_time = '19:00:00'
        next_training.save(update_fields=['start_time'])
        self.client.force_authenticate(user=self.admin_user)
        attendance = self.client.post(reverse('attendance-list-create'), {
            'athlete': self.athlete.pk,
            'training': attended_training.pk,
            'status': 'PRESENT',
        }, format='json')
        self.assertEqual(attendance.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.athlete_user)
        over_limit = self.client.post(
            reverse('training-reservations', kwargs={'training_id': next_training.pk}),
            {},
            format='json',
        )

        self.assertEqual(over_limit.status_code, status.HTTP_409_CONFLICT)

    def test_marking_absent_releases_membership_class_for_another_booking(self):
        self.plan.classes_per_week = 1
        self.plan.save(update_fields=['classes_per_week'])
        first_training = self.create_training()
        second_training = self.create_training()
        second_training.start_time = '19:00:00'
        second_training.save(update_fields=['start_time'])
        self.client.force_authenticate(user=self.athlete_user)
        reservation = self.client.post(
            reverse('training-reservations', kwargs={'training_id': first_training.pk}),
            {},
            format='json',
        )
        self.assertEqual(reservation.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.admin_user)
        attendance = self.client.post(reverse('attendance-list-create'), {
            'athlete': self.athlete.pk,
            'training': first_training.pk,
            'status': 'ABSENT',
        }, format='json')
        self.assertEqual(attendance.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.athlete_user)
        replacement = self.client.post(
            reverse('training-reservations', kwargs={'training_id': second_training.pk}),
            {},
            format='json',
        )
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)

    def test_athlete_without_an_active_membership_cannot_reserve(self):
        PlanMembership.objects.filter(user=self.athlete_user).update(status='EXPIRED')
        training = self.create_training()
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.post(
            reverse('training-reservations', kwargs={'training_id': training.pk}),
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_training_reports_active_reservation_count(self):
        training = self.create_training(capacity=2)
        TrainingReservation.objects.create(training=training, athlete=self.athlete)
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(reverse('training-detail', kwargs={'pk': training.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reserved_count'], 1)

    def test_reservation_duplicate_and_full_capacity_are_rejected(self):
        training = self.create_training(capacity=1)
        self.client.force_authenticate(user=self.athlete_user)
        reservation_url = reverse('training-reservations', kwargs={'training_id': training.pk})

        first_response = self.client.post(reservation_url, {}, format='json')
        duplicate_response = self.client.post(reservation_url, {}, format='json')

        other_athlete = Athlete.objects.create(
            club=self.club,
            first_name='Pedro',
            last_name='Lopez',
            status='ACTIVE',
            assigned_trainer=self.trainer_user,
        )
        self.client.force_authenticate(user=self.trainer_user)
        full_response = self.client.post(reservation_url, {'athlete': other_athlete.pk}, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(full_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(TrainingReservation.objects.filter(training=training, status='RESERVED').count(), 1)

    def test_cancelling_reservation_releases_capacity(self):
        training = self.create_training(capacity=1)
        reservation = TrainingReservation.objects.create(training=training, athlete=self.athlete)
        self.client.force_authenticate(user=self.athlete_user)

        cancel_response = self.client.post(
            reverse('training-reservation-cancel', kwargs={
                'training_id': training.pk,
                'reservation_id': reservation.pk,
            }),
            {},
            format='json',
        )
        rebook_response = self.client.post(
            reverse('training-reservations', kwargs={'training_id': training.pk}),
            {},
            format='json',
        )

        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data['status'], 'CANCELLED')
        self.assertEqual(rebook_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TrainingReservation.objects.filter(training=training, status='RESERVED').count(), 1)

    def test_athlete_cannot_reserve_class_from_another_club(self):
        training = self.create_training(club=self.other_club)
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.post(
            reverse('training-reservations', kwargs={'training_id': training.pk}),
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_athlete_only_sees_general_or_own_group_classes(self):
        own_group_training = self.create_training()
        own_group_training.group = self.group
        own_group_training.save(update_fields=['group'])
        general_training = self.create_training()
        other_group = Group.objects.create(club=self.club, name='Competidores', schedule='Martes')
        other_group_training = self.create_training()
        other_group_training.group = other_group
        other_group_training.save(update_fields=['group'])
        self.client.force_authenticate(user=self.athlete_user)

        response = self.client.get(reverse('training-list-create'))
        visible_ids = {row['id'] for row in response.data['results']}
        other_group_response = self.client.post(
            reverse('training-reservations', kwargs={'training_id': other_group_training.pk}),
            {},
            format='json',
        )

        self.assertEqual(visible_ids, {own_group_training.pk, general_training.pk})
        self.assertEqual(other_group_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_trainer_only_lists_and_manages_own_classes(self):
        own_training = self.create_training()
        other_trainer = User.objects.create_user(
            username='other-trainer', email='other-trainer@test.com', password='Password123!',
            club=self.club, role=self.trainer_role,
        )
        other_training = self.create_training()
        other_training.trainer = other_trainer
        other_training.save(update_fields=['trainer'])
        self.client.force_authenticate(user=self.trainer_user)

        response = self.client.get(reverse('training-list-create'))
        detail_response = self.client.get(reverse('training-detail', kwargs={'pk': other_training.pk}))

        self.assertEqual([row['id'] for row in response.data['results']], [own_training.pk])
        self.assertEqual(detail_response.status_code, status.HTTP_403_FORBIDDEN)
