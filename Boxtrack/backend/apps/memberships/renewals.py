"""Renovación de membresías (P3).

Reglas de fechas (la convención del proyecto es `fin = inicio + duración`, vigente hasta `fin` inclusive):
- Renovación anticipada (la membresía vigente aún no vence): la nueva empieza al día siguiente del
  vencimiento actual, de modo que no se pierde ningún día ya pagado. Queda `SCHEDULED` y pasa a `ACTIVE`
  automáticamente cuando comienza.
- Renovación posterior al vencimiento: empieza el día en que se confirma el pago, sin crédito retroactivo
  por los días sin cobertura.
Cada renovación es un registro nuevo enlazado con `renewal_of`; nunca se modifican los anteriores.
No hay cobros recurrentes: cada renovación requiere una acción y un pago explícitos del deportista.
"""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.memberships.models import Membership, MembershipPlan, expire_overdue_memberships
from apps.notifications.models import Notification

RENEWAL_WINDOW_DAYS = 7


class RenewalConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'No es posible renovar la membresía en este momento.'
    default_code = 'renewal_conflict'


def renewal_info(athlete, today=None):
    """Estado de renovación calculado en el servidor (el cliente solo lo muestra)."""
    today = today or timezone.localdate()
    memberships = Membership.objects.filter(athlete=athlete)
    pending = memberships.filter(status='PENDING').first()
    scheduled = memberships.filter(status='SCHEDULED').first()
    active = memberships.filter(status='ACTIVE').first()
    last_expired = None if active else memberships.filter(status='EXPIRED').order_by('-end_date', '-id').first()
    base = active or last_expired

    info = {
        'state': 'NONE', 'can_renew': False, 'reason': '', 'window_days': RENEWAL_WINDOW_DAYS,
        'membership': base.pk if base else None, 'end_date': base.end_date if base else None,
        'days_left': None, 'plan': None, 'next_start_date': None, 'scheduled_membership': scheduled.pk if scheduled else None,
        'scheduled_start_date': scheduled.start_date if scheduled else None,
        'scheduled_end_date': scheduled.end_date if scheduled else None,
    }
    if base:
        plan = base.plan if base.plan.is_active and base.plan.club_id == athlete.club_id else None
        info['plan'] = {'id': plan.pk, 'name': plan.name, 'price': str(plan.price), 'currency': plan.currency, 'duration_days': plan.duration_days} if plan else None
    if active and active.end_date:
        info['days_left'] = (active.end_date - today).days

    if pending:
        info.update(state='PENDING', reason='Tienes una compra o renovación pendiente de pago.')
    elif scheduled:
        info.update(state='SCHEDULED', reason='Ya tienes una renovación programada.')
    elif active:
        days_left = info['days_left']
        if days_left is not None and days_left <= RENEWAL_WINDOW_DAYS:
            info.update(state='EXPIRING', can_renew=True, next_start_date=active.end_date + timedelta(days=1))
        else:
            info.update(state='ACTIVE', reason=f'Podrás renovar a partir de {RENEWAL_WINDOW_DAYS} días antes del vencimiento.')
    elif last_expired:
        info.update(state='EXPIRED', can_renew=True, next_start_date=today)
    else:
        info.update(reason='Aún no tienes una membresía que renovar. Elige un plan.')
    info['_base'] = base
    return info


def create_renewal_membership(athlete, plan_id=None):
    """Crea la membresía PENDING de una renovación. Debe llamarse con el deportista bloqueado en una transacción."""
    expire_overdue_memberships(athlete.club_id)
    info = renewal_info(athlete)
    if not info['can_renew']:
        raise RenewalConflict(info['reason'] or None)
    base = info['_base']
    # Precio, moneda y duración salen del plan en la base de datos, nunca del cliente.
    if plan_id is None:
        plan = base.plan
        if not plan.is_active:
            raise RenewalConflict('Tu plan anterior ya no está disponible. Elige otro plan del club.')
    else:
        plan = get_object_or_404(MembershipPlan, pk=plan_id, club_id=athlete.club_id, is_active=True)
    return Membership.objects.create(
        club=plan.club, athlete=athlete, plan=plan, renewal_of=base, plan_name=plan.name, price_paid=plan.price,
        currency=plan.currency, duration_days=plan.duration_days, weekly_class_limit=plan.weekly_class_limit,
    )


def activate_pending_membership(membership, confirmed_by=None, note=''):
    """Pone en vigor una compra o renovación pendiente ya confirmada. Devuelve el estado resultante."""
    today = timezone.localdate()
    expire_overdue_memberships(membership.club_id)
    current = Membership.objects.filter(
        athlete=membership.athlete, status__in=['ACTIVE', 'SCHEDULED'], end_date__gte=today,
    ).exclude(pk=membership.pk).order_by('-end_date').first()
    if current:
        membership.status = 'SCHEDULED'
        membership.start_date = current.end_date + timedelta(days=1)
    else:
        membership.status = 'ACTIVE'
        membership.start_date = today
    membership.end_date = membership.start_date + timedelta(days=membership.duration_days)
    membership.confirmed_at = timezone.now()
    if confirmed_by:
        membership.confirmed_by = confirmed_by
    membership.review_note = note
    membership.save()
    user = membership.athlete.user
    if user:
        if membership.status == 'SCHEDULED':
            title = 'Renovación aprobada'
            message = (f'Tu renovación del plan {membership.plan_name} fue confirmada. '
                       f'Comienza el {membership.start_date:%d/%m/%Y} y vence el {membership.end_date:%d/%m/%Y}.')
        elif membership.renewal_of_id:
            title = 'Renovación aprobada'
            message = f'Tu renovación del plan {membership.plan_name} fue confirmada y está activa hasta el {membership.end_date:%d/%m/%Y}.'
        else:
            title = 'Membresía activada'
            message = f'Tu plan {membership.plan_name} está activo hasta el {membership.end_date:%d/%m/%Y}.'
        Notification.objects.create(club=membership.club, user=user, title=title, message=message, notification_type='INFO')
    return membership.status
