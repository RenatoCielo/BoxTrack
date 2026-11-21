from django.urls import path

from apps.notifications.views import NotificationDetailView, NotificationListView, NotificationUnreadCountView

urlpatterns = [
	path('', NotificationListView.as_view(), name='notification-list'),
	path('unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
	path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
]
