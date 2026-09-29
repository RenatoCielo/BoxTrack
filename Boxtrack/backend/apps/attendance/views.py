from rest_framework import generics, permissions

from apps.attendance.models import Attendance
from apps.attendance.serializers import AttendanceSerializer
from apps.common.permissions import StaffWritePermission


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Attendance.objects.select_related('club', 'athlete', 'training').all()
        return Attendance.objects.filter(club_id=user.club_id).select_related('club', 'athlete', 'training')

    def perform_create(self, serializer):
        athlete = serializer.validated_data['athlete']
        training = serializer.validated_data['training']

        if athlete.club_id != self.request.user.club_id or training.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para registrar esta asistencia.')

        serializer.save(club=self.request.user.club)


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.select_related('club', 'athlete', 'training').all()
    serializer_class = AttendanceSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]
