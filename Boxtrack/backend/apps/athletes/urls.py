from django.urls import path

from apps.athletes.views import AthleteListCreateView, AthleteDetailView

urlpatterns = [
    path('', AthleteListCreateView.as_view(), name='athlete-list-create'),
    path('<int:pk>/', AthleteDetailView.as_view(), name='athlete-detail'),
]
