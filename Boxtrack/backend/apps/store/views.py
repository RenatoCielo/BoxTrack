import hashlib
import hmac
import json
import mimetypes
import os
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction
from django.db.models import F
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.permissions import user_role
from apps.notifications.models import Notification
from apps.store.models import Order, OrderItem, Product, StoreSettings
from apps.store.serializers import OrderSerializer, OrderStatusSerializer, ProductSerializer


class StoreUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'El pago online no está configurado. Contacta al administrador del gimnasio.'
    default_code = 'payment_provider_unavailable'


class ProductPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_superuser or user_role(request.user) == 'ADMIN'

    def has_object_permission(self, request, view, obj):
        return request.user.is_superuser or obj.club_id == request.user.club_id


class ProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, ProductPermission]

    def get_queryset(self):
        queryset = Product.objects.filter(club_id=self.request.user.club_id)
        if user_role(self.request.user) != 'ADMIN' and not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated, ProductPermission]

    def get_queryset(self):
        queryset = Product.objects.filter(club_id=self.request.user.club_id)
        if user_role(self.request.user) != 'ADMIN' and not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)
        return queryset


class StoreCheckoutConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        online_payment_available = all(os.getenv(key) for key in (
            'MERCADOPAGO_ACCESS_TOKEN',
            'MERCADOPAGO_WEBHOOK_SECRET',
            'MERCADOPAGO_NOTIFICATION_URL',
        ))
        store_settings = StoreSettings.objects.filter(club_id=request.user.club_id).first()
        return Response({
            'mercado_pago_available': online_payment_available,
            'bank_transfer_instructions': store_settings.bank_transfer_instructions if store_settings else '',
        })

    def patch(self, request):
        if not request.user.is_superuser and user_role(request.user) != 'ADMIN':
            raise PermissionDenied('Solo el administrador puede configurar los datos bancarios del gimnasio.')
        instructions = request.data.get('bank_transfer_instructions')
        if not isinstance(instructions, str) or len(instructions) > 2000:
            raise ValidationError({'bank_transfer_instructions': 'Ingresa instrucciones de transferencia válidas (máximo 2000 caracteres).'})
        store_settings, _ = StoreSettings.objects.get_or_create(club=request.user.club)
        store_settings.bank_transfer_instructions = instructions.strip()
        store_settings.save(update_fields=['bank_transfer_instructions', 'updated_at'])
        return Response({'bank_transfer_instructions': store_settings.bank_transfer_instructions})


def release_order_stock(order):
    if order.stock_released:
        return
    for item in order.items.select_related('product'):
        Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity)
    order.stock_released = True
    order.save(update_fields=['stock_released', 'updated_at'])


def release_expired_checkouts(club_id):
    expired_orders = Order.objects.filter(
        club_id=club_id,
        payment_method='MERCADO_PAGO',
        status='PENDING',
        stock_released=False,
        expires_at__lte=timezone.now(),
    )
    with transaction.atomic():
        for order in expired_orders.select_for_update():
            order.status = 'CANCELLED'
            order.save(update_fields=['status', 'updated_at'])
            release_order_stock(order)


class OrderListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        release_expired_checkouts(request.user.club_id)
        queryset = Order.objects.filter(club_id=request.user.club_id).select_related('user').prefetch_related('items')
        if user_role(request.user) != 'ADMIN' and not request.user.is_superuser:
            queryset = queryset.filter(user=request.user)
        return Response(OrderSerializer(queryset, many=True).data)

    def post(self, request):
        release_expired_checkouts(request.user.club_id)
        items_data = request.data.get('items')
        payment_method = request.data.get('payment_method')
        if not isinstance(items_data, list) or not items_data:
            raise ValidationError({'items': 'Agrega al menos un producto al carrito.'})
        valid_methods = {choice[0] for choice in Order.PAYMENT_METHOD_CHOICES}
        if payment_method not in valid_methods:
            raise ValidationError({'payment_method': 'Selecciona un método de pago válido.'})
        if payment_method == 'BANK_TRANSFER':
            store_settings = StoreSettings.objects.filter(club_id=request.user.club_id).first()
            if not store_settings or not store_settings.bank_transfer_instructions.strip():
                raise ValidationError({'payment_method': 'El gimnasio aún no ha configurado los datos para transferencia bancaria.'})
        if payment_method == 'MERCADO_PAGO' and not all(os.getenv(key) for key in (
            'MERCADOPAGO_ACCESS_TOKEN',
            'MERCADOPAGO_WEBHOOK_SECRET',
            'MERCADOPAGO_NOTIFICATION_URL',
        )):
            raise StoreUnavailable()

        quantities = {}
        for entry in items_data:
            try:
                product_id = int(entry.get('product'))
                quantity = int(entry.get('quantity'))
            except (AttributeError, TypeError, ValueError):
                raise ValidationError({'items': 'Cada producto debe incluir un identificador y una cantidad válida.'})
            if quantity < 1 or quantity > 20:
                raise ValidationError({'items': 'La cantidad por producto debe estar entre 1 y 20.'})
            quantities[product_id] = quantities.get(product_id, 0) + quantity
            if quantities[product_id] > 20:
                raise ValidationError({'items': 'La cantidad máxima por producto es 20 unidades.'})

        with transaction.atomic():
            products = list(Product.objects.select_for_update().filter(
                club_id=request.user.club_id,
                is_active=True,
                pk__in=quantities,
            ).order_by('pk'))
            if len(products) != len(quantities):
                raise ValidationError({'items': 'Uno o más productos no están disponibles en este gimnasio.'})
            for product in products:
                if product.stock < quantities[product.pk]:
                    raise ValidationError({'items': f'Stock insuficiente para {product.name}. Disponibles: {product.stock}.'})

            order = Order.objects.create(
                club=request.user.club,
                user=request.user,
                payment_method=payment_method,
                notes=request.data.get('notes', '').strip(),
                expires_at=timezone.now() + timedelta(minutes=30) if payment_method == 'MERCADO_PAGO' else None,
            )
            total = 0
            for product in products:
                quantity = quantities[product.pk]
                subtotal = product.price * quantity
                total += subtotal
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=quantity,
                    subtotal=subtotal,
                )
                Product.objects.filter(pk=product.pk).update(stock=F('stock') - quantity)
            order.total = total
            order.save(update_fields=['total', 'updated_at'])

        if payment_method == 'MERCADO_PAGO':
            try:
                checkout_url, payment_reference = create_mercadopago_preference(order)
                order.checkout_url = checkout_url
                order.payment_reference = payment_reference
                order.save(update_fields=['checkout_url', 'payment_reference', 'updated_at'])
            except Exception as error:
                with transaction.atomic():
                    order.status = 'CANCELLED'
                    order.save(update_fields=['status', 'updated_at'])
                    release_order_stock(order)
                if isinstance(error, StoreUnavailable):
                    raise
                raise StoreUnavailable('No se pudo iniciar el pago online. No se realizó el cobro; vuelve a intentarlo.') from error

        if payment_method == 'BANK_TRANSFER':
            Notification.objects.create(
                club=order.club,
                user=order.user,
                title='Pedido listo para enviar comprobante',
                message=f'Envía el comprobante de transferencia del pedido #{order.pk}. El gimnasio lo revisará y te notificará el resultado.',
                notification_type='ALERT',
            )

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = OrderStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.filter(club_id=self.request.user.club_id).select_related('user').prefetch_related('items')
        if user_role(self.request.user) != 'ADMIN' and not self.request.user.is_superuser:
            queryset = queryset.filter(user=self.request.user)
        return queryset

    def get(self, request, *args, **kwargs):
        return Response(OrderSerializer(self.get_object()).data)

    def patch(self, request, *args, **kwargs):
        order = self.get_object()
        if request.user.is_superuser or user_role(request.user) == 'ADMIN':
            serializer = self.get_serializer(order, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            new_status = serializer.validated_data.get('status', order.status)
            if order.payment_method == 'BANK_TRANSFER' and new_status in ('PAID', 'READY', 'COMPLETED') and order.proof_status != 'APPROVED':
                raise ValidationError({'status': 'Primero debes aprobar el comprobante de transferencia.'})
            if order.status in ('PAID', 'READY', 'COMPLETED') and new_status == 'CANCELLED':
                raise ValidationError({'status': 'Los pedidos pagados deben gestionarse como devolución; el sistema no emite reembolsos automáticamente.'})
            if new_status == 'CANCELLED' and order.status != 'CANCELLED':
                with transaction.atomic():
                    order.status = 'CANCELLED'
                    order.notes = serializer.validated_data.get('notes', order.notes)
                    order.save(update_fields=['status', 'notes', 'updated_at'])
                    release_order_stock(order)
            else:
                serializer.save()
        else:
            if order.user_id != request.user.id:
                raise PermissionDenied('Solo puedes consultar tus pedidos.')
            if set(request.data) != {'status'} or request.data.get('status') != 'CANCELLED' or order.status != 'PENDING':
                raise PermissionDenied('Solo puedes cancelar un pedido pendiente de pago.')
            with transaction.atomic():
                order.status = 'CANCELLED'
                order.save(update_fields=['status', 'updated_at'])
                release_order_stock(order)
        return Response(OrderSerializer(order).data)


class OrderPaymentProofUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
    allowed_mime_types = {'application/pdf', 'image/jpeg', 'image/png', 'image/webp'}

    @staticmethod
    def has_allowed_signature(upload):
        header = upload.read(12)
        upload.seek(0)
        return (
            header.startswith(b'%PDF-')
            or header.startswith(b'\xff\xd8\xff')
            or header.startswith(b'\x89PNG\r\n\x1a\n')
            or (header.startswith(b'RIFF') and header[8:12] == b'WEBP')
        )

    def post(self, request, pk):
        queryset = Order.objects.select_related('club', 'user')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        order = get_object_or_404(queryset, pk=pk)
        if order.user_id != request.user.id:
            raise PermissionDenied('Solo puedes enviar el comprobante de tu propio pedido.')
        if order.payment_method != 'BANK_TRANSFER' or order.status != 'PENDING':
            raise ValidationError({'order': 'Este pedido no está esperando un comprobante de transferencia.'})
        if order.proof_status == 'SUBMITTED':
            raise ValidationError({'proof': 'El comprobante ya está en revisión; espera la respuesta del gimnasio.'})

        proof = request.FILES.get('proof')
        if not proof:
            raise ValidationError({'proof': 'Selecciona una imagen o PDF del comprobante.'})
        extension = Path(proof.name).suffix.lower()
        if extension not in self.allowed_extensions or proof.content_type not in self.allowed_mime_types:
            raise ValidationError({'proof': 'Usa un comprobante en PDF, JPG, PNG o WEBP.'})
        if proof.size > 5 * 1024 * 1024:
            raise ValidationError({'proof': 'El archivo no puede superar los 5 MB.'})
        if not self.has_allowed_signature(proof):
            raise ValidationError({'proof': 'El contenido del archivo no coincide con una imagen o PDF válido.'})

        old_proof = order.payment_proof
        order.payment_proof = proof
        order.proof_status = 'SUBMITTED'
        order.proof_review_note = ''
        order.proof_reviewed_by = None
        order.proof_reviewed_at = None
        order.save(update_fields=[
            'payment_proof', 'proof_status', 'proof_review_note',
            'proof_reviewed_by', 'proof_reviewed_at', 'updated_at'
        ])
        if old_proof:
            old_proof.delete(save=False)

        Notification.objects.create(
            club=order.club,
            user=order.user,
            title='Comprobante en revisión',
            message=f'Recibimos el comprobante del pedido #{order.pk}. Te notificaremos cuando el gimnasio lo revise.',
            notification_type='ALERT',
        )
        admin_users = User.objects.filter(club=order.club, role__name='ADMIN', is_active=True)
        for admin_user in admin_users:
            Notification.objects.create(
                club=order.club,
                user=admin_user,
                title='Comprobante pendiente de revisión',
                message=f'El pedido #{order.pk} de {order.user.get_full_name() or order.user.username} requiere validar una transferencia.',
                notification_type='ALERT',
            )
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderPaymentProofDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        queryset = Order.objects.select_related('club', 'user')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        order = get_object_or_404(queryset, pk=pk)
        if order.user_id != request.user.id and user_role(request.user) != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied('No tienes permisos para revisar este comprobante.')
        if not order.payment_proof:
            raise ValidationError({'proof': 'Este pedido todavía no tiene un comprobante.'})
        content_type = mimetypes.guess_type(order.payment_proof.name)[0] or 'application/octet-stream'
        return FileResponse(order.payment_proof.open('rb'), content_type=content_type, filename=Path(order.payment_proof.name).name)


class OrderPaymentProofReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_superuser and user_role(request.user) != 'ADMIN':
            raise PermissionDenied('Solo el administrador del gimnasio puede revisar comprobantes.')
        queryset = Order.objects.select_for_update().select_related('user', 'club')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        decision = request.data.get('decision')
        note = str(request.data.get('note', '')).strip()[:500]
        if decision not in ('APPROVE', 'REJECT'):
            raise ValidationError({'decision': 'Selecciona aprobar o rechazar el comprobante.'})
        if decision == 'REJECT' and not note:
            raise ValidationError({'note': 'Explica brevemente por qué se rechaza el comprobante.'})

        with transaction.atomic():
            order = get_object_or_404(queryset, pk=pk)
            if order.payment_method != 'BANK_TRANSFER' or order.status != 'PENDING' or not order.payment_proof:
                raise ValidationError({'order': 'El pedido no tiene un comprobante pendiente de revisión.'})
            if order.proof_status != 'SUBMITTED':
                raise ValidationError({'proof': 'El comprobante ya fue revisado o no se ha enviado.'})
            proof_status = 'APPROVED' if decision == 'APPROVE' else 'REJECTED'
            order.mark_proof_reviewed(request.user, proof_status, note)
            if decision == 'APPROVE':
                order.status = 'PAID'
                notification_title = 'Pago aprobado'
                notification_message = f'El comprobante del pedido #{order.pk} fue aprobado. El gimnasio preparará tu reserva para retiro.'
            else:
                notification_title = 'Comprobante rechazado'
                notification_message = f'No pudimos aprobar el comprobante del pedido #{order.pk}. Revisa el motivo y vuelve a enviarlo.'
                if note:
                    notification_message = f'{notification_message} Motivo: {note}'
            order.save(update_fields=[
                'status', 'proof_status', 'proof_review_note', 'proof_reviewed_by',
                'proof_reviewed_at', 'updated_at'
            ])
            Notification.objects.create(
                club=order.club,
                user=order.user,
                title=notification_title,
                message=notification_message,
                notification_type='ALERT',
            )
        return Response(OrderSerializer(order).data)


def create_mercadopago_preference(order):
    token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    notification_url = os.getenv('MERCADOPAGO_NOTIFICATION_URL')
    if not token or not notification_url or not os.getenv('MERCADOPAGO_WEBHOOK_SECRET'):
        raise StoreUnavailable('Mercado Pago requiere token, secreto de webhook y URL pública de notificaciones en el .env de la raíz del proyecto.')
    payload = {
        'items': [{
            'title': item.product_name,
            'quantity': item.quantity,
            'currency_id': 'CLP',
            'unit_price': float(item.unit_price),
        } for item in order.items.all()],
        'external_reference': str(order.pk),
        'notification_url': notification_url,
        'back_urls': {
            'success': f'{frontend_url}/store?payment=success',
            'failure': f'{frontend_url}/store?payment=failure',
            'pending': f'{frontend_url}/store?payment=pending',
        },
        'auto_return': 'approved',
        'expiration_date_from': timezone.now().isoformat(),
        'expiration_date_to': (timezone.now() + timedelta(minutes=30)).isoformat(),
        'statement_descriptor': 'BOXTRACK',
    }
    request = urllib.request.Request(
        'https://api.mercadopago.com/checkout/preferences',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode('utf-8'))
    return result.get('init_point') or result['sandbox_init_point'], result['id']


class MercadoPagoWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = os.getenv('MERCADOPAGO_WEBHOOK_SECRET')
        signature = request.headers.get('x-signature', '')
        request_id = request.headers.get('x-request-id', '')
        data_id = str(request.query_params.get('data.id') or request.data.get('data', {}).get('id', '')).lower()
        signature_parts = dict(part.split('=', 1) for part in signature.split(',') if '=' in part)
        timestamp = signature_parts.get('ts')
        received_signature = signature_parts.get('v1')
        manifest = f'id:{data_id};request-id:{request_id};ts:{timestamp};'
        expected = hmac.new((secret or '').encode(), manifest.encode(), hashlib.sha256).hexdigest()
        if not secret or not timestamp or not received_signature or not hmac.compare_digest(expected, received_signature):
            return Response({'detail': 'Firma de webhook no válida.'}, status=status.HTTP_401_UNAUTHORIZED)

        token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
        if not token or not data_id:
            return Response({'detail': 'Notificación incompleta.'}, status=status.HTTP_400_BAD_REQUEST)
        payment_request = urllib.request.Request(
            f'https://api.mercadopago.com/v1/payments/{data_id}',
            headers={'Authorization': f'Bearer {token}'},
        )
        try:
            with urllib.request.urlopen(payment_request, timeout=15) as response:
                payment = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, ValueError):
            return Response({'detail': 'No se pudo verificar el pago con el proveedor.'}, status=status.HTTP_502_BAD_GATEWAY)
        if payment.get('status') != 'approved':
            return Response({'received': True}, status=status.HTTP_200_OK)

        with transaction.atomic():
            order = get_object_or_404(Order.objects.select_for_update(), pk=payment.get('external_reference'))
            if order.payment_method != 'MERCADO_PAGO':
                return Response({'detail': 'Referencia de pedido no válida.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                paid_amount = Decimal(str(payment.get('transaction_amount')))
            except (InvalidOperation, TypeError):
                return Response({'detail': 'El importe del pago no es válido.'}, status=status.HTTP_400_BAD_REQUEST)
            if payment.get('currency_id') != 'CLP' or paid_amount != order.total:
                return Response({'detail': 'El importe del pago no coincide con el pedido.'}, status=status.HTTP_400_BAD_REQUEST)
            if order.status == 'PENDING':
                order.status = 'PAID'
                order.payment_reference = str(payment.get('id', data_id))
                order.save(update_fields=['status', 'payment_reference', 'updated_at'])
        return Response({'received': True}, status=status.HTTP_200_OK)