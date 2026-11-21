from django.urls import path

from apps.clubs.views import (
    ClubDetailView,
    ClubListView,
    ClubPendingListView,
    ClubVerificationDocumentUploadView,
    ClubVerificationUpdateView,
)
from apps.clubs.plan_views import (
    ClubBrandSettingsView, ClubPublicationView, PlanDetailView, PlanListCreateView,
    PublicSiteSettingsView,
)
from apps.clubs.membership_views import (
    ClubMembershipListView, CurrentMembershipView, MembershipProofDownloadView,
    MembershipReviewView,
)

urlpatterns = [
    path('', ClubListView.as_view(), name='club-list'),
    path('pending/', ClubPendingListView.as_view(), name='club-pending-list'),
    path('memberships/', ClubMembershipListView.as_view(), name='club-memberships'),
    path('memberships/current/', CurrentMembershipView.as_view(), name='current-membership'),
    path('memberships/<int:pk>/review/', MembershipReviewView.as_view(), name='membership-review'),
    path('memberships/<int:pk>/proof/', MembershipProofDownloadView.as_view(), name='membership-proof'),
    path('plans/', PlanListCreateView.as_view(), name='club-plans'),
    path('plans/<int:pk>/', PlanDetailView.as_view(), name='club-plan-detail'),
    path('publication/', ClubPublicationView.as_view(), name='club-publication'),
    path('brand/', ClubBrandSettingsView.as_view(), name='club-brand-settings'),
    path('site-showcase/', PublicSiteSettingsView.as_view(), name='site-showcase-settings'),
    path('<int:pk>/', ClubDetailView.as_view(), name='club-detail'),
    path('<int:pk>/review/', ClubVerificationUpdateView.as_view(), name='club-review'),
    path('<int:pk>/document/', ClubVerificationDocumentUploadView.as_view(), name='club-verification-document'),
]
