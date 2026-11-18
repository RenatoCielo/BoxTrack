from django.urls import path

from apps.clubs.views import (
    ClubDetailView,
    ClubListView,
    ClubPendingListView,
    ClubVerificationDocumentUploadView,
    ClubVerificationUpdateView,
)
from apps.clubs.plan_views import ClubPublicationView, PlanDetailView, PlanListCreateView

urlpatterns = [
    path('', ClubListView.as_view(), name='club-list'),
    path('pending/', ClubPendingListView.as_view(), name='club-pending-list'),
    path('plans/', PlanListCreateView.as_view(), name='club-plans'),
    path('plans/<int:pk>/', PlanDetailView.as_view(), name='club-plan-detail'),
    path('publication/', ClubPublicationView.as_view(), name='club-publication'),
    path('<int:pk>/', ClubDetailView.as_view(), name='club-detail'),
    path('<int:pk>/review/', ClubVerificationUpdateView.as_view(), name='club-review'),
    path('<int:pk>/document/', ClubVerificationDocumentUploadView.as_view(), name='club-verification-document'),
]
