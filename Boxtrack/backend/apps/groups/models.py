from django.db import models


class Group(models.Model):
    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    schedule = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
