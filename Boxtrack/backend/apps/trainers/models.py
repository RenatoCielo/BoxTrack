from django.db import models

from apps.common.models import SpanishSchemaModel

class TrainerProfile(SpanishSchemaModel):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='trainer_profiles')
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='trainer_profile')
    specialty = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    professional_title = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'perfiles_entrenadores'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username}'
