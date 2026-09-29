from django.urls import path

from apps.competitions.views import FightRecordListCreateView, FightRecordDetailView

urlpatterns = [
    path('fights/', FightRecordListCreateView.as_view(), name='fight-record-list-create'),
    path('fights/<int:pk>/', FightRecordDetailView.as_view(), name='fight-record-detail'),
]
