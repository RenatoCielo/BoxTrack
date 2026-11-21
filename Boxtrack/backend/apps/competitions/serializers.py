from django.db.models import Count, Q
from rest_framework import serializers
from django.utils import timezone

from apps.athletes.models import Athlete
from apps.clubs.models import Club
from apps.competitions.models import Competition, FightAgreement, FightBout


class FightRecordSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all())

    class Meta:
        model = Competition
        fields = [
            'id', 'club', 'athlete', 'opponent_name', 'fight_date', 'event',
            'category', 'result', 'fight_type', 'notes', 'created_at'
        ]
        read_only_fields = ['club', 'created_at']

    def validate_result(self, value):
        valid = {choice[0] for choice in Competition.RESULT_CHOICES}
        if value not in valid:
            raise serializers.ValidationError('Resultado no válido.')
        return value


class CompetitionSerializer(serializers.ModelSerializer):
    athlete = serializers.PrimaryKeyRelatedField(queryset=Athlete.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Competition
        fields = [
            'id', 'club', 'name', 'event', 'competition_date', 'category',
            'location', 'notes', 'created_at', 'athlete', 'opponent_name',
            'result', 'fight_type', 'fight_date'
        ]
        read_only_fields = ['club', 'created_at']


class RivalClubSerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ['id', 'name', 'logo', 'address', 'disciplines']


class FightAgreementSerializer(serializers.ModelSerializer):
    proposing_club_name = serializers.CharField(source='proposing_club.name', read_only=True)
    proposing_club_id = serializers.IntegerField(read_only=True)
    opponent_club_name = serializers.CharField(source='opponent_club.name', read_only=True)
    opponent_club_id = serializers.IntegerField(read_only=True)
    opponent_club = serializers.PrimaryKeyRelatedField(
        queryset=Club.objects.filter(is_active=True, verification_status='APPROVED'),
        write_only=True,
        required=False,
    )
    is_incoming = serializers.SerializerMethodField()
    bouts = serializers.SerializerMethodField()
    initial_home_athlete = serializers.PrimaryKeyRelatedField(
        queryset=Athlete.objects.all(), write_only=True, required=False
    )
    initial_away_athlete = serializers.PrimaryKeyRelatedField(
        queryset=Athlete.objects.all(), write_only=True, allow_null=True, required=False
    )

    class Meta:
        model = FightAgreement
        fields = [
            'id', 'proposing_club', 'proposing_club_id', 'proposing_club_name',
            'opponent_club', 'opponent_club_id', 'opponent_club_name', 'is_incoming', 'proposed_by', 'planned_date',
            'location', 'notes', 'status', 'created_at', 'updated_at', 'bouts',
            'initial_home_athlete', 'initial_away_athlete',
        ]
        read_only_fields = [
            'id', 'proposing_club', 'proposing_club_id', 'proposing_club_name',
            'opponent_club_id', 'opponent_club_name',
            'is_incoming', 'proposed_by', 'status', 'created_at', 'updated_at',
            'bouts',
        ]

    def get_is_incoming(self, obj):
        request = self.context.get('request')
        return bool(request and obj.opponent_club_id == request.user.club_id)

    def validate_planned_date(self, value):
        if value <= timezone.localdate():
            raise serializers.ValidationError('Selecciona una fecha futura para el combate.')
        return value

    def validate_opponent_club(self, value):
        request = self.context['request']
        if value.pk == request.user.club_id:
            raise serializers.ValidationError('Selecciona un gimnasio distinto al tuyo.')
        return value

    def validate_location(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Indica dónde se realizará el encuentro.')
        return value

    def validate_notes(self, value):
        return value.strip()

    def create(self, validated_data):
        home_athlete = validated_data.pop('initial_home_athlete', None)
        away_athlete = validated_data.pop('initial_away_athlete', None)
        agreement = super().create(validated_data)
        if home_athlete:
            FightBout.objects.create(
                agreement=agreement,
                home_athlete=home_athlete,
                away_athlete=away_athlete,
                last_suggested_by_club=agreement.proposing_club,
            )
        return agreement

    def validate(self, attrs):
        request = self.context['request']
        home_athlete = attrs.get('initial_home_athlete')
        away_athlete = attrs.get('initial_away_athlete')
        opponent_club = attrs.get('opponent_club')
        if not self.instance and not home_athlete:
            raise serializers.ValidationError({
                'initial_home_athlete': 'Elige al menos un competidor de tu gimnasio.'
            })
        if not self.instance and away_athlete and not home_athlete:
            raise serializers.ValidationError({
                'initial_home_athlete': 'Elige primero a un competidor de tu gimnasio.'
            })
        if home_athlete and (
            home_athlete.club_id != request.user.club_id
            or not home_athlete.is_competitor
            or home_athlete.status != 'ACTIVE'
        ):
            raise serializers.ValidationError({
                'initial_home_athlete': 'Elige un competidor activo de tu gimnasio.'
            })
        if home_athlete and not home_athlete.gender:
            raise serializers.ValidationError({
                'initial_home_athlete': 'Completa el género del competidor antes de proponer un cruce.'
            })
        if away_athlete and (
            not opponent_club
            or away_athlete.club_id != opponent_club.pk
            or not away_athlete.is_competitor
            or away_athlete.status != 'ACTIVE'
        ):
            raise serializers.ValidationError({
                'initial_away_athlete': 'Elige un competidor activo del gimnasio rival.'
            })
        if away_athlete and home_athlete.gender != away_athlete.gender:
            raise serializers.ValidationError({
                'initial_away_athlete': 'El competidor rival debe ser del mismo género para este emparejamiento.'
            })
        return attrs

    def get_bouts(self, agreement):
        bouts = agreement.bouts.select_related('home_athlete', 'away_athlete', 'last_suggested_by_club')
        return FightBoutSerializer(bouts, many=True, context=self.context).data


class FightBoutSerializer(serializers.ModelSerializer):
    home_athlete_name = serializers.CharField(source='home_athlete.display_name', read_only=True)
    home_athlete_category = serializers.CharField(source='home_athlete.category', read_only=True)
    home_athlete_weight = serializers.DecimalField(
        source='home_athlete.registered_weight', max_digits=5, decimal_places=2, read_only=True, allow_null=True
    )
    away_athlete_name = serializers.CharField(source='away_athlete.display_name', read_only=True, allow_null=True)
    away_athlete_category = serializers.CharField(source='away_athlete.category', read_only=True, allow_null=True)
    away_athlete_weight = serializers.DecimalField(
        source='away_athlete.registered_weight', max_digits=5, decimal_places=2, read_only=True, allow_null=True
    )
    home_athlete_gender = serializers.CharField(source='home_athlete.gender', read_only=True)
    away_athlete_gender = serializers.CharField(source='away_athlete.gender', read_only=True, allow_null=True)
    home_athlete_fight_record = serializers.SerializerMethodField()
    away_athlete_fight_record = serializers.SerializerMethodField()
    home_athlete_recorded_fights = serializers.SerializerMethodField()
    away_athlete_recorded_fights = serializers.SerializerMethodField()
    is_incoming = serializers.SerializerMethodField()
    last_suggested_by_club_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = FightBout
        fields = [
            'id', 'home_athlete', 'home_athlete_name', 'home_athlete_category',
            'home_athlete_weight', 'away_athlete', 'away_athlete_name',
            'away_athlete_category', 'away_athlete_weight', 'home_athlete_gender',
            'away_athlete_gender', 'home_athlete_fight_record', 'away_athlete_fight_record',
            'home_athlete_recorded_fights', 'away_athlete_recorded_fights', 'status',
            'last_suggested_by_club_id', 'is_incoming', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_is_incoming(self, bout):
        request = self.context.get('request')
        return bool(
            request and bout.last_suggested_by_club_id
            and bout.last_suggested_by_club_id != request.user.club_id
        )

    def _fight_stats(self, bout, side):
        cache_name = f'_{side}_fight_stats'
        if hasattr(bout, cache_name):
            return getattr(bout, cache_name)
        athlete_id = getattr(bout, f'{side}_athlete_id')
        stats = Competition.objects.filter(athlete_id=athlete_id).exclude(
            fight_type='SPARRING'
        ).aggregate(
            wins=Count('id', filter=Q(result='WIN')),
            losses=Count('id', filter=Q(result='LOSS')),
            draws=Count('id', filter=Q(result='DRAW')),
            total=Count('id'),
        ) if athlete_id else {'wins': 0, 'losses': 0, 'draws': 0, 'total': 0}
        setattr(bout, cache_name, stats)
        return stats

    def get_home_athlete_fight_record(self, bout):
        stats = self._fight_stats(bout, 'home')
        return f"{stats['wins']}-{stats['losses']}-{stats['draws']}"

    def get_away_athlete_fight_record(self, bout):
        if not bout.away_athlete_id:
            return ''
        stats = self._fight_stats(bout, 'away')
        return f"{stats['wins']}-{stats['losses']}-{stats['draws']}"

    def get_home_athlete_recorded_fights(self, bout):
        return self._fight_stats(bout, 'home')['total']

    def get_away_athlete_recorded_fights(self, bout):
        if not bout.away_athlete_id:
            return 0
        return self._fight_stats(bout, 'away')['total']


class FightMatchCandidateSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    gender = serializers.CharField(read_only=True)
    recorded_fights = serializers.IntegerField(read_only=True)
    fight_record = serializers.SerializerMethodField()
    experience_level = serializers.SerializerMethodField()
    match_score = serializers.SerializerMethodField()
    match_reasons = serializers.SerializerMethodField()

    class Meta:
        model = Athlete
        fields = [
            'id', 'display_name', 'photo', 'gender', 'category', 'registered_weight',
            'fight_record', 'recorded_fights', 'experience_level', 'match_score', 'match_reasons',
        ]

    def get_fight_record(self, athlete):
        return f'{athlete.fight_wins}-{athlete.fight_losses}-{athlete.fight_draws}'

    def _comparison(self, athlete):
        home_id = self.context.get('home_athlete_id')
        if home_id is None:
            return None
        home = self.context.get('home_athlete')
        if not home:
            return None
        fight_count = athlete.recorded_fights
        home_count = home.recorded_fights
        weight_difference = None
        if athlete.registered_weight is not None and home.registered_weight is not None:
            weight_difference = abs(float(athlete.registered_weight - home.registered_weight))
        category_match = bool(
            athlete.category and home.category
            and athlete.category.strip().casefold() == home.category.strip().casefold()
        )
        experience_difference = abs(fight_count - home_count)
        score = 0
        reasons = []
        if category_match:
            score += 25
            reasons.append('Misma categoría')
        if weight_difference is not None:
            score += max(0, 40 - round(weight_difference * 8))
            reasons.append(
                'Peso muy cercano' if weight_difference <= 2
                else 'Peso compatible' if weight_difference <= 5
                else f'{weight_difference:.1f} kg de diferencia'
            )
        if experience_difference <= 2:
            score += 35
            reasons.append('Experiencia competitiva similar')
        elif experience_difference <= 5:
            score += 20
            reasons.append('Experiencia competitiva cercana')
        else:
            reasons.append('Diferencia de experiencia: revisar')
        return {'score': score, 'reasons': reasons}

    def get_experience_level(self, athlete):
        count = athlete.recorded_fights
        if count == 0:
            return 'Sin combates registrados'
        if count <= 3:
            return 'Inicial'
        if count <= 9:
            return 'Intermedia'
        return 'Avanzada'

    def get_match_score(self, athlete):
        comparison = self._comparison(athlete)
        return comparison['score'] if comparison else None

    def get_match_reasons(self, athlete):
        comparison = self._comparison(athlete)
        return comparison['reasons'] if comparison else []
