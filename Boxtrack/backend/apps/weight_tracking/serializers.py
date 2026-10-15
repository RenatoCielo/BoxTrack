from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.weight_tracking.models import WeightRecord
from apps.common.permissions import user_role


class WeightRecordSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())

    class Meta:
        model = WeightRecord
        fields = ['id', 'club', 'athlete', 'weight', 'recorded_date', 'notes', 'created_at']
        read_only_fields = ['club', 'created_at']

    def validate_athlete(self, athlete):
        if athlete.club_id != self.context['request'].user.club_id:
            raise serializers.ValidationError('El deportista debe pertenecer a tu club.')
        if user_role(self.context['request'].user) == 'TRAINER' and athlete.assigned_trainer_id != self.context['request'].user.id:
            raise serializers.ValidationError('Solo puedes registrar peso de deportistas asignados a ti.')
        return athlete