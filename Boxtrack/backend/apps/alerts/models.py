from django.db import models


class Alert(models.Model):
    LEVEL_CHOICES = [
        ('INFO', 'Información'),
        ('WARNING', 'Advertencia'),
        ('CRITICAL', 'Crítica'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='alerts')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='INFO')
    source = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.title} - {self.level}'
