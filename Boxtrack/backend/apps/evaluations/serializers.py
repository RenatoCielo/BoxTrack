from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.evaluations.models import Evaluation
from apps.common.permissions import user_role


class EvaluationSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())
    evaluator = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Evaluation
        fields = [
            'id', 'club', 'athlete', 'evaluator', 'evaluation_date', 'technical',
            'defense', 'speed', 'endurance', 'power', 'coordination', 'mobility',
            'general_condition', 'observations', 'strengths', 'improvement_areas',
            'next_goals', 'created_at', 'updated_at'
        ]
        read_only_fields = ['club', 'evaluator', 'created_at', 'updated_at']

    def validate(self, attrs):
        athlete = attrs.get('athlete', getattr(self.instance, 'athlete', None))
        if athlete and athlete.club_id != self.context['request'].user.club_id:
            raise serializers.ValidationError({'athlete': 'El deportista debe pertenecer a tu club.'})
        if athlete and user_role(self.context['request'].user) == 'TRAINER' and athlete.assigned_trainer_id != self.context['request'].user.id:
            raise serializers.ValidationError({'athlete': 'Solo puedes evaluar deportistas asignados a ti.'})
        for field in ('technical', 'defense', 'speed', 'endurance', 'power', 'coordination', 'mobility', 'general_condition'):
            score = attrs.get(field)
            if score is not None and score > 10:
                raise serializers.ValidationError({field: 'La evaluación debe estar entre 0 y 10.'})
        return attrs