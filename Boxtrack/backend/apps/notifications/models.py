from django.db import models


class Notification(models.Model):
    TYPE_CHOICES = [
        ('INFO', 'Información'),
        ('TRAINING', 'Entrenamiento'),
        ('EVALUATION', 'Evaluación'),
        ('COMPETITION', 'Competencia'),
        ('ALERT', 'Alerta'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='INFO')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.title} - {self.user}'
