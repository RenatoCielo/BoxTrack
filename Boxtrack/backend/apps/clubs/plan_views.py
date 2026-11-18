from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError

from apps.clubs.models import Plan
from apps.clubs.serializers import ClubPublicationSerializer, PlanSerializer
from apps.common.permissions import AdminOnlyPermission


class ClubPublicationPermission(AdminOnlyPermission):
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        return request.user.is_superuser or obj.pk == request.user.club_id


class PlanListCreateView(generics.ListCreateAPIView):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOnlyPermission]

    def get_queryset(self):
        queryset = Plan.objects.select_related('club')
        if not self.request.user.is_superuser:
            queryset = queryset.filter(club_id=self.request.user.club_id)
        return queryset

    def perform_create(self, serializer):
        club = self.request.user.club
        if club is None:
            raise ValidationError('Tu cuenta debe estar asociada a un club para crear planes.')
        serializer.save(club=club)


class PlanDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOnlyPermission]

    def get_queryset(self):
        queryset = Plan.objects.select_related('club')
        if not self.request.user.is_superuser:
            queryset = queryset.filter(club_id=self.request.user.club_id)
        return queryset


class ClubPublicationView(generics.RetrieveUpdateAPIView):
    serializer_class = ClubPublicationSerializer
    permission_classes = [permissions.IsAuthenticated, ClubPublicationPermission]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        club = self.request.user.club
        if club is None:
            raise ValidationError('Tu cuenta debe estar asociada a un club para editar su publicación.')
        self.check_object_permissions(self.request, club)
        return club
