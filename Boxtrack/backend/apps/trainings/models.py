from django.db import models

from apps.common.models import SpanishSchemaModel

class Training(SpanishSchemaModel):
    ACTIVITY_TYPES = [
        ('TECHNICAL', 'Técnica'),
        ('TACTICAL', 'Táctica'),
        ('PHYSICAL', 'Acondicionamiento físico'),
        ('SPARRING', 'Sparring'),
        ('COMPETITION', 'Preparación competitiva'),
    ]

    STATUS_CHOICES = [
        ('SCHEDULED', 'Programado'),
        ('CANCELLED', 'Cancelado'),
        ('COMPLETED', 'Completado'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='trainings')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES, default='TECHNICAL')
    trainer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='trainings')
    group = models.ForeignKey('groups.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='trainings')
    scheduled_date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    capacity = models.PositiveIntegerField(default=20)
    weekly_schedule = models.ForeignKey(
        'trainings.WeeklyTrainingSchedule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='occurrences',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    objectives = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clases'
        constraints = [
            models.UniqueConstraint(
                fields=['weekly_schedule', 'scheduled_date'],
                condition=models.Q(weekly_schedule__isnull=False),
                name='unique_weekly_training_occurrence',
            ),
        ]

    def __str__(self):
        return f'{self.title} - {self.scheduled_date}'


class WeeklyTrainingSchedule(SpanishSchemaModel):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='weekly_training_schedules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=30, choices=Training.ACTIVITY_TYPES, default='TECHNICAL')
    trainer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='weekly_training_schedules')
    group = models.ForeignKey('groups.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='weekly_training_schedules')
    weekdays = models.JSONField(default=list)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    capacity = models.PositiveIntegerField(default=20)
    objectives = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'horarios_semanales_clases'
        ordering = ['start_time', 'title', 'id']

    def __str__(self):
        return f'{self.title} - horario semanal'


class TrainingReservation(SpanishSchemaModel):
    STATUS_CHOICES = [
        ('RESERVED', 'Reservado'),
        ('CANCELLED', 'Cancelado'),
    ]

    training = models.ForeignKey(Training, on_delete=models.CASCADE, related_name='reservations')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='training_reservations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RESERVED')
    reserved_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reservas_clases'
        constraints = [
            models.UniqueConstraint(fields=['training', 'athlete'], name='unique_training_athlete_reservation'),
        ]
        indexes = [models.Index(fields=['training', 'status'])]

    def __str__(self):
        return f'{self.athlete} - {self.training} - {self.status}'
