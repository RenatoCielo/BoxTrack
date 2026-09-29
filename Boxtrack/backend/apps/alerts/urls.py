from django.urls import path

from apps.alerts.views import AlertDetailView, AlertListCreateView

urlpatterns = [
	path('', AlertListCreateView.as_view(), name='alert-list-create'),
	path('<int:pk>/', AlertDetailView.as_view(), name='alert-detail'),
]
