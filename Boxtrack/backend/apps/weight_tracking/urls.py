from django.urls import path

from apps.weight_tracking.views import WeightRecordDetailView, WeightRecordListCreateView

urlpatterns = [
	path('', WeightRecordListCreateView.as_view(), name='weight-list-create'),
	path('<int:pk>/', WeightRecordDetailView.as_view(), name='weight-detail'),
]
