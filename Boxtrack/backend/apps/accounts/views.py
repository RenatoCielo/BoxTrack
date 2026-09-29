from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    ClubMemberCreateSerializer,
    RegisterSerializer,
    UserSerializer,
)
from apps.common.permissions import AdminOnlyPermission


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'detail': 'Se requieren username y password.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(username=username).first()

    if user is None or not user.check_password(password) or not user.is_active:
        return Response({'detail': 'Credenciales inválidas.'}, status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        },
        status=status.HTTP_200_OK,
    )


class ClubMemberListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, AdminOnlyPermission]

    def check_club_admin(self, request):
        if request.user.is_superuser:
            return
        if getattr(getattr(request.user, 'role', None), 'name', None) != 'ADMIN':
            raise PermissionDenied('Solo el administrador del club puede gestionar cuentas.')

    def get(self, request):
        self.check_club_admin(request)
        users = User.objects.filter(club_id=request.user.club_id).select_related('club', 'role')
        return Response(UserSerializer(users, many=True).data)

    def post(self, request):
        self.check_club_admin(request)
        serializer = ClubMemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, profile, temporary_password = serializer.save(club=request.user.club)
        return Response(
            {
                'user': UserSerializer(user).data,
                'profile_id': profile.pk,
                'temporary_password': temporary_password,
            },
            status=status.HTTP_201_CREATED,
        )


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Contraseña actualizada correctamente.'}, status=status.HTTP_200_OK)
