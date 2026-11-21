import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from apps.common.models import SpanishSchemaModel

def private_verification_storage():
    return FileSystemStorage(location=settings.BASE_DIR / '.private_uploads' / 'club-verification')


def club_verification_upload_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'{instance.pk}/{uuid.uuid4().hex}.{extension}'


def site_promotion_upload_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'site/promotions/{uuid.uuid4().hex}.{extension}'


def membership_proof_upload_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'membership-proofs/{instance.club_id}/{uuid.uuid4().hex}.{extension}'


def private_membership_proof_storage():
    return FileSystemStorage(location=settings.BASE_DIR / '.private_uploads')


class Club(SpanishSchemaModel):
    VERIFICATION_STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
    ]

    name = models.CharField(max_length=200)
    legal_rut = models.CharField(max_length=20, blank=True, default='')
    legal_representative_name = models.CharField(max_length=200, blank=True, default='')
    legal_representative_rut = models.CharField(max_length=20, blank=True, default='')
    verification_status = models.CharField(max_length=16, choices=VERIFICATION_STATUS_CHOICES, default='PENDING')
    verification_document = models.FileField(storage=private_verification_storage, upload_to=club_verification_upload_path, blank=True, null=True)
    verification_note = models.TextField(blank=True)
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='clubs_verified')
    description = models.TextField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    disciplines = models.JSONField(default=list, blank=True)
    logo = models.ImageField(upload_to='clubs/logos/', blank=True, null=True)
    brand_primary = models.CharField(max_length=7, default='#B21F32')
    brand_accent = models.CharField(max_length=7, default='#D6A94B')
    brand_surface = models.CharField(max_length=7, default='#151518')
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clubes'
        constraints = [
            models.UniqueConstraint(fields=['legal_rut'], condition=~models.Q(legal_rut=''), name='unique_nonblank_club_legal_rut'),
        ]

    def __str__(self):
        return self.name


class Plan(SpanishSchemaModel):
    DURATION_CHOICES = [
        ('Por clase', 'Por clase'),
        ('Diario', 'Diario'),
        ('Semanal', 'Semanal'),
        ('Mensual', 'Mensual'),
        ('Anual', 'Anual'),
    ]

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    duration = models.CharField(max_length=80, choices=DURATION_CHOICES, default='Mensual')
    classes_per_week = models.PositiveSmallIntegerField(null=True, blank=True, default=4)
    is_premium = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'planes'
        ordering = ['sort_order', 'id']
        indexes = [models.Index(fields=['club', 'is_active', 'sort_order'])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(is_premium=True) | models.Q(classes_per_week__isnull=False),
                name='premium_required_for_unlimited_plan',
            ),
        ]

    def __str__(self):
        return f'{self.name} - {self.club.name}'


class PlanMembership(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente de aprobación'),
        ('ACTIVE', 'Activo'),
        ('REJECTED', 'Rechazado'),
        ('EXPIRED', 'Vencido'),
    ]

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='memberships')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='club_memberships')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='plan_memberships')
    price_at_signup = models.DecimalField(max_digits=12, decimal_places=0)
    payment_proof = models.FileField(
        storage=private_membership_proof_storage,
        upload_to=membership_proof_upload_path,
    )
    starts_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='club_memberships_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'membresias_planes'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='PENDING'),
                name='unique_pending_membership_per_user',
            ),
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status='ACTIVE'),
                name='unique_active_membership_per_user',
            ),
        ]
        indexes = [models.Index(fields=['club', 'status', 'created_at'])]

    def __str__(self):
        return f'{self.user} - {self.plan.name} - {self.status}'


class PublicSiteSettings(SpanishSchemaModel):
    headline = models.CharField(max_length=180, blank=True)
    intro = models.CharField(max_length=300, blank=True)
    promotion_image = models.ImageField(upload_to=site_promotion_upload_path, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracion_portada_publica'

    def __str__(self):
        return 'Promoción de portada BOXTRACK'
