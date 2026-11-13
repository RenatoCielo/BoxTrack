from django.urls import path

from apps.memberships.views import (
    MembershipListCreateView, MembershipPaymentDetailView, MembershipPaymentListCreateView, MembershipRenewalView, MembershipReviewView,
    MembershipSettingsView, MembershipTransferProofView, MembershipTransferProofFileView, MembershipTransferProofReviewView, PlanDetailView, PlanListCreateView,
)

urlpatterns = [
    path('renewal/', MembershipRenewalView.as_view(), name='membership-renewal'),
    path('plans/', PlanListCreateView.as_view(), name='membership-plan-list-create'),
    path('plans/<int:pk>/', PlanDetailView.as_view(), name='membership-plan-detail'),
    path('settings/', MembershipSettingsView.as_view(), name='membership-settings'),
    path('payments/', MembershipPaymentListCreateView.as_view(), name='membership-payment-list-create'),
    path('payments/<int:pk>/', MembershipPaymentDetailView.as_view(), name='membership-payment-detail'),
    path('', MembershipListCreateView.as_view(), name='membership-list-create'),
    path('<int:pk>/review/', MembershipReviewView.as_view(), name='membership-review'),
    path('<int:pk>/proof/', MembershipTransferProofView.as_view(), name='membership-proof'),
    path('<int:pk>/proof/file/', MembershipTransferProofFileView.as_view(), name='membership-proof-file'),
    path('<int:pk>/proof/review/', MembershipTransferProofReviewView.as_view(), name='membership-proof-review'),
]
