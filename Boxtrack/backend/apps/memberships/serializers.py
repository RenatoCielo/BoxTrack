from rest_framework import serializers
from django.utils import timezone

from apps.memberships.models import Membership, MembershipPayment, MembershipPlan


class MembershipPlanSerializer(serializers.ModelSerializer):
    active_members = serializers.SerializerMethodField()

    class Meta:
        model = MembershipPlan
        fields = [
            'id', 'club', 'name', 'description', 'price', 'currency', 'duration_days', 'benefits',
            'weekly_class_limit', 'is_active', 'active_members', 'created_at', 'updated_at',
        ]
        read_only_fields = ['club', 'created_at', 'updated_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor que cero.')
        return value

    def validate_duration_days(self, value):
        if value < 1:
            raise serializers.ValidationError('La duración debe ser de al menos 1 día.')
        return value

    def validate_weekly_class_limit(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('El límite semanal debe ser al menos 1 o quedar vacío (sin límite).')
        return value

    def validate_currency(self, value):
        return value.strip().upper()

    def validate_name(self, value):
        value = value.strip()
        club_id = self.context['request'].user.club_id
        duplicates = MembershipPlan.objects.filter(club_id=club_id, name__iexact=value)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError('Ya existe un plan con ese nombre en tu club.')
        return value

    def get_active_members(self, obj):
        if hasattr(obj, 'active_members'):
            return obj.active_members
        return obj.memberships.filter(status='ACTIVE').count()


class MembershipSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.display_name', read_only=True)
    club_name = serializers.CharField(source='club.name', read_only=True)
    is_renewal = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_provider = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            'id', 'club', 'club_name', 'athlete', 'athlete_name', 'plan', 'plan_name', 'price_paid', 'currency',
            'duration_days', 'weekly_class_limit', 'status', 'start_date', 'end_date', 'review_note',
            'renewal_of', 'is_renewal', 'days_remaining', 'payment_status', 'payment_provider', 'confirmed_at', 'created_at',
        ]
        read_only_fields = fields

    def get_is_renewal(self, obj):
        return obj.renewal_of_id is not None

    def get_days_remaining(self, obj):
        if obj.status != 'ACTIVE' or not obj.end_date:
            return None
        return max((obj.end_date - timezone.localdate()).days, 0)

    def get_payment_status(self, obj):
        payment = next(iter(obj.payments.all()), None)
        return payment.status if payment else None

    def get_payment_provider(self, obj):
        payment = next(iter(obj.payments.all()), None)
        return payment.payment_provider if payment else None


class MembershipPaymentSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='membership.athlete.display_name', read_only=True)
    plan_name = serializers.CharField(source='membership.plan_name', read_only=True)
    checkout_url = serializers.SerializerMethodField()
    is_renewal = serializers.SerializerMethodField()

    class Meta:
        model = MembershipPayment
        fields = [
            'id', 'club', 'membership', 'plan', 'plan_name', 'athlete_name', 'amount', 'currency', 'status',
            'payment_provider', 'provider_status', 'checkout_url', 'is_renewal', 'expires_at', 'paid_at', 'created_at',
        ]
        read_only_fields = fields

    def get_is_renewal(self, obj):
        return obj.membership.renewal_of_id is not None

    def get_checkout_url(self, obj):
        # El enlace solo se entrega al comprador y mientras el pago siga abierto.
        request = self.context.get('request')
        if obj.status == 'PENDING' and request and obj.user_id == request.user.id:
            return obj.checkout_url
        return ''
