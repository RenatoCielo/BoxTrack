from rest_framework import serializers

from apps.groups.models import Group
from apps.trainings.models import Training, TrainingReservation
from apps.accounts.models import User


class TrainingSerializer(serializers.ModelSerializer):
    trainer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    reserved_count = serializers.SerializerMethodField()

    class Meta:
        model = Training
        fields = [
            'id', 'club', 'title', 'description', 'activity_type', 'trainer', 'group',
            'scheduled_date', 'start_time', 'duration_minutes', 'capacity', 'status', 'objectives',
            'observations', 'reserved_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['club', 'created_at', 'updated_at']

    def validate(self, attrs):
        club_id = self.context['request'].user.club_id
        trainer = attrs.get('trainer')
        group = attrs.get('group')
        capacity = attrs.get('capacity')
        if trainer and trainer.club_id != club_id:
            raise serializers.ValidationError({'trainer': 'El entrenador debe pertenecer al mismo club.'})
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


class TrainingReservationSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.__str__', read_only=True)

    class Meta:
        model = TrainingReservation
        fields = ['id', 'training', 'athlete', 'athlete_name', 'status', 'reserved_at']
        read_only_fields = fields
