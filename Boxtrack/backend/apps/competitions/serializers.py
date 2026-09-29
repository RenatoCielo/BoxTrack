from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.competitions.models import Competition


class FightRecordSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())

    class Meta:
        model = Competition
        fields = [
            'id', 'club', 'athlete', 'opponent_name', 'fight_date', 'event',
            'category', 'result', 'fight_type', 'notes', 'created_at'
        ]
        read_only_fields = ['club', 'created_at']

    def validate_result(self, value):
        valid = {choice[0] for choice in Competition.RESULT_CHOICES}
        if value not in valid:
            raise serializers.ValidationError('Resultado no válido.')
        return value


class CompetitionSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Competition
        fields = [
            'id', 'club', 'name', 'event', 'competition_date', 'category',
            'location', 'notes', 'created_at', 'athlete', 'opponent_name',
            'result', 'fight_type', 'fight_date'
        ]
        read_only_fields = ['club', 'created_at']
