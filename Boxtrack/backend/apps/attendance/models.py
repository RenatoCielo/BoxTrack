from django.db import models


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('PRESENT', 'Presente'),
        ('ABSENT', 'Ausente'),
        ('JUSTIFIED', 'Justificado'),
        ('LATE', 'Atrasado'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='attendances')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='attendance_records')
    training = models.ForeignKey('trainings.Training', on_delete=models.CASCADE, related_name='attendance_records')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PRESENT')
    registered_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('athlete', 'training')
        indexes = [
            models.Index(fields=['club', 'status']),
            models.Index(fields=['training', 'status']),
        ]

    def __str__(self):
        return f'{self.athlete} - {self.training} - {self.status}'
