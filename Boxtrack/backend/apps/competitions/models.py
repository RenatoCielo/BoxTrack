from django.db import models


class Competition(models.Model):
    RESULT_CHOICES = [
        ('WIN', 'Victoria'),
        ('LOSS', 'Derrota'),
        ('DRAW', 'Empate'),
    ]

    FIGHT_TYPE_CHOICES = [
        ('AMATEUR', 'Amateur'),
        ('PRO', 'Profesional'),
        ('SPARRING', 'Sparring'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='competitions')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='fight_records', null=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    opponent_name = models.CharField(max_length=200, blank=True)
    fight_date = models.DateField(null=True, blank=True)
    event = models.CharField(max_length=200, blank=True)
    competition_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, blank=True)
    fight_type = models.CharField(max_length=20, choices=FIGHT_TYPE_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fight_date', '-competition_date', '-created_at']
        indexes = [
            models.Index(fields=['club', 'athlete']),
            models.Index(fields=['athlete', 'fight_date']),
        ]

    def __str__(self):
        if self.opponent_name:
            return f'{self.athlete} vs {self.opponent_name}'
        return self.name or 'Competencia'
