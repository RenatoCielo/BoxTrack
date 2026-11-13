from datetime import timedelta
import mimetypes
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.athletes.models import Athlete
from apps.common.permissions import ClubRolePermission, user_role
from apps.memberships.models import Membership, MembershipPayment, MembershipPlan, MembershipSettings, MembershipTransferProof, expire_overdue_memberships
from apps.memberships.payments import cancel_pending_payments, expire_pending_payments, start_membership_checkout, start_transbank_membership_checkout
from apps.memberships.renewals import activate_pending_membership, create_renewal_membership, renewal_info
from apps.memberships.serializers import MembershipPaymentSerializer, MembershipPlanSerializer, MembershipSerializer
from apps.notifications.models import Notification
from apps.store.models import StoreSettings
from apps.store.views import OrderPaymentProofUploadView, mercadopago_configured
from apps.store.transbank import transbank_configured


class PlanPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')
    write_roles = ('ADMIN',)
    message = 'Solo el administrador del club puede crear o modificar planes.'


class MembershipPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')
    write_roles = ('ADMIN', 'ATHLETE')
    message = 'No tienes permisos para gestionar membresías.'


def notify(membership, title, message):
    user = membership.athlete.user
    if user:
        Notification.objects.create(club=membership.club, user=user, title=title, message=message, notification_type='INFO')


def manual_payment_method(request):
    method = request.data.get('payment_method', 'MANUAL')
    if method not in ('MANUAL', 'BANK_TRANSFER'):
        raise ValidationError({'payment_method': 'Selecciona pago al club o transferencia bancaria.'})
    if method == 'BANK_TRANSFER':
        settings_row = StoreSettings.objects.filter(club_id=request.user.club_id).first()
        if not settings_row or not settings_row.bank_transfer_instructions.strip():
            raise ValidationError({'payment_method': 'El club aún no ha configurado los datos de transferencia.'})
    return method


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
        store_settings = StoreSettings.objects.filter(club_id=request.user.club_id).first()
        return Response({
            'require_active_membership': bool(settings_row and settings_row.require_active_membership),
            'mercado_pago_available': online,
            'transbank_available': transbank_configured(),
            'bank_transfer_instructions': store_settings.bank_transfer_instructions if store_settings else '',
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
        queryset = Membership.objects.select_related('athlete', 'athlete__user', 'club').prefetch_related('payments', 'transfer_proofs')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(athlete__user=request.user)
        elif user_role(request.user) == 'TRAINER':
            queryset = queryset.filter(athlete__assigned_trainer=request.user)
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
        payment_method = manual_payment_method(request)
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
                Athlete.objects.select_for_update().get(pk=athlete.pk)
                if Membership.objects.select_for_update().filter(athlete=athlete, status__in=['PENDING', 'ACTIVE', 'SCHEDULED']).exists():
                    return Response({'detail': 'El deportista ya tiene una membresía activa o pendiente de pago.'}, status=status.HTTP_409_CONFLICT)
                membership = Membership.objects.create(
                    club=plan.club, athlete=athlete, plan=plan, plan_name=plan.name, price_paid=plan.price,
                    currency=plan.currency, duration_days=plan.duration_days, weekly_class_limit=plan.weekly_class_limit, payment_method=payment_method,
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
                if membership.payments.filter(payment_provider__in=('MERCADO_PAGO', 'TRANSBANK')).exists():
                    return Response({'detail': 'El pago online se confirma únicamente cuando el proveedor verifica la transacción.'}, status=status.HTTP_409_CONFLICT)
                if membership.payment_method == 'BANK_TRANSFER':
                    return Response({'detail': 'Debes revisar y aprobar el comprobante de transferencia.'}, status=status.HTTP_409_CONFLICT)
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
                actor = 'por ti' if role == 'ATHLETE' else 'por el club'
                notify(membership, 'Membresía cancelada', f'Tu plan {membership.plan_name} fue cancelado {actor}.' + (f' Motivo: {note}' if note else ''))
            else:
                return Response({'decision': 'Usa CONFIRM, REJECT o CANCEL.'}, status=status.HTTP_400_BAD_REQUEST)
            membership.review_note = note
            membership.save()
            cancel_pending_payments(membership)
        return Response(MembershipSerializer(membership).data)


class MembershipTransferProofView(APIView):
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        if user_role(request.user) != 'ATHLETE':
            raise PermissionDenied('Solo el deportista puede enviar su comprobante.')
        proof = request.FILES.get('proof')
        if not proof:
            raise ValidationError({'proof': 'Selecciona una imagen o PDF del comprobante.'})
        if Path(proof.name).suffix.lower() not in OrderPaymentProofUploadView.allowed_extensions or proof.content_type not in OrderPaymentProofUploadView.allowed_mime_types:
            raise ValidationError({'proof': 'Usa un comprobante en PDF, JPG, PNG o WEBP.'})
        if proof.size > 5 * 1024 * 1024:
            raise ValidationError({'proof': 'El archivo no puede superar los 5 MB.'})
        if not OrderPaymentProofUploadView.has_allowed_signature(proof):
            raise ValidationError({'proof': 'El contenido del archivo no coincide con una imagen o PDF válido.'})
        with transaction.atomic():
            membership = get_object_or_404(
                Membership.objects.select_for_update().select_related('club', 'athlete', 'athlete__user'),
                pk=pk, club_id=request.user.club_id, athlete__user=request.user,
            )
            if membership.status != 'PENDING' or membership.payment_method != 'BANK_TRANSFER':
                raise ValidationError({'proof': 'Esta membresía no espera un comprobante de transferencia.'})
            if membership.transfer_proofs.filter(proof_status='SUBMITTED').exists():
                raise ValidationError({'proof': 'El comprobante ya está en revisión.'})
            MembershipTransferProof.objects.create(membership=membership, payment_proof=proof)
            notify(membership, 'Comprobante en revisión', f'Recibimos el comprobante del plan {membership.plan_name}. El club lo revisará.')
            for admin in User.objects.filter(club=membership.club, role__name='ADMIN', is_active=True):
                Notification.objects.create(club=membership.club, user=admin, title='Comprobante de membresía pendiente', message=f'{membership.athlete.display_name} envió un comprobante para {membership.plan_name}.', notification_type='ALERT')
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class MembershipTransferProofFileView(APIView):
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def get(self, request, pk):
        queryset = Membership.objects.select_related('athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        membership = get_object_or_404(queryset, pk=pk)
        if not request.user.is_superuser and user_role(request.user) != 'ADMIN' and (user_role(request.user) != 'ATHLETE' or membership.athlete.user_id != request.user.id):
            raise PermissionDenied('No tienes permisos para ver este comprobante.')
        proof = membership.transfer_proofs.first()
        if not proof:
            raise ValidationError({'proof': 'No hay comprobante disponible.'})
        content_type = mimetypes.guess_type(proof.payment_proof.name)[0] or 'application/octet-stream'
        return FileResponse(proof.payment_proof.open('rb'), content_type=content_type, filename=Path(proof.payment_proof.name).name)


class MembershipTransferProofReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def post(self, request, pk):
        if user_role(request.user) != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied('Solo el administrador puede revisar comprobantes.')
        decision = request.data.get('decision')
        note = str(request.data.get('note', '')).strip()[:500]
        if decision not in ('APPROVE', 'REJECT'):
            raise ValidationError({'decision': 'Selecciona aprobar o rechazar el comprobante.'})
        if decision == 'REJECT' and not note:
            raise ValidationError({'note': 'Indica el motivo del rechazo.'})
        with transaction.atomic():
            queryset = Membership.objects.select_for_update().select_related('athlete', 'athlete__user', 'club')
            if not request.user.is_superuser:
                queryset = queryset.filter(club_id=request.user.club_id)
            membership = get_object_or_404(queryset, pk=pk)
            proof = membership.transfer_proofs.first()
            if membership.status != 'PENDING' or membership.payment_method != 'BANK_TRANSFER' or not proof or proof.proof_status != 'SUBMITTED':
                raise ValidationError({'proof': 'No hay un comprobante pendiente de revisión.'})
            proof.proof_status = 'APPROVED' if decision == 'APPROVE' else 'REJECTED'
            proof.proof_review_note = note
            proof.proof_reviewed_by = request.user
            proof.proof_reviewed_at = timezone.now()
            proof.save(update_fields=['proof_status', 'proof_review_note', 'proof_reviewed_by', 'proof_reviewed_at'])
            if decision == 'APPROVE':
                activate_pending_membership(membership, confirmed_by=request.user, note='Transferencia aprobada.')
            else:
                notify(membership, 'Comprobante rechazado', f'El comprobante de {membership.plan_name} fue rechazado. Motivo: {note}. Puedes enviar otro.')
        return Response(MembershipSerializer(membership).data)


class MembershipPaymentListCreateView(APIView):
    """El deportista inicia su compra online y consulta sus pagos; el administrador ve los del club."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def get(self, request):
        if user_role(request.user) == 'TRAINER':
            raise PermissionDenied('Los entrenadores consultan el estado del pago desde la membresÃ­a asignada.')
        expire_pending_payments(request.user.club_id)
        queryset = MembershipPayment.objects.select_related('membership', 'membership__athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(user=request.user)
        elif user_role(request.user) == 'TRAINER':
            queryset = queryset.filter(membership__athlete__assigned_trainer=request.user)
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
        provider = str(request.data.get('provider', 'MERCADO_PAGO')).upper()
        if provider not in ('MERCADO_PAGO', 'TRANSBANK'):
            return Response({'provider': 'Elige MERCADO_PAGO o TRANSBANK.'}, status=status.HTTP_400_BAD_REQUEST)
        payment, created = (
            start_transbank_membership_checkout(request.user, plan_id, request)
            if provider == 'TRANSBANK' else start_membership_checkout(request.user, plan_id)
        )
        payment = MembershipPayment.objects.select_related('membership', 'membership__athlete').get(pk=payment.pk)
        return Response(
            MembershipPaymentSerializer(payment, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MembershipPaymentDetailView(APIView):
    """Consulta del estado real del pago (lo actualiza únicamente el webhook verificado) y cancelación del propio pago abierto."""
    permission_classes = [permissions.IsAuthenticated, MembershipPermission]

    def get_payment(self, request, pk):
        if user_role(request.user) == 'TRAINER':
            raise PermissionDenied('Los entrenadores consultan el estado del pago desde la membresÃ­a asignada.')
        expire_pending_payments(request.user.club_id)
        queryset = MembershipPayment.objects.select_related('membership', 'membership__athlete')
        if not request.user.is_superuser:
            queryset = queryset.filter(club_id=request.user.club_id)
        if user_role(request.user) == 'ATHLETE':
            queryset = queryset.filter(user=request.user)
        elif user_role(request.user) == 'TRAINER':
            queryset = queryset.filter(membership__athlete__assigned_trainer=request.user)
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
            notify(payment.membership, 'Pago cancelado', f'Cancelaste el pago de tu plan {payment.membership.plan_name}. Puedes intentarlo nuevamente desde Membresías.')
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
        provider = str(request.data.get('provider', 'MERCADO_PAGO')).upper()
        if provider not in ('MERCADO_PAGO', 'TRANSBANK'):
            return Response({'provider': 'Elige MERCADO_PAGO o TRANSBANK.'}, status=status.HTTP_400_BAD_REQUEST)
        plan_id = request.data.get('plan')
        if plan_id in (None, ''):
            plan_id = None
        else:
            try:
                plan_id = int(plan_id)
            except (TypeError, ValueError):
                return Response({'plan': 'Plan no válido.'}, status=status.HTTP_400_BAD_REQUEST)

        if method == 'ONLINE':
            payment, created = (
                start_transbank_membership_checkout(request.user, plan_id, request, renew=True)
                if provider == 'TRANSBANK' else start_membership_checkout(request.user, plan_id, renew=True)
            )
            payment = MembershipPayment.objects.select_related('membership', 'membership__athlete').get(pk=payment.pk)
            return Response({
                'membership': MembershipSerializer(payment.membership).data,
                'payment': MembershipPaymentSerializer(payment, context={'request': request}).data,
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        try:
            with transaction.atomic():
                Athlete.objects.select_for_update().get(pk=athlete.pk)
                membership = create_renewal_membership(athlete, plan_id)
                membership.payment_method = manual_payment_method(request)
                membership.save(update_fields=['payment_method', 'updated_at'])
        except IntegrityError:
            return Response({'detail': 'Ya existe una compra o renovación pendiente.'}, status=status.HTTP_409_CONFLICT)
        return Response({'membership': MembershipSerializer(membership).data, 'payment': None}, status=status.HTTP_201_CREATED)


