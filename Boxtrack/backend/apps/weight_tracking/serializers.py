from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.weight_tracking.models import WeightRecord


class WeightRecordSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())

    class Meta:
        model = WeightRecord
        fields = ['id', 'club', 'athlete', 'weight', 'recorded_date', 'notes', 'created_at']
        read_only_fields = ['club', 'created_at']

    def validate_athlete(self, athlete):
        if athlete.club_id != self.context['request'].user.club_id:
            raise serializers.ValidationError('El deportista debe pertenecer a tu club.')
        return athlete