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
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    duration = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'planes'
        ordering = ['sort_order', 'id']
        indexes = [models.Index(fields=['club', 'is_active', 'sort_order'])]

    def __str__(self):
        return f'{self.name} - {self.club.name}'
