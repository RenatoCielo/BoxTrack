from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
import uuid


def payment_proof_upload_path(instance, filename):
    extension = filename.rsplit('.', 1)[-1].lower()
    return f'store/payment-proofs/{instance.club_id}/{instance.pk}/{uuid.uuid4().hex}.{extension}'


def private_payment_proof_storage():
    return FileSystemStorage(location=settings.BASE_DIR / '.private_uploads')


class StoreSettings(models.Model):
    club = models.OneToOneField('clubs.Club', on_delete=models.CASCADE, related_name='store_settings')
    bank_transfer_instructions = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Configuración de tienda - {self.club.name}'


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('GLOVES', 'Guantes'),
        ('WRAPS', 'Vendas'),
        ('HEADGEAR', 'Cabezal'),
        ('MOUTHGUARD', 'Bucal'),
        ('BOOTS', 'Botas'),
        ('CLOTHING', 'Vestimenta'),
        ('PROTECTIVE', 'Protección'),
        ('SUPPLEMENTS', 'Complementos'),
        ('OTHER', 'Otros'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='store_products')
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default='OTHER')
    sku = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        constraints = [
            models.UniqueConstraint(fields=['club', 'sku'], condition=~models.Q(sku=''), name='unique_store_sku_per_club'),
        ]
        indexes = [models.Index(fields=['club', 'is_active', 'category'])]

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pendiente'),
        ('PAID', 'Pagada'),
        ('READY', 'Lista para retirar'),
        ('COMPLETED', 'Retirada'),
        ('CANCELLED', 'Cancelada'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('MERCADO_PAGO', 'Mercado Pago'),
        ('BANK_TRANSFER', 'Transferencia'),
        ('RESERVE', 'Reserva para retiro'),
    ]
    PROOF_STATUS_CHOICES = [
        ('NOT_SUBMITTED', 'Sin comprobante'),
        ('SUBMITTED', 'En revisión'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado'),
    ]

    club = models.ForeignKey('clubs.Club', on_delete=models.CASCADE, related_name='store_orders')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='store_orders')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_reference = models.CharField(max_length=120, blank=True)
    checkout_url = models.URLField(blank=True)
    payment_proof = models.FileField(storage=private_payment_proof_storage, upload_to=payment_proof_upload_path, blank=True, null=True)
    proof_status = models.CharField(max_length=16, choices=PROOF_STATUS_CHOICES, default='NOT_SUBMITTED')
    proof_review_note = models.CharField(max_length=500, blank=True)
    proof_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_proofs_reviewed')
    proof_reviewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    shipping_address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_released = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['club', 'status', 'created_at'])]

    def __str__(self):
        return f'Pedido #{self.pk} - {self.user}'

    def mark_proof_reviewed(self, reviewer, status_value, note=''):
        self.proof_status = status_value
        self.proof_review_note = note.strip()
        self.proof_reviewed_by = reviewer
        self.proof_reviewed_at = timezone.now()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    product_name = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'{self.quantity} x {self.product_name}'