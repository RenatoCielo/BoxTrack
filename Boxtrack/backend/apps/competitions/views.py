from rest_framework import generics, permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Count, Q

from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.competitions.models import Competition, FightAgreement, FightBout
from apps.competitions.serializers import (
    FightAgreementSerializer, FightBoutSerializer, FightMatchCandidateSerializer,
    FightRecordSerializer, RivalClubSerializer,
)
from apps.common.permissions import StaffWritePermission, scope_to_assigned_athletes, user_role
from apps.notifications.models import Notification


def annotate_competitor_records(queryset):
    non_sparring = ~Q(fight_records__fight_type='SPARRING')
    return queryset.annotate(
        recorded_fights=Count('fight_records', filter=non_sparring, distinct=True),
        fight_wins=Count(
            'fight_records',
            filter=non_sparring & Q(fight_records__result='WIN'),
            distinct=True,
        ),
        fight_losses=Count(
            'fight_records',
            filter=non_sparring & Q(fight_records__result='LOSS'),
            distinct=True,
        ),
        fight_draws=Count(
            'fight_records',
            filter=non_sparring & Q(fight_records__result='DRAW'),
            distinct=True,
        ),
    )


class ClubAdminOnlyPermission(permissions.BasePermission):
    message = 'Solo el administrador del club puede coordinar combates con otros gimnasios.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and not user.is_superuser
            and user.club_id and user_role(user) == 'ADMIN'
            and user.club.is_active and user.club.verification_status == 'APPROVED'
        )


class ClubCompetitionPermission(permissions.BasePermission):
    message = 'No tienes permisos para acceder a este historial de peleas.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'club_id', None) == getattr(obj, 'club_id', None)


class FightRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = FightRecordSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        athlete_id = self.request.query_params.get('athlete')

        queryset = Competition.objects.filter(club_id=user.club_id).select_related('athlete')
        queryset = scope_to_assigned_athletes(queryset, user)
        if athlete_id:
            athlete = Athlete.objects.filter(id=athlete_id).first()
            if athlete is None:
                self.permission_denied(self.request, message='No tienes permisos para consultar este historial.')
            if athlete.club_id != user.club_id:
                self.permission_denied(self.request, message='No tienes permisos para consultar este historial.')
            queryset = queryset.filter(athlete=athlete)
        return queryset.order_by('-fight_date')

    def perform_create(self, serializer):
        athlete = serializer.validated_data['athlete']
        if athlete.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para registrar peleas de este deportista.')
        if user_role(self.request.user) == 'TRAINER' and athlete.assigned_trainer_id != self.request.user.id:
            self.permission_denied(self.request, message='Solo puedes registrar combates de deportistas asignados a ti.')
        serializer.save(club=self.request.user.club)


class FightRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FightRecordSerializer
    queryset = Competition.objects.select_related('athlete').all()
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Competition.objects.filter(club_id=user.club_id).select_related('athlete')
        return scope_to_assigned_athletes(queryset, user)

    def get_object(self):
        obj = super().get_object()
        if obj.club_id != self.request.user.club_id:
            self.permission_denied(self.request, message='No tienes permisos para acceder a este historial.')
        return obj


class RivalClubListView(generics.ListAPIView):
    serializer_class = RivalClubSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def get_queryset(self):
        return Club.objects.filter(
            is_active=True, verification_status='APPROVED'
        ).exclude(pk=self.request.user.club_id).order_by('name')


class RecommendedCompetitorListMixin:
    pagination_class = None

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        return Response(sorted(
            response.data,
            key=lambda row: (
                -(row['match_score'] if row['match_score'] is not None else -1),
                row['display_name'].casefold(),
            ),
        ))


class RivalCompetitorListView(RecommendedCompetitorListMixin, generics.ListAPIView):
    serializer_class = FightMatchCandidateSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def get_queryset(self):
        rival = Club.objects.filter(
            pk=self.kwargs['club_id'],
            is_active=True,
            verification_status='APPROVED',
        ).exclude(pk=self.request.user.club_id).first()
        if rival is None:
            raise PermissionDenied('No se puede consultar el plantel de ese gimnasio.')
        queryset = annotate_competitor_records(Athlete.objects.filter(
            club=rival, status='ACTIVE', is_competitor=True
        )).order_by('last_name', 'first_name', 'id')
        home_id = self.request.query_params.get('home_athlete')
        self.home_athlete = None
        if home_id:
            try:
                self.home_athlete = annotate_competitor_records(Athlete.objects).get(
                    pk=home_id, club_id=self.request.user.club_id,
                    status='ACTIVE', is_competitor=True,
                )
            except (Athlete.DoesNotExist, ValueError):
                raise PermissionDenied('El competidor local indicado no está disponible.')
            if not self.home_athlete.gender:
                return queryset.none()
            queryset = queryset.filter(gender=self.home_athlete.gender)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['home_athlete'] = getattr(self, 'home_athlete', None)
        context['home_athlete_id'] = self.request.query_params.get('home_athlete')
        return context


class FightAgreementListCreateView(generics.ListCreateAPIView):
    serializer_class = FightAgreementSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def get_queryset(self):
        club_id = self.request.user.club_id
        return FightAgreement.objects.filter(
            Q(proposing_club_id=club_id) | Q(opponent_club_id=club_id)
        ).select_related('proposing_club', 'opponent_club').order_by('planned_date', '-created_at')

    @transaction.atomic
    def perform_create(self, serializer):
        opponent_club = serializer.validated_data['opponent_club']
        agreement = serializer.save(
            proposing_club=self.request.user.club,
            proposed_by=self.request.user,
        )
        for admin in opponent_club.users.filter(role__name='ADMIN', is_active=True):
            Notification.objects.create(
                club=opponent_club,
                user=admin,
                title='Nueva propuesta de combate',
                message=(
                    f'{self.request.user.club.name} propone un encuentro para '
                    f'{agreement.planned_date:%d/%m/%Y}. Revisa la sección Combates entre gimnasios.'
                ),
                notification_type='COMPETITION',
                action_url='/fights?tab=agreements',
            )


class FightAgreementDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = FightAgreementSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        club_id = self.request.user.club_id
        return FightAgreement.objects.filter(
            Q(proposing_club_id=club_id) | Q(opponent_club_id=club_id)
        ).select_related('proposing_club', 'opponent_club')

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        agreement = self.get_object()
        requested_status = request.data.get('status')
        is_incoming = agreement.opponent_club_id == request.user.club_id
        valid_transition = (
            agreement.status == 'PENDING'
            and (
                (is_incoming and requested_status in ('CONFIRMED', 'DECLINED'))
                or (not is_incoming and requested_status == 'CANCELLED')
            )
        ) or (agreement.status == 'CONFIRMED' and requested_status == 'CANCELLED')
        if not valid_transition:
            raise PermissionDenied('No se puede realizar ese cambio para esta propuesta.')

        agreement.status = requested_status
        agreement.responded_by = request.user
        agreement.save(update_fields=['status', 'responded_by', 'updated_at'])
        receiving_club = agreement.proposing_club if is_incoming else agreement.opponent_club
        for admin in receiving_club.users.filter(role__name='ADMIN', is_active=True):
            Notification.objects.create(
                club=receiving_club,
                user=admin,
                title='Actualización de combate entre gimnasios',
                message=(
                    f'{request.user.club.name} actualizó la propuesta para '
                    f'{agreement.planned_date:%d/%m/%Y}. Estado: {agreement.get_status_display()}.'
                ),
                notification_type='COMPETITION',
                action_url='/fights?tab=agreements',
            )
        return Response(self.get_serializer(agreement).data, status=status.HTTP_200_OK)


class FightAgreementCompetitorListView(RecommendedCompetitorListMixin, generics.ListAPIView):
    serializer_class = FightMatchCandidateSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def get_agreement(self):
        club_id = self.request.user.club_id
        agreement = FightAgreement.objects.filter(
            Q(proposing_club_id=club_id) | Q(opponent_club_id=club_id),
            pk=self.kwargs['agreement_id'],
        ).first()
        if agreement is None:
            raise PermissionDenied('No tienes acceso a esta propuesta de combate.')
        return agreement

    def get_queryset(self):
        agreement = self.get_agreement()
        requested_club = self.request.query_params.get('club')
        participant_clubs = {agreement.proposing_club_id, agreement.opponent_club_id}
        try:
            club_id = int(requested_club)
        except (TypeError, ValueError):
            raise PermissionDenied('Selecciona uno de los gimnasios participantes.')
        if club_id not in participant_clubs:
            raise PermissionDenied('Solo puedes consultar competidores de los gimnasios participantes.')
        queryset = annotate_competitor_records(Athlete.objects.filter(
            club_id=club_id, status='ACTIVE', is_competitor=True
        )).order_by('last_name', 'first_name', 'id')
        home_id = self.request.query_params.get('home_athlete')
        self.home_athlete = None
        if home_id:
            try:
                self.home_athlete = annotate_competitor_records(Athlete.objects).get(
                    pk=home_id,
                    club_id=agreement.proposing_club_id,
                    is_competitor=True,
                    status='ACTIVE',
                )
            except (Athlete.DoesNotExist, ValueError):
                raise PermissionDenied('El competidor local indicado no está disponible.')
            if not self.home_athlete.gender:
                return queryset.none()
            queryset = queryset.filter(gender=self.home_athlete.gender)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['home_athlete'] = getattr(self, 'home_athlete', None)
        context['home_athlete_id'] = self.request.query_params.get('home_athlete')
        return context


class FightBoutDetailView(generics.RetrieveAPIView):
    serializer_class = FightBoutSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def get_queryset(self):
        club_id = self.request.user.club_id
        agreement_id = self.kwargs['agreement_id']
        return FightBout.objects.filter(
            agreement_id=agreement_id,
        ).filter(
            Q(agreement__proposing_club_id=club_id) | Q(agreement__opponent_club_id=club_id)
        ).select_related(
            'agreement__proposing_club', 'agreement__opponent_club',
            'home_athlete', 'away_athlete', 'last_suggested_by_club',
        )

    def patch(self, request, *args, **kwargs):
        bout = self.get_object()
        agreement = bout.agreement
        user_club_id = request.user.club_id
        owns_home_side = user_club_id == agreement.proposing_club_id
        side_field = 'home_athlete' if owns_home_side else 'away_athlete'
        supplied_fields = set(request.data) - {'status'}
        if supplied_fields - {side_field}:
            raise PermissionDenied('Solo puedes sugerir competidores de tu propio gimnasio.')

        if side_field in request.data:
            if bout.status in ('CONFIRMED', 'DECLINED', 'CANCELLED'):
                raise PermissionDenied('Este emparejamiento ya no admite contrapropuestas.')
            try:
                athlete = Athlete.objects.get(
                    pk=request.data[side_field],
                    club_id=user_club_id,
                    is_competitor=True,
                    status='ACTIVE',
                )
            except (Athlete.DoesNotExist, ValueError, TypeError):
                raise PermissionDenied('Elige un competidor activo de tu gimnasio.')
            opposing_athlete = bout.away_athlete if owns_home_side else bout.home_athlete
            if not athlete.gender or (
                opposing_athlete and athlete.gender != opposing_athlete.gender
            ):
                raise PermissionDenied('Elige un competidor del mismo género que el rival.')
            setattr(bout, side_field, athlete)
            bout.status = 'COUNTERED'
            bout.last_suggested_by_club = request.user.club
        elif 'status' in request.data:
            new_status = request.data['status']
            has_opponent_suggestion = (
                bout.last_suggested_by_club_id
                and bout.last_suggested_by_club_id != user_club_id
            )
            if new_status == 'CONFIRMED':
                if bout.status not in ('PENDING', 'COUNTERED') or not has_opponent_suggestion:
                    raise PermissionDenied('Solo puedes aceptar una propuesta del gimnasio rival.')
                if not bout.home_athlete_id or not bout.away_athlete_id:
                    raise PermissionDenied('Ambos gimnasios deben proponer un competidor primero.')
                bout.status = 'CONFIRMED'
            elif new_status == 'DECLINED':
                if bout.status not in ('PENDING', 'COUNTERED') or not has_opponent_suggestion:
                    raise PermissionDenied('Solo puedes rechazar una propuesta del gimnasio rival.')
                bout.status = 'DECLINED'
            elif new_status == 'CANCELLED' and bout.status == 'CONFIRMED':
                bout.status = 'CANCELLED'
            else:
                raise PermissionDenied('Cambio de estado no permitido para este emparejamiento.')
        else:
            raise serializers.ValidationError({'detail': 'Indica un competidor o el estado de respuesta.'})

        bout.save()
        other_club = agreement.opponent_club if owns_home_side else agreement.proposing_club
        from apps.notifications.models import Notification

        message = (
            f'{request.user.club.name} propuso un competidor para el encuentro del '
            f'{agreement.planned_date:%d/%m/%Y}.'
            if side_field in request.data else
            f'{request.user.club.name} actualizó el emparejamiento para el '
            f'{agreement.planned_date:%d/%m/%Y}. Estado: {bout.get_status_display()}.'
        )
        for admin in other_club.users.filter(role__name='ADMIN', is_active=True):
            Notification.objects.create(
                club=other_club,
                user=admin,
                title='Actualización de emparejamiento',
                message=message,
                notification_type='COMPETITION',
                action_url='/fights?tab=agreements',
            )
        return Response(self.get_serializer(bout).data)


class FightBoutListCreateView(generics.GenericAPIView):
    serializer_class = FightBoutSerializer
    permission_classes = [permissions.IsAuthenticated, ClubAdminOnlyPermission]

    def post(self, request, agreement_id):
        agreement = FightAgreement.objects.filter(
            pk=agreement_id,
            proposing_club_id=request.user.club_id,
            status='PENDING',
        ).select_related('proposing_club', 'opponent_club').first()
        if agreement is None:
            raise PermissionDenied('Solo puedes agregar cruces a una propuesta pendiente que inició tu gimnasio.')

        try:
            home_athlete = Athlete.objects.get(
                pk=request.data.get('home_athlete'),
                club_id=agreement.proposing_club_id,
                status='ACTIVE',
                is_competitor=True,
            )
        except (Athlete.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({
                'home_athlete': 'Elige un competidor activo de tu gimnasio.'
            })
        if not home_athlete.gender:
            raise serializers.ValidationError({
                'home_athlete': 'Completa el género del competidor antes de proponer un cruce.'
            })
        away_athlete = None
        away_athlete_id = request.data.get('away_athlete')
        if away_athlete_id:
            try:
                away_athlete = Athlete.objects.get(
                    pk=away_athlete_id,
                    club_id=agreement.opponent_club_id,
                    status='ACTIVE',
                    is_competitor=True,
                )
            except (Athlete.DoesNotExist, ValueError, TypeError):
                raise serializers.ValidationError({
                    'away_athlete': 'Elige un competidor activo del gimnasio rival.'
                })
            if away_athlete.gender != home_athlete.gender:
                raise serializers.ValidationError({
                    'away_athlete': 'El competidor rival debe ser del mismo género.'
                })
        if FightBout.objects.filter(agreement=agreement, home_athlete=home_athlete).exists():
            raise serializers.ValidationError({
                'home_athlete': 'Este competidor ya tiene un cruce en este encuentro.'
            })
        bout = FightBout.objects.create(
            agreement=agreement,
            home_athlete=home_athlete,
            away_athlete=away_athlete,
            last_suggested_by_club=agreement.proposing_club,
        )
        for admin in agreement.opponent_club.users.filter(role__name='ADMIN', is_active=True):
            Notification.objects.create(
                club=agreement.opponent_club,
                user=admin,
                title='Nuevo cruce de combate propuesto',
                message=(
                    f'{request.user.club.name} propuso un nuevo cruce para '
                    f'{agreement.planned_date:%d/%m/%Y}.'
                ),
                notification_type='COMPETITION',
                action_url='/fights?tab=agreements',
            )
        return Response(
            self.get_serializer(bout, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )
