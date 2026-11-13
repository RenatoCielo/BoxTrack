from django.urls import path

from apps.dashboard.views import GlobalClubListView, GlobalUserListView, dashboard_summary, global_dashboard_summary

urlpatterns = [
    path('', dashboard_summary, name='dashboard-summary'),
    path('global/', global_dashboard_summary, name='global-dashboard-summary'),
    path('global/clubs/', GlobalClubListView.as_view(), name='global-dashboard-clubs'),
    path('global/users/', GlobalUserListView.as_view(), name='global-dashboard-users'),
]
