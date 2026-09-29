from django.utils import timezone
from rest_framework import serializers

from apps.alerts.models import Alert
from apps.athletes.models import Athlete


class AlertSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Alert
        fields = ['id', 'club', 'athlete', 'title', 'message', 'level', 'source', 'created_at', 'is_resolved', 'resolved_at']
        read_only_fields = ['club', 'created_at', 'resolved_at']

    def validate_athlete(self, athlete):
        if athlete and athlete.club_id != self.context['request'].user.club_id:
            raise serializers.ValidationError('El deportista debe pertenecer a tu club.')
        return athlete

    def update(self, instance, validated_data):
        is_resolved = validated_data.pop('is_resolved', instance.is_resolved)
        if is_resolved != instance.is_resolved:
            instance.is_resolved = is_resolved
            instance.resolved_at = timezone.now() if is_resolved else None
        return super().update(instance, validated_data)