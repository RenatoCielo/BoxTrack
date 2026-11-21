from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from apps.clubs.models import Plan, PublicSiteSettings
from apps.clubs.serializers import (
    ClubBrandSettingsSerializer, ClubPublicationSerializer, PlanSerializer,
    PublicSiteSettingsSerializer,
)
from apps.common.permissions import AdminOnlyPermission, SuperuserOnlyPermission


class ClubPublicationPermission(AdminOnlyPermission):
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        return request.user.is_superuser or obj.pk == request.user.club_id


class ClubAdminSettingsPermission(AdminOnlyPermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and not request.user.is_superuser
            and super().has_permission(request, view)
        )


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


class ClubBrandSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = ClubBrandSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminSettingsPermission]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        if not self.request.user.club_id:
            raise ValidationError('Solo el administrador de un gimnasio puede personalizar su página.')
        return self.request.user.club


class PublicSiteSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = PublicSiteSettingsSerializer
    permission_classes = [permissions.IsAuthenticated, SuperuserOnlyPermission]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        settings, _ = PublicSiteSettings.objects.get_or_create(pk=1)
        return settings
