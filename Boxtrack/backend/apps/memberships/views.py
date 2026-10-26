from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.athletes.models import Athlete
from apps.common.permissions import ClubRolePermission, user_role
from apps.memberships.models import Membership, MembershipPayment, MembershipPlan, MembershipSettings, expire_overdue_memberships
from apps.memberships.payments import cancel_pending_payments, expire_pending_payments, start_membership_checkout
from apps.memberships.renewals import activate_pending_membership, create_renewal_membership, renewal_info
from apps.memberships.serializers import MembershipPaymentSerializer, MembershipPlanSerializer, MembershipSerializer
from apps.notifications.models import Notification
from apps.store.views import mercadopago_configured


class PlanPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')
    write_roles = ('ADMIN',)
    message = 'Solo el administrador del club puede crear o modificar planes.'


class MembershipPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'ATHLETE')
    write_roles = ('ADMIN', 'ATHLETE')
    message = 'No tienes permisos para gestionar membresías.'


def notify(membership, title, message):
    user = membership.athlete.user
    if user:
        Notification.objects.create(club=membership.club, user=user, title=title, message=message, notification_type='INFO')


class PlanListCreateView(generics.ListCreateAPIView):
    serializer_class = MembershipPlanSerializer
    permission_classes = [permissions.IsAuthenticated, PlanPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = MembershipPlan.objects.annotate(active_members=Count('memberships', filter=Q(memberships__status='ACTIVE')))
        if not user.is_superuser:
            queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'ATHLETE':
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('price', 'name')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class PlanDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MembershipPlanSerializer
    permission_classes = [permissions.IsAuthenticated, PlanPermission]

    def get_queryset(self):
        user = self.request.user
        queryset = MembershipPlan.objects.all()
        if not user.is_superuser:
            queryset = queryset.filter(club_id=user.club_id)
        if user_role(user) == 'ATHLETE':
            queryset = queryset.filter(is_active=True)
        return queryset


class MembershipSettingsView(APIView):
    """Lectura para todo el club (el frontend la usa para avisar antes de reservar); escritura solo del admin."""
    permission_classes = [permissions.IsAuthenticated, PlanPermission]

    def get(self, request):
        online = mercadopago_configured()
        if not request.user.club_id:
            return Response({'require_active_membership': False, 'mercado_pago_available': online})
        settings_row = MembershipSettings.objects.filter(club_id=request.user.club_id).first()
        return Response({
            'require_active_membership': bool(settings_row and settings_row.require_active_membership),
            'mercado_pago_available': online,
        })

    def patch(self, request):
        value = request.data.get('require_active_membership')
        if not isinstance(value, bool):
            return Response({'require_active_membership': 'Indica true (Activado) o false (Desactivado).'}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.club_id:
            raise PermissionDenied('Tu cuenta no pertenece a un club.')
        settings_row, _ = MembershipSettings.objects.update_or_create(club_id=request.user.club_id, defaults={'require_active_membership': value})
        return Response({'require_active_membership': settings_row.require_active_membership})


class MembershipListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def scoped(self, request):
        queryset = Membership.objects.select_related('athlete', 'athlete__user')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(athlete__user=request.user)
        return queryset

    def get(self, request):
        expire_overdue_memberships(None if request.user.is_superuser else request.user.club_id)
        queryset = self.scoped(request)
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return Response(MembershipSerializer(queryset, many=True).data)

    def post(self, request):
        role = user_role(request.user)
        plan_id = request.data.get('plan')
        if not plan_id:
            return Response({'plan': 'Debes elegir un plan.'}, status=status.HTTP_400_BAD_REQUEST)
        # El club y el precio salen siempre del servidor, nunca del cliente.
        plan = get_object_or_404(MembershipPlan, pk=plan_id, club_id=request.user.club_id, is_active=True)
        if role == 'ATHLETE':
            athlete = get_object_or_404(Athlete, user=request.user, club_id=request.user.club_id, status='ACTIVE')
        elif request.data.get('athlete'):
            athlete = get_object_or_404(Athlete, pk=request.data['athlete'], club_id=request.user.club_id, status='ACTIVE')
        else:
            return Response({'athlete': 'Debes indicar el deportista.'}, status=status.HTTP_400_BAD_REQUEST)

        expire_overdue_memberships(request.user.club_id)
        try:
            with transaction.atomic():
                if Membership.objects.select_for_update().filter(athlete=athlete, status__in=['PENDING', 'ACTIVE', 'SCHEDULED']).exists():
                    return Response({'detail': 'El deportista ya tiene una membresía activa o pendiente de pago.'}, status=status.HTTP_409_CONFLICT)
                membership = Membership.objects.create(
                    club=plan.club, athlete=athlete, plan=plan, plan_name=plan.name, price_paid=plan.price,
                    currency=plan.currency, duration_days=plan.duration_days, weekly_class_limit=plan.weekly_class_limit,
                )
        except IntegrityError:
            return Response({'detail': 'El deportista ya tiene una membresía activa o pendiente de pago.'}, status=status.HTTP_409_CONFLICT)
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class MembershipReviewView(APIView):
    """El administrador confirma el pago, rechaza o cancela; el deportista solo puede cancelar lo pendiente."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def post(self, request, pk):
        decision = request.data.get('decision')
        note = str(request.data.get('note', '')).strip()[:500]
        role = user_role(request.user)
        with transaction.atomic():
            queryset = Membership.objects.select_for_update().select_related('athlete', 'athlete__user', 'club')
            if not request.user.is_superuser:
                queryset = queryset.filter(club_id=request.user.club_id)
            membership = get_object_or_404(queryset, pk=pk)

            if role == 'ATHLETE':
                if membership.athlete.user_id != request.user.id or decision != 'CANCEL' or membership.status != 'PENDING':
                    raise PermissionDenied('Solo puedes cancelar tu propia solicitud pendiente.')
            elif role != 'ADMIN' and not request.user.is_superuser:
                raise PermissionDenied('No tienes permisos para revisar membresías.')

            if decision == 'CONFIRM':
                if membership.status != 'PENDING':
                    return Response({'detail': 'Solo se puede confirmar una membresía pendiente de pago.'}, status=status.HTTP_409_CONFLICT)
                activate_pending_membership(membership, confirmed_by=request.user)
            elif decision == 'REJECT':
                if membership.status != 'PENDING':
                    return Response({'detail': 'Solo se puede rechazar una solicitud pendiente.'}, status=status.HTTP_409_CONFLICT)
                if not note:
                    return Response({'note': 'Indica el motivo del rechazo.'}, status=status.HTTP_400_BAD_REQUEST)
                membership.status = 'REJECTED'
                membership.confirmed_by = request.user
                membership.confirmed_at = timezone.now()
                notify(membership, 'Solicitud de membresía rechazada', f'Tu solicitud del plan {membership.plan_name} fue rechazada. Motivo: {note}')
            elif decision == 'CANCEL':
                if membership.status not in ('PENDING', 'ACTIVE', 'SCHEDULED'):
                    return Response({'detail': 'Esta membresía ya no se puede cancelar.'}, status=status.HTTP_409_CONFLICT)
                membership.status = 'CANCELLED'
                notify(membership, 'Membresía cancelada', f'Tu plan {membership.plan_name} fue cancelado por el club.' + (f' Motivo: {note}' if note else ''))
            else:
                return Response({'decision': 'Usa CONFIRM, REJECT o CANCEL.'}, status=status.HTTP_400_BAD_REQUEST)
            membership.review_note = note
            membership.save()
            cancel_pending_payments(membership)
        return Response(MembershipSerializer(membership).data)


class MembershipPaymentListCreateView(APIView):
    """El deportista inicia su compra online y consulta sus pagos; el administrador ve los del club."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def get(self, request):
        expire_pending_payments(request.user.club_id)
        queryset = MembershipPayment.objects.select_related('membership', 'membership__athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(user=request.user)
        return Response(MembershipPaymentSerializer(queryset, many=True, context={'request': request}).data)

    def post(self, request):
        if user_role(request.user) != 'ATHLETE':
            raise PermissionDenied('Solo un deportista puede comprar su propio plan.')
        plan_id = request.data.get('plan')
        if not plan_id:
            return Response({'plan': 'Debes elegir un plan.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError):
            return Response({'plan': 'Plan no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        payment, created = start_membership_checkout(request.user, plan_id)
        payment = MembershipPayment.objects.select_related('membership', 'membership__athlete').get(pk=payment.pk)
        return Response(
            MembershipPaymentSerializer(payment, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MembershipPaymentDetailView(APIView):
    """Consulta del estado real del pago (lo actualiza únicamente el webhook verificado) y cancelación del propio pago abierto."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def get_payment(self, request, pk):
        expire_pending_payments(request.user.club_id)
        queryset = MembershipPayment.objects.select_related('membership', 'membership__athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(user=request.user)
        return get_object_or_404(queryset, pk=pk)

    def get(self, request, pk):
        payment = self.get_payment(request, pk)
        return Response(MembershipPaymentSerializer(payment, context={'request': request}).data)

    def delete(self, request, pk):
        if user_role(request.user) != 'ATHLETE':
            raise PermissionDenied('Solo el comprador puede cancelar su pago pendiente.')
        with transaction.atomic():
            payment = get_object_or_404(
                MembershipPayment.objects.select_for_update().select_related('membership', 'membership__athlete'),
                pk=pk, user=request.user, club_id=request.user.club_id,
            )
            if payment.status != 'PENDING':
                return Response({'detail': 'Solo se puede cancelar un pago pendiente.'}, status=status.HTTP_409_CONFLICT)
            payment.status = 'CANCELLED'
            payment.save(update_fields=['status', 'updated_at'])
            if payment.membership.status == 'PENDING':
                payment.membership.status = 'CANCELLED'
                payment.membership.save(update_fields=['status', 'updated_at'])
        return Response(MembershipPaymentSerializer(payment, context={'request': request}).data)


class MembershipRenewalView(APIView):
    """GET: estado de renovación calculado en el servidor. POST: inicia la renovación (manual u online)."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def athlete(self, request):
        if user_role(request.user) != 'ATHLETE':
            raise PermissionDenied('Solo un deportista puede renovar su propia membresía.')
        return get_object_or_404(Athlete, user=request.user, club_id=request.user.club_id, status='ACTIVE')

    def get(self, request):
        athlete = self.athlete(request)
        expire_overdue_memberships(request.user.club_id)
        info = renewal_info(athlete)
        info.pop('_base', None)
        return Response(info)

    def post(self, request):
        athlete = self.athlete(request)
        method = str(request.data.get('method', 'MANUAL')).upper()
        if method not in ('MANUAL', 'ONLINE'):
            return Response({'method': 'Usa MANUAL u ONLINE.'}, status=status.HTTP_400_BAD_REQUEST)
        plan_id = request.data.get('plan')
        if plan_id in (None, ''):
            plan_id = None
        else:
            try:
                plan_id = int(plan_id)
            except (TypeError, ValueError):
                return Response({'plan': 'Plan no válido.'}, status=status.HTTP_400_BAD_REQUEST)

        if method == 'ONLINE':
            payment, created = start_membership_checkout(request.user, plan_id, renew=True)
            payment = MembershipPayment.objects.select_related('membership', 'membership__athlete').get(pk=payment.pk)
            return Response({
                'membership': MembershipSerializer(payment.membership).data,
                'payment': MembershipPaymentSerializer(payment, context={'request': request}).data,
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        try:
            with transaction.atomic():
                Athlete.objects.select_for_update().get(pk=athlete.pk)
                membership = create_renewal_membership(athlete, plan_id)
        except IntegrityError:
            return Response({'detail': 'Ya existe una compra o renovación pendiente.'}, status=status.HTTP_409_CONFLICT)
        return Response({'membership': MembershipSerializer(membership).data, 'payment': None}, status=status.HTTP_201_CREATED)


