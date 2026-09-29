from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club
from apps.notifications.models import Notification


class NotificationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Club Avisos', email='notifications@test.com')
        self.other_club = Club.objects.create(name='Otro Club', email='other-notifications@test.com')
        role = Role.objects.create(name='ATHLETE', description='Deportista')
        self.user = User.objects.create_user(username='notification-user', password='Password123!', club=self.club, role=role)
        self.other_user = User.objects.create_user(username='other-notification-user', password='Password123!', club=self.club, role=role)
        self.notice = Notification.objects.create(club=self.club, user=self.user, title='Cupo reservado', message='Listo', notification_type='TRAINING')
        self.other_notice = Notification.objects.create(club=self.club, user=self.other_user, title='Privada', message='Oculta')
        self.client.force_authenticate(user=self.user)

    def test_user_only_sees_and_can_read_own_notifications(self):
        response = self.client.get(reverse('notification-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row['id'] for row in response.data['results']], [self.notice.pk])

        update_response = self.client.patch(reverse('notification-detail', kwargs={'pk': self.notice.pk}), {'is_read': True}, format='json')
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(update_response.data['is_read'])

    def test_user_cannot_read_another_users_notification(self):
        response = self.client.get(reverse('notification-detail', kwargs={'pk': self.other_notice.pk}))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)