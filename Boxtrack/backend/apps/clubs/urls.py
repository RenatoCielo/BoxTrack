from django.urls import path

from apps.clubs.views import ClubListView, ClubDetailView

urlpatterns = [
    path('', ClubListView.as_view(), name='club-list'),
    path('<int:pk>/', ClubDetailView.as_view(), name='club-detail'),
]
