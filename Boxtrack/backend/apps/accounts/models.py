from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import SpanishSchemaModel, SpanishSchemaModelBase


class Role(SpanishSchemaModel):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrador del club'),
        ('TRAINER', 'Entrenador'),
        ('ATHLETE', 'Deportista'),
    ]

    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'roles'
        ordering = ['name']

    def __str__(self):
        return self.get_name_display()


class User(AbstractUser, SpanishSchemaModel, metaclass=SpanishSchemaModelBase):
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    use_nickname = models.BooleanField(default=False)
    share_phone = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuarios'
        ordering = ['username']

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.role})'

    @property
    def display_name(self):
        if self.use_nickname and self.nickname.strip():
            return self.nickname.strip()
        return self.get_full_name().strip() or self.username
