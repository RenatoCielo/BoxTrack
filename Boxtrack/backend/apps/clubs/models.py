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
        ('PENDING', 'Pendiente de documentos'),
        ('IN_REVIEW', 'En revisión'),
        ('NEEDS_INFO', 'Requiere información'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
    ]

    name = models.CharField(max_length=200)
    legal_rut = models.CharField(max_length=20, blank=True, default='')
    legal_representative_name = models.CharField(max_length=200, blank=True, default='')
    legal_representative_rut = models.CharField(max_length=20, blank=True, default='')
    verification_status = models.CharField(max_length=16, choices=VERIFICATION_STATUS_CHOICES, default='APPROVED')
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clubes'
        constraints = [
            models.UniqueConstraint(fields=['legal_rut'], condition=~models.Q(legal_rut=''), name='unique_nonblank_club_legal_rut'),
        ]

    def __str__(self):
        return self.name
