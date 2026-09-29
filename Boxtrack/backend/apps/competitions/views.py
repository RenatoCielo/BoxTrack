from rest_framework import generics, permissions

from apps.athletes.models import Athlete
from apps.competitions.models import Competition
from apps.competitions.serializers import CompetitionSerializer, FightRecordSerializer
from apps.common.permissions import StaffWritePermission


class ClubCompetitionPermission(permissions.BasePermission):
    message = 'No tienes permisos para acceder a este historial de peleas.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'club_id', None) == getattr(obj, 'club_id', None)


class FightRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = FightRecordSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        athlete_id = self.request.query_params.get('athlete')

        queryset = Competition.objects.filter(club_id=user.club_id).select_related('athlete')
        if athlete_id:
            athlete = Athlete.objects.filter(id=athlete_id).first()
            if athlete is None:
                self.permission_denied(self.request, message='No tienes permisos para consultar este historial.')
            if athlete.club_id != user.club_id:
                self.permission_denied(self.request, message='No tienes permisos para consultar este historial.')
            queryset = queryset.filter(athlete=athlete)
        return queryset.order_by('-fight_date')

    def perform_create(self, serializer):
        athlete = serializer.validated_data['athlete']
        if athlete.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para registrar peleas de este deportista.')
        serializer.save(club=self.request.user.club)


class FightRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FightRecordSerializer
    queryset = Competition.objects.select_related('athlete').all()
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        return Competition.objects.filter(club_id=user.club_id).select_related('athlete')

    def get_object(self):
        obj = super().get_object()
        if obj.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para acceder a este historial.')
        return obj
