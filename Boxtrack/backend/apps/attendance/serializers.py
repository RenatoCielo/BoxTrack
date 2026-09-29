from rest_framework import serializers

from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.trainings.models import Training


class AttendanceSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())
    training = serializers.PrimaryKeyRelatedField(queryset=Training.objects.all())

    class Meta:
        model = Attendance
        fields = ['id', 'club', 'athlete', 'training', 'status', 'registered_at', 'notes']
        read_only_fields = ['club', 'registered_at']

    def validate(self, attrs):
        athlete = attrs.get('athlete')
        training = attrs.get('training')

        if athlete and training and athlete.club_id != training.club_id:
            raise serializers.ValidationError('El deportista no pertenece al mismo club del entrenamiento.')
        return attrs
