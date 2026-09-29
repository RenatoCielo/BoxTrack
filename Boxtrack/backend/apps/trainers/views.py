from rest_framework import generics, permissions

from apps.trainers.models import TrainerProfile
from apps.trainers.serializers import TrainerProfileSerializer
from apps.common.permissions import AdminOnlyPermission


class TrainerListCreateView(generics.ListCreateAPIView):
    serializer_class = TrainerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOnlyPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return TrainerProfile.objects.select_related('club', 'user').all()
        return TrainerProfile.objects.filter(club_id=user.club_id).select_related('club', 'user')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class TrainerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TrainerProfile.objects.select_related('club', 'user').all()
    serializer_class = TrainerProfileSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOnlyPermission]
