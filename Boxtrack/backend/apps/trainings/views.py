from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from datetime import date, timedelta
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.athletes.models import Athlete
from apps.clubs.models import PlanMembership
from apps.common.permissions import ClubRolePermission, scope_to_assigned_athletes, user_role
from apps.notifications.models import Notification
from apps.trainings.models import Training, WeeklyTrainingSchedule
from apps.trainings.models import TrainingReservation
from apps.trainings.quotas import weekly_quota_stats
from apps.trainings.serializers import (
    TrainingReservationSerializer,
    TrainingSerializer,
    WeeklyTrainingScheduleSerializer,
)


def ensure_upcoming_weekly_trainings(club_id, from_date=None):
    if not club_id:
        return
    today = from_date or timezone.localdate()
    last_day = today + timedelta(days=83)
    schedules = WeeklyTrainingSchedule.objects.filter(
        club_id=club_id,
        is_active=True,
        starts_on__lte=last_day,
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).select_related('trainer', 'group')
    for schedule in schedules:
        first_day = max(today, schedule.starts_on)
        final_day = min(last_day, schedule.ends_on) if schedule.ends_on else last_day
        matching_dates = [
            first_day + timedelta(days=offset)
            for offset in range((final_day - first_day).days + 1)
            if (first_day + timedelta(days=offset)).weekday() in schedule.weekdays
        ]
        existing_dates = set(
            Training.objects.filter(
                weekly_schedule=schedule,
                scheduled_date__in=matching_dates,
            ).values_list('scheduled_date', flat=True)
        )
        Training.objects.bulk_create(
            [
                Training(
                    club_id=club_id,
                    title=schedule.title,
                    description=schedule.description,
                    activity_type=schedule.activity_type,
                    trainer=schedule.trainer,
                    group=schedule.group,
                    scheduled_date=scheduled_date,
                    start_time=schedule.start_time,
                    duration_minutes=schedule.duration_minutes,
                    capacity=schedule.capacity,
                    weekly_schedule=schedule,
                    objectives=schedule.objectives,
                )
                for scheduled_date in matching_dates
                if scheduled_date not in existing_dates
            ],
            ignore_conflicts=True,
        )


class ClubTrainingPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')
    write_roles = ('ADMIN', 'TRAINER')
    message = 'Solo el equipo del club puede programar o modificar clases.'

    def has_permission(self, request, view):
        user = request.user
        if (
            user and user.is_authenticated and request.method in permissions.SAFE_METHODS
            and user_role(user) == 'ATHLETE' and user.club_id and user.club.is_active
        ):
            # Los deportistas deben ver la agenda aunque el club aún esté en verificación.
            return True
        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if obj.club_id != request.user.club_id:
            return False
        if user_role(request.user) == 'TRAINER' and obj.trainer_id != request.user.id:
            return False
        if user_role(request.user) != 'ATHLETE' or request.method not in permissions.SAFE_METHODS:
            return True
        athlete = Athlete.objects.filter(user=request.user, club_id=obj.club_id).only('group_id').first()
        return bool(athlete and (obj.group_id is None or obj.group_id == athlete.group_id))


class TrainingListCreateView(generics.ListCreateAPIView):
    serializer_class = TrainingSerializer
    permission_classes = [permissions.IsAuthenticated, ClubTrainingPermission]

    def list(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            if user_role(request.user) == 'ATHLETE':
                self.week_start = self._week_start_from_query(request.query_params.get('week_start'))
                ensure_upcoming_weekly_trainings(request.user.club_id, self.week_start)
            else:
                ensure_upcoming_weekly_trainings(request.user.club_id)
        return super().list(request, *args, **kwargs)

    @staticmethod
    def _week_start_from_query(value):
        if not value:
            today = timezone.localdate()
            return today - timedelta(days=today.weekday())
        try:
            requested_date = date.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValidationError({'week_start': 'Indica una fecha válida en formato YYYY-MM-DD.'})
        if requested_date.weekday() != 0:
            raise ValidationError({'week_start': 'La semana debe comenzar un lunes.'})
        return requested_date

    def get_queryset(self):
        user = self.request.user
        queryset = Training.objects.select_related('club', 'trainer', 'group').annotate(
            reserved_count=Count('reservations', filter=Q(reservations__status='RESERVED'))
        )
        if user.is_superuser:
            return queryset.all()
        queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'ATHLETE':
            athlete = Athlete.objects.filter(user=user, club_id=user.club_id).only('id', 'group_id').first()
            if not athlete:
                return queryset.none()
            week_start = getattr(self, 'week_start', self._week_start_from_query(None))
            week_end = week_start + timedelta(days=7)
            today = timezone.localdate()
            membership = PlanMembership.objects.filter(
                athlete=athlete,
                status='ACTIVE',
                starts_on__lte=min(today, week_end - timedelta(days=1)),
                expires_on__gte=max(today, week_start),
            ).first()
            if not membership:
                return queryset.none()
            membership_start = max(week_start, membership.starts_on)
            membership_end = min(week_end - timedelta(days=1), membership.expires_on)
            own_reservation = TrainingReservation.objects.filter(
                training_id=OuterRef('pk'),
                athlete_id=athlete.id,
                status='RESERVED',
            ).values('id')[:1]
            queryset = queryset.filter(
                Q(group__isnull=True) | Q(group_id=athlete.group_id),
                scheduled_date__gte=membership_start,
                scheduled_date__lte=membership_end,
            ).annotate(
                own_reservation_id=Subquery(own_reservation)
            )
        elif user_role(user) == 'TRAINER':
            queryset = queryset.filter(trainer_id=user.id)
        return queryset.order_by('scheduled_date', 'start_time', 'id')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class WeeklyTrainingScheduleListCreateView(generics.ListCreateAPIView):
    serializer_class = WeeklyTrainingScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, ClubTrainingPermission]

    def get_queryset(self):
        queryset = WeeklyTrainingSchedule.objects.select_related('club', 'trainer', 'group')
        user = self.request.user
        if user.is_superuser:
            return queryset.all()
        queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'TRAINER':
            queryset = queryset.filter(trainer_id=user.id)
        return queryset

    def perform_create(self, serializer):
        schedule = serializer.save(club=self.request.user.club)
        ensure_upcoming_weekly_trainings(schedule.club_id)


class WeeklyTrainingScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WeeklyTrainingScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, ClubTrainingPermission]

    def get_queryset(self):
        queryset = WeeklyTrainingSchedule.objects.select_related('club', 'trainer', 'group')
        user = self.request.user
        if user.is_superuser:
            return queryset.all()
        queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'TRAINER':
            queryset = queryset.filter(trainer_id=user.id)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class TrainingDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TrainingSerializer
    permission_classes = [permissions.IsAuthenticated, ClubTrainingPermission]

    def get_queryset(self):
        queryset = Training.objects.select_related('club', 'trainer', 'group').annotate(
            reserved_count=Count('reservations', filter=Q(reservations__status='RESERVED'))
        )
        return queryset


class TrainingReservationListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_training(self, request, training_id, lock=False):
        queryset = Training.objects.all()
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'TRAINER':
            queryset = queryset.filter(trainer_id=request.user.id)
        if lock:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=training_id)

    def get(self, request, training_id):
        training = self.get_training(request, training_id)
        role_name = getattr(getattr(request.user, 'role', None), 'name', None)
        reservations = TrainingReservation.objects.filter(training=training, status='RESERVED').select_related('athlete', 'athlete__user')
        if role_name == 'ATHLETE':
            athlete = get_object_or_404(Athlete, user=request.user, club=training.club)
            if training.group_id is not None and training.group_id != athlete.group_id:
                raise PermissionDenied('Esta clase corresponde a otro grupo de preparación.')
            reservations = reservations.filter(athlete=athlete)
        elif role_name not in ('ADMIN', 'TRAINER') and not request.user.is_superuser:
            raise PermissionDenied('No tienes permisos para ver las reservas.')
        return Response(TrainingReservationSerializer(reservations.select_related('athlete'), many=True).data)

    def post(self, request, training_id):
        role_name = getattr(getattr(request.user, 'role', None), 'name', None)
        with transaction.atomic():
            training = self.get_training(request, training_id, lock=True)
            if training.status != 'SCHEDULED':
                return Response({'detail': 'Esta clase no acepta reservas.'}, status=status.HTTP_400_BAD_REQUEST)

            if role_name == 'ATHLETE':
                athlete = get_object_or_404(Athlete, user=request.user, club=training.club, status='ACTIVE')
                if training.group_id is not None and training.group_id != athlete.group_id:
                    raise PermissionDenied('Esta clase corresponde a otro grupo de preparación.')
                membership = PlanMembership.objects.select_for_update().filter(
                    athlete=athlete,
                    status='ACTIVE',
                    starts_on__lte=min(timezone.localdate(), training.scheduled_date),
                    expires_on__gte=max(timezone.localdate(), training.scheduled_date),
                ).select_related('plan').first()
                if not membership:
                    raise PermissionDenied('Necesitas una membresía vigente en la fecha de esta clase.')
                weekly_limit = membership.plan.classes_per_week
                if weekly_limit is not None:
                    week_start = training.scheduled_date - timedelta(days=training.scheduled_date.weekday())
                    quota = weekly_quota_stats(athlete, week_start)
                    if quota['used'] >= weekly_limit:
                        return Response(
                            {'detail': f'Tu plan permite hasta {weekly_limit} clases por semana. Marca una ausencia o cancela una reserva para liberar el cupo.'},
                            status=status.HTTP_409_CONFLICT,
                        )
            elif role_name in ('ADMIN', 'TRAINER') or request.user.is_superuser:
                athlete_id = request.data.get('athlete')
                if not athlete_id:
                    return Response({'athlete': 'Debes indicar el deportista.'}, status=status.HTTP_400_BAD_REQUEST)
                athlete = get_object_or_404(Athlete, pk=athlete_id, club=training.club, status='ACTIVE')
            else:
                raise PermissionDenied('No tienes permisos para reservar esta clase.')

            reservation = TrainingReservation.objects.filter(training=training, athlete=athlete).first()
            if reservation and reservation.status == 'RESERVED':
                return Response({'detail': 'El deportista ya tiene un cupo reservado.'}, status=status.HTTP_409_CONFLICT)

            active_reservations = TrainingReservation.objects.filter(training=training, status='RESERVED').count()
            if active_reservations >= training.capacity:
                return Response({'detail': 'La clase ya alcanzó su capacidad máxima.'}, status=status.HTTP_409_CONFLICT)

            if reservation:
                reservation.status = 'RESERVED'
                reservation.save(update_fields=['status', 'updated_at'])
            else:
                reservation = TrainingReservation.objects.create(training=training, athlete=athlete)
            if athlete.user_id:
                Notification.objects.create(
                    club=training.club,
                    user=athlete.user,
                    title='Cupo reservado',
                    message=f'Tu cupo para {training.title} quedó confirmado.',
                    notification_type='TRAINING',
                    action_url='/trainings',
                )

        return Response(
            TrainingReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class TrainingReservationCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, training_id, reservation_id):
        queryset = TrainingReservation.objects.select_related('training', 'athlete', 'athlete__user')
        if not request.user.is_superuser:
            queryset = queryset.filter(training__club_id=request.user.club_id)
        if user_role(request.user) == 'TRAINER':
            queryset = queryset.filter(training__trainer_id=request.user.id)
        reservation = get_object_or_404(queryset, pk=reservation_id, training_id=training_id)
        role_name = getattr(getattr(request.user, 'role', None), 'name', None)
        if role_name == 'ATHLETE':
            if reservation.athlete.user_id != request.user.id:
                raise PermissionDenied('Solo puedes cancelar tu propia reserva.')
        elif role_name not in ('ADMIN', 'TRAINER') and not request.user.is_superuser:
            raise PermissionDenied('No tienes permisos para cancelar reservas.')

        if reservation.status == 'RESERVED':
            reservation.status = 'CANCELLED'
            reservation.save(update_fields=['status', 'updated_at'])
            if reservation.athlete.user_id:
                Notification.objects.create(
                    club=reservation.training.club,
                    user=reservation.athlete.user,
                    title='Reserva cancelada',
                    message=f'Se canceló tu cupo para {reservation.training.title}.',
                    notification_type='TRAINING',
                    action_url='/trainings',
                )
        return Response(TrainingReservationSerializer(reservation).data)
