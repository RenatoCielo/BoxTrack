import mimetypes
import re
from pathlib import Path
from datetime import date, timedelta

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.athletes.models import Athlete
from apps.clubs.models import Club, Plan, PlanMembership
from apps.common.permissions import user_role
from apps.notifications.models import Notification
from apps.store.models import StoreSettings
from apps.trainings.quotas import weekly_quota_stats


class MembershipSignupSerializer(serializers.Serializer):
    plan = serializers.IntegerField()
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    proof = serializers.FileField(write_only=True)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Este nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        value = value.strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Este correo ya está registrado.')
        return value

    def validate_first_name(self, value):
        value = ' '.join(value.split())
        if not value:
            raise serializers.ValidationError('Ingresa tu nombre.')
        return value

    def validate_last_name(self, value):
        value = ' '.join(value.split())
        if not value:
            raise serializers.ValidationError('Ingresa tu apellido.')
        return value

    def validate_proof(self, proof):
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
        allowed_types = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp'}
        extension = Path(proof.name).suffix.lower()
        header = proof.read(12)
        proof.seek(0)
        valid_signature = (
            header.startswith(b'%PDF-')
            or header.startswith(b'\xff\xd8\xff')
            or header.startswith(b'\x89PNG\r\n\x1a\n')
            or (header.startswith(b'RIFF') and header[8:12] == b'WEBP')
        )
        if extension not in allowed_extensions or proof.content_type not in allowed_types or not valid_signature:
            raise serializers.ValidationError('Sube un comprobante válido en PDF, JPG, PNG o WEBP.')
        if proof.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('El comprobante no puede superar los 5 MB.')
        return proof

    def validate_phone(self, value):
        normalized = re.sub(r'[\s().-]', '', value)
        if normalized and not re.fullmatch(r'\+?[1-9]\d{7,14}', normalized):
            raise serializers.ValidationError('Ingresa un teléfono válido con código de país.')
        return normalized

    def validate(self, attrs):
        club = self.context['club']
        plan = get_object_or_404(Plan, pk=attrs['plan'], club=club, is_active=True)
        instructions = StoreSettings.objects.filter(club=club).values_list(
            'bank_transfer_instructions', flat=True
        ).first()
        if not instructions or not instructions.strip():
            raise serializers.ValidationError({
                'plan': 'El gimnasio aún no ha configurado las instrucciones para transferencias.'
            })
        attrs['plan_instance'] = plan

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        plan = validated_data.pop('plan_instance')
        validated_data.pop('plan')
        password = validated_data.pop('password')
        proof = validated_data.pop('proof')
        role, _ = Role.objects.get_or_create(name='ATHLETE', defaults={'description': 'Deportista'})
        user = User.objects.create_user(
            username=validated_data.pop('username'),
            email=validated_data.pop('email'),
            password=password,
            first_name=validated_data.pop('first_name'),
            last_name=validated_data.pop('last_name'),
            phone=validated_data.pop('phone', ''),
            role=role,
            club=plan.club,
            is_active=False,
        )
        athlete = Athlete.objects.create(
            club=plan.club,
            user=user,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            status='INACTIVE',
        )
        membership = PlanMembership.objects.create(
            club=plan.club,
            plan=plan,
            user=user,
            athlete=athlete,
            price_at_signup=plan.price,
            payment_proof=proof,
        )
        for admin in User.objects.filter(club=plan.club, role__name='ADMIN', is_active=True):
            Notification.objects.create(
                club=plan.club,
                user=admin,
                title='Nueva solicitud de plan',
                message=f'{user.get_full_name() or user.username} envió un comprobante para {plan.name}.',
                notification_type='ALERT',
                action_url='/memberships',
            )
        return membership


class MembershipSignupView(generics.CreateAPIView):
    serializer_class = MembershipSignupSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['club'] = get_object_or_404(
            Club,
            pk=self.kwargs['club_id'],
            verification_status='APPROVED',
            is_public=True,
            is_active=True,
        )
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()
        return Response(
            {
                'detail': 'Solicitud enviada. El gimnasio revisará el comprobante y aprobará tu ingreso.',
                'status': membership.status,
            },
            status=status.HTTP_201_CREATED,
        )


class MembershipSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_duration = serializers.CharField(source='plan.duration', read_only=True)
    classes_per_week = serializers.IntegerField(source='plan.classes_per_week', read_only=True)
    is_premium = serializers.BooleanField(source='plan.is_premium', read_only=True)
    athlete_name = serializers.CharField(source='athlete.display_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    has_payment_proof = serializers.SerializerMethodField()

    class Meta:
        model = PlanMembership
        fields = [
            'id', 'plan', 'plan_name', 'plan_duration', 'classes_per_week', 'is_premium',
            'athlete_name', 'user_email', 'price_at_signup', 'starts_on', 'expires_on',
            'status', 'review_note', 'created_at', 'has_payment_proof',
        ]

    def get_has_payment_proof(self, membership):
        return bool(membership.payment_proof)


class ClubMembershipListView(generics.ListAPIView):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if user_role(self.request.user) != 'ADMIN' and not self.request.user.is_superuser:
            raise PermissionDenied('Solo el administrador del club puede revisar solicitudes de planes.')
        queryset = PlanMembership.objects.select_related('plan', 'athlete', 'user', 'club')
        if not self.request.user.is_superuser:
            queryset = queryset.filter(club_id=self.request.user.club_id)
        return queryset


class CurrentMembershipView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if user_role(request.user) != 'ATHLETE':
            raise PermissionDenied('Esta información está disponible para deportistas.')
        today = timezone.localdate()
        membership = PlanMembership.objects.filter(
            user=request.user,
            status='ACTIVE',
            starts_on__lte=today,
            expires_on__gte=today,
        ).select_related('plan').first()
        if not membership:
            return Response(None)
        requested_week = request.query_params.get('week_start')
        try:
            week_start = date.fromisoformat(requested_week) if requested_week else today - timedelta(days=today.weekday())
        except ValueError:
            raise ValidationError({'week_start': 'Usa una fecha válida que comience en lunes.'})
        if week_start.weekday() != 0:
            raise ValidationError({'week_start': 'La semana debe comenzar el lunes.'})
        quota = weekly_quota_stats(membership.athlete, week_start)
        weekly_limit = membership.plan.classes_per_week
        data = MembershipSerializer(membership).data
        data.update({
            'classes_used_this_week': quota['attended'],
            'classes_reserved_this_week': quota['used'],
            'classes_remaining_this_week': (
                None if weekly_limit is None else max(0, weekly_limit - quota['used'])
            ),
        })
        return Response(data)


class MembershipReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if user_role(request.user) != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied('Solo el administrador del club puede revisar solicitudes.')
        decision = request.data.get('decision')
        if decision not in ('APPROVE', 'REJECT'):
            raise ValidationError({'decision': 'Selecciona aprobar o rechazar.'})
        note = str(request.data.get('note', '')).strip()[:500]
        if decision == 'REJECT' and not note:
            raise ValidationError({'note': 'Explica brevemente por qué se rechaza la solicitud.'})

        with transaction.atomic():
            queryset = PlanMembership.objects.select_for_update().select_related('club', 'user', 'athlete')
            if not request.user.is_superuser:
                queryset = queryset.filter(club_id=request.user.club_id)
            membership = get_object_or_404(queryset, pk=pk, status='PENDING')
            if decision == 'APPROVE':
                if not membership.club.is_active or membership.club.verification_status != 'APPROVED':
                    raise ValidationError({'club': 'El gimnasio debe estar aprobado y activo para habilitar nuevos deportistas.'})
                date_serializer = MembershipApprovalDatesSerializer(data=request.data)
                date_serializer.is_valid(raise_exception=True)
                membership.starts_on = date_serializer.validated_data['starts_on']
                membership.expires_on = date_serializer.validated_data['expires_on']
                membership.status = 'ACTIVE'
                membership.user.is_active = True
                membership.user.save(update_fields=['is_active', 'updated_at'])
                membership.athlete.status = 'ACTIVE'
                membership.athlete.admission_date = membership.starts_on
                membership.athlete.save(update_fields=['status', 'admission_date', 'updated_at'])
            else:
                membership.status = 'REJECTED'
            membership.reviewed_by = request.user
            membership.reviewed_at = timezone.now()
            membership.review_note = note
            membership.save()
            Notification.objects.create(
                club=membership.club,
                user=membership.user,
                title='Solicitud de plan revisada',
                message=(
                    'Tu ingreso fue aprobado. Ya puedes iniciar sesión y reservar clases.'
                    if decision == 'APPROVE'
                    else f'Tu solicitud fue rechazada. Motivo: {note}'
                ),
                notification_type='ALERT',
                action_url='/trainings',
            )
        return Response(MembershipSerializer(membership).data)


class MembershipApprovalDatesSerializer(serializers.Serializer):
    starts_on = serializers.DateField()
    expires_on = serializers.DateField()

    def validate(self, attrs):
        if attrs['expires_on'] < attrs['starts_on']:
            raise serializers.ValidationError({'expires_on': 'La fecha de vencimiento debe ser posterior al inicio.'})
        return attrs


class MembershipProofDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        if user_role(request.user) != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied('Solo el administrador del club puede revisar comprobantes.')
        queryset = PlanMembership.objects.select_related('club')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        membership = get_object_or_404(queryset, pk=pk)
        if not membership.payment_proof:
            raise ValidationError({'proof': 'Esta solicitud no tiene comprobante.'})
        content_type = mimetypes.guess_type(membership.payment_proof.name)[0] or 'application/octet-stream'
        return FileResponse(
            membership.payment_proof.open('rb'),
            content_type=content_type,
            filename=Path(membership.payment_proof.name).name,
        )
