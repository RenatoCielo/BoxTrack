"""Pago online de membresías con Mercado Pago.

Reutiliza la integración de la tienda (`apps.store.views`): misma configuración por variables de entorno,
misma firma de webhook y misma consulta del pago a la API oficial. La membresía solo se activa cuando
el proveedor confirma un pago aprobado con el monto y la moneda registrados en el servidor.
"""
import logging
import os
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.accounts.models import User
from apps.athletes.models import Athlete
from apps.memberships.models import Membership, MembershipPayment, MembershipPlan, expire_overdue_memberships
from apps.memberships.renewals import activate_pending_membership, create_renewal_membership
from apps.notifications.models import Notification
from apps.store.views import StoreUnavailable, mercadopago_configured, post_mercadopago_preference
from apps.store.transbank import TransbankUnavailable, clp_amount, response_value, transbank_configured, webpay_transaction

logger = logging.getLogger(__name__)

CHECKOUT_MINUTES = 30
OPEN_STATUSES = ['PENDING', 'ACTIVE', 'SCHEDULED']
EXTERNAL_PREFIX = 'membership:'


class PaymentConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'El deportista ya tiene una membresía activa o pendiente de pago.'
    default_code = 'conflict'


def notify_user(club, user, title, message):
    if user:
        Notification.objects.create(club=club, user=user, title=title, message=message, notification_type='INFO')


def notify_admins(club, title, message):
    for admin in User.objects.filter(club=club, role__name='ADMIN', is_active=True):
        Notification.objects.create(club=club, user=admin, title=title, message=message, notification_type='ALERT')


def expire_pending_payments(club_id):
    """Cierra los checkouts vencidos y libera al deportista para volver a intentarlo."""
    overdue = MembershipPayment.objects.filter(club_id=club_id, status='PENDING', expires_at__lte=timezone.now())
    with transaction.atomic():
        for payment in overdue.select_for_update().select_related('membership'):
            payment.status = 'EXPIRED'
            payment.save(update_fields=['status', 'updated_at'])
            if payment.membership.status == 'PENDING':
                payment.membership.status = 'CANCELLED'
                payment.membership.review_note = 'El pago online venció sin confirmarse.'
                payment.membership.save(update_fields=['status', 'review_note', 'updated_at'])
                notify_user(payment.club, payment.user, 'Pago vencido', f'El pago de tu plan {payment.membership.plan_name}                 venció sin confirmarse. Puedes intentarlo nuevamente desde Membresías.')


def activate_membership(membership, note='Pago online confirmado por el proveedor.'):
    return activate_pending_membership(membership, note=note)


def start_membership_checkout(user, plan_id, renew=False):
    """Crea (o reutiliza) la compra o renovación pendiente y devuelve (pago, creado)."""
    if not mercadopago_configured():
        raise StoreUnavailable('El pago online no está disponible en este momento. Puedes solicitar el plan y pagarlo directamente al club.')
    athlete = get_object_or_404(Athlete, user=user, club_id=user.club_id, status='ACTIVE')
    expire_overdue_memberships(user.club_id)
    expire_pending_payments(user.club_id)
    plan = None
    if not renew:
        # Precio, moneda y duración salen siempre de la base de datos, nunca del cliente.
        plan = get_object_or_404(MembershipPlan, pk=plan_id, club_id=user.club_id, is_active=True)

    try:
        with transaction.atomic():
            Athlete.objects.select_for_update().get(pk=athlete.pk)
            open_membership = Membership.objects.filter(athlete=athlete, status='PENDING').first()
            if open_membership:
                existing = open_membership.payments.filter(status='PENDING').exclude(checkout_url='').first()
                same_plan = plan_id is None or (existing and existing.plan_id == plan_id)
                if existing and same_plan and bool(open_membership.renewal_of_id) == renew:
                    return existing, False
                raise PaymentConflict()
            if renew:
                membership = create_renewal_membership(athlete, plan_id)
                plan = membership.plan
            else:
                if Membership.objects.filter(athlete=athlete, status__in=OPEN_STATUSES).exists():
                    raise PaymentConflict()
                membership = Membership.objects.create(
                    club=plan.club, athlete=athlete, plan=plan, plan_name=plan.name, price_paid=plan.price,
                    currency=plan.currency, duration_days=plan.duration_days, weekly_class_limit=plan.weekly_class_limit,
                )
            payment = MembershipPayment.objects.create(
                club=plan.club, user=user, plan=plan, membership=membership, amount=plan.price, currency=plan.currency,
                expires_at=timezone.now() + timedelta(minutes=CHECKOUT_MINUTES),
            )
    except IntegrityError as error:
        raise PaymentConflict() from error

    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    payload = {
        'items': [{
            'title': f'Membresía {plan.name}',
            'quantity': 1,
            'currency_id': plan.currency,
            'unit_price': float(plan.price),
        }],
        'external_reference': f'{EXTERNAL_PREFIX}{payment.pk}',
        'metadata': {'club_id': plan.club_id, 'user_id': user.pk, 'plan_id': plan.pk, 'membership_id': membership.pk},
        'notification_url': os.getenv('MERCADOPAGO_NOTIFICATION_URL'),
        'back_urls': {
            'success': f'{frontend_url}/memberships?payment=success&ref={payment.pk}',
            'failure': f'{frontend_url}/memberships?payment=failure&ref={payment.pk}',
            'pending': f'{frontend_url}/memberships?payment=pending&ref={payment.pk}',
        },
        'auto_return': 'approved',
        'expiration_date_from': timezone.now().isoformat(),
        'expiration_date_to': payment.expires_at.isoformat(),
        'statement_descriptor': 'BOXTRACK',
    }
    try:
        checkout_url, reference = post_mercadopago_preference(payload)
    except Exception as error:
        with transaction.atomic():
            payment.status = 'CANCELLED'
            payment.save(update_fields=['status', 'updated_at'])
            membership.status = 'CANCELLED'
            membership.review_note = 'No se pudo iniciar el pago online.'
            membership.save(update_fields=['status', 'review_note', 'updated_at'])
        if isinstance(error, StoreUnavailable):
            raise
        raise StoreUnavailable('No se pudo iniciar el pago online. No se realizó ningún cobro; vuelve a intentarlo.') from error
    payment.checkout_url = checkout_url
    payment.payment_reference = str(reference)
    payment.save(update_fields=['checkout_url', 'payment_reference', 'updated_at'])
    return payment, True


def start_transbank_membership_checkout(user, plan_id, request, renew=False):
    """Initialise a Webpay Plus test transaction for a purchase or renewal."""
    if not transbank_configured():
        raise StoreUnavailable('Transbank Webpay Plus no está configurado para pruebas.')
    athlete = get_object_or_404(Athlete, user=user, club_id=user.club_id, status='ACTIVE')
    expire_overdue_memberships(user.club_id)
    expire_pending_payments(user.club_id)
    plan = None
    if not renew:
        plan = get_object_or_404(MembershipPlan, pk=plan_id, club_id=user.club_id, is_active=True)
        amount = clp_amount(plan.price)
        if plan.currency != 'CLP':
            raise PaymentConflict('Transbank Webpay Plus solo admite planes en CLP.')

    try:
        with transaction.atomic():
            Athlete.objects.select_for_update().get(pk=athlete.pk)
            open_membership = Membership.objects.filter(athlete=athlete, status='PENDING').first()
            if open_membership:
                existing = open_membership.payments.filter(
                    payment_provider='TRANSBANK', status='PENDING', checkout_url__gt='',
                ).first()
                same_plan = plan_id is None or (existing and existing.plan_id == plan_id)
                if existing and same_plan and bool(open_membership.renewal_of_id) == renew:
                    return existing, False
                raise PaymentConflict()
            if renew:
                membership = create_renewal_membership(athlete, plan_id)
                plan = membership.plan
                amount = clp_amount(plan.price)
                if plan.currency != 'CLP':
                    raise PaymentConflict('Transbank Webpay Plus solo admite planes en CLP.')
            else:
                if Membership.objects.filter(athlete=athlete, status__in=OPEN_STATUSES).exists():
                    raise PaymentConflict()
                membership = Membership.objects.create(
                    club=plan.club, athlete=athlete, plan=plan, plan_name=plan.name, price_paid=plan.price,
                    currency=plan.currency, duration_days=plan.duration_days, weekly_class_limit=plan.weekly_class_limit,
                )
            payment = MembershipPayment.objects.create(
                club=plan.club, user=user, plan=plan, membership=membership, amount=plan.price, currency=plan.currency,
                payment_provider='TRANSBANK', expires_at=timezone.now() + timedelta(minutes=CHECKOUT_MINUTES),
                transbank_buy_order=f'BTM{membership.pk}{secrets.token_hex(6)}'[:26],
                transbank_session_id=f'BTMS{user.pk}{secrets.token_hex(8)}'[:61],
            )
    except IntegrityError as error:
        raise PaymentConflict() from error

    return_url = request.build_absolute_uri(reverse('transbank-return'))
    try:
        response = webpay_transaction().create(
            payment.transbank_buy_order, payment.transbank_session_id, amount, return_url,
        )
        token = response_value(response, 'token')
        provider_url = response_value(response, 'url')
        if not token or not provider_url:
            raise TransbankUnavailable('Transbank no devolvió una sesión Webpay válida.')
        payment.transbank_token = str(token)
        payment.transbank_url = str(provider_url)
        payment.payment_reference = payment.transbank_buy_order
        payment.checkout_url = request.build_absolute_uri(reverse('transbank-checkout', args=[token]))
        payment.save(update_fields=['transbank_token', 'transbank_url', 'payment_reference', 'checkout_url', 'updated_at'])
    except Exception as error:
        with transaction.atomic():
            payment.status = 'CANCELLED'
            payment.provider_status = 'INITIALIZATION_FAILED'
            payment.save(update_fields=['status', 'provider_status', 'updated_at'])
            membership.status = 'CANCELLED'
            membership.review_note = 'No se pudo iniciar el pago Transbank.'
            membership.save(update_fields=['status', 'review_note', 'updated_at'])
        if isinstance(error, StoreUnavailable):
            raise
        raise StoreUnavailable('No se pudo iniciar el pago Transbank de pruebas; no se activó la membresía.') from error
    return payment, True


def cancel_pending_payments(membership):
    return MembershipPayment.objects.filter(membership=membership, status='PENDING').update(status='CANCELLED', updated_at=timezone.now())


def process_membership_payment(provider_payment, data_id):
    """Aplica una notificación ya autenticada y verificada contra la API de Mercado Pago. Es idempotente."""
    reference = str(provider_payment.get('external_reference') or '')
    try:
        payment_pk = int(reference[len(EXTERNAL_PREFIX):])
    except ValueError:
        return Response({'detail': 'Referencia de pago no válida.'}, status=status.HTTP_400_BAD_REQUEST)
    provider_id = str(provider_payment.get('id') or data_id)
    provider_status = str(provider_payment.get('status') or '').lower()
    ok = Response({'received': True}, status=status.HTTP_200_OK)

    with transaction.atomic():
        payment = MembershipPayment.objects.select_for_update().select_related(
            'membership', 'membership__athlete', 'membership__athlete__user', 'membership__club',
        ).filter(pk=payment_pk).first()
        if not payment:
            return Response({'detail': 'Referencia de pago no válida.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = payment.membership

        if provider_status == 'approved':
            try:
                paid_amount = Decimal(str(provider_payment.get('transaction_amount')))
            except (InvalidOperation, TypeError):
                return Response({'detail': 'El importe del pago no es válido.'}, status=status.HTTP_400_BAD_REQUEST)
            if provider_payment.get('currency_id') != payment.currency or paid_amount != payment.amount:
                logger.warning('Pago de membresía %s con monto o moneda distintos a los registrados.', payment.pk)
                return Response({'detail': 'El importe del pago no coincide con la compra.'}, status=status.HTTP_400_BAD_REQUEST)
            if payment.provider_payment_id == provider_id or payment.status in ('REFUNDED',):
                return ok
            if MembershipPayment.objects.filter(provider_payment_id=provider_id).exclude(pk=payment.pk).exists():
                return Response({'detail': 'El pago ya está asociado a otra compra.'}, status=status.HTTP_400_BAD_REQUEST)
            if payment.provider_payment_id:
                # Segundo cobro aprobado para la misma compra: no se activa nada y se avisa al club.
                logger.warning('Cobro duplicado %s para el pago de membresía %s.', provider_id, payment.pk)
                notify_admins(payment.club, 'Posible cobro duplicado', f'Mercado Pago aprobó un segundo pago ({provider_id}) para la compra #{payment.pk}. Revisa y reembolsa si corresponde.')
                return ok

            payment.provider_payment_id = provider_id
            payment.provider_status = provider_status
            payment.paid_at = timezone.now()
            if membership.status == 'PENDING':
                payment.status = 'APPROVED'
                activate_membership(membership)
            elif membership.status in ('ACTIVE', 'SCHEDULED'):
                payment.status = 'APPROVED'
            else:
                # El pago llegó después de cancelar o vencer la compra: se reactiva solo si no hay otra membresía abierta.
                try:
                    with transaction.atomic():
                        other_open = Membership.objects.filter(
                            athlete=membership.athlete, status__in=OPEN_STATUSES,
                        ).exclude(pk=membership.pk)
                        if membership.renewal_of_id:
                            other_open = other_open.exclude(pk=membership.renewal_of_id)
                        if other_open.exists():
                            raise IntegrityError
                        activate_membership(membership)
                        payment.status = 'APPROVED'
                except IntegrityError:
                    payment.status = 'REVIEW'
                    notify_admins(payment.club, 'Pago aprobado que requiere revisión', f'La compra #{payment.pk} fue cobrada pero la membresía no pudo activarse automáticamente. Revísala y reembolsa si corresponde.')
                    notify_user(payment.club, membership.athlete.user, 'Tu pago requiere revisión', f'Recibimos el pago de tu plan {membership.plan_name}, pero el club debe revisarlo antes de activarlo. Te avisaremos cuando esté resuelto.')
            payment.save()
            return ok

        if provider_status in ('refunded', 'charged_back'):
            if payment.provider_payment_id == provider_id and payment.status in ('APPROVED', 'REVIEW'):
                payment.status = 'REFUNDED'
                payment.provider_status = provider_status
                payment.save(update_fields=['status', 'provider_status', 'updated_at'])
                if membership.status in ('ACTIVE', 'SCHEDULED'):
                    membership.status = 'CANCELLED'
                    membership.review_note = 'El pago fue reembolsado o contracargado.'
                    membership.save(update_fields=['status', 'review_note', 'updated_at'])
                notify_user(payment.club, membership.athlete.user, 'Pago reembolsado', f'El pago de tu plan {membership.plan_name} fue reembolsado y la membresía quedó cancelada.')
            return ok

        if payment.status != 'PENDING':
            return ok

        if provider_status in ('rejected', 'cancelled'):
            payment.status = 'REJECTED' if provider_status == 'rejected' else 'CANCELLED'
            payment.provider_status = provider_status
            payment.save(update_fields=['status', 'provider_status', 'updated_at'])
            if membership.status == 'PENDING':
                membership.status = 'CANCELLED'
                membership.review_note = 'El pago online no fue aprobado.'
                membership.save(update_fields=['status', 'review_note', 'updated_at'])
            notify_user(payment.club, membership.athlete.user, 'Pago no aprobado', f'El pago de tu plan {membership.plan_name} no fue aprobado. Puedes intentarlo nuevamente desde Membresías.')
        elif provider_status:
            payment.provider_status = provider_status
            payment.save(update_fields=['provider_status', 'updated_at'])
    return ok
