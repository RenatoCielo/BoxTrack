from django.db.models import Case, CharField, Count, F, Q, Value, When
from django.db.models.functions import Coalesce
from rest_framework import generics, permissions, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.athletes.models import Athlete
from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.clubs.models import Club
from apps.common.permissions import StaffWritePermission
from apps.groups.models import Group
from apps.trainings.models import Training


class SuperuserOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class GlobalClubSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Club
        fields = ['id', 'name', 'verification_status', 'is_active', 'user_count']


class GlobalUserSerializer(serializers.ModelSerializer):
    club_name = serializers.CharField(source='club.name', read_only=True, default=None)
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'role', 'club_name', 'is_active']

    def get_role(self, obj):
        if obj.is_superuser:
            return 'SUPERUSER'
        return obj.role.name if obj.role else 'OTHER'


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, SuperuserOnly])
def global_dashboard_summary(request):
    clubs = Club.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
    )
    users = User.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
    )
    clubs_by_status = list(
        Club.objects.values('verification_status').annotate(count=Count('id')).order_by('verification_status')
    )
    users_by_role = list(
        User.objects.annotate(
            group=Case(
                When(is_superuser=True, then=Value('SUPERUSER')),
                default=Coalesce(F('role__name'), Value('OTHER')),
                output_field=CharField(),
            )
        ).values('group').annotate(count=Count('id')).order_by('group')
    )
    return Response({
        'clubs': clubs, 'users': users,
        'clubs_by_status': clubs_by_status, 'users_by_role': users_by_role,
    })


class GlobalClubListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, SuperuserOnly]
    serializer_class = GlobalClubSerializer

    def get_queryset(self):
        queryset = Club.objects.annotate(user_count=Count('users')).order_by('name', 'id')
        search = self.request.query_params.get('search', '').strip()
        return queryset.filter(name__icontains=search) if search else queryset


class GlobalUserListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, SuperuserOnly]
    serializer_class = GlobalUserSerializer

    def get_queryset(self):
        queryset = User.objects.select_related('club', 'role').order_by('username', 'id')
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) | Q(first_name__icontains=search)
                | Q(last_name__icontains=search) | Q(club__name__icontains=search)
            )
        return queryset


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, StaffWritePermission])
def dashboard_summary(request):
    user = request.user
    if user.is_superuser:
        athletes = Athlete.objects.all()
        trainings = Training.objects.all()
        attendance = Attendance.objects.all()
        groups = Group.objects.all()
    elif user.club_id:
        athletes = Athlete.objects.filter(club_id=user.club_id)
        trainings = Training.objects.filter(club_id=user.club_id)
        attendance = Attendance.objects.filter(club_id=user.club_id)
        groups = Group.objects.filter(club_id=user.club_id)
    else:
        athletes = Athlete.objects.none()
        trainings = Training.objects.none()
        attendance = Attendance.objects.none()
        groups = Group.objects.none()

    summary = {
        'athletes_total': athletes.count(),
        'athletes_active': athletes.filter(status='ACTIVE').count(),
        'trainings_total': trainings.count(),
        'trainings_scheduled': trainings.filter(status='SCHEDULED').count(),
        'attendance_records': attendance.count(),
        'groups_total': groups.count(),
        'groups_active': groups.filter(is_active=True).count(),
    }

    return Response(summary)
