from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from apps.clubs.models import Club
from apps.clubs.serializers import ClubSerializer, ClubVerificationSerializer


class ClubAccessPermission(permissions.BasePermission):
    message = 'No tienes permisos para acceder a este club.'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        return getattr(request.user, 'club_id', None) == getattr(obj, 'id', None)


class ClubListView(generics.ListAPIView):
    serializer_class = ClubSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self.request.user, 'is_superuser', False):
            return Club.objects.all().order_by('-created_at')
        if getattr(self.request.user, 'club_id', None):
            return Club.objects.filter(pk=self.request.user.club_id)
        return Club.objects.none()


class ClubDetailView(generics.RetrieveAPIView):
    serializer_class = ClubSerializer
    queryset = Club.objects.all()
    permission_classes = [permissions.IsAuthenticated, ClubAccessPermission]


class ClubPendingListView(generics.ListAPIView):
    serializer_class = ClubSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not getattr(self.request.user, 'is_superuser', False):
            return Club.objects.none()
        return Club.objects.filter(verification_status='PENDING').order_by('created_at')


class ClubVerificationUpdateView(generics.UpdateAPIView):
    serializer_class = ClubVerificationSerializer
    queryset = Club.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Solo un administrador global puede revisar clubes.')
        response = super().update(request, *args, **kwargs)
        club = self.get_object()
        if club.verification_status == 'APPROVED':
            club.verified_at = timezone.now()
            club.verified_by = request.user
            club.save(update_fields=['verified_at', 'verified_by'])
        return response


class ClubVerificationDocumentUploadView(generics.UpdateAPIView):
    serializer_class = ClubSerializer
    queryset = Club.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def update(self, request, *args, **kwargs):
        club = self.get_object()
        if not request.user.is_superuser and getattr(request.user, 'club_id', None) != club.pk:
            raise PermissionDenied('No puedes subir documentos para este club.')
        if 'verification_document' not in request.FILES:
            return Response({'verification_document': ['Se requiere un documento de verificación.']}, status=status.HTTP_400_BAD_REQUEST)
        club.verification_document = request.FILES['verification_document']
        club.verification_status = 'IN_REVIEW'
        club.verification_submitted_at = timezone.now()
        club.save(update_fields=['verification_document', 'verification_status', 'verification_submitted_at'])
        return Response(ClubSerializer(club).data, status=status.HTTP_200_OK)
