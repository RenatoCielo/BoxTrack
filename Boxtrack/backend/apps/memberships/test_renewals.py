"""Pruebas de renovación de membresías (P3). Los pagos online usan un proveedor simulado (mock): no hay llamadas reales a Mercado Pago."""
from datetime import timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.memberships.models import Membership, MembershipPayment, MembershipPlan, MembershipSettings, expire_overdue_memberships
from apps.memberships.test_payments import FETCH, PREFERENCE, MembershipPaymentBase
from apps.memberships.renewals import RENEWAL_WINDOW_DAYS
from apps.notifications.models import Notification


class RenewalBase(MembershipPaymentBase):
    def today(self):
        return timezone.localdate()

    def state(self, user=None):
        self.client.force_authenticate(user=user or self.athlete_user)
        return self.client.get(reverse('membership-renewal'))

    def renew(self, method='MANUAL', plan=None, user=None, extra=None):
        self.client.force_authenticate(user=user or self.athlete_user)
        body = {'method': method, **(extra or {})}
        if plan is not None:
            body['plan'] = plan.pk
        with mock.patch(PREFERENCE, return_value=('https://mp.test/checkout/renew', 'pref-r')):
            return self.client.post(reverse('membership-renewal'), body, format='json')

    def confirm(self, membership):
        self.client.force_authenticate(user=self.admin)
        return self.client.post(reverse('membership-review', kwargs={'pk': membership.pk}), {'decision': 'CONFIRM'}, format='json')

    def expired_membership(self):
        membership = self.activate(days_left=0)
        Membership.objects.filter(pk=membership.pk).update(status='EXPIRED', end_date=self.today() - timedelta(days=3))
        membership.refresh_from_db()
        return membership


class RenewalStateTests(RenewalBase):
    def test_states_are_computed_on_the_server(self):
        self.assertEqual(self.state().data['state'], 'NONE')
        self.assertFalse(self.state().data['can_renew'])

        active = self.activate(days_left=RENEWAL_WINDOW_DAYS + 20)
        data = self.state().data
        self.assertEqual((data['state'], data['can_renew']), ('ACTIVE', False))

        Membership.objects.filter(pk=active.pk).update(end_date=self.today() + timedelta(days=5))
        data = self.state().data
        self.assertEqual((data['state'], data['can_renew'], data['days_left']), ('EXPIRING', True, 5))
        self.assertEqual(data['next_start_date'], self.today() + timedelta(days=6))
        self.assertEqual(data['plan']['id'], self.plan.id)
        self.assertNotIn('_base', data)

    def test_expired_membership_can_be_renewed(self):
        self.expired_membership()
        data = self.state().data
        self.assertEqual((data['state'], data['can_renew']), ('EXPIRED', True))
        self.assertEqual(data['next_start_date'], self.today())

    def test_admin_cannot_use_athlete_renewal_and_anonymous_is_rejected(self):
        self.assertEqual(self.state(user=self.admin).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.renew(user=self.admin).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(reverse('membership-renewal')).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_other_club_athlete_does_not_see_this_clubs_state(self):
        self.activate(days_left=3)
        from apps.accounts.models import Role, User
        from apps.athletes.models import Athlete
        other_user = User.objects.create_user(
            username='ath2', email='x@demo.com', password='Password123!', club=self.other_club, role=Role.objects.get(name='ATHLETE'))
        Athlete.objects.create(club=self.other_club, user=other_user, first_name='Ana', last_name='Soto', status='ACTIVE')
        data = self.state(user=other_user).data
        self.assertEqual((data['state'], data['membership']), ('NONE', None))


class ManualRenewalTests(RenewalBase):
    def test_early_renewal_keeps_paid_days_and_history(self):
        current = self.activate(days_left=5)
        original_end = current.end_date
        response = self.renew()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        renewal = Membership.objects.get(pk=response.data['membership']['id'])
        self.assertEqual((renewal.status, renewal.renewal_of_id), ('PENDING', current.pk))
        self.assertIsNone(response.data['payment'])

        confirmed = self.confirm(renewal)
        self.assertEqual(confirmed.status_code, status.HTTP_200_OK, confirmed.data)
        renewal.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(renewal.status, 'SCHEDULED')
        self.assertEqual(renewal.start_date, original_end + timedelta(days=1))
        self.assertEqual(renewal.end_date, renewal.start_date + timedelta(days=30))
        self.assertEqual((current.status, current.end_date), ('ACTIVE', original_end))
        self.assertEqual(Membership.objects.filter(athlete=self.athlete).count(), 2)
        note = Notification.objects.filter(user=self.athlete_user, title='Renovación aprobada').first()
        self.assertIsNotNone(note)
        self.assertIn(f'{renewal.start_date:%d/%m/%Y}', note.message)

    def test_late_renewal_starts_on_confirmation_day(self):
        previous = self.expired_membership()
        response = self.renew()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        renewal = Membership.objects.get(pk=response.data['membership']['id'])
        self.assertEqual(renewal.renewal_of_id, previous.pk)
        self.confirm(renewal)
        renewal.refresh_from_db()
        self.assertEqual((renewal.status, renewal.start_date), ('ACTIVE', self.today()))
        self.assertEqual(renewal.end_date, self.today() + timedelta(days=30))
        previous.refresh_from_db()
        self.assertEqual((previous.status, previous.end_date), ('EXPIRED', self.today() - timedelta(days=3)))

    def test_renewal_too_early_or_without_membership_is_rejected(self):
        self.assertEqual(self.renew().status_code, status.HTTP_409_CONFLICT)
        self.activate(days_left=RENEWAL_WINDOW_DAYS + 5)
        response = self.renew()
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Membership.objects.count(), 1)

    def test_duplicate_requests_do_not_create_two_renewals(self):
        self.activate(days_left=2)
        self.assertEqual(self.renew().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.renew().status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Membership.objects.filter(status='PENDING').count(), 1)

    def test_no_second_renewal_while_one_is_scheduled_and_no_new_purchase(self):
        self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        self.confirm(renewal)
        self.assertEqual(self.renew().status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.request_plan().status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.state().data['state'], 'SCHEDULED')

    def test_price_and_duration_come_from_the_database(self):
        self.activate(days_left=2)
        premium = MembershipPlan.objects.create(club=self.club, name='Trimestral', price=80000, duration_days=90)
        response = self.renew(plan=premium, extra={'price_paid': 1, 'duration_days': 1, 'amount': 1, 'status': 'ACTIVE'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        membership = Membership.objects.get(pk=response.data['membership']['id'])
        self.assertEqual((membership.price_paid, membership.duration_days, membership.status), (80000, 90, 'PENDING'))

    def test_plan_of_another_club_or_inactive_is_rejected(self):
        self.activate(days_left=2)
        self.assertEqual(self.renew(plan=self.other_plan).status_code, status.HTTP_404_NOT_FOUND)
        inactive = MembershipPlan.objects.create(club=self.club, name='Viejo', price=1000, duration_days=10, is_active=False)
        self.assertEqual(self.renew(plan=inactive).status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Membership.objects.filter(status='PENDING').exists())

    def test_default_plan_inactive_requires_choosing_another(self):
        self.activate(days_left=2)
        self.plan.is_active = False
        self.plan.save()
        self.assertEqual(self.renew().status_code, status.HTTP_409_CONFLICT)
        self.assertIsNone(self.state().data['plan'])

    def test_invalid_method_and_plan_values(self):
        self.activate(days_left=2)
        self.assertEqual(self.renew(method='TARJETA').status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(user=self.athlete_user)
        bad = self.client.post(reverse('membership-renewal'), {'plan': 'abc'}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_of_other_club_cannot_confirm_and_reject_keeps_original(self):
        current = self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        self.client.force_authenticate(user=self.other_admin)
        self.assertEqual(
            self.client.post(reverse('membership-review', kwargs={'pk': renewal.pk}), {'decision': 'CONFIRM'}, format='json').status_code,
            status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(user=self.admin)
        rejected = self.client.post(reverse('membership-review', kwargs={'pk': renewal.pk}), {'decision': 'REJECT', 'note': 'Sin pago'}, format='json')
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        renewal.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual((renewal.status, current.status), ('REJECTED', 'ACTIVE'))
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Solicitud de membresía rechazada').exists())
        self.assertEqual(self.renew().status_code, status.HTTP_201_CREATED)

    def test_admin_cancelling_a_scheduled_renewal_notifies_the_athlete(self):
        self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        self.confirm(renewal)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(reverse('membership-review', kwargs={'pk': renewal.pk}), {'decision': 'CANCEL', 'note': 'Error'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, 'CANCELLED')
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Membresía cancelada').exists())

    def test_admin_cannot_manually_confirm_online_payment_in_review(self):
        self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        MembershipPayment.objects.create(
            club=self.club, user=self.athlete_user, plan=self.plan, membership=renewal,
            amount=self.plan.price, currency=self.plan.currency, status='REVIEW',
            payment_provider='TRANSBANK', expires_at=timezone.now(),
        )
        self.assertEqual(self.confirm(renewal).status_code, status.HTTP_409_CONFLICT)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, 'PENDING')

    def test_athlete_cancels_manual_renewal_and_is_notified(self):
        self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        self.client.force_authenticate(user=self.athlete_user)
        response = self.client.post(reverse('membership-review', kwargs={'pk': renewal.pk}), {'decision': 'CANCEL'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        note = Notification.objects.get(user=self.athlete_user, title='Membresía cancelada')
        self.assertIn('por ti', note.message)


class ScheduledMembershipTests(RenewalBase):
    def schedule(self):
        current = self.activate(days_left=2)
        renewal = Membership.objects.get(pk=self.renew().data['membership']['id'])
        self.confirm(renewal)
        renewal.refresh_from_db()
        return current, renewal

    def test_scheduled_renewal_becomes_active_when_current_one_ends(self):
        current, renewal = self.schedule()
        expire_overdue_memberships(self.club.id)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, 'SCHEDULED')

        Membership.objects.filter(pk=current.pk).update(end_date=self.today() - timedelta(days=1))
        Membership.objects.filter(pk=renewal.pk).update(start_date=self.today())
        expire_overdue_memberships(self.club.id)
        current.refresh_from_db()
        renewal.refresh_from_db()
        self.assertEqual((current.status, renewal.status), ('EXPIRED', 'ACTIVE'))
        self.assertEqual(Membership.objects.filter(athlete=self.athlete, status='ACTIVE').count(), 1)

    def test_scheduled_period_already_over_is_expired_not_activated(self):
        current, renewal = self.schedule()
        Membership.objects.filter(pk=current.pk).update(end_date=self.today() - timedelta(days=40))
        Membership.objects.filter(pk=renewal.pk).update(
            start_date=self.today() - timedelta(days=39),
            end_date=self.today() - timedelta(days=9),
        )
        expire_overdue_memberships(self.club.id)
        renewal.refresh_from_db()
        self.assertEqual(renewal.status, 'EXPIRED')
        self.assertEqual(self.state().data['membership'], renewal.pk)
        self.assertEqual(self.state().data['state'], 'EXPIRED')

    def test_database_prevents_two_scheduled_or_two_pending_memberships(self):
        current, renewal = self.schedule()
        make = lambda status_: Membership.objects.create(
            club=self.club, athlete=self.athlete, plan=self.plan, plan_name='Mensual', price_paid=1, duration_days=1, status=status_)
        make('PENDING')
        for status_ in ('SCHEDULED', 'PENDING', 'ACTIVE'):
            with self.assertRaises(IntegrityError), transaction.atomic():
                make(status_)

    def test_required_membership_covers_classes_in_the_renewed_period(self):
        current, renewal = self.schedule()
        MembershipSettings.objects.create(club=self.club, require_active_membership=True)
        inside_renewal = self.make_training(current.end_date + timedelta(days=3))
        self.assertEqual(self.reserve(inside_renewal).status_code, status.HTTP_201_CREATED)
        beyond = self.make_training(renewal.end_date + timedelta(days=3), title='Tarde')
        blocked = self.reserve(beyond)
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)

    def test_required_membership_blocks_when_renewal_is_only_pending(self):
        current = self.activate(days_left=2)
        self.renew()
        MembershipSettings.objects.create(club=self.club, require_active_membership=True)
        after_end = self.make_training(current.end_date + timedelta(days=2))
        self.assertEqual(self.reserve(after_end).status_code, status.HTTP_409_CONFLICT)


class OnlineRenewalTests(RenewalBase):
    def start_online(self, plan=None):
        response = self.renew(method='ONLINE', plan=plan)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return MembershipPayment.objects.get(pk=response.data['payment']['id'])

    def test_online_renewal_is_pending_until_the_verified_webhook(self):
        current = self.activate(days_left=4)
        payment = self.start_online()
        self.assertEqual((payment.status, payment.membership.status, payment.amount), ('PENDING', 'PENDING', self.plan.price))
        self.assertTrue(payment.membership.renewal_of_id == current.pk)
        self.assertTrue(MembershipPayment.objects.get(pk=payment.pk).membership.renewal_of_id)

        self.client.force_authenticate(user=self.athlete_user)
        listing = self.client.get(reverse('membership-payment-list-create'))
        self.assertTrue(listing.data[0]['is_renewal'])

        # Volver de la página de éxito o una notificación pendiente no activa nada.
        self.client.get(f'/memberships?payment=success&ref={payment.pk}')
        self.notify(self.provider_payment(payment, status_='in_process'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

        self.notify(self.provider_payment(payment))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('APPROVED', 'SCHEDULED'))
        self.assertEqual(payment.membership.start_date, current.end_date + timedelta(days=1))

    def test_repeated_webhook_does_not_duplicate_renewals(self):
        self.activate(days_left=4)
        payment = self.start_online()
        provider = self.provider_payment(payment)
        for _ in range(3):
            self.assertEqual(self.notify(provider).status_code, status.HTTP_200_OK)
        self.assertEqual(Membership.objects.filter(athlete=self.athlete).count(), 2)
        self.assertEqual(Membership.objects.filter(athlete=self.athlete, status='SCHEDULED').count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.athlete_user, title='Renovación aprobada').count(), 1)

    def test_rejected_renewal_keeps_current_membership_and_allows_retry(self):
        current = self.activate(days_left=4)
        payment = self.start_online()
        self.notify(self.provider_payment(payment, status_='rejected'))
        payment.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status, current.status), ('REJECTED', 'CANCELLED', 'ACTIVE'))
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Pago no aprobado').exists())
        retry = self.start_online()
        self.assertNotEqual(retry.pk, payment.pk)
        self.assertEqual(retry.membership.renewal_of_id, current.pk)

    def test_duplicate_online_request_reuses_the_open_checkout(self):
        self.activate(days_left=4)
        first = self.start_online()
        again = self.renew(method='ONLINE')
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(again.data['payment']['id'], first.pk)
        self.assertEqual(MembershipPayment.objects.count(), 1)
        self.assertEqual(Membership.objects.filter(status='PENDING').count(), 1)

    def test_mercado_pago_does_not_reuse_transbank_checkout(self):
        self.activate(days_left=4)
        payment = self.start_online()
        MembershipPayment.objects.filter(pk=payment.pk).update(payment_provider='TRANSBANK')
        response = self.renew(method='ONLINE')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(MembershipPayment.objects.count(), 1)

    def test_athlete_can_cancel_pending_online_renewal_without_touching_current(self):
        current = self.activate(days_left=4)
        payment = self.start_online()
        self.client.force_authenticate(user=self.athlete_user)
        response = self.client.delete(reverse('membership-payment-detail', kwargs={'pk': payment.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status, current.status), ('CANCELLED', 'CANCELLED', 'ACTIVE'))
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Pago cancelado').exists())

    def test_provider_cancellation_notifies_athlete(self):
        self.activate(days_left=4)
        payment = self.start_online()
        self.notify(self.provider_payment(payment, status_='cancelled'))
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Pago cancelado').exists())

    def test_expired_checkout_notifies_and_frees_the_athlete(self):
        self.activate(days_left=4)
        payment = self.start_online()
        MembershipPayment.objects.filter(pk=payment.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        self.client.force_authenticate(user=self.athlete_user)
        self.client.get(reverse('membership-payment-list-create'))
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('EXPIRED', 'CANCELLED'))
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Pago vencido').exists())

    def test_amount_mismatch_does_not_activate_renewal(self):
        self.activate(days_left=4)
        payment = self.start_online()
        response = self.notify(self.provider_payment(payment, amount=1))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status), ('PENDING', 'PENDING'))

    def test_refund_of_scheduled_renewal_cancels_only_the_renewal(self):
        current = self.activate(days_left=4)
        payment = self.start_online()
        self.notify(self.provider_payment(payment))
        self.notify(self.provider_payment(payment, status_='refunded'))
        payment.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual((payment.status, payment.membership.status, current.status), ('REFUNDED', 'CANCELLED', 'ACTIVE'))

    def test_late_payment_that_cannot_be_applied_requires_review_and_notifies_both(self):
        current = self.activate(days_left=4)
        payment = self.start_online()
        self.notify(self.provider_payment(payment, status_='cancelled'))
        payment.refresh_from_db()
        self.assertEqual(payment.membership.status, 'CANCELLED')
        # Mientras tanto el deportista inició otra renovación, así que el cobro tardío no puede aplicarse solo.
        second = self.start_online()
        late = self.provider_payment(payment, pid='7777')
        self.notify(late)
        payment.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(payment.status, 'REVIEW')
        self.assertEqual(second.membership.status, 'PENDING')
        self.assertTrue(Notification.objects.filter(user=self.athlete_user, title='Tu pago requiere revisión').exists())
        self.assertTrue(Notification.objects.filter(user=self.admin, title='Pago aprobado que requiere revisión').exists())
        current.refresh_from_db()
        self.assertEqual(current.status, 'ACTIVE')

    def test_online_renewal_unavailable_without_credentials_keeps_manual_option(self):
        self.activate(days_left=4)
        with mock.patch.dict('os.environ', {'MERCADOPAGO_ACCESS_TOKEN': ''}):
            response = self.renew(method='ONLINE')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(Membership.objects.filter(status='PENDING').exists())
        self.assertEqual(self.renew().status_code, status.HTTP_201_CREATED)

    def test_provider_failure_leaves_no_pending_renewal(self):
        self.activate(days_left=4)
        self.client.force_authenticate(user=self.athlete_user)
        with mock.patch(PREFERENCE, side_effect=OSError('caído')):
            response = self.client.post(reverse('membership-renewal'), {'method': 'ONLINE'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(Membership.objects.filter(status='PENDING').exists())
        self.assertEqual(self.renew(method='ONLINE').status_code, status.HTTP_201_CREATED)

    def test_store_webhook_regression_numeric_reference_is_untouched(self):
        with mock.patch(FETCH, return_value={'id': '1', 'status': 'approved', 'external_reference': '999999'}):
            from apps.memberships.test_payments import signed_webhook
            response = signed_webhook(self.anon, '1')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
