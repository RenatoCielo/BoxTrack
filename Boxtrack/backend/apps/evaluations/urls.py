from django.urls import path

from apps.evaluations.views import EvaluationDetailView, EvaluationListCreateView

urlpatterns = [
	path('', EvaluationListCreateView.as_view(), name='evaluation-list-create'),
	path('<int:pk>/', EvaluationDetailView.as_view(), name='evaluation-detail'),
]
