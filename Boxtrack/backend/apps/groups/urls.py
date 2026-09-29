from django.urls import path

from apps.groups.views import GroupListCreateView, GroupDetailView

urlpatterns = [
    path('', GroupListCreateView.as_view(), name='group-list-create'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
]
