from django.db import models


class Athlete(models.Model):
    GENDER_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('X', 'Otro / no especifica'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Activo'),
        ('INACTIVE', 'Inactivo'),
    ]

    GUARDA_CHOICES = [
        ('RIGHT', 'Derecha'),
        ('LEFT', 'Zurda'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='athletes')
    user = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='athlete_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='athletes/photos/', blank=True, null=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    is_competitor = models.BooleanField(default=False)
    assigned_trainer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='athletes_assigned')
    group = models.ForeignKey('groups.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='athletes')
    category = models.CharField(max_length=100, blank=True)
    registered_weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    guard = models.CharField(max_length=10, choices=GUARDA_CHOICES, blank=True)
    experience = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['club', 'status']),
            models.Index(fields=['group', 'assigned_trainer']),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
