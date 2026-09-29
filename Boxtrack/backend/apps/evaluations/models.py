from django.db import models


class Evaluation(models.Model):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='evaluations')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations_done')
    evaluation_date = models.DateField()
    technical = models.PositiveSmallIntegerField(default=0)
    defense = models.PositiveSmallIntegerField(default=0)
    speed = models.PositiveSmallIntegerField(default=0)
    endurance = models.PositiveSmallIntegerField(default=0)
    power = models.PositiveSmallIntegerField(default=0)
    coordination = models.PositiveSmallIntegerField(default=0)
    mobility = models.PositiveSmallIntegerField(default=0)
    general_condition = models.PositiveSmallIntegerField(default=0)
    observations = models.TextField(blank=True)
    strengths = models.TextField(blank=True)
    improvement_areas = models.TextField(blank=True)
    next_goals = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.athlete} - {self.evaluation_date}'
