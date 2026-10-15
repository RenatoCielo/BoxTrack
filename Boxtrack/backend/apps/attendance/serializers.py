from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.trainings.models import Training
from apps.common.permissions import user_role


class AttendanceSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())
    training = serializers.PrimaryKeyRelatedField(queryset=Training.objects.all())

    class Meta:
        model = Attendance
        fields = ['id', 'club', 'athlete', 'training', 'status', 'registered_at', 'notes']
        read_only_fields = ['club', 'registered_at']

    def validate(self, attrs):
        athlete = attrs.get('athlete', getattr(self.instance, 'athlete', None))
        training = attrs.get('training', getattr(self.instance, 'training', None))
        request_user = self.context['request'].user

        if athlete and training and athlete.club_id != training.club_id:
            raise serializers.ValidationError({'athlete': 'El deportista no pertenece al mismo club del entrenamiento.'})
        if athlete and athlete.club_id != request_user.club_id:
            raise serializers.ValidationError({'athlete': 'El deportista debe pertenecer al club de tu cuenta.'})
        if training and training.club_id != request_user.club_id:
            raise serializers.ValidationError({'training': 'La clase debe pertenecer al club de tu cuenta.'})
        if user_role(request_user) == 'TRAINER':
            if athlete and athlete.assigned_trainer_id != request_user.id:
                raise serializers.ValidationError({'athlete': 'Solo puedes registrar asistencia de deportistas asignados a ti.'})
            if training and training.trainer_id != request_user.id:
                raise serializers.ValidationError({'training': 'Solo puedes registrar asistencia en tus propias clases.'})
        return attrs
