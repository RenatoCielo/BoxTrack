from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied

from apps.alerts.models import Alert
from apps.alerts.serializers import AlertSerializer
from apps.common.permissions import StaffWritePermission


class AlertListCreateView(generics.ListCreateAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return Alert.objects.filter(club_id=self.request.user.club_id).select_related('athlete').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class AlertDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return Alert.objects.filter(club_id=self.request.user.club_id).select_related('athlete')