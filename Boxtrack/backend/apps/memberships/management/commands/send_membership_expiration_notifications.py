from django.core.management.base import BaseCommand

from apps.memberships.expiration_notices import send_membership_expiration_notices


class Command(BaseCommand):
    help = 'Envía avisos internos únicos de vencimiento de membresías.'

    def handle(self, *args, **options):
        count = send_membership_expiration_notices()
        self.stdout.write(self.style.SUCCESS(f'Avisos de vencimiento creados: {count}'))
