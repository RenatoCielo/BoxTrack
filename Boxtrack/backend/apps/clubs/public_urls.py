from django.urls import path

from apps.clubs.membership_views import MembershipSignupView
from apps.clubs.public_views import PublicClubDetailView, PublicClubListView, PublicSiteOverviewView

urlpatterns = [
    path('site/', PublicSiteOverviewView.as_view(), name='public-site-overview'),
    path('<int:club_id>/memberships/', MembershipSignupView.as_view(), name='public-membership-signup'),
    path('', PublicClubListView.as_view(), name='public-club-list'),
    path('<int:pk>/', PublicClubDetailView.as_view(), name='public-club-detail'),
]
