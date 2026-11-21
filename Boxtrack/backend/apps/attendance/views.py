from datetime import timedelta

from django.db import transaction
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.attendance.serializers import AttendanceSerializer
from apps.clubs.models import PlanMembership
from apps.common.permissions import StaffWritePermission
from apps.common.permissions import scope_to_assigned_athletes
from apps.trainings.models import Training
from apps.trainings.quotas import ATTENDANCE_COUNTS_TOWARD_QUOTA, weekly_quota_stats


def save_attendance_with_quota(serializer):
    athlete = serializer.validated_data.get('athlete', getattr(serializer.instance, 'athlete', None))
    training = serializer.validated_data.get('training', getattr(serializer.instance, 'training', None))
    status_value = serializer.validated_data.get(
        'status',
        getattr(serializer.instance, 'status', 'PRESENT'),
    )
    with transaction.atomic():
        membership = PlanMembership.objects.select_for_update().filter(
            athlete=athlete,
            status='ACTIVE',
            starts_on__lte=training.scheduled_date,
            expires_on__gte=training.scheduled_date,
        ).select_related('plan').first()
        if membership and status_value in ATTENDANCE_COUNTS_TOWARD_QUOTA:
            weekly_limit = membership.plan.classes_per_week
            if weekly_limit is not None:
                week_start = training.scheduled_date - timedelta(days=training.scheduled_date.weekday())
                quota = weekly_quota_stats(athlete, week_start)
                instance = serializer.instance
                same_attendance = (
                    instance is not None
                    and instance.athlete_id == athlete.id
                    and instance.training_id == training.id
                )
                previous_status = instance.status if same_attendance else None
                has_active_reservation = training.reservations.filter(
                    athlete=athlete,
                    status='RESERVED',
                ).exists()
                already_counted = (
                    previous_status in ATTENDANCE_COUNTS_TOWARD_QUOTA
                    or (
                        has_active_reservation
                        and previous_status not in ('ABSENT', 'JUSTIFIED')
                    )
                )
                projected_usage = quota['used'] + (0 if already_counted else 1)
                if projected_usage > weekly_limit:
                    raise ValidationError({
                        'status': f'El plan de {athlete} permite {weekly_limit} clases por semana y ya alcanzó ese límite.'
                    })
        serializer.save(club=athlete.club)


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Attendance.objects.select_related('club', 'athlete', 'training')
        if not user.is_superuser:
            queryset = queryset.filter(club_id=user.club_id)
        return scope_to_assigned_athletes(queryset, user)

    def create(self, request, *args, **kwargs):
        athlete_id = request.data.get('athlete')
        training_id = request.data.get('training')
        if athlete_id and training_id and not request.user.is_superuser:
            athlete = Athlete.objects.filter(pk=athlete_id).only('club_id').first()
            training = Training.objects.filter(pk=training_id).only('club_id').first()
            if (athlete and athlete.club_id != request.user.club_id) or (training and training.club_id != request.user.club_id):
                self.permission_denied(request, message='No tienes permisos para registrar asistencia de otro club.')
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        save_attendance_with_quota(serializer)


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Attendance.objects.select_related('club', 'athlete', 'training')
        if not user.is_superuser:
            queryset = queryset.filter(club_id=user.club_id)
        return scope_to_assigned_athletes(queryset, user)

    def perform_update(self, serializer):
        save_attendance_with_quota(serializer)
