from datetime import timedelta

from apps.attendance.models import Attendance
from apps.trainings.models import TrainingReservation


ATTENDANCE_COUNTS_TOWARD_QUOTA = ('PRESENT', 'LATE')
NON_ATTENDING_STATUSES = ('ABSENT', 'JUSTIFIED')


def weekly_quota_stats(athlete, week_start):
    week_end = week_start + timedelta(days=7)
    week_reservations = TrainingReservation.objects.filter(
        athlete=athlete,
        status='RESERVED',
        training__scheduled_date__gte=week_start,
        training__scheduled_date__lt=week_end,
        training__status__in=('SCHEDULED', 'COMPLETED'),
    )
    non_attending_training_ids = Attendance.objects.filter(
        athlete=athlete,
        training__scheduled_date__gte=week_start,
        training__scheduled_date__lt=week_end,
        status__in=NON_ATTENDING_STATUSES,
    ).values_list('training_id', flat=True)
    reserved_training_ids = list(
        week_reservations
        .exclude(training_id__in=non_attending_training_ids)
        .values_list('training_id', flat=True)
        .distinct()
    )
    attending_records = Attendance.objects.filter(
        athlete=athlete,
        training__scheduled_date__gte=week_start,
        training__scheduled_date__lt=week_end,
        training__status__in=('SCHEDULED', 'COMPLETED'),
        status__in=ATTENDANCE_COUNTS_TOWARD_QUOTA,
    )
    attending_without_reservation = attending_records.exclude(
        training_id__in=reserved_training_ids
    ).count()
    return {
        'used': len(reserved_training_ids) + attending_without_reservation,
        'attended': attending_records.count(),
    }
