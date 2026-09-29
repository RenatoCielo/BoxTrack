from django.db import models


class WeightRecord(models.Model):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='weight_records')
    athlete = models.ForeignKey('athletes.Athlete', on_delete=models.CASCADE, related_name='weight_records')
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    recorded_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.athlete} - {self.weight} kg'
