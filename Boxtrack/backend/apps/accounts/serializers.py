import re
import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import User, Role
from apps.clubs.models import Club
from apps.athletes.models import Athlete
from apps.trainers.models import TrainerProfile


class ClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'description', 'address', 'phone', 'email', 'website', 'is_active']


class UserSerializer(serializers.ModelSerializer):
    club = ClubSerializer(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone', 'role', 'club', 'is_active', 'must_change_password']

    def get_role(self, obj):
        return obj.role.name if obj.role else None


class RegisterSerializer(serializers.Serializer):
    club_name = serializers.CharField(max_length=200)
    club_email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Este nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Este correo ya está registrado.')
        return value

    def create(self, validated_data):
        club_name = validated_data.pop('club_name')
        club_email = validated_data.pop('club_email', '')
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        phone = validated_data.pop('phone', '')

        role_admin, _ = Role.objects.get_or_create(
            name='ADMIN',
            defaults={'description': 'Administrador del club'}
        )

        club = Club.objects.create(
            name=club_name,
            email=club_email,
            is_active=True,
        )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role_admin,
            club=club,
        )

        return user


class ClubMemberCreateSerializer(serializers.Serializer):
    ROLE_CHOICES = [('TRAINER', 'Entrenador'), ('ATHLETE', 'Deportista')]

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    specialty = serializers.CharField(max_length=200, required=False, allow_blank=True)
    professional_title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    experience_years = serializers.IntegerField(min_value=0, required=False, default=0)
    bio = serializers.CharField(required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_competitor = serializers.BooleanField(required=False, default=False)

    def validate_first_name(self, value):
        return self._validate_person_name(value)

    def validate_last_name(self, value):
        return self._validate_person_name(value)

    @staticmethod
    def _validate_person_name(value):
        normalized = ' '.join(value.split())
        if not re.fullmatch(r"[^\W\d_]+(?:[ '-][^\W\d_]+)*", normalized, flags=re.UNICODE):
            raise serializers.ValidationError('Usa solo letras, espacios, guiones o apóstrofes.')
        return normalized

    def validate_phone(self, value):
        normalized = re.sub(r'[\s().-]', '', value)
        if normalized and not re.fullmatch(r'\+?[1-9]\d{7,14}', normalized):
            raise serializers.ValidationError('Ingresa un teléfono válido con código de país, por ejemplo +56912345678.')
        return normalized

    @staticmethod
    def _unique_credentials(first_name, last_name, club):
        first_slug = slugify(first_name) or 'usuario'
        last_slug = slugify(last_name) or 'miembro'
        person_slug = f'{first_slug}.{last_slug}'
        club_slug = slugify(club.name) or f'boxtrack-{club.pk}'
        domain = f'{club_slug}.com'
        suffix = 1
        while True:
            suffix_text = '' if suffix == 1 else str(suffix)
            username = f'{person_slug}{suffix_text}'[:150]
            email = f'{person_slug}{suffix_text}@{domain}'[:254]
            if not User.objects.filter(username=username).exists() and not User.objects.filter(email=email).exists():
                return username, email
            suffix += 1

    @staticmethod
    def _temporary_password():
        alphabet = string.ascii_letters + string.digits + '!@#$%&*+-_'
        return ''.join(secrets.choice(alphabet) for _ in range(18))

    @transaction.atomic
    def create(self, validated_data):
        role_name = validated_data.pop('role')
        profile_data = {
            'specialty': validated_data.pop('specialty', ''),
            'professional_title': validated_data.pop('professional_title', ''),
            'experience_years': validated_data.pop('experience_years', 0),
            'bio': validated_data.pop('bio', ''),
            'category': validated_data.pop('category', ''),
            'is_competitor': validated_data.pop('is_competitor', False),
        }
        club = validated_data.pop('club')
        username, email = self._unique_credentials(
            validated_data['first_name'], validated_data['last_name'], club
        )
        temporary_password = self._temporary_password()
        role, _ = Role.objects.get_or_create(name=role_name)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=temporary_password,
            role=role,
            club=club,
            must_change_password=True,
            **validated_data,
        )

        if role_name == 'ATHLETE':
            profile = Athlete.objects.create(
                club=club,
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                category=profile_data['category'],
                is_competitor=profile_data['is_competitor'],
            )
        else:
            profile = TrainerProfile.objects.create(
                club=club,
                user=user,
                specialty=profile_data['specialty'],
                professional_title=profile_data['professional_title'],
                experience_years=profile_data['experience_years'],
                bio=profile_data['bio'],
            )
        return user, profile, temporary_password


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('La contraseña actual no es correcta.')
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context['request'].user)
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        return user
