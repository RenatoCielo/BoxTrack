from django.urls import path

from apps.trainings.views import (
    TrainingDetailView,
    TrainingListCreateView,
    TrainingReservationCancelView,
    TrainingReservationListCreateView,
    WeeklyTrainingScheduleDetailView,
    WeeklyTrainingScheduleListCreateView,
)

urlpatterns = [
    path('', TrainingListCreateView.as_view(), name='training-list-create'),
    path('weekly-schedules/', WeeklyTrainingScheduleListCreateView.as_view(), name='weekly-training-schedule-list-create'),
    path('weekly-schedules/<int:pk>/', WeeklyTrainingScheduleDetailView.as_view(), name='weekly-training-schedule-detail'),
    path('<int:training_id>/reservations/', TrainingReservationListCreateView.as_view(), name='training-reservations'),
    path('<int:training_id>/reservations/<int:reservation_id>/cancel/', TrainingReservationCancelView.as_view(), name='training-reservation-cancel'),
    path('<int:pk>/', TrainingDetailView.as_view(), name='training-detail'),
]
