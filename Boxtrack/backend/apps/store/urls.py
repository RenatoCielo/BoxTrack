from django.urls import path

from apps.store.views import (
    MercadoPagoWebhookView,
    OrderDetailView,
    OrderListCreateView,
    OrderPaymentProofDownloadView,
    OrderPaymentProofReviewView,
    OrderPaymentProofUploadView,
    ProductDetailView,
    ProductListCreateView,
    StoreCheckoutConfigView,
)

urlpatterns = [
    path('products/', ProductListCreateView.as_view(), name='store-products'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='store-product-detail'),
    path('checkout-config/', StoreCheckoutConfigView.as_view(), name='store-checkout-config'),
    path('orders/', OrderListCreateView.as_view(), name='store-orders'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='store-order-detail'),
    path('orders/<int:pk>/proof/', OrderPaymentProofUploadView.as_view(), name='store-order-proof-upload'),
    path('orders/<int:pk>/proof/file/', OrderPaymentProofDownloadView.as_view(), name='store-order-proof-download'),
    path('orders/<int:pk>/proof/review/', OrderPaymentProofReviewView.as_view(), name='store-order-proof-review'),
    path('payments/mercadopago/webhook/', MercadoPagoWebhookView.as_view(), name='mercadopago-webhook'),
]