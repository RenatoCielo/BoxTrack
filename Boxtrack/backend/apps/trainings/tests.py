from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.groups.models import Group
from apps.trainings.models import Training, TrainingReservation


class TrainingTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Demo', email='demo@club.com')
        self.other_club = Club.objects.create(name='Otro Club', email='otro@club.com')
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

    def create_training(self, capacity=20, club=None):
        return Training.objects.create(
            club=club or self.club,
            title='Clase técnica',
            scheduled_date='2026-10-10',
            start_time='18:00:00',
            duration_minutes=60,
            capacity=capacity,
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
