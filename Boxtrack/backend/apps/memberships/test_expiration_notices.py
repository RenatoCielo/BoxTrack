from datetime import timedelta

from django.utils import timezone

from apps.memberships.models import Membership, MembershipExpirationNotice
from apps.memberships.expiration_notices import send_membership_expiration_notices
from apps.memberships.tests import MembershipBase
from apps.notifications.models import Notification


class MembershipExpirationNoticeTests(MembershipBase):
    def test_due_milestones_are_delivered_once_to_the_linked_athlete(self):
        today = timezone.localdate()
        membership = self.activate(days_left=30)
        for days in (7, 3, 1):
            Membership.objects.filter(pk=membership.pk).update(end_date=today + timedelta(days=days))
            self.assertEqual(send_membership_expiration_notices(today), 1)

        self.assertEqual(send_membership_expiration_notices(today), 0)
        self.assertEqual(MembershipExpirationNotice.objects.filter(membership=membership).count(), 3)
        self.assertEqual(Notification.objects.filter(user=self.athlete_user).count(), 3)
        self.assertTrue(all(self.club.name in notice.message for notice in Notification.objects.filter(user=self.athlete_user)))

    def test_expired_notice_is_sent_once_and_contains_plan_and_expiry_date(self):
        today = timezone.localdate()
        membership = self.activate(days_left=0)
        expiry = today - timedelta(days=1)
        Membership.objects.filter(pk=membership.pk).update(status='EXPIRED', end_date=expiry)

        self.assertEqual(send_membership_expiration_notices(today), 1)
        self.assertEqual(send_membership_expiration_notices(today), 0)
        notice = Notification.objects.get(user=self.athlete_user)
        self.assertIn(self.plan.name, notice.message)
        self.assertIn(expiry.strftime('%d/%m/%Y'), notice.message)

    def test_replacement_membership_suppresses_old_expiration_alert(self):
        today = timezone.localdate()
        expired = self.activate(days_left=0)
        Membership.objects.filter(pk=expired.pk).update(status='EXPIRED', end_date=today - timedelta(days=1))
        Membership.objects.create(
            club=self.club, athlete=self.athlete, plan=self.plan, plan_name=self.plan.name, price_paid=self.plan.price,
            currency=self.plan.currency, duration_days=self.plan.duration_days, status='ACTIVE',
            start_date=today, end_date=today + timedelta(days=30),
        )

        self.assertEqual(send_membership_expiration_notices(today), 0)
        self.assertFalse(Notification.objects.filter(user=self.athlete_user).exists())

    def test_user_from_another_club_is_never_notified(self):
        membership = self.activate(days_left=7)
        self.athlete.user = self.other_admin
        self.athlete.save(update_fields=['user'])
        self.assertEqual(send_membership_expiration_notices(timezone.localdate()), 0)
        self.assertFalse(Notification.objects.filter(user=self.other_admin).exists())
