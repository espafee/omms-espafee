from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from core.permissions import RoleBasedPermission
from core.roles import ADMIN, FIELD_ASSIGNABLE_ROLES, SALES
from core.viewsets import ServiceModelViewSet

from .serializers import (
    ClientCreateSerializer,
    ClientOptionSerializer,
    CustomTokenObtainPairSerializer,
    FieldStaffOptionSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .services import UserService

User = get_user_model()


class UserViewSet(ServiceModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [RoleBasedPermission]
    service_class = UserService
    allowed_roles = (ADMIN,)
    write_roles = (ADMIN,)
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "username", "first_name", "last_name", "organization_name"]
    ordering_fields = ["created_at", "email", "first_name"]


class ClientDirectoryView(generics.ListCreateAPIView):
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN, SALES)
    write_roles = (ADMIN,)

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CLIENT).order_by("organization_name", "email")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ClientCreateSerializer
        return ClientOptionSerializer


class FieldStaffDirectoryView(generics.ListAPIView):
    serializer_class = FieldStaffOptionSerializer
    permission_classes = [RoleBasedPermission]
    allowed_roles = (ADMIN, SALES)

    def get_queryset(self):
        return User.objects.filter(role__in=FIELD_ASSIGNABLE_ROLES, is_active=True).order_by("first_name", "email")


class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    throttle_scope = "registration"

    def create(self, request, *args, **kwargs):
        if not settings.OMMS_PUBLIC_REGISTRATION_ENABLED:
            return Response(
                {
                    "detail": "Public registration is disabled. Ask an OMMS administrator to create or invite this user."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "auth_token"


class CustomTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth_token"


class CustomTokenVerifyView(TokenVerifyView):
    throttle_scope = "auth_token"


class AuthHealthView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"authenticated": True, "user_id": request.user.id})
