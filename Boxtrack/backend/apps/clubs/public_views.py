from django.db.models import Prefetch
from rest_framework import generics, permissions

from apps.clubs.models import Club, Plan
from apps.clubs.serializers import PublicClubDetailSerializer, PublicClubListSerializer


class PublicClubListView(generics.ListAPIView):
    serializer_class = PublicClubListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Club.objects.filter(
            verification_status='APPROVED',
            is_public=True,
            is_active=True,
        ).order_by('name')


class PublicClubDetailView(generics.RetrieveAPIView):
    serializer_class = PublicClubDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        active_plans = Plan.objects.filter(is_active=True).order_by('sort_order', 'id')
        return Club.objects.filter(
            verification_status='APPROVED',
            is_public=True,
            is_active=True,
        ).prefetch_related(
            Prefetch('plans', queryset=active_plans, to_attr='active_public_plans')
        )
