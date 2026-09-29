from rest_framework import generics, permissions

from apps.clubs.models import Club
from apps.clubs.serializers import ClubSerializer


class ClubAccessPermission(permissions.BasePermission):
    message = 'No tienes permisos para acceder a este club.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'club_id', None) == getattr(obj, 'id', None)


class ClubListView(generics.ListAPIView):
    serializer_class = ClubSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, 'is_superuser', False):
            return Club.objects.all()
        if getattr(self.request.user, 'club_id', None):
            return Club.objects.filter(pk=self.request.user.club_id)
        return Club.objects.none()


class ClubDetailView(generics.RetrieveAPIView):
    serializer_class = ClubSerializer
    queryset = Club.objects.all()
    permission_classes = [permissions.IsAuthenticated, ClubAccessPermission]
