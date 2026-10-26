from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.common.models import SpanishSchemaModel
from apps.trainings.models import TrainingReservation


class MembershipPlan(SpanishSchemaModel):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='membership_plans')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='CLP')
    duration_days = models.PositiveIntegerField(default=30)
    benefits = models.TextField(blank=True)
    weekly_class_limit = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'planes_membresia'
        ordering = ['price', 'name']
        constraints = [
            models.UniqueConstraint(fields=['club', 'name'], name='unique_membership_plan_name_per_club'),
        ]
        indexes = [models.Index(fields=['club', 'is_active'])]

    def __str__(self):
        return f'{self.name} - {self.club}'


class Membership(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente de pago'),
        ('ACTIVE', 'Activa'),
        ('SCHEDULED', 'Renovación programada'),
        ('EXPIRED', 'Vencida'),
        ('REJECTED', 'Rechazada'),
        ('CANCELLED', 'Cancelada'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='memberships')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='memberships')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='memberships')
    # Membresía anterior que esta renueva; los registros previos nunca se modifican ni se borran.
    renewal_of = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='renewals')
    # Instantánea de las condiciones al contratar: editar el plan después no altera lo ya cobrado.
    plan_name = models.CharField(max_length=120)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='CLP')
    duration_days = models.PositiveIntegerField()
    weekly_class_limit = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    confirmed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='memberships_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'membresias'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['athlete'], condition=models.Q(status='PENDING'), name='unique_pending_membership_per_athlete'),
            models.UniqueConstraint(fields=['athlete'], condition=models.Q(status='ACTIVE'), name='unique_active_membership_per_athlete'),
            models.UniqueConstraint(fields=['athlete'], condition=models.Q(status='SCHEDULED'), name='unique_scheduled_membership_per_athlete'),
        ]
        indexes = [models.Index(fields=['club', 'status', 'end_date'])]

    def __str__(self):
        return f'{self.athlete} - {self.plan_name} ({self.status})'


class MembershipPayment(SpanishSchemaModel):
    """Pago online (Mercado Pago) de una membresía. Monto y moneda son una instantánea tomada del plan en el servidor."""
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
        ('CANCELLED', 'Cancelado'),
        ('EXPIRED', 'Vencido'),
        ('REFUNDED', 'Reembolsado'),
        ('REVIEW', 'Requiere revisión'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='membership_payments')
    user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='membership_payments')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='payments')
    membership = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='CLP')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    payment_reference = models.CharField(max_length=120, blank=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    provider_payment_id = models.CharField(max_length=64, null=True, blank=True, unique=True)
    provider_status = models.CharField(max_length=40, blank=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pagos_membresia'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['membership'],
                condition=models.Q(status='PENDING'),
                name='unique_pending_payment_per_membership',
            ),
        ]
        indexes = [models.Index(fields=['club', 'status'])]

    def __str__(self):
        return f'Pago #{self.pk} {self.membership_id} ({self.status})'


class MembershipSettings(SpanishSchemaModel):
    club = models.OneToOneField('clubs.Club', on_delete=models.CASCADE, related_name='membership_settings')
    require_active_membership = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracion_membresias'

    def __str__(self):
        return f'Configuración de membresías - {self.club}'


def membership_required(club_id):
    return MembershipSettings.objects.filter(club_id=club_id, require_active_membership=True).exists()


MEMBERSHIP_REQUIRED_CODE = 'MEMBERSHIP_REQUIRED'


def membership_required_error(athlete, training):
    """Mensaje si el club exige membresía y el deportista no tiene una vigente en la fecha de la clase."""
    if not membership_required(athlete.club_id):
        return None
    expire_overdue_memberships(athlete.club_id)
    valid = Membership.objects.filter(
        athlete=athlete, status__in=['ACTIVE', 'SCHEDULED'], end_date__gte=training.scheduled_date,
    ).filter(models.Q(start_date__isnull=True) | models.Q(start_date__lte=training.scheduled_date)).exists()
    if valid:
        return None
    has_pending = Membership.objects.filter(athlete=athlete, status='PENDING').exists()
    if has_pending:
        return 'Tu membresía aún está pendiente de pago. Cuando el club la confirme podrás reservar clases. Revisa tus planes en Membresías.'
    return 'Tu club exige una membresía activa y vigente para reservar clases. Consulta los planes disponibles en Membresías.'


def weekly_limit_error(athlete, training):
    """Devuelve un mensaje si reservar `training` supera el límite semanal del plan vigente del deportista."""
    expire_overdue_memberships(athlete.club_id)
    day = training.scheduled_date
    candidates = Membership.objects.filter(athlete=athlete, status__in=['ACTIVE', 'SCHEDULED'], weekly_class_limit__isnull=False)
    membership = (
        candidates.filter(end_date__gte=day).filter(models.Q(start_date__isnull=True) | models.Q(start_date__lte=day)).first()
        or candidates.filter(status='ACTIVE').first()
    )
    if not membership:
        return None
    week_start = training.scheduled_date - timedelta(days=training.scheduled_date.weekday())
    week_end = week_start + timedelta(days=6)
    used = TrainingReservation.objects.filter(
        athlete=athlete, status='RESERVED', training__status='SCHEDULED',
        training__scheduled_date__range=(week_start, week_end),
    ).exclude(training=training).count()
    if used >= membership.weekly_class_limit:
        return (
            f'Tu plan {membership.plan_name} permite {membership.weekly_class_limit} '
            f'clase(s) por semana y ya usaste {used} en esa semana.'
        )
    return None


def expire_overdue_memberships(club_id=None):
    """Vence las membresías cuya fecha final pasó y pone en vigor las renovaciones programadas que ya empezaron."""
    today = timezone.localdate()
    queryset = Membership.objects.filter(status='ACTIVE', end_date__lt=today)
    if club_id is not None:
        queryset = queryset.filter(club_id=club_id)
    expired = queryset.update(status='EXPIRED')
    scheduled = Membership.objects.filter(status='SCHEDULED', start_date__lte=today)
    if club_id is not None:
        scheduled = scheduled.filter(club_id=club_id)
    for membership in scheduled.exclude(athlete__memberships__status='ACTIVE'):
        membership.status = 'ACTIVE'
        membership.save(update_fields=['status', 'updated_at'])
    return expired
