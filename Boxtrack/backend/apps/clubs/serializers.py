from rest_framework import serializers

from apps.clubs.models import Club


class ClubSerializer(serializers.ModelSerializer):
    verification_document = serializers.FileField(read_only=True)

    class Meta:
        model = Club
        fields = [
            'id', 'name', 'legal_rut', 'legal_representative_name',
            'legal_representative_rut', 'description', 'address', 'phone',
            'email', 'website', 'disciplines', 'verification_status',
            'verification_note', 'verification_document', 'is_active'
        ]


class ClubVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['verification_status', 'verification_note']

    def validate_verification_status(self, value):
        allowed = {choice[0] for choice in Club.VERIFICATION_STATUS_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError('Estado de verificación no válido.')
        return value
