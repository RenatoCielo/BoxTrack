from django.db import models

from apps.common.models import SpanishSchemaModel

class Competition(SpanishSchemaModel):
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
        db_table = 'competencias'
        ordering = ['-fight_date', '-competition_date', '-created_at']
        indexes = [
            models.Index(fields=['club', 'athlete']),
            models.Index(fields=['athlete', 'fight_date']),
        ]

    def __str__(self):
        if self.opponent_name:
            return f'{self.athlete} vs {self.opponent_name}'
        return self.name or 'Competencia'


class CompetitorRequest(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('APPROVED', 'Aprobada'),
        ('REJECTED', 'Rechazada'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='competitor_requests')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='competitor_requests')
    requested_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='competitor_requests_made')
    reviewed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='competitor_requests_reviewed')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    request_note = models.TextField(blank=True)
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'solicitudes_competidor'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['athlete'], condition=models.Q(status='PENDING'), name='unique_pending_competitor_request'),
        ]

    def __str__(self):
        return f'{self.athlete} - {self.status}'


class FightMatch(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PROPOSED', 'Propuesto'),
        ('ACCEPTED', 'Confirmado'),
        ('DECLINED', 'Rechazado'),
        ('CANCELLED', 'Cancelado'),
        ('COMPLETED', 'Realizado'),
    ]
    RESULT_CHOICES = Competition.RESULT_CHOICES

    challenger_club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='fight_matches_proposed')
    opponent_club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='fight_matches_received')
    challenger_athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='fight_matches_as_challenger')
    opponent_athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='fight_matches_as_opponent')
    proposed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='fight_matches_proposed')
    responded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='fight_matches_responded')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROPOSED')
    event = models.CharField(max_length=200, blank=True)
    fight_date = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=100, blank=True)
    fight_type = models.CharField(max_length=20, choices=Competition.FIGHT_TYPE_CHOICES, default='AMATEUR')
    notes = models.TextField(blank=True)
    response_note = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    challenger_result = models.CharField(max_length=20, choices=RESULT_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'combates_entre_clubes'
        ordering = ['-fight_date', '-id']
