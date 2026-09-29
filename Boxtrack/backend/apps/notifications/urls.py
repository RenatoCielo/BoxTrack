from django.urls import path

from apps.notifications.views import NotificationDetailView, NotificationListView

urlpatterns = [
	path('', NotificationListView.as_view(), name='notification-list'),
	path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
]
