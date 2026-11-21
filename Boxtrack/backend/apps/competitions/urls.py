from django.urls import path

from apps.competitions.views import (
    FightAgreementDetailView, FightAgreementListCreateView, FightRecordDetailView,
    FightAgreementCompetitorListView, FightBoutDetailView, FightBoutListCreateView,
    FightRecordListCreateView, RivalClubListView, RivalCompetitorListView,
)

urlpatterns = [
    path('fights/', FightRecordListCreateView.as_view(), name='fight-record-list-create'),
    path('fights/<int:pk>/', FightRecordDetailView.as_view(), name='fight-record-detail'),
    path('rivals/', RivalClubListView.as_view(), name='fight-rival-clubs'),
    path('rivals/<int:club_id>/competitors/', RivalCompetitorListView.as_view(), name='fight-rival-competitors'),
    path('agreements/', FightAgreementListCreateView.as_view(), name='fight-agreement-list-create'),
    path('agreements/<int:pk>/', FightAgreementDetailView.as_view(), name='fight-agreement-detail'),
    path('agreements/<int:agreement_id>/competitors/', FightAgreementCompetitorListView.as_view(), name='fight-agreement-competitors'),
    path('agreements/<int:agreement_id>/bouts/', FightBoutListCreateView.as_view(), name='fight-agreement-bout-list-create'),
    path('agreements/<int:agreement_id>/bouts/<int:pk>/', FightBoutDetailView.as_view(), name='fight-agreement-bout-detail'),
]
