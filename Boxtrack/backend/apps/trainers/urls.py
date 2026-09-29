from django.urls import path

from apps.trainers.views import TrainerListCreateView, TrainerDetailView

urlpatterns = [
    path('', TrainerListCreateView.as_view(), name='trainer-list-create'),
    path('<int:pk>/', TrainerDetailView.as_view(), name='trainer-detail'),
]
