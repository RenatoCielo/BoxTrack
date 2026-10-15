from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.alerts.models import Alert
from apps.alerts.serializers import AlertSerializer
from apps.common.permissions import StaffWritePermission, user_role


class AlertListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        queryset = Alert.objects.filter(club_id=self.request.user.club_id).select_related('athlete')
        if user_role(self.request.user) == 'TRAINER':
            queryset = queryset.filter(Q(athlete__isnull=True) | Q(athlete__assigned_trainer_id=self.request.user.id))
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class AlertDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        queryset = Alert.objects.filter(club_id=self.request.user.club_id).select_related('athlete')
        if user_role(self.request.user) == 'TRAINER':
            queryset = queryset.filter(Q(athlete__isnull=True) | Q(athlete__assigned_trainer_id=self.request.user.id))
        return queryset