from django.urls import path

from apps.clubs.views import (
    ClubDetailView,
    ClubBrandingView,
    ClubDisciplineInitializeView,
    ClubListView,
    ClubPendingListView,
    ClubVerificationDocumentUploadView,
    ClubVerificationUpdateView,
)

urlpatterns = [
    path('', ClubListView.as_view(), name='club-list'),
    path('branding/', ClubBrandingView.as_view(), name='club-branding'),
    path('discipline/initialize/', ClubDisciplineInitializeView.as_view(), name='club-discipline-initialize'),
    path('pending/', ClubPendingListView.as_view(), name='club-pending-list'),
    path('<int:pk>/', ClubDetailView.as_view(), name='club-detail'),
    path('<int:pk>/review/', ClubVerificationUpdateView.as_view(), name='club-review'),
    path('<int:pk>/document/', ClubVerificationDocumentUploadView.as_view(), name='club-verification-document'),
]
