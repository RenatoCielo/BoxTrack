from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.athletes.models import Athlete
from apps.attendance.models import Attendance
from apps.common.permissions import StaffWritePermission
from apps.groups.models import Group
from apps.trainings.models import Training


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
