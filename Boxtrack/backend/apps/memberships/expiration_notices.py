from datetime import timedelta

from django.db import transaction
from django.db.models import Exists, OuterRef, F
from django.utils import timezone

from apps.memberships.models import Membership, MembershipExpirationNotice, expire_overdue_memberships
from apps.notifications.models import Notification


REMINDERS = {
    7: ('DAYS_7', 'Tu membresía vence en 7 días'),
    3: ('DAYS_3', 'Tu membresía vence en 3 días'),
    1: ('DAY_1', 'Tu membresía vence mañana'),
}


def send_membership_expiration_notices(today=None):
    """Create one in-app notification for each due milestone, safely repeatable each day."""
    today = today or timezone.localdate()
    expire_overdue_memberships()
    sent = 0

    replacement = Membership.objects.filter(
        athlete_id=OuterRef('athlete_id'), created_at__gt=OuterRef('created_at'),
        status__in=['ACTIVE', 'SCHEDULED'],
    )
    for days_left, (code, title) in REMINDERS.items():
        memberships = Membership.objects.select_related('club', 'athlete__user').annotate(
            has_replacement=Exists(replacement),
        ).filter(
            status='ACTIVE', end_date=today + timedelta(days=days_left), athlete__user__isnull=False,
            athlete__user__is_active=True, athlete__user__club_id=F('club_id'),
            athlete__club_id=F('club_id'), has_replacement=False,
        )
        for membership in memberships:
            with transaction.atomic():
                _, created = MembershipExpirationNotice.objects.get_or_create(
                    membership=membership, notice_code=code, defaults={'user': membership.athlete.user},
                )
                if not created:
                    continue
                Notification.objects.create(
                    club=membership.club,
                    user=membership.athlete.user,
                    title=title,
                    message=(f"El plan {membership.plan_name} de {membership.club.name} "
                             f"vence el {membership.end_date:%d/%m/%Y}. Puedes revisar la renovación en Membresías."),
                    notification_type='INFO',
                )
                sent += 1

    expired = Membership.objects.select_related('club', 'athlete__user').annotate(
        has_replacement=Exists(replacement),
    ).filter(
        status='EXPIRED', end_date__lt=today, end_date__gte=today - timedelta(days=7),
        athlete__user__isnull=False, athlete__user__is_active=True,
        athlete__user__club_id=F('club_id'), athlete__club_id=F('club_id'), has_replacement=False,
    )
    for membership in expired:
        with transaction.atomic():
            _, created = MembershipExpirationNotice.objects.get_or_create(
                membership=membership, notice_code='EXPIRED', defaults={'user': membership.athlete.user},
            )
            if not created:
                continue
            Notification.objects.create(
                club=membership.club,
                user=membership.athlete.user,
                title='Tu membresía venció',
                message=(f"El plan {membership.plan_name} de {membership.club.name} "
                         f"venció el {membership.end_date:%d/%m/%Y}. Revisa las opciones de renovación en Membresías."),
                notification_type='INFO',
            )
            sent += 1
    return sent
