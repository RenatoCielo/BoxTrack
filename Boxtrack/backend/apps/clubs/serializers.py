from PIL import Image, UnidentifiedImageError
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
            'verification_note', 'verification_document', 'is_active', 'logo', 'primary_color', 'accent_color'
        ]


class ClubBrandingSerializer(serializers.ModelSerializer):
    primary_color = serializers.RegexField(regex=r'^#[0-9A-Fa-f]{6}$')
    accent_color = serializers.RegexField(regex=r'^#[0-9A-Fa-f]{6}$')
    logo = serializers.ImageField(required=False)

    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'primary_color', 'accent_color']
        read_only_fields = ['id', 'name']

    def validate_logo(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('El logotipo no puede superar 2 MB.')
        try:
            image = Image.open(value)
            if image.format not in ('PNG', 'JPEG', 'WEBP'):
                raise serializers.ValidationError('Usa una imagen PNG, JPG o WebP.')
            if image.width > 5000 or image.height > 5000:
                raise serializers.ValidationError('La imagen no puede superar 5000 × 5000 píxeles.')
            image.verify()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
            raise serializers.ValidationError('El archivo no contiene una imagen válida.') from error
        finally:
            value.seek(0)
        return value

    def validate_primary_color(self, value):
        return value.upper()

    def validate_accent_color(self, value):
        return value.upper()


class ClubVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['verification_status', 'verification_note']

    def validate_verification_status(self, value):
        allowed = {choice[0] for choice in Club.VERIFICATION_STATUS_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError('Estado de verificación no válido.')
        return value
