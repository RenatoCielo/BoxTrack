from rest_framework import serializers

from apps.groups.models import Group
from apps.trainings.models import Training, TrainingReservation, WeeklyTrainingSchedule
from apps.accounts.models import User
from apps.common.permissions import user_role


class TrainingSerializer(serializers.ModelSerializer):
    trainer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    reserved_count = serializers.SerializerMethodField()
    own_reservation_id = serializers.IntegerField(read_only=True, default=None)
    weekly_schedule = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Training
        fields = [
            'id', 'club', 'title', 'description', 'activity_type', 'trainer', 'group',
            'scheduled_date', 'start_time', 'duration_minutes', 'capacity', 'status', 'objectives',
            'observations', 'reserved_count', 'own_reservation_id', 'weekly_schedule',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['club', 'created_at', 'updated_at']

    def validate(self, attrs):
        user = self.context['request'].user
        club_id = user.club_id
        trainer = attrs.get('trainer')
        group = attrs.get('group')
        capacity = attrs.get('capacity')
        if trainer and trainer.club_id != club_id:
            raise serializers.ValidationError({'trainer': 'El entrenador debe pertenecer al mismo club.'})
        if trainer and (not trainer.is_active or user_role(trainer) != 'TRAINER'):
            raise serializers.ValidationError({'trainer': 'Selecciona una cuenta activa con rol de entrenador.'})
        if user_role(user) == 'TRAINER':
            if trainer and trainer.id != user.id:
                raise serializers.ValidationError({'trainer': 'Solo puedes programar clases a tu nombre.'})
            attrs['trainer'] = user
        if group and group.club_id != club_id:
            raise serializers.ValidationError({'group': 'El grupo debe pertenecer al mismo club.'})
        if capacity is not None and capacity < 1:
            raise serializers.ValidationError({'capacity': 'La capacidad debe ser al menos 1.'})
        if self.instance and capacity is not None:
            active_reservations = self.instance.reservations.filter(status='RESERVED').count()
            if capacity < active_reservations:
                raise serializers.ValidationError({'capacity': 'No puede ser menor que los cupos ya reservados.'})
        return attrs

    def get_reserved_count(self, obj):
        if hasattr(obj, 'reserved_count'):
            return obj.reserved_count
        return obj.reservations.filter(status='RESERVED').count()


class WeeklyTrainingScheduleSerializer(serializers.ModelSerializer):
    trainer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)

    class Meta:
        model = WeeklyTrainingSchedule
        fields = [
            'id', 'club', 'title', 'description', 'activity_type', 'trainer', 'group',
            'weekdays', 'starts_on', 'ends_on', 'start_time', 'duration_minutes',
            'capacity', 'objectives', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['club', 'created_at', 'updated_at']

    def validate_weekdays(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError('Selecciona al menos un día de la semana.')
        if any(isinstance(day, bool) or not isinstance(day, int) or day < 0 or day > 6 for day in value):
            raise serializers.ValidationError('Los días deben estar entre lunes (0) y domingo (6).')
        if len(set(value)) != len(value):
            raise serializers.ValidationError('No repitas días de la semana.')
        return sorted(value)

    def validate(self, attrs):
        user = self.context['request'].user
        club_id = user.club_id
        trainer = attrs.get('trainer', self.instance.trainer if self.instance else None)
        group = attrs.get('group', self.instance.group if self.instance else None)
        capacity = attrs.get('capacity')
        starts_on = attrs.get('starts_on', self.instance.starts_on if self.instance else None)
        ends_on = attrs.get('ends_on', self.instance.ends_on if self.instance else None)
        if trainer and trainer.club_id != club_id:
            raise serializers.ValidationError({'trainer': 'El entrenador debe pertenecer al mismo club.'})
        if trainer and (not trainer.is_active or user_role(trainer) != 'TRAINER'):
            raise serializers.ValidationError({'trainer': 'Selecciona una cuenta activa con rol de entrenador.'})
        if user_role(user) == 'TRAINER':
            if trainer and trainer.id != user.id:
                raise serializers.ValidationError({'trainer': 'Solo puedes programar clases a tu nombre.'})
            attrs['trainer'] = user
        if group and group.club_id != club_id:
            raise serializers.ValidationError({'group': 'El grupo debe pertenecer al mismo club.'})
        if capacity is not None and capacity < 1:
            raise serializers.ValidationError({'capacity': 'La capacidad debe ser al menos 1.'})
        if starts_on and ends_on and ends_on < starts_on:
            raise serializers.ValidationError({'ends_on': 'La fecha de término debe ser posterior al inicio.'})
        return attrs


class TrainingReservationSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.display_name', read_only=True)

    class Meta:
        model = TrainingReservation
        fields = ['id', 'training', 'athlete', 'athlete_name', 'status', 'reserved_at']
        read_only_fields = fields
