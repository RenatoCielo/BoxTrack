from pathlib import Path

from rest_framework import serializers

from apps.store.models import Order, OrderItem, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'club', 'name', 'description', 'category', 'sku', 'price', 'stock', 'image_url', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'club', 'created_at', 'updated_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor que cero.')
        return value

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('El nombre del producto es obligatorio.')
        return value.strip()


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'unit_price', 'quantity', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_name = serializers.SerializerMethodField()
    has_payment_proof = serializers.SerializerMethodField()
    payment_proof_file_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'club', 'user', 'buyer_name', 'status', 'payment_method',
            'payment_reference', 'checkout_url', 'has_payment_proof', 'payment_proof_file_name', 'proof_status',
            'proof_review_note', 'proof_reviewed_at', 'notes',
            'total', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_buyer_name(self, order):
        return order.user.get_full_name() or order.user.username

    def get_has_payment_proof(self, order):
        return bool(order.payment_proof)

    def get_payment_proof_file_name(self, order):
        return Path(order.payment_proof.name).name if order.payment_proof else ''


class OrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status', 'notes']