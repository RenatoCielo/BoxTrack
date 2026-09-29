from django.db.models import Q
from rest_framework import generics, permissions, filters

from apps.athletes.models import Athlete
from apps.athletes.serializers import AthleteSerializer
from apps.common.permissions import ClubRolePermission


class ClubAthletePermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER')
    write_roles = ('ADMIN',)
    message = 'Solo el administrador puede crear o modificar fichas de deportistas.'


class AthleteListCreateView(generics.ListCreateAPIView):
    serializer_class = AthleteSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAthletePermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name', 'category']
    ordering_fields = ['first_name', 'admission_date', 'status']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = Athlete.objects.select_related('club', 'group', 'assigned_trainer').all()
        else:
            queryset = Athlete.objects.filter(club_id=user.club_id).select_related('club', 'group', 'assigned_trainer')
        competitor_filter = self.request.query_params.get('is_competitor')
        if competitor_filter in ('true', 'false'):
            queryset = queryset.filter(is_competitor=competitor_filter == 'true')
        return queryset.order_by('last_name', 'first_name', 'id')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class AthleteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Athlete.objects.select_related('club', 'group', 'assigned_trainer').all()
    serializer_class = AthleteSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAthletePermission]

    def perform_update(self, serializer):
        athlete = serializer.save()
        if athlete.user_id:
            should_be_active = athlete.status == 'ACTIVE'
            if athlete.user.is_active != should_be_active:
                athlete.user.is_active = should_be_active
                athlete.user.save(update_fields=['is_active'])

    def perform_destroy(self, instance):
        instance.status = 'INACTIVE'
        instance.save(update_fields=['status', 'updated_at'])
        if instance.user_id and instance.user.is_active:
            instance.user.is_active = False
            instance.user.save(update_fields=['is_active'])
