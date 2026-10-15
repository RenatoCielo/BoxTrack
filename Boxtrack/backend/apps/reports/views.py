import csv
import io

from django.apps import apps
from django.db.models import Q
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response


MODEL_MAP = {
    'athletes': 'athletes.Athlete',
    'trainings': 'trainings.Training',
    'attendance': 'attendance.Attendance',
    'evaluations': 'evaluations.Evaluation',
    'weight': 'weight_tracking.WeightRecord',
    'fights': 'competitions.Competition',
    'alerts': 'alerts.Alert',
}


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def export_report(request, model_name):
    model_path = MODEL_MAP.get(model_name)
    if not model_path:
        return Response({'detail': 'Modelo no soportado para exportación.'}, status=400)

    model = apps.get_model(model_path)
    queryset = model.objects.all()
    if request.user.is_superuser:
        pass
    elif request.user.club_id:
        queryset = queryset.filter(club_id=request.user.club_id)
    else:
        queryset = queryset.none()

    fieldnames = []
    for field in model._meta.fields:
        if field.name == 'id':
            fieldnames.append('id')
        elif field.name == 'club':
            continue
        else:
            fieldnames.append(field.name)

    if not fieldnames:
        fieldnames = ['id']

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for item in queryset:
        row = {}
        for field_name in fieldnames:
            value = getattr(item, field_name)
            if hasattr(value, 'isoformat'):
                row[field_name] = value.isoformat()
            elif isinstance(value, bool):
                row[field_name] = 'true' if value else 'false'
            elif value is None:
                row[field_name] = ''
            else:
                row[field_name] = value
        writer.writerow(row)

    response = Response(output.getvalue(), content_type='text/csv; charset=utf-8')
    filename = f'boxtrack-{model_name}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
