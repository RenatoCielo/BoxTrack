from django.urls import path

from apps.clubs.public_views import PublicClubDetailView, PublicClubListView

urlpatterns = [
    path('', PublicClubListView.as_view(), name='public-club-list'),
    path('<int:pk>/', PublicClubDetailView.as_view(), name='public-club-detail'),
]
