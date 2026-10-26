from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.athletes.models import Athlete
from apps.common.permissions import ClubRolePermission, user_role
from apps.competitions.models import Competition, CompetitorRequest, FightMatch
from apps.notifications.models import Notification

OPEN_MATCH_STATUSES = ('PROPOSED', 'ACCEPTED')


class CompetitionFlowPermission(ClubRolePermission):
    allowed_roles = ('ADMIN', 'TRAINER', 'ATHLETE')


def notify(club, user, title, message):
    if user is not None:
        Notification.objects.create(club=club, user=user, title=title, message=message, notification_type='COMPETITION')


def athlete_name(athlete):
    return f'{athlete.first_name} {athlete.last_name}'.strip()


def staff_can_manage(user, athlete):
    if user.is_superuser:
        return True
    if athlete.club_id != user.club_id:
        return False
    role = user_role(user)
    return role == 'ADMIN' or (role == 'TRAINER' and athlete.assigned_trainer_id == user.id)


class CompetitorRequestSerializer(serializers.ModelSerializer):
    athlete_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CompetitorRequest
        fields = [
            'id', 'club', 'athlete', 'athlete_name', 'requested_by', 'requested_by_name', 'status',
            'request_note', 'review_note', 'reviewed_by', 'reviewed_at', 'created_at'
        ]
        read_only_fields = fields

    def get_athlete_name(self, obj):
        return athlete_name(obj.athlete)

    def get_requested_by_name(self, obj):
        return obj.requested_by.get_full_name() or obj.requested_by.username if obj.requested_by else ''


class CompetitorRequestListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, CompetitionFlowPermission]

    def get_queryset(self, user):
        queryset = CompetitorRequest.objects.filter(club_id=user.club_id).select_related('athlete', 'requested_by')
        role = user_role(user)
        if role == 'TRAINER':
            queryset = queryset.filter(athlete__assigned_trainer_id=user.id)
        elif role == 'ATHLETE':
            queryset = queryset.filter(athlete__user_id=user.id)
        return queryset.order_by('-created_at', '-id')

    def get(self, request):
        queryset = self.get_queryset(request.user)
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return Response(CompetitorRequestSerializer(queryset, many=True).data)

    def post(self, request):
        user = request.user
        if user_role(user) != 'TRAINER':
            return Response({'detail': 'Solo un entrenador puede solicitar el paso de un deportista a competidor.'}, status=status.HTTP_403_FORBIDDEN)
        athlete = Athlete.objects.filter(id=request.data.get('athlete'), club_id=user.club_id).first()
        if athlete is None or athlete.assigned_trainer_id != user.id:
            return Response({'detail': 'Solo puedes solicitar el cambio de deportistas asignados a ti.'}, status=status.HTTP_403_FORBIDDEN)
        if athlete.status != 'ACTIVE':
            return Response({'detail': 'El deportista debe estar activo.'}, status=status.HTTP_400_BAD_REQUEST)
        if athlete.is_competitor:
            return Response({'detail': 'El deportista ya es competidor.'}, status=status.HTTP_400_BAD_REQUEST)
        if CompetitorRequest.objects.filter(athlete=athlete, status='PENDING').exists():
            return Response({'detail': 'Ya existe una solicitud pendiente para este deportista.'}, status=status.HTTP_409_CONFLICT)
        competitor_request = CompetitorRequest.objects.create(
            club=athlete.club, athlete=athlete, requested_by=user, request_note=str(request.data.get('request_note', ''))[:1000]
        )
        for admin in athlete.club.users.filter(role__name='ADMIN', is_active=True):
            notify(athlete.club, admin, 'Solicitud de competidor', f'{user.get_full_name() or user.username} solicita que {athlete_name(athlete)} pase a competidor.')
        return Response(CompetitorRequestSerializer(competitor_request).data, status=status.HTTP_201_CREATED)


class CompetitorRequestReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated, CompetitionFlowPermission]

    def post(self, request, pk):
        user = request.user
        if user_role(user) != 'ADMIN' and not user.is_superuser:
            return Response({'detail': 'Solo el administrador puede resolver solicitudes.'}, status=status.HTTP_403_FORBIDDEN)
        competitor_request = CompetitorRequest.objects.select_related('athlete', 'requested_by').filter(pk=pk).first()
        if competitor_request is None or (not user.is_superuser and competitor_request.club_id != user.club_id):
            return Response({'detail': 'Solicitud no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if competitor_request.status != 'PENDING':
            return Response({'detail': 'La solicitud ya fue resuelta.'}, status=status.HTTP_409_CONFLICT)
        decision = request.data.get('decision')
        if decision not in ('APPROVE', 'REJECT'):
            return Response({'detail': 'La decisión debe ser APPROVE o REJECT.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            competitor_request.status = 'APPROVED' if decision == 'APPROVE' else 'REJECTED'
            competitor_request.reviewed_by = user
            competitor_request.reviewed_at = timezone.now()
            competitor_request.review_note = str(request.data.get('review_note', ''))[:1000]
            competitor_request.save()
            athlete = competitor_request.athlete
            if decision == 'APPROVE' and not athlete.is_competitor:
                athlete.is_competitor = True
                athlete.save(update_fields=['is_competitor', 'updated_at'])
        approved = decision == 'APPROVE'
        text = f'{athlete_name(athlete)} {"ahora es competidor" if approved else "no fue aprobado como competidor"}.'
        notify(competitor_request.club, competitor_request.requested_by, 'Solicitud de competidor resuelta', text)
        if approved:
            notify(competitor_request.club, athlete.user, 'Ahora eres competidor', 'Tu club aprobó tu paso a competidor.')
        return Response(CompetitorRequestSerializer(competitor_request).data)


class FightMatchSerializer(serializers.ModelSerializer):
    challenger_athlete_name = serializers.SerializerMethodField()
    opponent_athlete_name = serializers.SerializerMethodField()
    challenger_club_name = serializers.CharField(source='challenger_club.name', read_only=True)
    opponent_club_name = serializers.CharField(source='opponent_club.name', read_only=True)

    class Meta:
        model = FightMatch
        fields = [
            'id', 'status', 'challenger_club', 'challenger_club_name', 'opponent_club', 'opponent_club_name',
            'challenger_athlete', 'challenger_athlete_name', 'opponent_athlete', 'opponent_athlete_name',
            'event', 'fight_date', 'location', 'category', 'fight_type', 'notes', 'response_note',
            'responded_at', 'challenger_result', 'created_at'
        ]
        read_only_fields = fields

    def get_challenger_athlete_name(self, obj):
        return athlete_name(obj.challenger_athlete)

    def get_opponent_athlete_name(self, obj):
        return athlete_name(obj.opponent_athlete)


def visible_matches(user):
    queryset = FightMatch.objects.select_related('challenger_club', 'opponent_club', 'challenger_athlete', 'opponent_athlete')
    if not user.is_superuser:
        queryset = queryset.filter(Q(challenger_club_id=user.club_id) | Q(opponent_club_id=user.club_id))
        role = user_role(user)
        if role == 'TRAINER':
            queryset = queryset.filter(Q(challenger_athlete__assigned_trainer_id=user.id) | Q(opponent_athlete__assigned_trainer_id=user.id))
        elif role == 'ATHLETE':
            queryset = queryset.filter(Q(challenger_athlete__user_id=user.id) | Q(opponent_athlete__user_id=user.id))
    return queryset.order_by('-fight_date', '-id')


def match_error(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': message}, status=code)


class FightMatchListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, CompetitionFlowPermission]

    def get(self, request):
        queryset = visible_matches(request.user)
        if request.query_params.get('status'):
            queryset = queryset.filter(status=request.query_params['status'])
        return Response(FightMatchSerializer(queryset, many=True).data)

    def post(self, request):
        user = request.user
        if user_role(user) not in ('ADMIN', 'TRAINER'):
            return match_error('Solo el staff del club puede proponer combates.', status.HTTP_403_FORBIDDEN)
        challenger = Athlete.objects.select_related('club').filter(id=request.data.get('challenger_athlete')).first()
        opponent = Athlete.objects.select_related('club').filter(id=request.data.get('opponent_athlete')).first()
        if challenger is None or opponent is None:
            return match_error('Selecciona los dos competidores.')
        if not staff_can_manage(user, challenger):
            return match_error('Solo puedes proponer combates con deportistas de tu club (o asignados a ti).', status.HTTP_403_FORBIDDEN)
        if opponent.club_id == challenger.club_id:
            return match_error('El rival debe pertenecer a otro club.')
        if opponent.club.verification_status != 'APPROVED' or not opponent.club.is_active:
            return match_error('El club rival no está disponible.')
        for athlete in (challenger, opponent):
            if not athlete.is_competitor or athlete.status != 'ACTIVE':
                return match_error(f'{athlete_name(athlete)} debe ser un competidor activo.')
        try:
            serializer = FightMatchInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as error:
            return Response(error.detail, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        if data['fight_date'] < timezone.localdate():
            return match_error('La fecha del combate no puede estar en el pasado.')
        busy = FightMatch.objects.filter(status__in=OPEN_MATCH_STATUSES, fight_date=data['fight_date']).filter(
            Q(challenger_athlete__in=(challenger, opponent)) | Q(opponent_athlete__in=(challenger, opponent))
        )
        if busy.exists():
            return match_error('Alguno de los competidores ya tiene un combate propuesto o confirmado para esa fecha.', status.HTTP_409_CONFLICT)
        match = FightMatch.objects.create(
            challenger_club=challenger.club, opponent_club=opponent.club,
            challenger_athlete=challenger, opponent_athlete=opponent, proposed_by=user, **data
        )
        text = f'{challenger.club.name} propone {athlete_name(challenger)} vs {athlete_name(opponent)} el {match.fight_date}.'
        for admin in opponent.club.users.filter(role__name='ADMIN', is_active=True):
            notify(opponent.club, admin, 'Nueva propuesta de combate', text)
        notify(opponent.club, opponent.assigned_trainer, 'Nueva propuesta de combate', text)
        return Response(FightMatchSerializer(match).data, status=status.HTTP_201_CREATED)


class FightMatchInputSerializer(serializers.Serializer):
    fight_date = serializers.DateField()
    event = serializers.CharField(required=False, allow_blank=True, max_length=200)
    location = serializers.CharField(required=False, allow_blank=True, max_length=200)
    category = serializers.CharField(required=False, allow_blank=True, max_length=100)
    fight_type = serializers.ChoiceField(choices=Competition.FIGHT_TYPE_CHOICES, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class FightMatchActionView(APIView):
    permission_classes = [permissions.IsAuthenticated, CompetitionFlowPermission]

    def post(self, request, pk, action):
        user = request.user
        match = FightMatch.objects.select_related('challenger_club', 'opponent_club', 'challenger_athlete', 'opponent_athlete').filter(pk=pk).first()
        if match is None or not visible_matches(user).filter(pk=pk).exists() or user_role(user) == 'ATHLETE':
            return match_error('Combate no encontrado.', status.HTTP_404_NOT_FOUND)
        handler = {'accept': self.accept, 'decline': self.decline, 'cancel': self.cancel, 'result': self.result}.get(action)
        if handler is None:
            return match_error('Acción no válida.')
        return handler(request, user, match)

    def is_opponent_side(self, user, match):
        return user.is_superuser or staff_can_manage(user, match.opponent_athlete)

    def is_challenger_side(self, user, match):
        return user.is_superuser or staff_can_manage(user, match.challenger_athlete)

    def accept(self, request, user, match):
        return self.respond(request, user, match, 'ACCEPTED', 'confirmó')

    def decline(self, request, user, match):
        return self.respond(request, user, match, 'DECLINED', 'rechazó')

    def respond(self, request, user, match, new_status, verb):
        if match.status != 'PROPOSED':
            return match_error('El combate ya fue respondido.', status.HTTP_409_CONFLICT)
        if not self.is_opponent_side(user, match):
            return match_error('Solo el club rival puede responder la propuesta.', status.HTTP_403_FORBIDDEN)
        if new_status == 'ACCEPTED' and match.fight_date < timezone.localdate():
            return match_error('La fecha de la propuesta ya pasó.')
        match.status = new_status
        match.responded_by = user
        match.responded_at = timezone.now()
        match.response_note = str(request.data.get('response_note', ''))[:1000]
        match.save()
        notify(match.challenger_club, match.proposed_by, 'Respuesta a tu propuesta de combate', f'{match.opponent_club.name} {verb} el combate {athlete_name(match.challenger_athlete)} vs {athlete_name(match.opponent_athlete)}.')
        return Response(FightMatchSerializer(match).data)

    def cancel(self, request, user, match):
        if match.status not in OPEN_MATCH_STATUSES:
            return match_error('El combate ya no se puede cancelar.', status.HTTP_409_CONFLICT)
        if not (self.is_challenger_side(user, match) or (match.status == 'ACCEPTED' and self.is_opponent_side(user, match))):
            return match_error('No tienes permisos para cancelar este combate.', status.HTTP_403_FORBIDDEN)
        match.status = 'CANCELLED'
        match.responded_by = user
        match.responded_at = timezone.now()
        match.response_note = str(request.data.get('response_note', ''))[:1000]
        match.save()
        other_club, other_athlete = (match.opponent_club, match.opponent_athlete) if user.club_id == match.challenger_club_id else (match.challenger_club, match.challenger_athlete)
        text = f'Se canceló el combate {athlete_name(match.challenger_athlete)} vs {athlete_name(match.opponent_athlete)}.'
        for admin in other_club.users.filter(role__name='ADMIN', is_active=True):
            notify(other_club, admin, 'Combate cancelado', text)
        notify(other_club, other_athlete.assigned_trainer, 'Combate cancelado', text)
        return Response(FightMatchSerializer(match).data)

    def result(self, request, user, match):
        if match.status != 'ACCEPTED':
            return match_error('Solo se puede registrar el resultado de un combate confirmado.', status.HTTP_409_CONFLICT)
        if not (self.is_challenger_side(user, match) or self.is_opponent_side(user, match)):
            return match_error('No tienes permisos para registrar este resultado.', status.HTTP_403_FORBIDDEN)
        if match.fight_date > timezone.localdate():
            return match_error('El resultado solo se puede registrar desde la fecha del combate.')
        result = request.data.get('result')
        if result not in {choice[0] for choice in Competition.RESULT_CHOICES}:
            return match_error('Resultado no válido.')
        inverse = {'WIN': 'LOSS', 'LOSS': 'WIN', 'DRAW': 'DRAW'}[result]
        with transaction.atomic():
            match.status = 'COMPLETED'
            match.challenger_result = result
            match.save()
            # Cada club conserva su propio historial a partir del mismo combate.
            for club, athlete, rival, outcome in (
                (match.challenger_club, match.challenger_athlete, match.opponent_athlete, result),
                (match.opponent_club, match.opponent_athlete, match.challenger_athlete, inverse),
            ):
                Competition.objects.create(
                    club=club, athlete=athlete, opponent_name=f'{athlete_name(rival)} ({rival.club.name})',
                    fight_date=match.fight_date, event=match.event, category=match.category, location=match.location,
                    result=outcome, fight_type=match.fight_type, notes=match.notes
                )
        text = f'Resultado registrado: {athlete_name(match.challenger_athlete)} vs {athlete_name(match.opponent_athlete)}.'
        for club, athlete in ((match.challenger_club, match.challenger_athlete), (match.opponent_club, match.opponent_athlete)):
            notify(club, athlete.user, 'Resultado de combate', text)
            notify(club, athlete.assigned_trainer, 'Resultado de combate', text)
        return Response(FightMatchSerializer(match).data)


class CompetitorDirectoryView(APIView):
    permission_classes = [permissions.IsAuthenticated, CompetitionFlowPermission]

    def get(self, request):
        user = request.user
        if user_role(user) not in ('ADMIN', 'TRAINER'):
            return match_error('Solo el staff puede consultar competidores de otros clubes.', status.HTTP_403_FORBIDDEN)
        queryset = Athlete.objects.select_related('club').filter(
            is_competitor=True, status='ACTIVE', club__verification_status='APPROVED', club__is_active=True
        ).exclude(club_id=user.club_id)
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(club__name__icontains=search))
        rows = [
            {
                'id': athlete.id, 'name': athlete_name(athlete), 'club': athlete.club_id, 'club_name': athlete.club.name,
                'category': athlete.category, 'weight': athlete.registered_weight,
            }
            for athlete in queryset.order_by('club__name', 'last_name', 'first_name')[:200]
        ]
        return Response(rows)
