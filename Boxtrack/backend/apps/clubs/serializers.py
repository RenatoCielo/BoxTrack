from rest_framework import serializers
import re

from apps.clubs.models import Club, Plan, PublicSiteSettings
from apps.store.models import StoreSettings


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


class ClubBrandSettingsSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Club
        fields = [
            'name', 'description', 'address', 'phone', 'email', 'website',
            'logo', 'brand_primary', 'brand_accent', 'brand_surface',
        ]

    def validate_logo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('El logo no puede superar los 5 MB.')
        return value

    def validate_brand_primary(self, value):
        return self._validate_color(value)

    def validate_brand_accent(self, value):
        return self._validate_color(value)

    def validate_brand_surface(self, value):
        return self._validate_color(value)

    @staticmethod
    def _validate_color(value):
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise serializers.ValidationError('Usa un color hexadecimal válido, por ejemplo #B21F32.')
        return value.upper()


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    remove_promotion_image = serializers.BooleanField(write_only=True, required=False, default=False)
    promotion_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = PublicSiteSettings
        fields = ['headline', 'intro', 'promotion_image', 'remove_promotion_image']

    def validate_promotion_image(self, value):
        if value and value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError('La imagen promocional no puede superar los 8 MB.')
        return value

    def update(self, instance, validated_data):
        remove_image = validated_data.pop('remove_promotion_image', False)
        if remove_image and instance.promotion_image:
            instance.promotion_image.delete(save=False)
            instance.promotion_image = None
        return super().update(instance, validated_data)


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'description', 'price', 'duration', 'classes_per_week',
            'is_premium', 'is_active', 'sort_order',
        ]
        read_only_fields = ['id']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El nombre del plan es obligatorio.')
        return value

    def validate_duration(self, value):
        value = value.strip()
        if value not in dict(Plan.DURATION_CHOICES):
            raise serializers.ValidationError('Elige duración por clase, diaria, semanal, mensual o anual.')
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError('El precio no puede ser negativo.')
        return value

    def validate_classes_per_week(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Usa al menos 1 clase por semana o deja el campo vacío para ilimitado.')
        return value

    def validate(self, attrs):
        is_premium = attrs.get('is_premium', self.instance.is_premium if self.instance else False)
        classes_per_week = attrs.get(
            'classes_per_week',
            self.instance.classes_per_week if self.instance else 4,
        )
        if classes_per_week is None and not is_premium:
            raise serializers.ValidationError({
                'classes_per_week': 'Solo un plan premium puede permitir clases ilimitadas.'
            })
        return attrs


class PublicPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'duration', 'classes_per_week', 'is_premium']


class PublicClubListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'address', 'brand_primary', 'brand_accent', 'brand_surface']


class PublicClubDetailSerializer(serializers.ModelSerializer):
    plans = PublicPlanSerializer(source='active_public_plans', many=True, read_only=True)
    bank_transfer_instructions = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            'id', 'name', 'logo', 'description', 'address', 'phone', 'email',
            'website', 'brand_primary', 'brand_accent', 'brand_surface', 'plans',
            'bank_transfer_instructions',
        ]

    def get_bank_transfer_instructions(self, club):
        settings = StoreSettings.objects.filter(club=club).only('bank_transfer_instructions').first()
        return settings.bank_transfer_instructions if settings else ''
