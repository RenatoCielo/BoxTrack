import re

from rest_framework import serializers

from apps.accounts.models import User
from apps.athletes.models import Athlete
from apps.competitions.models import Competition
from apps.groups.models import Group


class ZeroToNullPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        if data in (None, '', '0', 0):
            return None
        return super().to_internal_value(data)


class AthleteSerializer(serializers.ModelSerializer):
    assigned_trainer = ZeroToNullPrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    group = ZeroToNullPrimaryKeyRelatedField(queryset=Group.objects.all(), required=False, allow_null=True)
    fight_record = serializers.SerializerMethodField()

    class Meta:
        model = Athlete
        fields = [
            'id', 'club', 'user', 'first_name', 'last_name', 'photo', 'birth_date', 'phone',
            'emergency_contact', 'admission_date', 'status', 'is_competitor', 'fight_record', 'assigned_trainer',
            'group', 'category', 'registered_weight', 'guard', 'experience',
            'observations', 'created_at', 'updated_at'
        ]
        read_only_fields = ['club', 'created_at', 'updated_at']

    def validate(self, attrs):
        request_user = self.context['request'].user
        phone = attrs.get('phone')
        normalized_phone = re.sub(r'[\s().-]', '', phone or '')
        if normalized_phone and not re.fullmatch(r'\+?[1-9]\d{7,14}', normalized_phone):
            raise serializers.ValidationError({'phone': 'Ingresa un teléfono válido con código de país, por ejemplo +56912345678.'})
        if phone is not None:
            attrs['phone'] = normalized_phone
        user = attrs.get('user')
        if user and user.club_id != request_user.club_id:
            raise serializers.ValidationError({'user': 'La cuenta debe pertenecer al mismo club.'})
        if user and getattr(user.role, 'name', None) != 'ATHLETE':
            raise serializers.ValidationError({'user': 'La cuenta vinculada debe tener rol de deportista.'})
        if user and Athlete.objects.filter(user=user).exclude(pk=getattr(self.instance, 'pk', None)).exists():
            raise serializers.ValidationError({'user': 'Esta cuenta ya tiene una ficha deportiva vinculada.'})
        group = attrs.get('group', getattr(self.instance, 'group', None))
        if group and group.club_id != request_user.club_id:
            raise serializers.ValidationError({'group': 'El grupo debe pertenecer al mismo club del deportista.'})
        trainer = attrs.get('assigned_trainer', getattr(self.instance, 'assigned_trainer', None))
        if trainer:
            if trainer.club_id != request_user.club_id:
                raise serializers.ValidationError({'assigned_trainer': 'El entrenador debe pertenecer al mismo club.'})
            if getattr(trainer.role, 'name', None) != 'TRAINER':
                raise serializers.ValidationError({'assigned_trainer': 'La cuenta seleccionada no tiene rol de entrenador.'})
        if attrs.get('status') not in [choice[0] for choice in Athlete.STATUS_CHOICES]:
            raise serializers.ValidationError({'status': 'Estado no válido.'})
        return attrs

    def get_fight_record(self, athlete):
        results = Competition.objects.filter(athlete=athlete).exclude(fight_type='SPARRING').values_list('result', flat=True)
        wins = sum(result == 'WIN' for result in results)
        losses = sum(result == 'LOSS' for result in results)
        draws = sum(result == 'DRAW' for result in results)
        return f'{wins}-{losses}-{draws}'
