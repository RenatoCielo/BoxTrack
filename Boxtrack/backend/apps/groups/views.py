from rest_framework import generics, permissions

from apps.groups.models import Group
from apps.groups.serializers import GroupSerializer
from apps.common.permissions import ClubRolePermission


class ClubGroupPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER')
    write_roles = ('ADMIN',)
    message = 'Solo el administrador puede crear o modificar grupos.'


class GroupListCreateView(generics.ListCreateAPIView):
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, ClubGroupPermission]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Group.objects.select_related('club').all()
        return Group.objects.filter(club_id=user.club_id).select_related('club')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class GroupDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Group.objects.select_related('club').all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated, ClubGroupPermission]
