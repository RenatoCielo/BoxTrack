from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/clubs/', include('apps.clubs.urls')),
    path('api/athletes/', include('apps.athletes.urls')),
    path('api/trainers/', include('apps.trainers.urls')),
    path('api/groups/', include('apps.groups.urls')),
    path('api/trainings/', include('apps.trainings.urls')),
    path('api/attendance/', include('apps.attendance.urls')),
    path('api/evaluations/', include('apps.evaluations.urls')),
    path('api/weight/', include('apps.weight_tracking.urls')),
    path('api/competitions/', include('apps.competitions.urls')),
    path('api/alerts/', include('apps.alerts.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/dashboard/', include('apps.dashboard.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/store/', include('apps.store.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
