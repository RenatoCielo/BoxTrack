from rest_framework import generics, permissions

from apps.evaluations.models import Evaluation
from apps.evaluations.serializers import EvaluationSerializer
from apps.common.permissions import StaffWritePermission, scope_to_assigned_athletes


class EvaluationListCreateView(generics.ListCreateAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        queryset = Evaluation.objects.filter(club_id=self.request.user.club_id).select_related('athlete', 'evaluator')
        return scope_to_assigned_athletes(queryset, self.request.user)

    def perform_create(self, serializer):
        serializer.save(club=self.request.user.club, evaluator=self.request.user)


class EvaluationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EvaluationSerializer
    permission_classes = [permissions.IsAuthenticated, StaffWritePermission]

    def get_queryset(self):
        queryset = Evaluation.objects.filter(club_id=self.request.user.club_id).select_related('athlete', 'evaluator')
        return scope_to_assigned_athletes(queryset, self.request.user)