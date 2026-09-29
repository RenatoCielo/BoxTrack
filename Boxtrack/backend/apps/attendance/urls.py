from django.urls import path

from apps.attendance.views import AttendanceListCreateView, AttendanceDetailView

urlpatterns = [
    path('', AttendanceListCreateView.as_view(), name='attendance-list-create'),
    path('<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
]
