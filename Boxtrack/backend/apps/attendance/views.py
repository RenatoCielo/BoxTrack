from rest_framework import generics, permissions

from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.attendance.serializers import AttendanceSerializer
from apps.common.permissions import StaffWritePermission
from apps.common.permissions import scope_to_assigned_athletes
from apps.trainings.models import Training


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
        athlete = serializer.validated_data['athlete']
        training = serializer.validated_data['training']

        if athlete.club_id != self.request.user.club_id or training.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para registrar esta asistencia.')

        serializer.save(club=self.request.user.club)


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Attendance.objects.select_related('club', 'athlete', 'training')
        if not user.is_superuser:
            queryset = queryset.filter(club_id=user.club_id)
        return scope_to_assigned_athletes(queryset, user)
