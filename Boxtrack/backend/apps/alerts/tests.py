from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.alerts.models import Alert
from apps.clubs.models import Club


class AlertTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Alertas', email='alerts@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-alerts@test.com')
        admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        self.admin = User.objects.create_user(username='alert-admin', password='Password123!', club=self.club, role=admin_role)
        self.trainer = User.objects.create_user(username='alert-trainer', password='Password123!', club=self.club, role=trainer_role)
        self.alert = Alert.objects.create(club=self.other_club, title='Alerta privada', message='No mostrar')

    def test_staff_can_create_and_resolve_club_alert(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('alert-list-create'), {
            'title': 'Revisar asistencia', 'message': 'Control semanal', 'level': 'WARNING'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        alert_id = response.data['id']
        update_response = self.client.patch(reverse('alert-detail', kwargs={'pk': alert_id}), {'is_resolved': True}, format='json')

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(update_response.data['resolved_at'])

    def test_other_club_alert_is_not_visible(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(reverse('alert-detail', kwargs={'pk': self.alert.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_athlete_cannot_manage_alerts(self):
        athlete_role = Role.objects.create(name='ATHLETE', description='Deportista')
        athlete = User.objects.create_user(username='alert-athlete', password='Password123!', club=self.club, role=athlete_role)
        self.client.force_authenticate(user=athlete)
        response = self.client.get(reverse('alert-list-create'))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)