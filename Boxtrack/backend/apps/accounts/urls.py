from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import ChangePasswordView, ClubMemberListCreateView, RegisterView, MeView, login_view

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', login_view, name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('members/', ClubMemberListCreateView.as_view(), name='club-members'),
    path('password/', ChangePasswordView.as_view(), name='change-password'),
]
