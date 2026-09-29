from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.athletes.models import Athlete
from apps.common.permissions import ClubRolePermission, user_role
from apps.notifications.models import Notification
from apps.trainings.models import Training
from apps.trainings.models import TrainingReservation
from apps.trainings.serializers import TrainingReservationSerializer, TrainingSerializer


class ClubTrainingPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')
    write_roles = ('ADMIN', 'TRAINER')
    message = 'Solo el equipo del club puede programar o modificar clases.'

    def has_object_permission(self, request, view, obj):
        if not super().has_object_permission(request, view, obj):
            return False
        if user_role(request.user) != 'ATHLETE' or request.method not in permissions.SAFE_METHODS:
            return True
        athlete = Athlete.objects.filter(user=request.user, club_id=obj.club_id).only('group_id').first()
        return bool(athlete and (obj.group_id is None or obj.group_id == athlete.group_id))


class TrainingListCreateView(generics.ListCreateAPIView):
    serializer_class = TrainingSerializer
    permission_classes = [permissions.IsAuthenticated, ClubTrainingPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Training.objects.select_related('club', 'trainer', 'group').annotate(
            reserved_count=Count('reservations', filter=Q(reservations__status='RESERVED'))
        )
        if user.is_superuser:
            return queryset.all()
        queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'ATHLETE':
            athlete = Athlete.objects.filter(user=user, club_id=user.club_id).only('group_id').first()
            if not athlete:
                return queryset.none()
            queryset = queryset.filter(Q(group__isnull=True) | Q(group_id=athlete.group_id))
        return queryset.order_by('scheduled_date', 'start_time', 'id')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


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
        if lock:
            queryset = queryset.select_for_update()
        return get_object_or_404(queryset, pk=training_id)

    def get(self, request, training_id):
        training = self.get_training(request, training_id)
        role_name = getattr(getattr(request.user, 'role', None), 'name', None)
        reservations = TrainingReservation.objects.filter(training=training, status='RESERVED')
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
                )

        return Response(
            TrainingReservationSerializer(reservation).data,
            status=status.HTTP_201_CREATED,
        )


class TrainingReservationCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, training_id, reservation_id):
        queryset = TrainingReservation.objects.select_related('training', 'athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(training__club_id=request.user.club_id)
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
                )
        return Response(TrainingReservationSerializer(reservation).data)
