from rest_framework import serializers

from apps.clubs.models import Club, Plan


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


class ClubPendingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = [
            'id', 'name', 'legal_rut', 'legal_representative_name',
            'email', 'created_at',
        ]


class ClubPublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['is_public']

    def validate_is_public(self, value):
        if self.instance.verification_status != 'APPROVED':
            raise serializers.ValidationError(
                'Solo puedes cambiar la publicación cuando tu club esté aprobado.'
            )
        return value


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'duration', 'is_active', 'sort_order']
        read_only_fields = ['id']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre del plan es obligatorio.')
        return value

    def validate_duration(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Indica el tipo o duración del plan.')
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value


class PublicPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'duration']


class PublicClubListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'address']


class PublicClubDetailSerializer(serializers.ModelSerializer):
    plans = PublicPlanSerializer(source='active_public_plans', many=True, read_only=True)

    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'description', 'address', 'phone', 'email', 'website', 'plans']
