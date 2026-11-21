from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.clubs.models import Club, Plan, PublicSiteSettings
from apps.clubs.serializers import PublicClubDetailSerializer, PublicClubListSerializer
from apps.competitions.models import FightAgreement, FightBout


class PublicClubUpdateSerializer(serializers.ModelSerializer):
    update_type = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'description', 'created_at', 'updated_at', 'update_type']

    def get_update_type(self, club):
        return 'NEW' if abs((club.updated_at - club.created_at).total_seconds()) < 2 else 'UPDATED'


class PublicFightHighlightSerializer(serializers.ModelSerializer):
    proposing_club_name = serializers.CharField(source='proposing_club.name', read_only=True)
    opponent_club_name = serializers.CharField(source='opponent_club.name', read_only=True)
    confirmed_bouts = serializers.SerializerMethodField()

    class Meta:
        model = FightAgreement
        fields = [
            'id', 'proposing_club_name', 'opponent_club_name',
            'planned_date', 'location', 'confirmed_bouts',
        ]

    def get_confirmed_bouts(self, agreement):
        return [
            {'id': bout.pk, 'category': bout.home_athlete.category or bout.away_athlete.category}
            for bout in agreement.bouts.all()
            if bout.home_athlete_id and bout.away_athlete_id
        ]


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


class PublicSiteOverviewView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        clubs = Club.objects.filter(
            verification_status='APPROVED',
            is_public=True,
            is_active=True,
        ).order_by('-updated_at', '-id')[:6]
        confirmed_bouts = FightBout.objects.filter(
            status='CONFIRMED',
            home_athlete__isnull=False,
            away_athlete__isnull=False,
        ).select_related('home_athlete', 'away_athlete')
        agreements = FightAgreement.objects.filter(
            status='CONFIRMED',
            planned_date__gte=timezone.localdate(),
            proposing_club__verification_status='APPROVED',
            proposing_club__is_public=True,
            proposing_club__is_active=True,
            opponent_club__verification_status='APPROVED',
            opponent_club__is_public=True,
            opponent_club__is_active=True,
        ).filter(bouts__status='CONFIRMED').distinct().select_related(
            'proposing_club', 'opponent_club'
        ).prefetch_related(
            Prefetch('bouts', queryset=confirmed_bouts)
        ).order_by('planned_date', 'id')[:5]
        settings = PublicSiteSettings.objects.first()
        promotion_image = None
        if settings and settings.promotion_image:
            promotion_image = request.build_absolute_uri(settings.promotion_image.url)
        return Response({
            'promotion': {
                'headline': settings.headline if settings and settings.headline else 'Próximos combates',
                'intro': settings.intro if settings and settings.intro else 'Encuentros confirmados por gimnasios de nuestra comunidad.',
                'image': promotion_image,
            },
            'club_updates': PublicClubUpdateSerializer(clubs, many=True, context={'request': request}).data,
            'featured_fights': PublicFightHighlightSerializer(
                agreements, many=True, context={'request': request}
            ).data,
        })
