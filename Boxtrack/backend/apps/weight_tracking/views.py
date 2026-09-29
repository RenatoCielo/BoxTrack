from rest_framework import generics, permissions

from apps.weight_tracking.models import WeightRecord
from apps.weight_tracking.serializers import WeightRecordSerializer
from apps.common.permissions import StaffWritePermission


class WeightRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = WeightRecordSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return WeightRecord.objects.filter(club_id=self.request.user.club_id).select_related('athlete').order_by('-recorded_date')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club)


class WeightRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WeightRecordSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return WeightRecord.objects.filter(club_id=self.request.user.club_id).select_related('athlete')