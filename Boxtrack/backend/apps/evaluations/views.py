from rest_framework import generics, permissions

from apps.evaluations.models import Evaluation
from apps.evaluations.serializers import EvaluationSerializer
from apps.common.permissions import StaffWritePermission


class EvaluationListCreateView(generics.ListCreateAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return Evaluation.objects.filter(club_id=self.request.user.club_id).select_related('athlete', 'evaluator')

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club, evaluator=self.request.user)


class EvaluationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        return Evaluation.objects.filter(club_id=self.request.user.club_id).select_related('athlete', 'evaluator')