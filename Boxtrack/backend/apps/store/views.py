import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlencode

from django.db import transaction
from django.db.models import F
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.html import escape
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
from apps.store.transbank import TransbankUnavailable, clp_amount, response_value, transbank_configured, webpay_transaction


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
            'transbank_available': transbank_configured(),
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
        payment_method__in=['MERCADO_PAGO', 'TRANSBANK'],
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
        if payment_method == 'TRANSBANK' and not transbank_configured():
            raise StoreUnavailable('Transbank Webpay Plus no está configurado para pruebas.')

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
                expires_at=timezone.now() + timedelta(minutes=30) if payment_method in ('MERCADO_PAGO', 'TRANSBANK') else None,
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
            if payment_method == 'TRANSBANK':
                clp_amount(total)
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

        if payment_method == 'TRANSBANK':
            try:
                order.transbank_buy_order = f'BTO{order.pk}{secrets.token_hex(6)}'[:26]
                order.transbank_session_id = f'BTOS{request.user.pk}{secrets.token_hex(8)}'[:61]
                order.save(update_fields=['transbank_buy_order', 'transbank_session_id', 'updated_at'])
                callback_url = request.build_absolute_uri(reverse('transbank-return'))
                response = webpay_transaction().create(
                    order.transbank_buy_order, order.transbank_session_id, clp_amount(order.total), callback_url,
                )
                token = response_value(response, 'token')
                provider_url = response_value(response, 'url')
                if not token or not provider_url:
                    raise TransbankUnavailable('Transbank no devolvió una sesión Webpay válida.')
                order.transbank_token = str(token)
                order.transbank_url = str(provider_url)
                order.checkout_url = request.build_absolute_uri(reverse('transbank-checkout', args=[token]))
                order.save(update_fields=['transbank_token', 'transbank_url', 'checkout_url', 'updated_at'])
            except Exception as error:
                with transaction.atomic():
                    order.status = 'CANCELLED'
                    order.save(update_fields=['status', 'updated_at'])
                    release_order_stock(order)
                if isinstance(error, StoreUnavailable):
                    raise
                raise StoreUnavailable('No se pudo iniciar el pago Transbank de pruebas; no se completó el pedido.') from error

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
            if (order.payment_method in ('MERCADO_PAGO', 'TRANSBANK')
                    and order.status in ('PENDING', 'PAYMENT_REVIEW')
                    and new_status in ('PAID', 'READY', 'COMPLETED')):
                raise ValidationError({'status': 'Los pagos online solo pueden completarse después de la confirmación del proveedor.'})
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


MERCADOPAGO_ENV_KEYS = ('MERCADOPAGO_ACCESS_TOKEN', 'MERCADOPAGO_WEBHOOK_SECRET', 'MERCADOPAGO_NOTIFICATION_URL')


def mercadopago_configured():
    return all(os.getenv(key) for key in MERCADOPAGO_ENV_KEYS)


def post_mercadopago_preference(payload):
    """Crea la preferencia en Mercado Pago y devuelve (url_checkout, id_preferencia)."""
    token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
    if not mercadopago_configured():
        raise StoreUnavailable('Mercado Pago requiere token, secreto de webhook y URL pública de notificaciones en el .env de la raíz del proyecto.')
    request = urllib.request.Request(
        'https://api.mercadopago.com/checkout/preferences',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode('utf-8'))
    return result.get('init_point') or result['sandbox_init_point'], result['id']


def create_mercadopago_preference(order):
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    notification_url = os.getenv('MERCADOPAGO_NOTIFICATION_URL')
    if not mercadopago_configured():
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
    return post_mercadopago_preference(payload)


def webhook_signature_valid(request, data_id):
    secret = os.getenv('MERCADOPAGO_WEBHOOK_SECRET')
    signature = request.headers.get('x-signature', '')
    request_id = request.headers.get('x-request-id', '')
    signature_parts = dict(part.split('=', 1) for part in signature.split(',') if '=' in part)
    timestamp = signature_parts.get('ts')
    received_signature = signature_parts.get('v1')
    manifest = f'id:{data_id};request-id:{request_id};ts:{timestamp};'
    expected = hmac.new((secret or '').encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return bool(secret and timestamp and received_signature and hmac.compare_digest(expected, received_signature))


def fetch_mercadopago_payment(data_id):
    """Consulta el pago real en la API oficial; lanza URLError o ValueError si falla."""
    token = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
    payment_request = urllib.request.Request(
        f'https://api.mercadopago.com/v1/payments/{data_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    with urllib.request.urlopen(payment_request, timeout=15) as response:
        return json.loads(response.read().decode('utf-8'))


class MercadoPagoWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        data = body.get('data') if isinstance(body.get('data'), dict) else {}
        data_id = str(request.query_params.get('data.id') or data.get('id', '')).lower()
        if not webhook_signature_valid(request, data_id):
            return Response({'detail': 'Firma de webhook no válida.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Solo los eventos de pago se consultan; merchant_order y otros se confirman (200) sin
        # tratar su id como id de pago ni cambiar ningún estado, para evitar reintentos inútiles.
        topic = str(body.get('type') or body.get('topic') or request.query_params.get('type')
                    or request.query_params.get('topic') or '').lower()
        if topic and topic != 'payment':
            return Response({'received': True, 'ignored': topic}, status=status.HTTP_200_OK)

        if not os.getenv('MERCADOPAGO_ACCESS_TOKEN') or not data_id:
            return Response({'detail': 'Notificación incompleta.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = fetch_mercadopago_payment(data_id)
        except (urllib.error.URLError, OSError, ValueError):
            return Response({'detail': 'No se pudo verificar el pago con el proveedor.'}, status=status.HTTP_502_BAD_GATEWAY)
        if not isinstance(payment, dict):
            return Response({'detail': 'No se pudo verificar el pago con el proveedor.'}, status=status.HTTP_502_BAD_GATEWAY)
        if str(payment.get('external_reference') or '').startswith('membership:'):
            from apps.memberships.payments import process_membership_payment
            return process_membership_payment(payment, data_id)
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


class TransbankCheckoutView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        order = Order.objects.filter(transbank_token=token, payment_method='TRANSBANK', status='PENDING').first()
        payment = None
        if order is None:
            from apps.memberships.models import MembershipPayment
            payment = MembershipPayment.objects.filter(transbank_token=token, payment_provider='TRANSBANK', status='PENDING').first()
        provider_url = order.transbank_url if order else payment.transbank_url if payment else ''
        if not provider_url:
            return HttpResponse('Checkout Transbank no disponible.', status=404)
        safe_url = escape(provider_url)
        safe_token = escape(token)
        return HttpResponse(
            '<!doctype html><html lang="es"><meta charset="utf-8"><title>Conectando con Webpay</title>'
            f'<form id="webpay" action="{safe_url}" method="post"><input type="hidden" name="token_ws" value="{safe_token}"></form>'
            '<p>Conectando con Transbank Webpay Plus…</p><script>document.getElementById("webpay").submit()</script></html>',
            content_type='text/html; charset=utf-8',
        )


class TransbankReturnView(APIView):
    """Webpay callback. The SDK commit result, not the browser return, settles the purchase."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)

    def _redirect(self, resource, result):
        frontend = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        page = 'store' if resource == 'order' else 'memberships'
        query = urlencode({'payment': result, 'provider': 'transbank'})
        return HttpResponseRedirect(f'{frontend}/{page}?{query}')

    def _handle(self, request):
        payload = request.data if request.method == 'POST' else request.query_params
        token = str(payload.get('token_ws') or '')
        aborted_token = str(payload.get('TBK_TOKEN') or '')
        buy_order = str(payload.get('TBK_ORDEN_COMPRA') or '')
        if not token and not aborted_token:
            return Response({'detail': 'Retorno Transbank incompleto.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.memberships.models import MembershipPayment
        payment = MembershipPayment.objects.filter(
            transbank_token=token or aborted_token, payment_provider='TRANSBANK',
        ).first() if (token or aborted_token) else None
        order = Order.objects.filter(transbank_token=token or aborted_token, payment_method='TRANSBANK').first() if (token or aborted_token) else None
        if payment is None and order is None and buy_order:
            payment = MembershipPayment.objects.filter(transbank_buy_order=buy_order, payment_provider='TRANSBANK').first()
            order = Order.objects.filter(transbank_buy_order=buy_order, payment_method='TRANSBANK').first() if payment is None else None
        if payment is None and order is None:
            return Response({'detail': 'Transacción Transbank no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        resource = 'membership' if payment else 'order'
        if not token:
            if payment:
                with transaction.atomic():
                    payment = MembershipPayment.objects.select_for_update().select_related('membership').get(pk=payment.pk)
                    if payment.status == 'PENDING':
                        payment.status = 'CANCELLED'
                        payment.provider_status = 'ABORTED'
                        payment.save(update_fields=['status', 'provider_status', 'updated_at'])
                        if payment.membership.status == 'PENDING':
                            payment.membership.status = 'CANCELLED'
                            payment.membership.save(update_fields=['status', 'updated_at'])
            else:
                with transaction.atomic():
                    order = Order.objects.select_for_update().get(pk=order.pk)
                    if order.status == 'PENDING':
                        order.status = 'CANCELLED'
                        order.save(update_fields=['status', 'updated_at'])
                        release_order_stock(order)
            return self._redirect(resource, 'failure')

        if payment:
            return self._commit_membership(payment.pk, token)
        return self._commit_order(order.pk, token)

    def _commit_membership(self, payment_id, token):
        from apps.memberships.models import MembershipPayment
        from apps.memberships.payments import process_membership_payment

        with transaction.atomic():
            payment = MembershipPayment.objects.select_for_update().select_related('membership', 'club').get(pk=payment_id)
            if payment.transbank_token != token:
                return self._redirect('membership', 'failure')
            if payment.status in ('APPROVED', 'REFUNDED') or payment.provider_status in ('AMOUNT_MISMATCH', 'REFERENCE_MISMATCH'):
                return self._redirect('membership', 'success' if payment.status == 'APPROVED' else 'failure')
            try:
                response = webpay_transaction().commit(token)
            except Exception:
                return self._redirect('membership', 'pending')
            result = {
                key: response_value(response, key) for key in (
                    'status', 'response_code', 'amount', 'buy_order', 'session_id', 'authorization_code',
                )
            }
            try:
                amount_ok = Decimal(str(result.get('amount'))) == payment.amount
            except (InvalidOperation, TypeError):
                amount_ok = False
            reference_ok = (str(result.get('buy_order') or '') == payment.transbank_buy_order
                            and str(result.get('session_id') or '') == payment.transbank_session_id)
            if not reference_ok or not amount_ok:
                payment.status = 'REVIEW'
                payment.provider_status = 'AMOUNT_MISMATCH' if reference_ok else 'REFERENCE_MISMATCH'
                payment.transbank_authorization_code = str(result.get('authorization_code') or '')
                payment.save(update_fields=['status', 'provider_status', 'transbank_authorization_code', 'updated_at'])
                for admin in payment.club.users.filter(role__name='ADMIN', is_active=True):
                    Notification.objects.create(club=payment.club, user=admin, title='Pago Transbank en revisión', message=f'El pago de membresía #{payment.pk} requiere revisión por discrepancia en la transacción.', notification_type='ALERT')
                return self._redirect('membership', 'pending')
            try:
                response_code = int(result.get('response_code'))
            except (TypeError, ValueError):
                response_code = -1
            approved = str(result.get('status') or '').upper() == 'AUTHORIZED' and response_code == 0
            verified_payment = {
                'id': f'TBK:{token}',
                'external_reference': f'membership:{payment.pk}',
                'status': 'approved' if approved else 'rejected',
                'transaction_amount': str(payment.amount),
                'currency_id': payment.currency,
            }
            process_membership_payment(verified_payment, f'TBK:{token}')
            payment.refresh_from_db()
            payment.transbank_authorization_code = str(result.get('authorization_code') or '')
            payment.provider_status = str(result.get('status') or 'REJECTED')
            payment.save(update_fields=['transbank_authorization_code', 'provider_status', 'updated_at'])
            settled = payment.status == 'APPROVED'
        return self._redirect('membership', 'success' if settled else 'pending' if payment.status == 'REVIEW' else 'failure')

    def _commit_order(self, order_id, token):
        with transaction.atomic():
            order = Order.objects.select_for_update().select_related('club').get(pk=order_id)
            if order.transbank_token != token:
                return self._redirect('order', 'failure')
            if order.status == 'PAID':
                return self._redirect('order', 'success')
            if order.status == 'PAYMENT_REVIEW':
                return self._redirect('order', 'pending')
            try:
                response = webpay_transaction().commit(token)
            except Exception:
                return self._redirect('order', 'pending')
            result = {
                key: response_value(response, key) for key in (
                    'status', 'response_code', 'amount', 'buy_order', 'session_id', 'authorization_code',
                )
            }
            reference_ok = (str(result['buy_order']) == order.transbank_buy_order
                            and str(result['session_id']) == order.transbank_session_id)
            try:
                amount_ok = Decimal(str(result.get('amount'))) == order.total
            except (InvalidOperation, TypeError):
                amount_ok = False
            try:
                response_code = int(result.get('response_code'))
            except (TypeError, ValueError):
                response_code = -1
            approved = str(result.get('status') or '').upper() == 'AUTHORIZED' and response_code == 0
            if not reference_ok or not amount_ok:
                order.status = 'PAYMENT_REVIEW'
                order.transbank_authorization_code = str(result.get('authorization_code') or '')
                order.payment_reference = 'TRANSBANK_REVIEW'
                order.save(update_fields=['status', 'transbank_authorization_code', 'payment_reference', 'updated_at'])
                for admin in order.club.users.filter(role__name='ADMIN', is_active=True):
                    Notification.objects.create(club=order.club, user=admin, title='Pago Transbank en revisión', message=f'El pedido #{order.pk} requiere revisión por discrepancia en la transacción.', notification_type='ALERT')
                return self._redirect('order', 'pending')
            if order.status == 'CANCELLED':
                if approved:
                    order.status = 'PAYMENT_REVIEW'
                    order.transbank_authorization_code = str(result.get('authorization_code') or '')
                    order.payment_reference = f'TBK_REVIEW:{token}'
                    for admin in order.club.users.filter(role__name='ADMIN', is_active=True):
                        Notification.objects.create(club=order.club, user=admin, title='Pago tardío Transbank', message=f'El pedido #{order.pk} fue autorizado después de cancelarse; requiere revisión manual.', notification_type='ALERT')
                    order.save(update_fields=['status', 'transbank_authorization_code', 'payment_reference', 'updated_at'])
                    return self._redirect('order', 'pending')
                return self._redirect('order', 'failure')
            if approved and order.status == 'PENDING' and not order.stock_released:
                order.status = 'PAID'
                order.transbank_authorization_code = str(result.get('authorization_code') or '')
                order.payment_reference = f'TBK:{token}'
                order.save(update_fields=['status', 'transbank_authorization_code', 'payment_reference', 'updated_at'])
                return self._redirect('order', 'success')
            if approved:
                order.status = 'PAYMENT_REVIEW'
                order.transbank_authorization_code = str(result.get('authorization_code') or '')
                order.payment_reference = f'TBK_REVIEW:{token}'
                for admin in order.club.users.filter(role__name='ADMIN', is_active=True):
                    Notification.objects.create(club=order.club, user=admin, title='Pago tardío Transbank', message=f'El pedido #{order.pk} fue autorizado después de liberar su inventario; requiere revisión.', notification_type='ALERT')
                order.save(update_fields=['status', 'transbank_authorization_code', 'payment_reference', 'updated_at'])
                return self._redirect('order', 'pending')
            order.status = 'CANCELLED'
            order.save(update_fields=['status', 'updated_at'])
            release_order_stock(order)
        return self._redirect('order', 'failure')
