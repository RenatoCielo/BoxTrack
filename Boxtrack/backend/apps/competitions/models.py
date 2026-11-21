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


class FightAgreement(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('CONFIRMED', 'Confirmado'),
        ('DECLINED', 'Rechazado'),
        ('CANCELLED', 'Cancelado'),
    ]

    proposing_club = models.ForeignKey(
        'clubs.Club', on_delete=models.CASCADE, related_name='proposed_fight_agreements'
    )
    opponent_club = models.ForeignKey(
        'clubs.Club', on_delete=models.CASCADE, related_name='received_fight_agreements'
    )
    proposed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='proposed_fight_agreements'
    )
    responded_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='responded_fight_agreements'
    )
    planned_date = models.DateField()
    location = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'acuerdos_combates'
        ordering = ['planned_date', '-created_at']
        indexes = [
            models.Index(fields=['proposing_club', 'status']),
            models.Index(fields=['opponent_club', 'status']),
        ]

    def __str__(self):
        return f'{self.proposing_club} vs {self.opponent_club} - {self.planned_date}'


class FightBout(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('PENDING', 'Propuesta'),
        ('COUNTERED', 'Contrapropuesta'),
        ('CONFIRMED', 'Acordado'),
        ('DECLINED', 'Rechazado'),
        ('CANCELLED', 'Cancelado'),
    ]

    agreement = models.ForeignKey(FightAgreement, on_delete=models.CASCADE, related_name='bouts')
    home_athlete = models.ForeignKey(
        'athletes.Athlete', on_delete=models.PROTECT, related_name='home_fight_bouts'
    )
    away_athlete = models.ForeignKey(
        'athletes.Athlete', on_delete=models.PROTECT, null=True, blank=True,
        related_name='away_fight_bouts',
    )
    last_suggested_by_club = models.ForeignKey(
        'clubs.Club', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='suggested_fight_bouts',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'propuestas_combate'
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['agreement', 'home_athlete'],
                name='unique_home_athlete_per_agreement',
            ),
        ]

    def __str__(self):
        rival = self.away_athlete or 'rival pendiente'
        return f'{self.home_athlete} vs {rival}'
