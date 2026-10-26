from django.urls import path

from apps.competitions.views import FightRecordListCreateView, FightRecordDetailView

from apps.competitions.inter_club import (
    CompetitorDirectoryView, CompetitorRequestListCreateView, CompetitorRequestReviewView,
    FightMatchActionView, FightMatchListCreateView,
)

urlpatterns = [
    path('competitor-requests/', CompetitorRequestListCreateView.as_view(), name='competitor-request-list-create'),
    path('competitor-requests/<int:pk>/review/', CompetitorRequestReviewView.as_view(), name='competitor-request-review'),
    path('matches/', FightMatchListCreateView.as_view(), name='fight-match-list-create'),
    path('matches/<int:pk>/<str:action>/', FightMatchActionView.as_view(), name='fight-match-action'),
    path('directory/', CompetitorDirectoryView.as_view(), name='competitor-directory'),
    path('fights/', FightRecordListCreateView.as_view(), name='fight-record-list-create'),
    path('fights/<int:pk>/', FightRecordDetailView.as_view(), name='fight-record-detail'),
]
