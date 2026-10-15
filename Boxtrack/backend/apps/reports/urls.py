from django.urls import path

from apps.reports.views import export_report

urlpatterns = [
    path('<str:model_name>/', export_report, name='report-export'),
]
