from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Role, User
from apps.clubs.models import Club


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

    def test_pending_list_includes_submitted_clubs_but_not_approved(self):
        submitted = Club.objects.create(name='Con documentos', verification_status='IN_REVIEW')
        Club.objects.create(name='Aprobado', verification_status='APPROVED')
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get(reverse('club-pending-list'))
        self.assertEqual({club['id'] for club in response.data['results']}, {self.club.id, submitted.id})
        response = self.client.patch(reverse('club-review', kwargs={'pk': submitted.pk}), {'verification_status': 'APPROVED'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submitted.refresh_from_db()
        self.assertEqual(submitted.verification_status, 'APPROVED')
class ClubBrandingTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.club = Club.objects.create(name='Gimnasio Norte')
        self.other_club = Club.objects.create(name='Gimnasio Sur')
        self.admin_role = Role.objects.create(name='ADMIN', description='Administrador')
        self.trainer_role = Role.objects.create(name='TRAINER', description='Entrenador')
        self.admin = User.objects.create_user(username='brand-admin', password='Password123!', club=self.club, role=self.admin_role)
        self.other_admin = User.objects.create_user(username='other-brand-admin', password='Password123!', club=self.other_club, role=self.admin_role)
        self.trainer = User.objects.create_user(username='brand-trainer', password='Password123!', club=self.club, role=self.trainer_role)

    def tearDown(self):
        if self.club.logo:
            self.club.logo.delete(save=False)

    def test_admin_initializes_empty_discipline_without_overwriting_other_clubs(self):
        self.other_club.disciplines = ['MMA', 'Boxeo']
        self.other_club.save(update_fields=['disciplines'])
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.post(reverse('club-discipline-initialize')).status_code, 403)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('club-discipline-initialize'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['disciplines'], ['Boxeo'])
        self.assertEqual(self.client.post(reverse('club-discipline-initialize')).status_code, 409)
        self.other_club.refresh_from_db()
        self.assertEqual(self.other_club.disciplines, ['MMA', 'Boxeo'])

    @staticmethod
    def image_upload(name='logo.png'):
        content = BytesIO()
        Image.new('RGB', (8, 8), color='red').save(content, format='PNG')
        return SimpleUploadedFile(name, content.getvalue(), content_type='image/png')

    def test_admin_saves_and_reads_only_own_club_branding(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(reverse('club-branding'), {
            'primary_color': '#123abc', 'accent_color': '#253647', 'logo': self.image_upload(),
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.club.refresh_from_db()
        self.other_club.refresh_from_db()
        self.assertEqual((self.club.primary_color, self.club.accent_color), ('#123ABC', '#253647'))
        self.assertEqual((self.other_club.primary_color, self.other_club.accent_color), ('#D7263D', '#1F2937'))
        self.assertTrue(self.club.logo.name.startswith('clubs/logos/'))

        profile = self.client.get('/api/auth/profile/').data['club']
        self.assertEqual((profile['primary_color'], profile['accent_color']), ('#123ABC', '#253647'))
        self.assertTrue(profile['logo'].endswith(self.club.logo.name))

    def test_invalid_color_and_image_are_rejected(self):
        self.client.force_authenticate(user=self.admin)
        invalid_color = self.client.patch(reverse('club-branding'), {'primary_color': 'red'}, format='multipart')
        invalid_image = self.client.patch(reverse('club-branding'), {
            'logo': SimpleUploadedFile('broken.png', b'not-an-image', content_type='image/png'),
        }, format='multipart')
        self.assertEqual(invalid_color.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_image.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_admin_of_own_club_can_change_branding(self):
        self.client.force_authenticate(user=self.trainer)
        self.assertEqual(self.client.patch(reverse('club-branding'), {'primary_color': '#123456'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.other_admin)
        self.assertEqual(self.client.get(reverse('club-branding')).data['name'], self.other_club.name)
